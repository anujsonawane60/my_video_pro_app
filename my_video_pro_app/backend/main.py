import os
import time
import shutil
import json
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Response, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import aiofiles
import uvicorn
from dotenv import load_dotenv
import requests
import re
import sys
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from audio_cleaner import AudioCleaner
from subtitle_generator import SubtitleGenerator
import traceback
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from database import engine, get_db
from models import Job, JobStep, Subtitle, AudioFile
from config import UPLOAD_DIR, OUTPUT_DIR
from tts_generator import TTSGenerator
from sts_generator import STSGenerator

# Load environment variables from .env file
load_dotenv()

# Helper function to extract plain text from SRT subtitle format
def extract_text_from_srt(srt_content):
    """
    Extract only the text content from SRT subtitles, removing timing and index information.
    Creates a clean script for text-to-speech conversion.
    """
    try:
        # Regular expression to match subtitle entries (index, timecode, and text)
        subtitle_pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)(?=\n\s*\n\s*\d+|\n\s*\n\s*$|$)')
        
        # Find all subtitle entries
        matches = subtitle_pattern.findall(srt_content)
        
        if not matches:
            # Try a more lenient pattern if the strict one doesn't match
            print("Using fallback subtitle pattern")
            subtitle_pattern = re.compile(r'\d+\s*\n[\d:,\s>-]+\n(.*?)(?=\n\s*\n\s*\d+|\n\s*\n\s*$|$)', re.DOTALL)
            matches = subtitle_pattern.findall(srt_content)
            # Just extract the captured groups directly
            text_only = [match.strip() for match in matches]
        else:
            # Extract only the text parts (group 4)
            text_only = [match[3].strip() for match in matches]
        
        # Join all text parts with proper spacing
        script = ' '.join(text_only)
        
        # Clean up extra whitespace, HTML tags, and other formatting
        script = re.sub(r'<[^>]+>', '', script)  # Remove HTML tags
        script = re.sub(r'\s+', ' ', script)     # Normalize whitespace
        script = re.sub(r'\n', ' ', script)      # Replace newlines with spaces
        script = script.strip()
        
        print(f"Extracted {len(text_only)} subtitle segments")
        
        if not script:
            # If extraction failed, return a simple error message for TTS
            return "Subtitle extraction failed. Please check the subtitle format."
        
        return script
    except Exception as e:
        print(f"Error extracting text from subtitles: {str(e)}")
        return "Error extracting subtitles. Please check the subtitle format."

app = FastAPI(title="Video Processing API", 
              description="API for processing videos with transcription, audio cleaning, and subtitle generation")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],  # React frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the outputs directory for static file serving
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# Initialize TTS and STS generators
tts_generator = TTSGenerator()
sts_generator = STSGenerator()

@app.get("/")
async def read_root():
    return {"message": "Video Processing API is running"}

@app.post("/upload-video/")
async def upload_video(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Upload a video file to process (DB version)"""
    try:
        print(f"Received upload request for file: {file.filename}")
        
        # Validate file type
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")

        # Create a temporary directory for upload (will rename after job creation)
        temp_upload_dir = tempfile.mkdtemp(dir=UPLOAD_DIR)
        temp_output_dir = tempfile.mkdtemp(dir=OUTPUT_DIR)

        # Save the uploaded file
        file_path = Path(temp_upload_dir) / file.filename
        try:
            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)
        except Exception as e:
            print(f"Error saving file: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file")

        # Create Job in DB (let DB generate UUID)
        try:
            job = Job(
                filename=file.filename,
                status="uploaded",
                upload_time=datetime.utcnow(),
                video_path=str(file_path),
                output_dir=str(temp_output_dir),
                current_step="upload"
            )
            db.add(job)
            db.commit()
            db.refresh(job)
        except Exception as e:
            print(f"Error creating job in database: {str(e)}")
            # Clean up temp directories
            shutil.rmtree(temp_upload_dir, ignore_errors=True)
            shutil.rmtree(temp_output_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail="Failed to create job in database")

        # Now rename the temp dirs to use the real job.id (UUID)
        try:
            job_upload_dir = UPLOAD_DIR / str(job.id)
            job_output_dir = OUTPUT_DIR / str(job.id)
            os.rename(temp_upload_dir, job_upload_dir)
            os.rename(temp_output_dir, job_output_dir)
            # Update job paths in DB
            job.video_path = str(job_upload_dir / file.filename)
            job.output_dir = str(job_output_dir)
            db.commit()
        except Exception as e:
            print(f"Error renaming directories: {str(e)}")
            # Try to clean up
            shutil.rmtree(temp_upload_dir, ignore_errors=True)
            shutil.rmtree(temp_output_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail="Failed to set up job directories")

        # Add initial steps
        try:
            for step_name in ["extract_audio", "generate_subtitles", "clean_audio", "create_final_video"]:
                step = JobStep(
                    job_id=job.id,
                    step_name=step_name,
                    status="pending",
                    file_path=None
                )
                db.add(step)
            db.commit()
        except Exception as e:
            print(f"Error creating job steps: {str(e)}")
            # Don't raise here, as the job is already created
            # Just log the error and continue

        return {
            "job_id": str(job.id),
            "status": "uploaded",
            "message": "Video uploaded successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in upload_video: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/extract-audio/{job_id}")
async def extract_audio(job_id: str, db: Session = Depends(get_db)):
    """Extract audio from the uploaded video (DB version)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        video_path = job.video_path
        output_dir = job.output_dir

        # Use ffmpeg directly for audio extraction
        import subprocess
        output_filename = f"audio_{job_id}.wav"
        output_path = os.path.join(output_dir, output_filename)
        command = [
            "ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", output_path
        ]
        subprocess.run(command, check=True)

        # Update job step in DB
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "extract_audio").first()
        if step:
            step.status = "completed"
            step.file_path = output_path
        job.status = "audio_extracted"
        db.commit()

        # Add the extracted audio to the AudioFile table
        audio_file = AudioFile(
            job_id=job.id,
            type="original",
            file_path=output_path,
            label="Extracted Audio",
            created_at=datetime.utcnow()
        )
        db.add(audio_file)
        db.commit()

        return {
            "job_id": str(job.id),
            "status": "audio_extracted",
            "audio_path": f"/outputs/{job_id}/{output_filename}"
        }
    except Exception as e:
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "extract_audio").first()
        if step:
            step.status = "failed"
            step.file_path = None
        job.status = "extract_audio_failed"
        db.commit()
        return JSONResponse(
            status_code=500,
            content={"job_id": str(job.id), "status": "failed", "error": str(e)}
        )

# --- New DB-driven background subtitle generation function ---
def run_subtitle_generation_db(job_id: str, transcription_method: str, language: str, whisper_model_size: str):
    """Run subtitle generation in background using DB session"""
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            print(f"Job {job_id} not found in background task.")
            return
        
        video_path = job.video_path
        output_dir = job.output_dir
        
        audio_path = os.path.join(output_dir, f"audio_{job_id}.wav")
        if not os.path.exists(audio_path):
            print(f"Audio file {audio_path} not found for job {job_id} in background task.")
            # Potentially update job status to reflect this specific error
            step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
            if step:
                step.status = "failed"
                step.details = "Prerequisite audio file not found." # You might want to add a 'details' column to JobStep
            job.status = "generate_subtitles_failed"
            db.commit()
            return

        subtitles_path = os.path.join(output_dir, f"subtitles_{job_id}.srt")
        
        print(f"Background task: Starting subtitle generation for job {job_id} using {transcription_method}...")
        generator = SubtitleGenerator(
            audio_path=audio_path,
            video_path=video_path, # video_path might not be strictly needed by SubtitleGenerator if audio is already there
            output_dir=output_dir,
            subtitles_path=subtitles_path,
            language=language,
            whisper_model_size=whisper_model_size,
            debug_mode=True # Set to False in production or based on env variable
        )
        
        generated_subtitle_file_path = generator.generate_subtitles()
        
        output_filename = os.path.basename(generated_subtitle_file_path) # f"subtitles_{job_id}.srt"
        # It's safer to use the filename from the generator, but ensure it follows a consistent pattern if not self.subtitles_path
        # If generator.generate_subtitles() always returns self.subtitles_path, then:
        # output_filename = f"subtitles_{job_id}.srt" 
        # And the copy line below would use `generated_subtitle_file_path` as source and `subtitles_path` as dest,
        # or if `generated_subtitle_file_path` *is* `subtitles_path`, no copy is needed unless you want to rename.

        # Ensure the file was actually created and is not just the fallback
        if os.path.exists(generated_subtitle_file_path) and os.path.getsize(generated_subtitle_file_path) > 0:
            # If generated_subtitle_file_path is different from subtitles_path, copy it.
            # If it's the same, this shutil.copy2 might be redundant but harmless if src and dst are identical.
            # However, SubtitleGenerator is already writing to `self.subtitles_path`, so `generated_subtitle_file_path` should be `subtitles_path`.
            # shutil.copy2(generated_subtitle_file_path, subtitles_path) # This line might be redundant if generator writes directly to subtitles_path
            
            # Update job step in DB
            step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
            if step:
                step.status = "completed"
                step.file_path = subtitles_path # Store the path
            
            # Add subtitle record
            subtitle_record = Subtitle(job_id=job.id, type="original", file_path=subtitles_path)
            db.add(subtitle_record)
            job.status = "subtitles_generated"
            print(f"Background task: Subtitle generation completed successfully for job {job_id}.")
        else:
            print(f"Background task: Subtitle generation failed or produced empty file for job {job_id}. Path: {generated_subtitle_file_path}")
            step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
            if step:
                step.status = "failed"
            job.status = "generate_subtitles_failed"
            # Basic subtitles might have been created by _create_basic_subtitles
            # Decide if you want to record this path or not.
            # If basic subtitles were created at `subtitles_path`, you might still want to record it but with a different status.
            if os.path.exists(subtitles_path):
                 # Optionally add basic subtitle record if it exists
                basic_subtitle_record = Subtitle(job_id=job.id, type="fallback_basic", file_path=subtitles_path)
                db.add(basic_subtitle_record)


        db.commit()
    except Exception as e:
        print(f"Error in background subtitle generation for job {job_id}: {e}")
        print(traceback.format_exc())
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
        if step:
            step.status = "failed"
            # step.details = str(e) # Consider adding details
        if job: # Ensure job is not None
            job.status = "generate_subtitles_failed"
        db.commit()
    finally:
        db.close()


@app.post("/generate-subtitles/{job_id}")
async def generate_subtitles(
    job_id: str,
    transcription_method: str = Form("whisper"),
    language: str = Form("en"),
    whisper_model_size: str = Form("base"),
    assemblyai_api_key: str = Form(None), # Stays as a Form param, but not used by run_subtitle_generation_db
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Generate subtitles for the video (DB version, supports background task)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    audio_path = os.path.join(job.output_dir, f"audio_{job_id}.wav")
    if not os.path.exists(audio_path):
        job.status = "generate_subtitles_failed"
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
        if step:
            step.status = "failed"
            # step.details = "Prerequisite audio file not found."
        db.commit()
        raise HTTPException(status_code=400, detail=f"Extracted audio not found for job {job_id}. Please extract audio first.")

    if background_tasks:
        # Mark step as in progress
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
        if step:
            step.status = "in_progress"
        job.status = "generating_subtitles"
        db.commit()
        
        # Call the background task without assemblyai_api_key
        background_tasks.add_task(
            run_subtitle_generation_db,
            job_id,
            transcription_method,
            language,
            whisper_model_size
        )
        return {
            "job_id": str(job.id),
            "status": "generating_subtitles",
            "message": "Subtitle generation started in background. This may take several minutes. Check job status for updates."
        }
    
    # Synchronous execution (if not using background_tasks)
    try:
        video_path = job.video_path # This might not be strictly needed if audio_path is used
        output_dir = job.output_dir
        
        subtitles_path = os.path.join(output_dir, f"subtitles_{job_id}.srt")
        
        generator = SubtitleGenerator(
            audio_path=audio_path,
            video_path=video_path,
            output_dir=output_dir,
            subtitles_path=subtitles_path,
            language=language,
            whisper_model_size=whisper_model_size,
            debug_mode=True 
        )
        
        generated_subtitle_file_path = generator.generate_subtitles()
        output_filename = os.path.basename(generated_subtitle_file_path)

        if not os.path.exists(generated_subtitle_file_path) or os.path.getsize(generated_subtitle_file_path) == 0 :
            # Check if basic subtitles were created due to failure
            if os.path.exists(subtitles_path) and "Error generating" in open(subtitles_path, 'r', encoding='utf-8').read(100):
                 # If basic fallback exists, treat it as such
                print(f"Subtitle generation resulted in fallback for job {job_id}.")
                job.status = "subtitles_fallback"
                subtitle_content = open(subtitles_path, 'r', encoding='utf-8').read()
            else:
                raise Exception("Subtitle generation failed or produced an empty file.")
        else:
            with open(generated_subtitle_file_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            job.status = "subtitles_generated"
        
        # Update job step in DB
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
        if step:
            step.status = "completed" if job.status == "subtitles_generated" else "failed" # Or "completed_with_fallback"
            step.file_path = generated_subtitle_file_path if os.path.exists(generated_subtitle_file_path) else subtitles_path
        
        # Add subtitle record
        subtitle_record = Subtitle(job_id=job.id, type="original", file_path=generated_subtitle_file_path if os.path.exists(generated_subtitle_file_path) else subtitles_path)
        db.add(subtitle_record)
        
        db.commit()
        
        return {
            "job_id": str(job.id),
            "status": job.status,
            "subtitle_path": f"/outputs/{job_id}/{output_filename}",
            "subtitle_content": subtitle_content
        }
    except Exception as e:
        print(f"Error in synchronous subtitle generation for job {job_id}: {e}")
        traceback.print_exc()
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
        if step:
            step.status = "failed"
            step.file_path = None
        job.status = "generate_subtitles_failed"
        db.commit()
        return JSONResponse(
            status_code=500,
            content={"job_id": str(job.id), "status": "failed", "error": str(e)}
        )

@app.post("/save-edited-subtitles/{job_id}")
async def save_edited_subtitles(
    job_id: str,
    subtitle_content: str = Form(...),
    db: Session = Depends(get_db)
):
    """Save edited subtitle content to a file (DB version)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        output_dir = job.output_dir
        # Use a consistent naming or base it on the job ID to avoid overwriting
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        output_filename = f"subtitles_{job_id}_edited_{timestamp}.srt"
        output_path = os.path.join(output_dir, output_filename)
        
        Path(output_dir).mkdir(parents=True, exist_ok=True) # Ensure output dir exists
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(subtitle_content)
        
        # Add subtitle record
        subtitle = Subtitle(job_id=job.id, type="edited", file_path=output_path, created_at=datetime.utcnow())
        db.add(subtitle)
        
        job.status = "subtitles_edited" # Or maintain the previous relevant status
        db.commit()
        
        return {
            "job_id": str(job.id),
            "status": "subtitles_edited",
            "edited_subtitle_path": f"/outputs/{job_id}/{output_filename}"
        }
    except Exception as e:
        print(f"Error saving edited subtitles for job {job_id}: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"job_id": str(job.id), "status": "failed_to_save_edited_subtitles", "error": str(e)}
        )

@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get the status of a processing job (DB version)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    steps = db.query(JobStep).filter(JobStep.job_id == job.id).all()
    step_dict = {step.step_name: {"status": step.status, "path": step.file_path} for step in steps}
    return {
        "id": str(job.id),
        "filename": job.filename,
        "status": job.status,
        "upload_time": job.upload_time.isoformat() if job.upload_time else None,
        "video_path": job.video_path, # Be cautious about exposing full paths if not needed by client
        "output_dir": job.output_dir, # Same caution as above
        "current_step": job.current_step,
        "steps": step_dict
    }

@app.get("/download/{job_id}/{file_type}")
async def download_file(job_id: str, file_type: str, db: Session = Depends(get_db)):
    """Download a processed file (DB version)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    file_path_to_serve = None
    filename_for_download = f"{file_type}_{job_id}"

    if file_type == "audio":
        audio_step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "extract_audio").first()
        if audio_step and audio_step.status == "completed" and audio_step.file_path and os.path.exists(audio_step.file_path):
            file_path_to_serve = audio_step.file_path
            filename_for_download += ".wav"
    elif file_type == "subtitles":
        # Prefer latest edited, then latest original
        subtitle_record = db.query(Subtitle).filter(Subtitle.job_id == job.id).order_by(Subtitle.type.desc(), Subtitle.created_at.desc()).first()
        if subtitle_record and subtitle_record.file_path and os.path.exists(subtitle_record.file_path):
            file_path_to_serve = subtitle_record.file_path
            filename_for_download += ".srt"
    elif file_type == "cleaned_audio":
        # Get the latest cleaned audio from AudioFile table or clean_audio step
        cleaned_audio_record = db.query(AudioFile).filter(AudioFile.job_id == job.id, AudioFile.type.like("cleaned%")).order_by(AudioFile.created_at.desc()).first()
        if cleaned_audio_record and cleaned_audio_record.file_path and os.path.exists(cleaned_audio_record.file_path):
             file_path_to_serve = cleaned_audio_record.file_path
             filename_for_download += ".wav"
        else: # Fallback to JobStep if AudioFile not found or path invalid
            audio_step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "clean_audio").first()
            if audio_step and audio_step.status == "completed" and audio_step.file_path and os.path.exists(audio_step.file_path):
                file_path_to_serve = audio_step.file_path
                filename_for_download += ".wav"
    elif file_type == "final_video":
        video_step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "create_final_video").first()
        if video_step and video_step.status == "completed" and video_step.file_path and os.path.exists(video_step.file_path):
            file_path_to_serve = video_step.file_path
            filename_for_download += ".mp4"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type requested")

    if not file_path_to_serve:
        raise HTTPException(status_code=404, detail=f"{file_type.replace('_', ' ').title()} not ready or not found for job {job_id}")
        
    return FileResponse(file_path_to_serve, filename=filename_for_download)


@app.get("/subtitle-content/{job_id}")
async def get_subtitle_content(job_id: str, db: Session = Depends(get_db)):
    """Get the subtitle content for a job (DB version)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Prefer latest edited, then latest original, then fallback
    subtitle = db.query(Subtitle).filter(Subtitle.job_id == job.id)\
                                 .order_by(Subtitle.type.desc(), Subtitle.created_at.desc())\
                                 .first()
    
    if not subtitle or not subtitle.file_path or not os.path.exists(subtitle.file_path):
        # Check JobStep as a fallback if no Subtitle record or file missing
        subtitle_step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "generate_subtitles").first()
        if subtitle_step and subtitle_step.file_path and os.path.exists(subtitle_step.file_path):
            file_to_read = subtitle_step.file_path
        else:
            raise HTTPException(status_code=404, detail="Subtitle file not found for this job.")
    else:
        file_to_read = subtitle.file_path
        
    try:
        with open(file_to_read, 'r', encoding='utf-8') as f:
            subtitle_content = f.read()
        return {"subtitle_content": subtitle_content, "file_path": file_to_read, "type": subtitle.type if subtitle else "unknown"}
    except Exception as e:
        print(f"Error reading subtitle file {file_to_read} for job {job_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to read subtitle file: {str(e)}"}
        )

@app.get("/available-audio/{job_id}")
async def get_available_audio(job_id: str, db: Session = Depends(get_db)):
    """Get a list of all available audio files for a job (DB version)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    audio_files_from_db = db.query(AudioFile).filter(AudioFile.job_id == job.id).order_by(AudioFile.created_at.desc()).all()
    available_audio = []
    
    for audio in audio_files_from_db:
        if audio.file_path and os.path.exists(audio.file_path):
            relative_path = f"/outputs/{job_id}/{os.path.basename(audio.file_path)}"
            available_audio.append({
                "id": str(audio.id), # AudioFile table primary key
                "type": audio.type,
                "label": audio.label or audio.type.title().replace("_", " "),
                "path": audio.file_path, # Absolute path (for server-side use)
                "url": relative_path,   # Relative path (for client-side use via /outputs mount)
                "voice_id": audio.voice_id, # If applicable
                "name": audio.label or os.path.basename(audio.file_path), 
                "created_at": audio.created_at.isoformat() if audio.created_at else None
            })
        else:
            print(f"Warning: Audio file record exists but file not found on disk - {audio.file_path} for job {job_id}")
            
    return {"available_audio": available_audio}

@app.get("/available-subtitles/{job_id}")
async def get_available_subtitles(job_id: str, db: Session = Depends(get_db)):
    """Get a list of all available subtitle files for a job (DB version)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    subtitles_from_db = db.query(Subtitle).filter(Subtitle.job_id == job.id).order_by(Subtitle.created_at.desc()).all()
    available_subtitles = []
    
    for sub in subtitles_from_db:
        if sub.file_path and os.path.exists(sub.file_path):
            relative_path = f"/outputs/{job_id}/{os.path.basename(sub.file_path)}"
            available_subtitles.append({
                "id": str(sub.id), # Subtitle table primary key
                "type": sub.type,
                "label": sub.type.title().replace("_", " ") + " Subtitles",
                "path": sub.file_path, # Absolute path
                "url": relative_path,   # Relative path for client
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
                "name": os.path.basename(sub.file_path)
            })
        else:
            print(f"Warning: Subtitle file record exists but file not found on disk - {sub.file_path} for job {job_id}")
            
    return {"available_subtitles": available_subtitles}


@app.delete("/project/{job_id}")
async def delete_project(job_id: str, db: Session = Depends(get_db)):
    """Delete a project/job and all related files and DB records."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_output_dir_path = job.output_dir
    job_upload_dir_path = None
    if job.video_path:
        job_upload_dir_path = os.path.dirname(job.video_path)

    # Delete from DB (cascades to steps, subtitles, audio_files due to foreign key constraints with onDelete='CASCADE')
    try:
        db.delete(job)
        db.commit()
    except Exception as e_db:
        db.rollback() # Rollback in case of DB error
        print(f"Error deleting job {job_id} from database: {e_db}")
        raise HTTPException(status_code=500, detail=f"Failed to delete job from database: {str(e_db)}")

    # Remove files from disk AFTER successful DB deletion
    try:
        # Delete the specific output directory for the job
        if job_output_dir_path and os.path.exists(job_output_dir_path) and str(job.id) in job_output_dir_path: # Safety check
            shutil.rmtree(job_output_dir_path, ignore_errors=True)
            print(f"Deleted output directory: {job_output_dir_path}")

        # Delete the specific upload directory for the job (which contains the original video)
        if job_upload_dir_path and os.path.exists(job_upload_dir_path) and str(job.id) in job_upload_dir_path: # Safety check
            shutil.rmtree(job_upload_dir_path, ignore_errors=True)
            print(f"Deleted upload directory: {job_upload_dir_path}")
            
    except Exception as e_fs:
        # Log FS deletion error but don't fail the request if DB deletion was successful
        print(f"Warning: Failed to delete all files for job {job_id} from filesystem: {e_fs}")
    
    return {"job_id": job_id, "status": "deleted", "message": "Project and associated data deleted."}


@app.get("/projects")
async def get_all_projects(db: Session = Depends(get_db)):
    """Fetch all projects from the database."""
    print("Received request to fetch all projects")
    projects = db.query(Job).order_by(Job.upload_time.desc()).all() # Fetch latest first
    project_list = []
    for project in projects:
        project_list.append({
            "id": str(project.id),
            "filename": project.filename,
            "name": project.filename, # Keep 'name' for consistency if frontend uses it
            "status": project.status,
            "upload_time": project.upload_time.isoformat() if project.upload_time else None,
            "current_step": project.current_step,
            # Avoid exposing full file paths unless necessary for client functionality not served by /download or /outputs
            # "video_path": project.video_path,
            # "output_dir": project.output_dir,
        })
    return project_list


@app.post("/clean-audio/{job_id}")
async def clean_audio(
    job_id: str, 
    audio_file_id: Optional[str] = Form(None), # Optional: ID of specific AudioFile entry to clean
    noise_reduction_sensitivity: float = Form(0.8), # Default, matches AudioCleaner
    vad_aggressiveness: int = Form(1),          # Default, matches AudioCleaner
    db: Session = Depends(get_db)
):
    """Clean an audio file for a job (DB version).
    If audio_file_id is provided, it cleans that specific audio.
    Otherwise, it defaults to cleaning the 'original' extracted audio for the job.
    Saves the new cleaned audio and adds a record to AudioFile history.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    print(f"Initiating audio cleaning for job_id: {job_id}. Sensitivity: {noise_reduction_sensitivity}, VAD: {vad_aggressiveness}")

    audio_to_clean_path = None
    original_audio_label_for_filename = "audio"

    if audio_file_id:
        audio_file_record = db.query(AudioFile).filter(AudioFile.id == audio_file_id, AudioFile.job_id == job_id).first()
        if not audio_file_record or not audio_file_record.file_path or not os.path.exists(audio_file_record.file_path):
            raise HTTPException(status_code=404, detail=f"Specified audio file (ID: {audio_file_id}) not found or path invalid for job {job_id}.")
        audio_to_clean_path = audio_file_record.file_path
        original_audio_label_for_filename = Path(audio_to_clean_path).stem
        print(f"[Job {job_id}] Cleaning specified audio: {audio_to_clean_path}")
    else:
        # Default to the 'original' extracted audio
        original_audio_record = db.query(AudioFile).filter(AudioFile.job_id == job.id, AudioFile.type == "original").first()
        if not original_audio_record or not original_audio_record.file_path or not os.path.exists(original_audio_record.file_path):
            # Fallback: check JobStep for 'extract_audio' if no 'original' AudioFile record
            extract_audio_step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == "extract_audio").first()
            if not extract_audio_step or not extract_audio_step.file_path or not os.path.exists(extract_audio_step.file_path):
                error_msg = "Default original extracted audio not found for this job. Cannot perform cleaning."
                print(f"[Job {job_id}] Error: {error_msg}")
                # Update DB for failure
                # ... (status update logic) ...
                raise HTTPException(status_code=404, detail=error_msg)
            audio_to_clean_path = extract_audio_step.file_path
        else:
            audio_to_clean_path = original_audio_record.file_path
        
        original_audio_label_for_filename = Path(audio_to_clean_path).stem
        print(f"[Job {job_id}] Cleaning default original audio: {audio_to_clean_path}")

    job_specific_output_dir = job.output_dir
    Path(job_specific_output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    cleaned_audio_filename = f"{original_audio_label_for_filename}_cleaned_{timestamp}.wav"
    final_cleaned_audio_output_path = os.path.join(job_specific_output_dir, cleaned_audio_filename)
    
    current_step_name = "clean_audio" # The general step being performed

    try:
        print(f"[Job {job_id}] Initializing AudioCleaner. Source: '{audio_to_clean_path}', Target: '{final_cleaned_audio_output_path}'")
        
        cleaner = AudioCleaner(
            audio_path=audio_to_clean_path,
            output_dir=job_specific_output_dir, # For intermediates
            noise_reduction_sensitivity=noise_reduction_sensitivity,
            vad_aggressiveness=vad_aggressiveness
        )
        
        actually_produced_path = cleaner.clean(output_path=final_cleaned_audio_output_path)

        if not os.path.exists(actually_produced_path) or actually_produced_path != final_cleaned_audio_output_path:
            error_message = (f"[Job {job_id}] Audio cleaning finished, but expected output "
                             f"{final_cleaned_audio_output_path} was not created or path mismatch. "
                             f"Got: {actually_produced_path}")
            print(error_message)
            raise Exception(error_message)

        # Update or create 'clean_audio' JobStep
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == current_step_name).first()
        if step:
            step.status = "completed"
            step.file_path = actually_produced_path
            step.finished_at = datetime.utcnow()
        else: # Should not happen if steps are pre-created, but as a fallback
            step = JobStep(job_id=job.id, step_name=current_step_name, status="completed", file_path=actually_produced_path, finished_at=datetime.utcnow())
            db.add(step)
        
        job.status = "audio_cleaned" # Or a more specific status like "custom_audio_cleaned"
        job.current_step = current_step_name
        
        # Add to AudioFile history
        cleaned_audio_record = AudioFile(
            job_id=job.id,
            type="cleaned", # Could be "cleaned_custom_settings" if params were not default
            file_path=actually_produced_path,
            label=f"Cleaned ({Path(audio_to_clean_path).name} @ {timestamp})",
            created_at=datetime.utcnow()
            # You could also store `noise_reduction_sensitivity` and `vad_aggressiveness` here if needed
        )
        db.add(cleaned_audio_record)
        db.commit()

        print(f"[Job {job_id}] Audio cleaning successful. Output: {actually_produced_path}")
        return {
            "job_id": str(job.id),
            "status": "audio_cleaned_successfully",
            "cleaned_audio_path": f"/outputs/{job.id}/{cleaned_audio_filename}", # Relative path for frontend
            "file_path": actually_produced_path,    # Absolute path
            "label": cleaned_audio_record.label,
            "audio_file_id": str(cleaned_audio_record.id), # ID of the new AudioFile record
            "created_at": cleaned_audio_record.created_at.isoformat()
        }
    except HTTPException as http_exc:
        # db.rollback() # Rollback if necessary, though commit happens only on success typically
        raise http_exc # Re-raise FastAPI/Starlette HTTPExceptions
    except Exception as e:
        db.rollback() # Rollback on other exceptions before updating status
        error_info = f"[Job {job_id}] Unhandled error during audio cleaning: {e}"
        print(error_info)
        print(traceback.format_exc())
        
        step = db.query(JobStep).filter(JobStep.job_id == job.id, JobStep.step_name == current_step_name).first()
        if step:
            step.status = "failed"
            # step.details = str(e)
        job.status = f"{current_step_name}_failed"
        job.current_step = current_step_name
        db.commit() # Commit failure status
        
        return JSONResponse(
            status_code=500,
            content={"job_id": str(job.id), "status": "failed_processing_error", "error": f"An internal error occurred: {str(e)}"}
        )


@app.get("/project/{job_id}/clean-audio-files") # Renamed for clarity from the older example
async def get_job_cleaned_audio_files(job_id: str, db: Session = Depends(get_db)):
    """List all 'cleaned' type audio files for a specific job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Query AudioFile table for records associated with this job_id and of type 'cleaned' or similar
    cleaned_audio_files_db = db.query(AudioFile)\
        .filter(AudioFile.job_id == job.id, AudioFile.type.like("cleaned%"))\
        .order_by(AudioFile.created_at.desc())\
        .all()

    result = []
    for audio_db_record in cleaned_audio_files_db:
        if audio_db_record.file_path and os.path.exists(audio_db_record.file_path):
            relative_url = f"/outputs/{job.id}/{os.path.basename(audio_db_record.file_path)}"
            result.append({
                "id": str(audio_db_record.id),
                "path": audio_db_record.file_path, # Absolute server path
                "url": relative_url,               # URL for client access
                "label": audio_db_record.label or "Cleaned Audio",
                "name": audio_db_record.label or os.path.basename(audio_db_record.file_path),
                "created_at": audio_db_record.created_at.isoformat() if audio_db_record.created_at else None,
                "type": audio_db_record.type
                # You can add other metadata stored in AudioFile record here
            })
        else:
            print(f"Warning: Cleaned audio record ID {audio_db_record.id} file not found: {audio_db_record.file_path}")
            
    return {"job_id": str(job.id), "cleaned_audio_files": result}

@app.get("/voices")
async def get_voices():
    """Get available voices from ElevenLabs"""
    try:
        voices = tts_generator.get_available_voices()
        return {"voices": voices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tts/{job_id}")
async def generate_tts(
    job_id: str,
    subtitle_id: str = Form(...),
    voice_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Generate speech from subtitle text"""
    try:
        # Get subtitle content
        subtitle = db.query(Subtitle).filter(Subtitle.id == subtitle_id, Subtitle.job_id == job_id).first()
        if not subtitle or not subtitle.file_path or not os.path.exists(subtitle.file_path):
            raise HTTPException(status_code=404, detail="Subtitle file not found")

        # Read subtitle content
        with open(subtitle.file_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        # Extract text from SRT
        text = tts_generator.extract_text_from_srt(srt_content)

        # Generate output path
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        output_filename = f"tts_{job_id}_{timestamp}.mp3"
        output_path = os.path.join(OUTPUT_DIR, str(job_id), output_filename)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Generate speech
        result = tts_generator.generate_speech(text, voice_id, output_path)

        # Add to AudioFile table
        audio_file = AudioFile(
            job_id=job_id,
            type="tts_generated",
            file_path=output_path,
            label=f"TTS Generated ({os.path.basename(subtitle.file_path)})",
            voice_id=voice_id,
            created_at=datetime.utcnow()
        )
        db.add(audio_file)
        db.commit()

        return {
            "status": "success",
            "audioUrl": f"/outputs/{job_id}/{output_filename}",
            "audioFileId": str(audio_file.id)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sts/{job_id}")
async def generate_sts(
    job_id: str,
    audio_id: str = Form(...),
    voice_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Convert voice in audio file to target voice"""
    try:
        # Get audio file
        audio = db.query(AudioFile).filter(AudioFile.id == audio_id, AudioFile.job_id == job_id).first()
        if not audio or not audio.file_path or not os.path.exists(audio.file_path):
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Generate output path
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        output_filename = f"sts_{job_id}_{timestamp}.mp3"
        output_path = os.path.join(OUTPUT_DIR, str(job_id), output_filename)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Convert voice
        result = sts_generator.convert_voice(audio.file_path, voice_id, output_path)

        # Add to AudioFile table
        audio_file = AudioFile(
            job_id=job_id,
            type="sts_generated",
            file_path=output_path,
            label=f"STS Generated ({os.path.basename(audio.file_path)})",
            voice_id=voice_id,
            created_at=datetime.utcnow()
        )
        db.add(audio_file)
        db.commit()

        return {
            "status": "success",
            "audioUrl": f"/outputs/{job_id}/{output_filename}",
            "audioFileId": str(audio_file.id)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Ensure necessary directories exist
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"UPLOAD_DIR: {UPLOAD_DIR.resolve()}")
    print(f"OUTPUT_DIR: {OUTPUT_DIR.resolve()}")
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)