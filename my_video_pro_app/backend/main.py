import os
import time
import shutil
import json
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import aiofiles
import uvicorn
from dotenv import load_dotenv
import requests
import re

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

# Import the VideoProcessor class from our existing code
from video_processor import VideoProcessor

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

# Create directories for storing uploads and processed files
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Dictionary to store jobs and their status
processing_jobs = {}

# Mount the outputs directory to serve files
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
# Mount the uploads directory as well (useful for debugging)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.get("/")
async def read_root():
    return {"message": "Video Processing API is running"}

@app.post("/upload-video/")
async def upload_video(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """Upload a video file to process"""
    # Generate a unique ID for this job
    job_id = str(int(time.time()))
    
    # Create job-specific directories
    job_upload_dir = UPLOAD_DIR / job_id
    job_output_dir = OUTPUT_DIR / job_id
    job_upload_dir.mkdir(exist_ok=True)
    job_output_dir.mkdir(exist_ok=True)
    
    # Save the uploaded file
    file_path = job_upload_dir / file.filename
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    
    # Register job in the processing jobs dictionary
    processing_jobs[job_id] = {
        "id": job_id,
        "filename": file.filename,
        "status": "uploaded",
        "upload_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video_path": str(file_path),
        "output_dir": str(job_output_dir),
        "steps": {
            "extract_audio": {"status": "pending", "path": None},
            "generate_subtitles": {"status": "pending", "path": None},
            "clean_audio": {"status": "pending", "path": None},
            "create_final_video": {"status": "pending", "path": None}
        }
    }
    
    return {"job_id": job_id, "status": "uploaded", "message": "Video uploaded successfully"}

@app.post("/extract-audio/{job_id}")
async def extract_audio(job_id: str):
    """Extract audio from the uploaded video"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    try:
        video_path = job["video_path"]
        output_dir = job["output_dir"]
        
        # Initialize VideoProcessor
        processor = VideoProcessor(video_path, debug_mode=True)
        
        # Extract audio
        audio_path = processor.extract_audio()
        
        # Copy the audio file to the job output directory
        output_filename = f"audio_{job_id}.wav"
        output_path = os.path.join(output_dir, output_filename)
        shutil.copy2(audio_path, output_path)
        
        # Update job status
        job["steps"]["extract_audio"]["status"] = "completed"
        job["steps"]["extract_audio"]["path"] = output_path
        job["status"] = "audio_extracted"
        
        return {
            "job_id": job_id, 
            "status": "audio_extracted", 
            "audio_path": f"/outputs/{job_id}/{output_filename}"
        }
        
    except Exception as e:
        job["steps"]["extract_audio"]["status"] = "failed"
        job["steps"]["extract_audio"]["error"] = str(e)
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

@app.post("/generate-subtitles/{job_id}")
async def generate_subtitles(
    job_id: str,
    transcription_method: str = Form("whisper"),
    language: str = Form("en"),
    whisper_model_size: str = Form("base"),
    assemblyai_api_key: str = Form(None)
):
    """Generate subtitles for the video"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    try:
        video_path = job["video_path"]
        output_dir = job["output_dir"]
        
        # Initialize VideoProcessor with appropriate settings
        use_assemblyai = transcription_method == "assemblyai"
        processor = VideoProcessor(
            video_path,
            whisper_model_size=whisper_model_size,
            use_assemblyai=use_assemblyai,
            assemblyai_api_key=assemblyai_api_key,
            debug_mode=True,
            language=language
        )
        
        # Generate subtitles
        subtitle_path = processor.generate_subtitles()
        
        # Copy the subtitle file to the job output directory
        output_filename = f"subtitles_{job_id}.srt"
        output_path = os.path.join(output_dir, output_filename)
        shutil.copy2(subtitle_path, output_path)
        
        # Read the subtitle content
        with open(output_path, 'r', encoding='utf-8') as f:
            subtitle_content = f.read()
        
        # Update job status
        job["steps"]["generate_subtitles"]["status"] = "completed"
        job["steps"]["generate_subtitles"]["path"] = output_path
        job["status"] = "subtitles_generated"
        
        return {
            "job_id": job_id, 
            "status": "subtitles_generated", 
            "subtitle_path": f"/outputs/{job_id}/{output_filename}",
            "subtitle_content": subtitle_content
        }
        
    except Exception as e:
        job["steps"]["generate_subtitles"]["status"] = "failed"
        job["steps"]["generate_subtitles"]["error"] = str(e)
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

@app.post("/save-edited-subtitles/{job_id}")
async def save_edited_subtitles(
    job_id: str,
    subtitle_content: str = Form(...)
):
    """Save edited subtitle content to a file"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    try:
        output_dir = job["output_dir"]
        
        # Save edited subtitle content to a new file
        output_filename = f"edited_subtitles_{job_id}.srt"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(subtitle_content)
        
        # Update job with edited subtitle path
        job["edited_subtitle_path"] = output_path
        
        return {
            "job_id": job_id, 
            "status": "subtitles_edited", 
            "edited_subtitle_path": f"/outputs/{job_id}/{output_filename}"
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

@app.post("/change-voice/{job_id}")
async def change_voice(
    job_id: str,
    voice_id: str = Form("21m00Tcm4TlvDq8ikWAM"),  # Default voice ID (Rachel)
    stability: float = Form(0.5),
    clarity: float = Form(0.75),
    voice_name: str = Form(None),  # Optional voice name for history
    custom_text: str = Form(None),  # Optional custom text to override subtitle text
    max_chunk_size: int = Form(400),  # Maximum chunk size to stay within credit limits
    subtitle_selection: str = Form("original"),  # 'original', 'edited', 'marathi', 'hindi'
    compare_with_original: bool = Form(False)  # Whether to generate a comparison view
):
    """Change voice using ElevenLabs API based on subtitles or custom text"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    try:
        output_dir = job["output_dir"]
        
        # Import VoiceChanger module
        from voice_changer import VoiceChanger
        
        # Initialize VoiceChanger (will use API key from .env file)
        voice_changer = VoiceChanger()
        
        # Create a timestamp for uniqueness
        timestamp = int(time.time())
        
        # Set output filename (include voice ID for reference)
        voice_id_short = voice_id[:8] if len(voice_id) > 8 else voice_id
        output_filename = f"voice_{voice_id_short}_{timestamp}_{job_id}.mp3"
        output_path = os.path.join(output_dir, output_filename)
        
        # Determine the text to use for voice generation
        script_text = ""
        if custom_text:
            # Use the provided custom text directly
            script_text = custom_text
            print(f"Using custom text for voice generation ({len(script_text)} characters)")
        else:
            # Determine which subtitle file to use based on subtitle_selection
            subtitle_path = None
            
            print(f"Subtitle selection requested: {subtitle_selection}")
            print(f"Available job keys: {job.keys()}")
            
            if subtitle_selection == "edited" and "edited_subtitle_path" in job:
                subtitle_path = job["edited_subtitle_path"]
                print(f"Using edited subtitle file: {subtitle_path}")
            elif subtitle_selection == "marathi" and "translated_subtitle_path_mr" in job:
                subtitle_path = job["translated_subtitle_path_mr"]
                print(f"Using Marathi subtitle file: {subtitle_path}")
            elif subtitle_selection == "hindi" and "translated_subtitle_path_hi" in job:
                subtitle_path = job["translated_subtitle_path_hi"]
                print(f"Using Hindi subtitle file: {subtitle_path}")
            else:
                # Default to original subtitles
                subtitle_path = job["steps"]["generate_subtitles"]["path"]
                print(f"Using original subtitle file: {subtitle_path}")
            
            if not subtitle_path or not os.path.exists(subtitle_path):
                raise HTTPException(status_code=400, detail=f"Selected subtitle file ({subtitle_selection}) not found")
                
            # Extract subtitle content
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
                
            # Extract plain text script from subtitles
            script_text = extract_text_from_srt(subtitle_content)
            
            if not script_text:
                raise HTTPException(status_code=500, detail="Failed to extract text from subtitles")
                
            print(f"Extracted script text from subtitles ({len(script_text)} characters)")
        
        # Generate audio from script using voice changer
        try:
            # First, check if the ElevenLabs API key is available
            if not voice_changer.api_key:
                raise ValueError("ElevenLabs API key is not set or is invalid")
                
            # Check available credits
            subscription_data = voice_changer.check_user_credits()
            if subscription_data:
                character_limit = subscription_data.get('character_limit', 0)
                characters_used = subscription_data.get('character_count', 0)
                available_credits = character_limit - characters_used
            else:
                available_credits = 0
            required_credits = len(script_text)
            
            print(f"Available credits: {available_credits}, Required: {required_credits}")
            
            # If text is too long for available credits, use chunking
            if required_credits > available_credits or required_credits > max_chunk_size:
                print(f"Text too long for available credits. Using chunking approach.")
                
                # Create a temporary directory for the chunks
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Split the text into smaller chunks that fit within credit limits and max_chunk_size
                    chunk_size = min(available_credits - 50, max_chunk_size)  # Leave some buffer
                    if chunk_size < 100:
                        # Not enough credits - return early with skip message
                        return await skip_voice_change(
                            job_id,
                            error_message=f"Not enough credits available. Available: {available_credits}, minimum needed: 100"
                        )
                    
                    # Split by sentences to keep coherent chunks
                    import re
                    sentences = re.split(r'(?<=[.!?])\s+', script_text)
                    chunks = []
                    current_chunk = ""
                    
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) <= chunk_size:
                            current_chunk += sentence + " "
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence + " "
                    
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    
                    print(f"Split text into {len(chunks)} chunks")
                    
                    # Process each chunk
                    chunk_files = []
                    for i, chunk in enumerate(chunks):
                        chunk_output = os.path.join(temp_dir, f"chunk_{i}.mp3")
                        print(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                        
                        success = voice_changer.generate_voice_from_text(
                            text=chunk,
                            voice_id=voice_id,
                            output_filename=chunk_output,
                            stability=stability,
                            similarity_boost=clarity
                        )
                        
                        if not success:
                            raise ValueError(f"Failed to generate voice for chunk {i+1}")
                        
                        chunk_files.append(chunk_output)
                    
                    # Combine all audio chunks
                    from pydub import AudioSegment
                    combined = AudioSegment.empty()
                    for chunk_file in chunk_files:
                        audio_segment = AudioSegment.from_mp3(chunk_file)
                        combined += audio_segment
                    
                    combined.export(output_path, format="mp3")
                    print(f"Combined {len(chunks)} audio chunks into {output_path}")
            else:
                # Use the appropriate method based on input type
                if subtitle_path and not custom_text:
                    print("Using timing-preserved TTS generation for subtitle file")
                    # Check if the subtitle file actually has timing info
                    with open(subtitle_path, 'r', encoding='utf-8') as f:
                        subtitle_content = f.read()
                        has_timing = '-->' in subtitle_content
                    
                    if has_timing:
                        # Use improved timing-preserved method
                        success = voice_changer.generate_voice_with_timing(
                            subtitle_path=subtitle_path,
                            voice_id=voice_id,
                            output_filename=output_path,
                            stability=stability,
                            similarity_boost=clarity
                        )
                    else:
                        # No timing info found, use regular approach
                        print("No timing info found in subtitle file, using standard TTS")
                        success = voice_changer.generate_voice_from_text(
                            text=script_text,
                            voice_id=voice_id,
                            output_filename=output_path,
                            stability=stability,
                            similarity_boost=clarity
                        )
                else:
                    # Process the entire text at once if using custom text
                    print("Using standard TTS for custom text")
                    success = voice_changer.generate_voice_from_text(
                        text=script_text,
                        voice_id=voice_id,
                        output_filename=output_path,
                        stability=stability,
                        similarity_boost=clarity
                    )
                
                if not success:
                    return await skip_voice_change(job_id, error_message="Failed to generate voice audio from subtitles")
        except ValueError as ve:
            print(f"Error in voice generation: {str(ve)}")
            return await skip_voice_change(job_id, error_message=f"Voice generation error: {str(ve)}")
        except Exception as e:
            print(f"Error in voice generation: {str(e)}")
            return await skip_voice_change(job_id, error_message=f"Voice generation error: {str(e)}")
        
        # Initialize voice history if it doesn't exist
        if "voice_history" not in job:
            job["voice_history"] = []
            
        # Add current voice to history with metadata
        voice_entry = {
            "voice_id": voice_id,
            "voice_name": voice_name or f"Voice {len(job['voice_history']) + 1}",
            "timestamp": timestamp,
            "path": output_path,
            "url_path": f"/outputs/{job_id}/{output_filename}",
            "stability": stability,
            "clarity": clarity
        }
        
        # Add to history
        job["voice_history"].append(voice_entry)
        
        # Update job status
        if "steps" not in job:
            job["steps"] = {}
        
        if "change_voice" not in job["steps"]:
            job["steps"]["change_voice"] = {}
        
        job["steps"]["change_voice"]["status"] = "completed"
        job["steps"]["change_voice"]["path"] = output_path
        job["status"] = "voice_changed"
        
        # If comparison is requested, prepare additional data
        comparison_data = None
        if compare_with_original:
            # Get original audio path
            original_audio_path = None
            if "steps" in job and "extract_audio" in job["steps"] and job["steps"]["extract_audio"]["status"] == "completed":
                original_audio_path = job["steps"]["extract_audio"]["path"]
            
            if original_audio_path and os.path.exists(original_audio_path):
                print(f"Creating comparison data between original audio and generated voice")
                # Add original audio info to the response
                comparison_data = {
                    "original_audio_path": f"/outputs/{job_id}/audio_{job_id}.wav",
                    "generated_audio_path": f"/outputs/{job_id}/{output_filename}",
                    "original_duration": get_audio_duration(original_audio_path),
                    "generated_duration": get_audio_duration(output_path),
                }
        
        return {
            "job_id": job_id, 
            "status": "voice_changed", 
            "voice_changed_audio_path": f"/outputs/{job_id}/{output_filename}",
            "voice_history": job["voice_history"],
            "comparison_data": comparison_data
        }
        
    except Exception as e:
        import traceback
        print(f"Voice change error: {str(e)}")
        print(traceback.format_exc())
        
        # Make sure we have change_voice in steps
        if "steps" in job and "change_voice" not in job["steps"]:
            job["steps"]["change_voice"] = {}
            
        # Update error status
        if "steps" in job and "change_voice" in job["steps"]:
            job["steps"]["change_voice"]["status"] = "failed"
            job["steps"]["change_voice"]["error"] = str(e)
            
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

# Helper function to get audio duration
def get_audio_duration(audio_path):
    """Get duration of audio file in seconds"""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Convert from ms to seconds
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return None

@app.get("/compare-audio/{job_id}/{voice_index}")
async def compare_audio(job_id: str, voice_index: int = 0):
    """Get comparison data for original audio and generated voice"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    
    # Get original audio path
    original_audio_path = None
    if "steps" in job and "extract_audio" in job["steps"] and job["steps"]["extract_audio"]["status"] == "completed":
        original_audio_path = job["steps"]["extract_audio"]["path"]
    
    if not original_audio_path or not os.path.exists(original_audio_path):
        raise HTTPException(status_code=404, detail="Original audio not found")
    
    # Get generated voice
    if "voice_history" not in job or len(job["voice_history"]) <= voice_index:
        raise HTTPException(status_code=404, detail="Generated voice not found")
    
    generated_audio_path = job["voice_history"][voice_index]["path"]
    if not os.path.exists(generated_audio_path):
        raise HTTPException(status_code=404, detail="Generated audio file not found")
    
    # Get audio durations
    original_duration = get_audio_duration(original_audio_path)
    generated_duration = get_audio_duration(generated_audio_path)
    
    # Get subtitle timing if available
    subtitle_timing = []
    if "steps" in job and "generate_subtitles" in job["steps"] and job["steps"]["generate_subtitles"]["status"] == "completed":
        subtitle_path = job["steps"]["generate_subtitles"]["path"]
        if os.path.exists(subtitle_path):
            # Extract timing information from SRT
            import re
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Match SRT timing entries
            timing_pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)(?=\n\s*\n\s*\d+|\n\s*\n\s*$|$)')
            matches = timing_pattern.findall(content)
            
            for idx, start_time, end_time, text in matches:
                # Parse timing from SRT format
                def parse_srt_time(time_str):
                    h, m, s = time_str.replace(',', '.').split(':')
                    return int(h) * 3600 + int(m) * 60 + float(s)
                
                start_sec = parse_srt_time(start_time)
                end_sec = parse_srt_time(end_time)
                
                subtitle_timing.append({
                    "index": int(idx),
                    "start": start_sec,
                    "end": end_sec,
                    "text": text.strip()
                })
    
    return {
        "job_id": job_id,
        "original_audio": {
            "path": f"/outputs/{job_id}/audio_{job_id}.wav",
            "duration": original_duration
        },
        "generated_audio": {
            "path": f"/outputs/{job_id}/{os.path.basename(generated_audio_path)}",
            "duration": generated_duration,
            "voice_name": job["voice_history"][voice_index]["voice_name"]
        },
        "subtitle_timing": subtitle_timing
    }

@app.get("/voice-history/{job_id}")
async def get_voice_history(job_id: str):
    """Get the voice change history for a job"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    
    # Return voice history or empty list if none exists
    voice_history = job.get("voice_history", [])
    
    return {"voice_history": voice_history}

@app.post("/clean-audio/{job_id}")
async def clean_audio(
    job_id: str,
    enable_noise_reduction: bool = Form(True),
    noise_reduction_sensitivity: float = Form(0.2),
    enable_vad_cleaning: bool = Form(True),
    vad_aggressiveness: int = Form(1)
):
    """Clean the audio by reducing noise and removing filler words"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    try:
        video_path = job["video_path"]
        output_dir = job["output_dir"]
        
        # Initialize VideoProcessor with appropriate settings
        processor = VideoProcessor(video_path, debug_mode=True)
        
        # Set audio cleaning options
        processor.noise_reduction_enabled = enable_noise_reduction
        processor.noise_reduction_sensitivity = noise_reduction_sensitivity
        processor.vad_cleaning_enabled = enable_vad_cleaning
        processor.vad_aggressiveness = vad_aggressiveness
        
        # Clean audio
        cleaned_audio_path = processor.clean_audio()
        
        # Copy the cleaned audio file to the job output directory
        output_filename = f"cleaned_audio_{job_id}.wav"
        output_path = os.path.join(output_dir, output_filename)
        shutil.copy2(cleaned_audio_path, output_path)
        
        # Update job status
        job["steps"]["clean_audio"]["status"] = "completed"
        job["steps"]["clean_audio"]["path"] = output_path
        job["status"] = "audio_cleaned"
        
        return {
            "job_id": job_id, 
            "status": "audio_cleaned", 
            "cleaned_audio_path": f"/outputs/{job_id}/{output_filename}"
        }
        
    except Exception as e:
        job["steps"]["clean_audio"]["status"] = "failed"
        job["steps"]["clean_audio"]["error"] = str(e)
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

@app.post("/create-final-video/{job_id}")
async def create_final_video(
    job_id: str,
    subtitle_path: str = Form(None),
    font_size: int = Form(24),
    subtitle_color: str = Form("white"),
    subtitle_bg_opacity: int = Form(80),
    use_direct_ffmpeg: bool = Form(True),
    audio_id: str = Form("cleaned"),  # Default to cleaned audio
    subtitle_id: str = Form(None)     # Added subtitle_id parameter
):
    """Create the final video with clean audio and subtitles"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    try:
        video_path = job["video_path"]
        output_dir = job["output_dir"]
        
        # Determine which subtitle file to use based on subtitle_id or subtitle_path
        subtitle_file_to_use = None
        
        print(f"Subtitle ID selected: {subtitle_id}")
        print(f"Subtitle path provided: {subtitle_path}")
        
        if subtitle_id:
            # Use subtitle based on ID
            if subtitle_id == "original" and "steps" in job and "generate_subtitles" in job["steps"] and job["steps"]["generate_subtitles"]["status"] == "completed":
                subtitle_file_to_use = job["steps"]["generate_subtitles"]["path"]
                print(f"Using original subtitles based on ID: {subtitle_file_to_use}")
            elif subtitle_id == "edited" and "edited_subtitle_path" in job:
                subtitle_file_to_use = job["edited_subtitle_path"]
                print(f"Using edited subtitles based on ID: {subtitle_file_to_use}")
            elif subtitle_id == "marathi" and "translated_subtitle_path_mr" in job:
                subtitle_file_to_use = job["translated_subtitle_path_mr"]
                print(f"Using Marathi subtitles based on ID: {subtitle_file_to_use}")
            elif subtitle_id == "hindi" and "translated_subtitle_path_hi" in job:
                subtitle_file_to_use = job["translated_subtitle_path_hi"]
                print(f"Using Hindi subtitles based on ID: {subtitle_file_to_use}")
            else:
                print(f"Could not find subtitles for ID: {subtitle_id}")
        elif subtitle_path:
            # Use provided path (from frontend)
            subtitle_file_to_use = subtitle_path
            print(f"Using provided subtitle path: {subtitle_file_to_use}")
        elif "edited_subtitle_path" in job and job["edited_subtitle_path"]:
            # Use edited subtitles
            subtitle_file_to_use = job["edited_subtitle_path"]
            print(f"Using edited subtitle path: {subtitle_file_to_use}")
        elif job["steps"]["generate_subtitles"]["status"] == "completed":
            # Use original subtitles
            subtitle_file_to_use = job["steps"]["generate_subtitles"]["path"]
            print(f"Using original subtitle path: {subtitle_file_to_use}")
        else:
            print("No suitable subtitle file found")
        
        # Verify that the selected subtitle file exists
        if subtitle_file_to_use and not os.path.exists(subtitle_file_to_use):
            print(f"Warning: Selected subtitle file does not exist: {subtitle_file_to_use}")
            subtitle_file_to_use = None
            
        # Determine which audio file to use based on audio_id
        custom_audio_path = None
        
        print(f"Audio ID selected: {audio_id}")
        print(f"Available voice history: {len(job.get('voice_history', []))} items")
        
        if audio_id == "original" and "steps" in job and "extract_audio" in job["steps"] and job["steps"]["extract_audio"]["status"] == "completed":
            custom_audio_path = job["steps"]["extract_audio"]["path"]
            print(f"Using original audio: {custom_audio_path}")
        elif audio_id == "cleaned" and "steps" in job and "clean_audio" in job["steps"] and job["steps"]["clean_audio"]["status"] == "completed":
            custom_audio_path = job["steps"]["clean_audio"]["path"]
            print(f"Using cleaned audio: {custom_audio_path}")
        elif audio_id and audio_id.startswith("voice_") and "voice_history" in job:
            try:
                voice_index = int(audio_id.split("_")[1])
                if 0 <= voice_index < len(job["voice_history"]):
                    custom_audio_path = job["voice_history"][voice_index]["path"]
                    print(f"Using voice changed audio #{voice_index}: {custom_audio_path}")
                else:
                    print(f"Voice index {voice_index} out of range (0-{len(job['voice_history'])-1})")
            except (ValueError, IndexError) as e:
                print(f"Error parsing voice index from {audio_id}: {str(e)}")
        else:
            print(f"Could not match audio_id {audio_id} to any available audio")
            # Fallback to using cleaned audio if available
            if "steps" in job and "clean_audio" in job["steps"] and job["steps"]["clean_audio"]["status"] == "completed":
                custom_audio_path = job["steps"]["clean_audio"]["path"]
                print(f"Falling back to cleaned audio: {custom_audio_path}")
            # Otherwise try original audio
            elif "steps" in job and "extract_audio" in job["steps"] and job["steps"]["extract_audio"]["status"] == "completed":
                custom_audio_path = job["steps"]["extract_audio"]["path"]
                print(f"Falling back to original audio: {custom_audio_path}")
        
        # Check if the selected audio file exists
        if custom_audio_path and not os.path.exists(custom_audio_path):
            custom_audio_path = None
            print(f"Warning: Selected audio file does not exist: {custom_audio_path}")
        
        # Initialize VideoProcessor with appropriate settings
        processor = VideoProcessor(video_path, debug_mode=True)
        
        # Set subtitle options
        processor.subtitle_font_size = font_size
        processor.subtitle_color = subtitle_color
        processor.subtitle_bg_opacity = subtitle_bg_opacity
        processor.use_direct_ffmpeg = use_direct_ffmpeg
        
        # Create final video with custom audio if available
        final_video_path = processor.create_final_video(
            custom_subtitle_path=subtitle_file_to_use,
            custom_audio_path=custom_audio_path
        )
        
        # Copy the final video file to the job output directory
        output_filename = f"final_video_{job_id}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        shutil.copy2(final_video_path, output_path)
        
        # Update job status
        job["steps"]["create_final_video"]["status"] = "completed"
        job["steps"]["create_final_video"]["path"] = output_path
        job["status"] = "completed"
        
        # Store the selected audio and subtitle choices in the job data
        job["final_audio_id"] = audio_id
        job["final_subtitle_id"] = subtitle_id
        
        return {
            "job_id": job_id, 
            "status": "completed", 
            "final_video_path": f"/outputs/{job_id}/{output_filename}"
        }
        
    except Exception as e:
        job["steps"]["create_final_video"]["status"] = "failed"
        job["steps"]["create_final_video"]["error"] = str(e)
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a processing job"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return processing_jobs[job_id]

@app.get("/video-info/{job_id}")
async def get_video_info(job_id: str):
    """Get information about the video"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    try:
        video_path = job["video_path"]
        
        # Initialize VideoProcessor
        processor = VideoProcessor(video_path)
        
        # Get video info
        video_info = processor.get_video_info()
        
        return {
            "job_id": job_id,
            "video_info": video_info
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

@app.get("/download/{job_id}/{file_type}")
async def download_file(job_id: str, file_type: str):
    """Download a processed file"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    
    # Map file_type to step and file extension
    file_mappings = {
        "audio": ("extract_audio", "wav"),
        "subtitles": ("generate_subtitles", "srt"),
        "cleaned_audio": ("clean_audio", "wav"),
        "final_video": ("create_final_video", "mp4")
    }
    
    if file_type not in file_mappings:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    step, extension = file_mappings[file_type]
    
    # Check if the file exists and is ready
    if job["steps"][step]["status"] != "completed":
        raise HTTPException(status_code=404, detail=f"{file_type} not ready or not found")
    
    file_path = job["steps"][step]["path"]
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Return the file
    return FileResponse(file_path, filename=f"{file_type}_{job_id}.{extension}")

@app.get("/subtitle-content/{job_id}")
async def get_subtitle_content(job_id: str):
    """Get the subtitle content for a job"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    subtitle_path = None
    
    # First try edited subtitles if they exist
    if "edited_subtitle_path" in job and job["edited_subtitle_path"]:
        subtitle_path = job["edited_subtitle_path"]
    # Then try original subtitles
    elif job["steps"]["generate_subtitles"]["status"] == "completed":
        subtitle_path = job["steps"]["generate_subtitles"]["path"]
        
    if not subtitle_path or not os.path.exists(subtitle_path):
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            subtitle_content = f.read()
        
        return {"subtitle_content": subtitle_content}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to read subtitle file: {str(e)}"}
        )

@app.post("/translate-subtitles/{job_id}")
async def translate_subtitles(
    job_id: str,
    target_language: str = Form(...),  # 'mr' for Marathi, 'hi' for Hindi
    content: str = Form(...)  # Subtitle content to translate
):
    """Translate subtitles to the target language"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    
    try:
        # Import required libraries
        import srt
        from googletrans import Translator, LANGUAGES
        
        # Validate target language
        if target_language not in ['mr', 'hi']:
            raise HTTPException(status_code=400, detail=f"Unsupported target language '{target_language}'. Please use 'mr' for Marathi or 'hi' for Hindi.")
        
        # Parse the SRT content
        try:
            print(f"Parsing SRT content for job {job_id}...")
            subtitles = list(srt.parse(content))
            print(f"Successfully parsed {len(subtitles)} subtitles")
        except Exception as parse_error:
            print(f"Error parsing SRT content: {str(parse_error)}")
            raise HTTPException(status_code=400, detail=f"Error parsing SRT content: {str(parse_error)}")
        
        if not subtitles:
            raise HTTPException(status_code=400, detail="No subtitles found in the input content.")
        
        # Initialize the translator
        translator = Translator(service_urls=['translate.google.com'])
        translated_subtitles = []
        
        # For longer subtitle files, process in batches to avoid timeouts
        batch_size = 20  # Process 20 subtitles at a time
        total_batches = (len(subtitles) + batch_size - 1) // batch_size  # Ceiling division
        
        print(f"Starting translation to {target_language} in {total_batches} batches")
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(subtitles))
            batch = subtitles[start_idx:end_idx]
            
            print(f"Processing batch {batch_idx+1}/{total_batches} (subtitles {start_idx+1}-{end_idx})")
            
            for sub in batch:
                try:
                    # Add a retry mechanism for each translation
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            translation = translator.translate(sub.content, src='en', dest=target_language)
                            translated_text = translation.text
                            break
                        except Exception as e:
                            if retry < max_retries - 1:
                                print(f"Translation attempt {retry+1} failed for subtitle {sub.index}, retrying...")
                                time.sleep(1)  # Wait before retrying
                            else:
                                raise e
                    
                    translated_subtitles.append(
                        srt.Subtitle(
                            index=sub.index,
                            start=sub.start,
                            end=sub.end,
                            content=translated_text,
                            proprietary=sub.proprietary
                        )
                    )
                except Exception as e:
                    # Keep original text if translation fails
                    print(f"Error translating subtitle {sub.index}: {str(e)}")
                    print(f"Using original text for subtitle {sub.index}")
                    translated_subtitles.append(sub)
            
            # Short pause between batches to prevent rate limiting
            if batch_idx < total_batches - 1:
                time.sleep(0.5)
        
        print(f"Translation complete. Composing final SRT file...")
        
        # Compose the final translated SRT content
        translated_content = srt.compose(translated_subtitles)
        
        # Save the translated subtitle file
        output_dir = job["output_dir"]
        language_name = "marathi" if target_language == "mr" else "hindi"
        output_filename = f"subtitles_{job_id}_{language_name}.srt"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        
        print(f"Translated subtitle file saved to {output_path}")
        
        # Store the translated subtitle path in the job data with language key
        path_key = f"translated_subtitle_path_{target_language}"
        job[path_key] = output_path
        
        print(f"Saved translated subtitle path in job data with key: {path_key}")
        print(f"Updated job keys: {job.keys()}")
        
        return {
            "job_id": job_id,
            "status": "success",
            "translated_content": translated_content,
            "translated_subtitle_path": f"/outputs/{job_id}/{output_filename}"
        }
    except Exception as e:
        import traceback
        print(f"Error translating subtitles: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "failed", "error": str(e)}
        )

@app.post("/skip-voice-change/{job_id}")
async def skip_voice_change(job_id: str, error_message: str = None):
    """Skip the voice changing step and mark it as skipped"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    
    # Update job status to indicate voice change was skipped
    if "steps" not in job:
        job["steps"] = {}
    
    if "change_voice" not in job["steps"]:
        job["steps"]["change_voice"] = {}
    
    job["steps"]["change_voice"]["status"] = "skipped"
    if error_message:
        job["steps"]["change_voice"]["error"] = error_message
    job["status"] = "voice_change_skipped"
    
    # Add an empty voice history if it doesn't exist
    if "voice_history" not in job:
        job["voice_history"] = []
    
    # Return a response that matches the structure the frontend expects
    return {
        "job_id": job_id,
        "status": "voice_change_skipped",
        "message": error_message or "Voice changing step was skipped",
        "voice_changed_audio_path": None,  # Include this field even if null
        "voice_history": job["voice_history"]
    }

@app.get("/available-audio/{job_id}")
async def get_available_audio(job_id: str):
    """Get a list of all available audio files for a job"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    available_audio = []
    
    print(f"Gathering available audio for job {job_id}")
    
    # Add original audio if available
    if "steps" in job and "extract_audio" in job["steps"] and job["steps"]["extract_audio"]["status"] == "completed":
        original_audio_path = job["steps"]["extract_audio"]["path"]
        if os.path.exists(original_audio_path):
            print(f"Found original audio: {original_audio_path}")
            available_audio.append({
                "id": "original",
                "name": "Original Audio",
                "path": original_audio_path,
                "url_path": f"/outputs/{job_id}/audio_{job_id}.wav",
                "type": "original"
            })
    
    # Add cleaned audio if available
    if "steps" in job and "clean_audio" in job["steps"] and job["steps"]["clean_audio"]["status"] == "completed":
        cleaned_audio_path = job["steps"]["clean_audio"]["path"]
        if os.path.exists(cleaned_audio_path):
            print(f"Found cleaned audio: {cleaned_audio_path}")
            available_audio.append({
                "id": "cleaned",
                "name": "Cleaned Audio",
                "path": cleaned_audio_path,
                "url_path": f"/outputs/{job_id}/cleaned_audio_{job_id}.wav",
                "type": "cleaned"
            })
    
    # Add voice changed audio files if available
    if "voice_history" in job and job["voice_history"]:
        print(f"Found {len(job['voice_history'])} voice history entries")
        for i, voice in enumerate(job["voice_history"]):
            if "path" in voice and os.path.exists(voice["path"]):
                print(f"Found voice {i}: {voice.get('voice_name', f'Voice {i+1}')} at {voice['path']}")
                available_audio.append({
                    "id": f"voice_{i}",
                    "name": f"{voice.get('voice_name', f'Voice {i+1}')}",
                    "path": voice["path"],
                    "url_path": voice["url_path"],
                    "type": "voice_changed",
                    "voice_id": voice.get("voice_id", ""),
                    "language": voice.get("language", "en")
                })
            else:
                print(f"Voice {i} has no path or file doesn't exist: {voice.get('path', 'No path')}")
    
    # Force at least one audio option if list is empty
    if not available_audio and "steps" in job and "extract_audio" in job["steps"]:
        # Try to create a minimal entry based on job data
        extract_step = job["steps"]["extract_audio"]
        if "path" in extract_step:
            audio_path = extract_step["path"]
            print(f"No audio files found, using fallback: {audio_path}")
            available_audio.append({
                "id": "original",
                "name": "Original Audio (Fallback)",
                "path": audio_path,
                "url_path": f"/outputs/{job_id}/audio_{job_id}.wav",
                "type": "original"
            })
    
    print(f"Returning {len(available_audio)} audio files")
    return {"available_audio": available_audio}

@app.get("/available-subtitles/{job_id}")
async def get_available_subtitles(job_id: str):
    """Get a list of all available subtitle files for a job"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = processing_jobs[job_id]
    available_subtitles = []
    
    print(f"Gathering available subtitles for job {job_id}")
    
    # Add original subtitles if available
    if "steps" in job and "generate_subtitles" in job["steps"] and job["steps"]["generate_subtitles"]["status"] == "completed":
        subtitle_path = job["steps"]["generate_subtitles"]["path"]
        if os.path.exists(subtitle_path):
            print(f"Found original subtitles: {subtitle_path}")
            available_subtitles.append({
                "id": "original",
                "name": "Original Subtitles",
                "path": subtitle_path,
                "url_path": f"/outputs/{job_id}/subtitles_{job_id}.srt",
                "type": "original",
                "language": job.get("language", "en")
            })
    
    # Add edited subtitles if available
    if "edited_subtitle_path" in job and job["edited_subtitle_path"]:
        edited_subtitle_path = job["edited_subtitle_path"]
        if os.path.exists(edited_subtitle_path):
            print(f"Found edited subtitles: {edited_subtitle_path}")
            available_subtitles.append({
                "id": "edited",
                "name": "Edited Subtitles",
                "path": edited_subtitle_path,
                "url_path": edited_subtitle_path.replace(str(OUTPUT_DIR), "/outputs"),
                "type": "edited",
                "language": job.get("language", "en")
            })
    
    # Add translated Marathi subtitles if available
    if "translated_subtitle_path_mr" in job and job["translated_subtitle_path_mr"]:
        mr_subtitle_path = job["translated_subtitle_path_mr"]
        if os.path.exists(mr_subtitle_path):
            print(f"Found Marathi subtitles: {mr_subtitle_path}")
            available_subtitles.append({
                "id": "marathi",
                "name": "Marathi Subtitles",
                "path": mr_subtitle_path,
                "url_path": mr_subtitle_path.replace(str(OUTPUT_DIR), "/outputs"),
                "type": "translated",
                "language": "mr"
            })
    
    # Add translated Hindi subtitles if available
    if "translated_subtitle_path_hi" in job and job["translated_subtitle_path_hi"]:
        hi_subtitle_path = job["translated_subtitle_path_hi"]
        if os.path.exists(hi_subtitle_path):
            print(f"Found Hindi subtitles: {hi_subtitle_path}")
            available_subtitles.append({
                "id": "hindi",
                "name": "Hindi Subtitles",
                "path": hi_subtitle_path,
                "url_path": hi_subtitle_path.replace(str(OUTPUT_DIR), "/outputs"),
                "type": "translated",
                "language": "hi"
            })
    
    print(f"Returning {len(available_subtitles)} subtitle files")
    return {"available_subtitles": available_subtitles}

# Run the server if executed directly
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    uvicorn.run("main:app", host=host, port=port, reload=debug) 