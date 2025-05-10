import os
import tempfile
import subprocess
import re
import shutil
import traceback
from typing import Dict, List, Tuple, Any

import numpy as np
import whisper
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_nonsilent
import torch
import assemblyai as aai  # Import AssemblyAI

class VideoProcessor:
    """
    A class for processing video files, extracting audio, generating subtitles,
    cleaning audio, and creating a final video with subtitles.
    """
    
    def __init__(self, video_path: str, whisper_model_size: str = "base", use_assemblyai: bool = False, assemblyai_api_key: str = None):
        """
        Initialize the VideoProcessor with a video file.
        
        Args:
            video_path: Path to the video file
            whisper_model_size: Size of the Whisper model to use ("tiny", "base", "small", "medium")
            use_assemblyai: Whether to use AssemblyAI instead of Whisper
            assemblyai_api_key: API key for AssemblyAI (required if use_assemblyai is True)
        """
        self.video_path = video_path
        self.output_dir = self._create_output_dir()
        self.audio_path = os.path.join(self.output_dir, "extracted_audio.wav")
        self.subtitles_path = os.path.join(self.output_dir, "subtitles.srt")
        self.cleaned_audio_path = os.path.join(self.output_dir, "cleaned_audio.wav")
        self.final_video_path = os.path.join(self.output_dir, "final_video.mp4")
        
        # Transcription settings
        self.use_assemblyai = use_assemblyai
        self.assemblyai_api_key = assemblyai_api_key
        
        # Whisper model parameters
        self.whisper_model_size = whisper_model_size
        self.whisper_model = None
        
        # Verbose logging for debugging
        self.verbose = True
        
        # Load the video file
        self.video = VideoFileClip(video_path)
        
        # Filler words to remove
        self.filler_words = ["um", "uh", "hmm", "uhh", "err", "ah", "like", "you know"]
    
    def _create_output_dir(self) -> str:
        """Create a temporary directory for output files."""
        output_dir = tempfile.mkdtemp()
        return output_dir
    
    def get_video_info(self) -> Dict[str, Any]:
        """
        Get basic information about the video.
        
        Returns:
            Dictionary containing video metadata
        """
        return {
            "duration": self.video.duration,
            "fps": self.video.fps,
            "width": self.video.w,
            "height": self.video.h,
            "audio": self.video.audio is not None
        }
    
    def extract_audio(self) -> str:
        """
        Extract audio from the video file.
        
        Returns:
            Path to the extracted audio file
        """
        # Ensure the audio exists
        if self.video.audio is None:
            raise ValueError("The video file does not contain an audio track.")
        
        # Extract audio with normalized settings
        self.video.audio.write_audiofile(
            self.audio_path, 
            codec='pcm_s16le',  # Use PCM for better compatibility
            ffmpeg_params=["-ac", "1"],  # Convert to mono
            fps=16000  # Use 16kHz sample rate for better compatibility with Whisper
        )
        
        # Verify the audio file exists and has content
        if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) < 1000:
            raise FileNotFoundError(f"Audio extraction failed or produced empty file: {self.audio_path}")
        
        if self.verbose:
            print(f"Audio extracted to {self.audio_path} ({os.path.getsize(self.audio_path)} bytes)")
        
        return self.audio_path
    
    def _load_whisper_model(self):
        """
        Load the Whisper model with error handling.
        """
        if self.whisper_model is None:
            try:
                print(f"Loading Whisper model: {self.whisper_model_size}")
                
                # Try to load model with GPU acceleration if available
                if torch.cuda.is_available():
                    print("Using GPU acceleration for Whisper")
                    device = "cuda"
                    # Set optimal parameters for CUDA
                    torch.cuda.empty_cache()
                    # Use mixed precision where supported
                    if self.whisper_model_size in ["base", "small", "medium"]:
                        use_fp16 = True
                    else:
                        use_fp16 = False
                else:
                    print("Using CPU for Whisper (this may be slow)")
                    device = "cpu"
                    use_fp16 = False
                
                # Attempt to load with error handling
                try:
                    self.whisper_model = whisper.load_model(self.whisper_model_size, device=device)
                    print(f"Successfully loaded {self.whisper_model_size} model on {device}")
                except RuntimeError as e:
                    if "CUDA out of memory" in str(e) and self.whisper_model_size != "tiny":
                        print(f"CUDA out of memory with {self.whisper_model_size} model, trying tiny")
                        self.whisper_model_size = "tiny"
                        self.whisper_model = whisper.load_model("tiny", device=device)
                    else:
                        # If GPU fails, try CPU as last resort
                        if device == "cuda":
                            print("GPU loading failed, falling back to CPU")
                            self.whisper_model = whisper.load_model(self.whisper_model_size, device="cpu")
                        else:
                            raise
                
            except Exception as e:
                print(f"Error loading Whisper model '{self.whisper_model_size}': {e}")
                
                # If the requested model fails, try to fall back to a smaller one
                if self.whisper_model_size != "tiny":
                    print("Falling back to 'tiny' model")
                    self.whisper_model_size = "tiny"
                    try:
                        self.whisper_model = whisper.load_model("tiny", device="cpu")
                    except Exception as e2:
                        print(f"Even tiny model failed: {e2}")
                        raise RuntimeError(f"Failed to load any Whisper model: {e2}")
                else:
                    # If even tiny fails, re-raise the exception
                    raise RuntimeError(f"Failed to load Whisper model: {e}")
    
    def _direct_transcribe_with_command_line(self) -> bool:
        """
        Try transcribing using the command line whisper tool as a fallback.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            print("Attempting transcription using command line whisper...")
            
            # Check if command line whisper is installed
            try:
                result = subprocess.run(
                    ["whisper", "--help"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5  # Timeout after 5 seconds
                )
                if result.returncode != 0:
                    print("Command line whisper not properly installed.")
                    return False
            except (subprocess.SubprocessError, FileNotFoundError):
                print("Command line whisper not installed or not in PATH.")
                return False
            
            # Set device flag based on availability
            device_flag = "--device cuda" if torch.cuda.is_available() else "--device cpu"
            
            # Try to execute whisper command line with timeout and proper error handling
            try:
                cmd = [
                    "whisper", 
                    self.audio_path, 
                    "--model", self.whisper_model_size,
                    "--language", "en",
                    "--output_dir", self.output_dir,
                    "--output_format", "srt"
                ]
                
                # Add device flag
                cmd.extend(device_flag.split())
                
                print(f"Running command: {' '.join(cmd)}")
                
                # Set a reasonable timeout based on audio length and model size
                timeout = max(300, int(self.video.duration * 1.5))  # At least 5 minutes
                
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout
                )
                
                # Check if process succeeded
                if result.returncode != 0:
                    print(f"Command failed with exit code {result.returncode}")
                    print(f"Error output: {result.stderr}")
                    return False
                
            except subprocess.TimeoutExpired:
                print(f"Command timed out after {timeout} seconds")
                return False
            except Exception as e:
                print(f"Command execution failed: {e}")
                return False
            
            # Check for output file (may have a different name)
            srt_files = [f for f in os.listdir(self.output_dir) if f.endswith('.srt')]
            if srt_files:
                generated_srt = os.path.join(self.output_dir, srt_files[0])
                if os.path.exists(generated_srt) and os.path.getsize(generated_srt) > 0:
                    # Copy to the expected subtitles path
                    with open(generated_srt, 'r', encoding='utf-8') as src, open(self.subtitles_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                    print("Command line transcription successful!")
                    return True
            
            print("Command line transcription attempt did not produce usable subtitles.")
            return False
            
        except Exception as e:
            print(f"Command line transcription failed: {e}")
            return False
    
    def _generate_subtitles_with_assemblyai(self) -> bool:
        """
        Generate subtitles using AssemblyAI API.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.assemblyai_api_key:
                print("AssemblyAI API key is required")
                return False
            
            print("Starting AssemblyAI transcription...")
            
            # Set the API key
            aai.settings.api_key = self.assemblyai_api_key
            
            # Configure the transcription
            config = aai.TranscriptionConfig(
                speech_model=aai.SpeechModel.best,  # Use the best model for accuracy
                punctuate=True,                     # Add punctuation
                format_text=True,                   # Format text with proper casing
                language_code="en"                  # Use English
            )
            
            # Create the transcriber with the configuration
            transcriber = aai.Transcriber(config=config)
            
            # Start the transcription
            print(f"Sending {self.audio_path} to AssemblyAI...")
            transcript = transcriber.transcribe(self.audio_path)
            
            # Check for errors
            if transcript.status == "error":
                print(f"AssemblyAI transcription error: {transcript.error}")
                return False
            
            print("AssemblyAI transcription completed successfully")
            
            # Convert the transcript to SRT format
            print("Converting to SRT format...")
            
            if transcript.utterances:
                with open(self.subtitles_path, "w", encoding="utf-8") as f:
                    for i, utterance in enumerate(transcript.utterances):
                        # SRT index
                        f.write(f"{i+1}\n")
                        
                        # Format timestamps (convert to SRT format)
                        start_ms = utterance.start
                        end_ms = utterance.end
                        
                        start_str = self._format_timestamp_ms(start_ms)
                        end_str = self._format_timestamp_ms(end_ms)
                        
                        f.write(f"{start_str} --> {end_str}\n")
                        
                        # Write the text
                        f.write(f"{utterance.text}\n\n")
            else:
                # If no utterances, use the words instead
                with open(self.subtitles_path, "w", encoding="utf-8") as f:
                    words = transcript.words
                    # Group words into chunks of reasonable size for subtitles
                    max_chars = 80
                    current_chunk = []
                    current_start = 0
                    current_length = 0
                    chunk_index = 1
                    
                    for word in words:
                        if current_length == 0:  # First word in chunk
                            current_start = word.start
                            
                        current_chunk.append(word)
                        current_length += len(word.text) + 1  # +1 for space
                        
                        # If we've reached a reasonable chunk size, write it
                        if current_length >= max_chars or word == words[-1]:
                            chunk_text = " ".join(w.text for w in current_chunk)
                            chunk_end = word.end
                            
                            # Write SRT entry
                            f.write(f"{chunk_index}\n")
                            f.write(f"{self._format_timestamp_ms(current_start)} --> {self._format_timestamp_ms(chunk_end)}\n")
                            f.write(f"{chunk_text}\n\n")
                            
                            # Reset for next chunk
                            current_chunk = []
                            current_length = 0
                            chunk_index += 1
            
            # Verify the file was created and has content
            if os.path.exists(self.subtitles_path) and os.path.getsize(self.subtitles_path) > 0:
                print(f"SRT file created successfully: {self.subtitles_path}")
                return True
            else:
                print("SRT file creation failed")
                return False
                
        except Exception as e:
            print(f"Error during AssemblyAI transcription: {e}")
            traceback.print_exc()
            return False
    
    def _format_timestamp_ms(self, ms: int) -> str:
        """
        Format milliseconds to SRT timestamp format (HH:MM:SS,mmm).
        
        Args:
            ms: Time in milliseconds
            
        Returns:
            Formatted timestamp string
        """
        seconds = ms / 1000
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"
    
    def generate_subtitles(self) -> str:
        """
        Generate subtitles from the extracted audio using Whisper or AssemblyAI.
        
        Returns:
            Path to the generated subtitles file
        """
        # Check if audio has been extracted
        if not os.path.exists(self.audio_path):
            self.extract_audio()
        
        print("Starting subtitle generation process...")
        
        success = False
        
        try:
            # Use AssemblyAI if specified
            if self.use_assemblyai:
                print("Using AssemblyAI for transcription...")
                success = self._generate_subtitles_with_assemblyai()
                
                # If AssemblyAI succeeded, return the path
                if success:
                    return self.subtitles_path
                else:
                    print("AssemblyAI transcription failed, falling back to Whisper")
            
            # If not using AssemblyAI or it failed, continue with Whisper approaches
            if not success:
                # Display GPU info if available
                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
                    total_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    used_mem = torch.cuda.memory_allocated() / (1024**3)
                    print(f"GPU: {gpu_name}, Memory: {used_mem:.2f}GB / {total_mem:.2f}GB")
                else:
                    print("No GPU detected, using CPU (this may be slow)")
                
                # Get audio file size and duration
                audio_size_mb = os.path.getsize(self.audio_path) / (1024*1024)
                audio_duration = self.video.duration
                print(f"Audio file: {audio_size_mb:.2f}MB, Duration: {audio_duration:.2f} seconds")
                
                # For very long videos, consider reducing model size
                if audio_duration > 600 and self.whisper_model_size not in ["tiny", "base"]:
                    print(f"Long video detected ({audio_duration:.2f}s), switching to 'base' model for better reliability")
                    self.whisper_model_size = "base"
                    self.whisper_model = None  # Force reload
                
                # Try multiple Whisper approaches in sequence
                print("Attempt 1: Using Whisper Python API...")
                success = self._generate_subtitles_with_api()
                
                # If that failed, try with a smaller model
                if not success and self.whisper_model_size != "tiny":
                    print("Attempt 2: Trying with smaller 'tiny' model...")
                    prev_size = self.whisper_model_size
                    self.whisper_model_size = "tiny"
                    self.whisper_model = None  # Force reload
                    success = self._generate_subtitles_with_api()
                    if not success:
                        self.whisper_model_size = prev_size  # Restore previous model size
                
                # If API approaches failed, try command line version as fallback
                if not success:
                    print("Attempt 3: Trying command line alternative...")
                    success = self._direct_transcribe_with_command_line()
                
                # As a last resort, try using an alternative algorithm
                if not success:
                    print("Attempt 4: Trying alternative algorithm with shorter segments...")
                    success = self._generate_chunked_subtitles()
            
            # Check if we got valid subtitles
            if os.path.exists(self.subtitles_path):
                with open(self.subtitles_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if len(content) > 50 and not content.startswith("1\n00:00:00,000 --> 00:00:05,000\nError generating"):
                    print(f"Successfully generated subtitles ({len(content)} bytes)")
                    return self.subtitles_path
                else:
                    print(f"Generated subtitles file appears invalid: {content[:100]}...")
                    # Continue to fallback
            
            # If all attempts failed, use manual creation as last resort
            if not success:
                return self._create_basic_subtitles()
            
            return self.subtitles_path
            
        except Exception as e:
            print(f"Error during subtitle generation: {e}")
            traceback.print_exc()
            return self._create_basic_subtitles()
    
    def _generate_chunked_subtitles(self) -> bool:
        """
        Alternative approach: break audio into smaller chunks and transcribe each separately.
        This can work better for longer videos or with limited memory.
        
        Returns:
            True if successful, False if it failed
        """
        try:
            print("Attempting chunked transcription...")
            
            # Load audio using pydub
            audio = AudioSegment.from_file(self.audio_path)
            duration_ms = len(audio)
            duration_sec = duration_ms / 1000
            
            # Define chunk size (30 seconds seems to work well)
            chunk_size_ms = 30 * 1000
            
            # Create temp directory for chunks
            chunks_dir = os.path.join(self.output_dir, "chunks")
            os.makedirs(chunks_dir, exist_ok=True)
            
            # Split audio into chunks
            chunks = []
            for i in range(0, len(audio), chunk_size_ms):
                chunk = audio[i:min(i + chunk_size_ms, len(audio))]
                chunk_path = os.path.join(chunks_dir, f"chunk_{i//chunk_size_ms}.wav")
                chunk.export(chunk_path, format="wav")
                chunks.append({
                    "path": chunk_path,
                    "start_ms": i,
                    "end_ms": min(i + chunk_size_ms, len(audio))
                })
            
            print(f"Split audio into {len(chunks)} chunks")
            
            # Load the smallest model
            self.whisper_model_size = "tiny"
            model = whisper.load_model("tiny")
            
            # Process each chunk
            all_segments = []
            
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)}...")
                
                try:
                    # Load audio data directly
                    chunk_audio = self._load_audio_for_whisper(chunk["path"])
                    if chunk_audio is None:
                        print(f"Failed to load chunk {i+1} audio data, skipping")
                        continue
                        
                    # Transcribe this chunk
                    result = model.transcribe(
                        chunk_audio,
                        language="en"
                    )
                    
                    # Adjust timestamps to account for chunk position
                    offset_ms = chunk["start_ms"]
                    offset_sec = offset_ms / 1000
                    
                    if "segments" in result:
                        for segment in result["segments"]:
                            # Add offset to start and end times
                            segment["start"] += offset_sec
                            segment["end"] += offset_sec
                            all_segments.append(segment)
                    elif "text" in result and result["text"]:
                        # Create a single segment if no segments are returned
                        segment = {
                            "start": offset_sec,
                            "end": offset_sec + (chunk["end_ms"] - chunk["start_ms"]) / 1000,
                            "text": result["text"]
                        }
                        all_segments.append(segment)
                    
                except Exception as e:
                    print(f"Error processing chunk {i}: {e}")
                    # Continue with next chunk even if this one fails
            
            # If we got some segments, write them to SRT
            if all_segments:
                # Sort segments by start time
                all_segments.sort(key=lambda x: x["start"])
                
                # Write to SRT file
                with open(self.subtitles_path, "w", encoding="utf-8") as f:
                    self._write_simple_srt(all_segments, f)
                
                # Verify file has content
                if os.path.getsize(self.subtitles_path) > 50:
                    print(f"Successfully generated subtitles from {len(all_segments)} segments")
                    return True
            
            print("Chunked transcription failed to produce usable subtitles")
            return False
            
        except Exception as e:
            print(f"Error in chunked transcription: {e}")
            return False
    
    def _load_audio_for_whisper(self, audio_path):
        """
        Load audio file directly without using ffmpeg, which is a common source of errors.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Numpy array of audio data ready for Whisper processing
        """
        try:
            print(f"Loading audio file directly: {audio_path}")
            
            # Use pydub to load the audio file
            audio = AudioSegment.from_file(audio_path)
            
            # Convert to the format Whisper expects (mono, 16kHz)
            audio = audio.set_frame_rate(16000).set_channels(1)
            
            # Convert to numpy array of float32 values in range [-1, 1]
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / (2**15 if audio.sample_width == 2 else 2**31)
            
            print(f"Audio loaded successfully: {len(samples)} samples, {audio.frame_rate}Hz")
            return samples
            
        except Exception as e:
            print(f"Error loading audio directly: {e}")
            traceback.print_exc()
            return None
            
    def _generate_subtitles_with_api(self) -> bool:
        """
        Generate subtitles using the Whisper Python API.
        
        Returns:
            True if successful, False if it failed
        """
        try:
            # Load the whisper model - simplified approach
            print(f"Loading {self.whisper_model_size} model...")
            model = whisper.load_model(self.whisper_model_size)
            print(f"Model loaded successfully")
            
            # Load audio directly without using ffmpeg
            audio_data = self._load_audio_for_whisper(self.audio_path)
            if audio_data is None:
                print("Failed to load audio data")
                return False
            
            # Simple transcription approach
            print(f"Transcribing audio with {self.whisper_model_size} model...")
            result = model.transcribe(audio_data, language="en")
            
            # Check if result contains text
            if not result or "text" not in result or not result["text"]:
                print("Warning: Transcription returned empty text")
                return False
                
            # Convert the result to SRT format
            print("Converting transcription to SRT format...")
            
            # Create SRT file from segments
            if "segments" in result and result["segments"]:
                with open(self.subtitles_path, "w", encoding="utf-8") as f:
                    self._write_simple_srt(result["segments"], f)
            else:
                # If no segments, create a single segment for the entire transcription
                with open(self.subtitles_path, "w", encoding="utf-8") as f:
                    f.write("1\n")
                    f.write("00:00:00,000 --> {:02d}:{:02d}:{:02d},{:03d}\n".format(
                        int(self.video.duration // 3600),
                        int((self.video.duration % 3600) // 60),
                        int(self.video.duration % 60),
                        int((self.video.duration % 1) * 1000)
                    ))
                    f.write(f"{result['text']}\n\n")
            
            # Verify the subtitle file has proper content
            with open(self.subtitles_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content.strip()) < 50:
                    print(f"Warning: Generated subtitles are very short ({len(content.strip())} bytes)")
                    return False
            
            print(f"Subtitles written to {self.subtitles_path}")
            return True
            
        except Exception as e:
            print(f"Error during Whisper transcription: {e}")
            traceback.print_exc()
            return False
    
    def _create_basic_subtitles(self) -> str:
        """
        Create basic subtitles with a single segment as a fallback.
        
        Returns:
            Path to the subtitle file
        """
        print("Creating basic subtitles as fallback...")
        
        # Get video info for duration
        video_info = self.get_video_info()
        duration = video_info["duration"]
        
        # Create a simple SRT file with a single segment
        with open(self.subtitles_path, "w", encoding="utf-8") as f:
            f.write("1\n")
            f.write("00:00:00,000 --> {:02d}:{:02d}:{:02d},{:03d}\n".format(
                int(duration // 3600),
                int((duration % 3600) // 60),
                int(duration % 60),
                int((duration % 1) * 1000)
            ))
            f.write("[Generated subtitles unavailable - please try with a different model size]")
        
        print("Basic subtitles created as fallback")
        return self.subtitles_path
    
    def _write_srt(self, segments: List[Dict[str, Any]], file) -> None:
        """
        Write segments to an SRT file.
        
        Args:
            segments: List of segments from Whisper transcription
            file: File object to write to
        """
        for i, segment in enumerate(segments):
            # Write segment index
            file.write(f"{i+1}\n")
            
            # Write timestamp
            start_time = self._format_timestamp(segment["start"])
            end_time = self._format_timestamp(segment["end"])
            file.write(f"{start_time} --> {end_time}\n")
            
            # Write text
            file.write(f"{segment['text'].strip()}\n\n")
    
    def _write_simple_srt(self, segments: List[Dict[str, Any]], file) -> None:
        """
        Write segments to an SRT file without word-level timestamps.
        Used as a fallback for tiny model.
        
        Args:
            segments: List of segments from Whisper transcription
            file: File object to write to
        """
        for i, segment in enumerate(segments):
            # Write segment index
            file.write(f"{i+1}\n")
            
            # Write timestamp
            start_time = self._format_timestamp(segment["start"])
            end_time = self._format_timestamp(segment["end"])
            file.write(f"{start_time} --> {end_time}\n")
            
            # Write text
            file.write(f"{segment['text'].strip()}\n\n")
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Format time in seconds to SRT timestamp format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
        
        Returns:
            Formatted timestamp string
        """
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"
    
    def clean_audio(self) -> str:
        """
        Clean the audio by removing filler words and sounds.
        
        Returns:
            Path to the cleaned audio file
        """
        # Check if audio has been extracted
        if not os.path.exists(self.audio_path):
            self.extract_audio()
        
        # Load the audio
        audio = AudioSegment.from_file(self.audio_path)
        
        # Load the subtitles if they exist, otherwise generate them
        if not os.path.exists(self.subtitles_path):
            self.generate_subtitles()
        
        # Parse the subtitles to identify filler words
        filler_word_timestamps = self._find_filler_words_in_subtitles()
        
        # Remove the filler words from audio
        cleaned_audio = self._remove_segments(audio, filler_word_timestamps)
        
        # Export the cleaned audio
        cleaned_audio.export(self.cleaned_audio_path, format="wav")
        
        return self.cleaned_audio_path
    
    def _find_filler_words_in_subtitles(self) -> List[Tuple[float, float]]:
        """
        Find timestamps of filler words in the subtitles.
        
        Returns:
            List of (start_time, end_time) tuples for filler words
        """
        filler_timestamps = []
        
        # If using tiny model, might not have word timestamps
        if self.whisper_model_size == "tiny":
            print("Using tiny model - word-level filler word removal not available")
            return []
        
        try:
            # Load the whisper model if not already loaded
            self._load_whisper_model()
            
            # Set up options including word timestamps
            options = {
                "language": "en", 
                "word_timestamps": True,
                "fp16": False
            }
            
            # Transcribe with word timestamps
            result = self.whisper_model.transcribe(
                self.audio_path, 
                **options
            )
            
            # Extract filler words with their timestamps
            for segment in result["segments"]:
                if "words" not in segment:
                    print("Warning: No word timestamps found in segment")
                    continue
                    
                for word_info in segment.get("words", []):
                    word = word_info["word"].lower().strip()
                    
                    # Check if word is a filler word
                    if any(filler in word for filler in self.filler_words):
                        filler_timestamps.append((word_info["start"], word_info["end"]))
        
        except Exception as e:
            print(f"Error finding filler words: {e}")
            # Return empty list if there's an error
        
        print(f"Found {len(filler_timestamps)} filler words to remove")
        return filler_timestamps
    
    def _remove_segments(self, audio: AudioSegment, segments: List[Tuple[float, float]]) -> AudioSegment:
        """
        Remove specified segments from an audio file.
        
        Args:
            audio: The AudioSegment object
            segments: List of (start_time, end_time) tuples to remove
        
        Returns:
            Modified AudioSegment with segments removed
        """
        if not segments:
            return audio
        
        # Sort segments by start time
        segments.sort(key=lambda x: x[0])
        
        # Merge overlapping segments
        merged_segments = []
        current_start, current_end = segments[0]
        
        for start, end in segments[1:]:
            if start <= current_end:
                # Segments overlap, merge them
                current_end = max(current_end, end)
            else:
                # No overlap, add the current segment and start a new one
                merged_segments.append((current_start, current_end))
                current_start, current_end = start, end
        
        # Add the last segment
        merged_segments.append((current_start, current_end))
        
        # Create a new audio by keeping the non-filler parts
        cleaned_audio = AudioSegment.empty()
        last_end = 0
        
        for start, end in merged_segments:
            # Convert seconds to milliseconds
            start_ms = int(start * 1000)
            end_ms = int(end * 1000)
            
            # Add the audio before this filler
            if start_ms > last_end:
                cleaned_audio += audio[last_end:start_ms]
            
            # Skip the filler word
            last_end = end_ms
        
        # Add the remaining audio after the last filler
        if last_end < len(audio):
            cleaned_audio += audio[last_end:]
        
        return cleaned_audio
    
    def create_final_video(self) -> str:
        """
        Create the final video with cleaned audio and subtitles.
        
        Returns:
            Path to the final video
        """
        try:
            print(f"Creating final video with subtitles from {self.subtitles_path}")
            print(f"Using cleaned audio from {self.cleaned_audio_path}")
            
            # Check if we have all required files
            if not os.path.exists(self.cleaned_audio_path):
                print("Clean audio file not found, extracting audio...")
                self.clean_audio()
            
            if not os.path.exists(self.subtitles_path):
                print("Subtitle file not found, generating subtitles...")
                self.generate_subtitles()
            
            # Create intermediate video with clean audio
            print("Creating video with clean audio...")
            video_with_clean_audio = os.path.join(self.output_dir, "video_with_clean_audio.mp4")
            
            # Load the original video and replace its audio
            video = VideoFileClip(self.video_path)
            audio = AudioFileClip(self.cleaned_audio_path)
            
            # Set the cleaned audio to the video
            video = video.set_audio(audio)
            
            # Write intermediate video with clean audio
            video.write_videofile(
                video_with_clean_audio,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.output_dir, "temp_audio.m4a"),
                remove_temp=True
            )
            
            # Close the clips to avoid memory issues
            video.close()
            audio.close()
            
            # Try two different approaches to add subtitles
            try:
                # First approach: Use our subtitle clip method
                print("Attempting subtitle overlay with MoviePy...")
                
                # Load the intermediate video
                video = VideoFileClip(video_with_clean_audio)
                print(f"Video dimensions: {video.w}x{video.h}, duration: {video.duration:.2f}s")
                
                # Create subtitle clips
                subtitles = self._create_subtitle_clips(video.duration)
                print(f"Created {len(subtitles)} subtitle clips")
                
                if subtitles:
                    # Debug information
                    for i, clip in enumerate(subtitles[:3]):  # Show info for first 3 clips
                        print(f"Subtitle {i+1}: position={clip.pos}, size={clip.w}x{clip.h}, start={clip.start}s, end={clip.end}s")
                    
                    # Write the composite video file with subtitles
                    print("Creating composite video with subtitles")
                    
                    # Use explicit composition to ensure clips are properly layered
                    # The video is the base layer, subtitles are overlaid on top
                    final_clip = CompositeVideoClip(
                        [video] + subtitles,
                        size=(video.w, video.h)
                    )
                    
                    # Ensure the final clip has the same audio as the intermediate video
                    final_clip = final_clip.set_audio(video.audio)
                    
                    # Ensure final clip has same duration as original
                    final_clip = final_clip.set_duration(video.duration)
                    
                    # Write the final video file
                    print(f"Writing final video to {self.final_video_path}")
                    final_clip.write_videofile(
                        self.final_video_path,
                        codec='libx264', 
                        audio_codec='aac',
                        temp_audiofile=os.path.join(self.output_dir, "temp_audio_final.m4a"),
                        remove_temp=True,
                        verbose=False  # Reduce output noise
                    )
                    
                    # Close the clips
                    final_clip.close()
                    video.close()
                    
                    print("Final video with subtitles created successfully!")
                    return self.final_video_path
                else:
                    print("No subtitle clips created, trying alternative method...")
                    video.close()
                    raise Exception("No subtitle clips could be created")
                    
            except Exception as e:
                print(f"Error with MoviePy subtitle rendering: {e}")
                traceback.print_exc()
                print("Using fallback approach: direct copy with clean audio only")
                
                # Fallback: Just use the video with clean audio
                import shutil
                shutil.copy(video_with_clean_audio, self.final_video_path)
                print(f"Created final video with clean audio (no subtitles) at {self.final_video_path}")
                return self.final_video_path
            
        except Exception as e:
            print(f"Error creating final video: {e}")
            traceback.print_exc()
            
            # If we have a video with clean audio, return that as fallback
            if 'video_with_clean_audio' in locals() and os.path.exists(video_with_clean_audio):
                print("Returning video with clean audio as fallback")
                return video_with_clean_audio
            
            # Otherwise return original video as last resort
            return self.video_path
    
    def _create_subtitle_clips(self, video_duration: float) -> List[TextClip]:
        """
        Create TextClip objects for each subtitle segment.
        
        Args:
            video_duration: Duration of the video in seconds
        
        Returns:
            List of TextClip objects representing subtitles
        """
        subtitle_clips = []
        
        try:
            print(f"Reading subtitles from: {self.subtitles_path}")
            
            # Check if file exists
            if not os.path.exists(self.subtitles_path):
                print(f"ERROR: Subtitle file not found: {self.subtitles_path}")
                return []
            
            # Parse the SRT file
            with open(self.subtitles_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                # If subtitles file is empty, return empty list
                print("ERROR: Subtitle file is empty")
                return []
            
            # Check if this is a placeholder subtitle
            if "[Generated subtitles unavailable" in content:
                print("WARNING: Using placeholder subtitles")
            
            # Split into subtitle blocks
            blocks = content.strip().split('\n\n')
            print(f"Found {len(blocks)} subtitle blocks")
            
            # Create subtitle clips for each block
            for i, block in enumerate(blocks):
                lines = block.split('\n')
                if len(lines) >= 3:  # Valid subtitle block
                    try:
                        # Parse the timestamp line
                        timestamp_line = lines[1]
                        start_time, end_time = self._parse_srt_timestamps(timestamp_line)
                        
                        # Get the text content (could be multiple lines)
                        text = ' '.join(lines[2:])
                        
                        print(f"Creating subtitle clip {i+1}: [{start_time:.2f} -> {end_time:.2f}] '{text[:30]}...'")
                        
                        # If text is too long, preprocess it with manual line breaks
                        max_chars_per_line = 50  # Reasonable number of characters per line
                        if len(text) > max_chars_per_line:
                            text = self._add_line_breaks(text, max_chars_per_line)
                            print(f"Split long text into multiple lines")
                            
                        # Create the TextClip using the best available approach
                        txt_clip = self._create_best_text_clip(text, start_time, end_time)
                        subtitle_clips.append(txt_clip)
                    except Exception as block_error:
                        print(f"Error processing subtitle block {i+1}: {block_error}")
                        traceback.print_exc()
                        continue
                else:
                    print(f"Warning: Invalid subtitle block format (block {i+1}): {block}")
            
            print(f"Created {len(subtitle_clips)} subtitle clips successfully")
            
        except Exception as e:
            print(f"Error creating subtitle clips: {e}")
            traceback.print_exc()
            # Return empty list if there's an error
        
        return subtitle_clips
        
    def _add_line_breaks(self, text, max_chars_per_line):
        """
        Add line breaks to text to ensure each line is not too long.
        
        Args:
            text: Text to process
            max_chars_per_line: Maximum characters per line
            
        Returns:
            Text with added line breaks
        """
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            # Check if adding this word would exceed the line length
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length > max_chars_per_line and current_line:
                # Line would be too long, finish current line
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                # Add word to current line
                current_line.append(word)
                current_length += word_length
        
        # Add the last line if not empty
        if current_line:
            lines.append(' '.join(current_line))
        
        # Join lines with newlines
        return '\n'.join(lines)
    
    def _create_best_text_clip(self, text, start_time, end_time):
        """
        Create the best possible text clip using multiple approaches.
        
        Args:
            text: Text to display
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            A text clip
        """
        try:
            # Method 1: Standard TextClip with explicit line breaks
            txt_clip = TextClip(
                text,
                fontsize=24,
                color='white', 
                bg_color='black',
                size=(self.video.w * 0.9, None),  # 90% of video width
                method='caption',
                align='center'
            )
            
            # Calculate position for bottom of the screen with padding
            bottom_position = (self.video.h - txt_clip.h - 50)  # 50px padding from bottom
            
            # Set position and timing - use explicit y position
            txt_clip = txt_clip.set_position(('center', bottom_position)).set_start(start_time).set_end(end_time)
            print(f"Positioned subtitle at y={bottom_position} (text height: {txt_clip.h}px)")
            return txt_clip
            
        except Exception as e1:
            print(f"Standard TextClip failed: {e1}, trying simple method")
            
            try:
                # Method 2: Simple TextClip
                txt_clip = TextClip(
                    text,
                    fontsize=20,
                    color='white',
                    bg_color='black',
                    method='label'
                )
                
                # Set position and timing - use explicit bottom position
                bottom_position = self.video.h - txt_clip.h - 40  # 40px padding from bottom
                txt_clip = txt_clip.set_position(('center', bottom_position)).set_start(start_time).set_end(end_time)
                print(f"Positioned subtitle at y={bottom_position} (simple method)")
                return txt_clip
                
            except Exception as e2:
                print(f"All TextClip methods failed: {e2}")
                print("Creating subtitle manually with PIL...")
                
                # Method 3: Use PIL directly
                txt_clip = self._create_subtitle_with_pil(
                    text, 
                    self.video.w, 
                    self.video.h,  # Pass video height for proper positioning
                    start_time, 
                    end_time
                )
                return txt_clip
                
    def _create_subtitle_with_pil(self, text, width, height, start_time, end_time):
        """
        Create a subtitle clip using PIL directly instead of TextClip.
        This is a fallback method when TextClip fails.
        
        Args:
            text: Text to display
            width: Width of the video
            height: Height of the video
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            A clip created from a PIL Image
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            from moviepy.video.VideoClip import ImageClip
            
            # Find a suitable font
            font_size = 24
            try:
                # Try to use a system font
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                try:
                    # Try default
                    font = ImageFont.truetype(ImageFont.getdefault().name, font_size)
                except Exception:
                    # Use default fallback
                    font = ImageFont.load_default()
            
            # Calculate maximum width for text 
            max_text_width = int(width * 0.85)  # Use 85% of video width
            
            # Text wrapping function - split text into lines that fit within max_width
            def wrap_text(text, font, max_width):
                lines = []
                words = text.split()
                current_line = []
                
                for word in words:
                    # Add word to current line
                    test_line = ' '.join(current_line + [word])
                    test_width = font.getlength(test_line) if hasattr(font, 'getlength') else draw.textlength(test_line, font)
                    
                    if test_width <= max_width:
                        # Word fits, add it to current line
                        current_line.append(word)
                    else:
                        # Line is full, save it and start a new line with this word
                        if current_line:  # Only add non-empty lines
                            lines.append(' '.join(current_line))
                            current_line = [word]
                        else:
                            # Word itself is too long, needs to be broken
                            lines.append(word)
                
                # Add the last line if not empty
                if current_line:
                    lines.append(' '.join(current_line))
                
                return lines
            
            # Create a temporary drawing object to measure text
            temp_img = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(temp_img)
            
            # Wrap the text into multiple lines
            wrapped_lines = wrap_text(text, font, max_text_width)
            
            # Calculate required height for all lines
            line_height = font_size + 4  # Add a small padding
            text_height = len(wrapped_lines) * line_height
            
            # Create image with appropriate dimensions - full-sized transparent
            # This allows proper positioning at the bottom
            img = Image.new('RGBA', (width, height), (0, 0, 0, 0))  # Fully transparent
            draw = ImageDraw.Draw(img)
            
            # Calculate the position at the bottom of the frame with padding
            bottom_padding = 40  # Pixels from bottom
            y_start = height - text_height - bottom_padding
            
            # Create the text background
            bg_padding = 10  # Padding around text
            bg_rect = [
                0,  # Left
                y_start - bg_padding,  # Top
                width,  # Right
                y_start + text_height + bg_padding  # Bottom
            ]
            
            # Draw semi-transparent black background for text
            draw.rectangle(bg_rect, fill=(0, 0, 0, 180))
            
            # Draw each line of text centered horizontally
            y_pos = y_start  # Start position
            for line in wrapped_lines:
                # Calculate horizontal position to center this line
                line_width = font.getlength(line) if hasattr(font, 'getlength') else draw.textlength(line, font)
                x_pos = (width - line_width) // 2
                
                # Draw text with a slight shadow for better readability
                # Draw shadow
                draw.text((x_pos+2, y_pos+2), line, font=font, fill=(0, 0, 0, 255))
                # Draw text
                draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255, 255))
                
                # Move to next line
                y_pos += line_height
            
            # Create a clip from this image
            clip = ImageClip(np.array(img), duration=end_time - start_time)
            print(f"Created PIL subtitle, positioned at y={y_start}")
            return clip
            
        except Exception as e:
            print(f"Error creating PIL subtitle: {e}")
            traceback.print_exc()
            # Return an empty clip as fallback
            from moviepy.video.VideoClip import ColorClip
            return ColorClip(size=(width, 40), color=(0, 0, 0), duration=end_time - start_time)
    
    def _parse_srt_timestamps(self, timestamp_line: str) -> Tuple[float, float]:
        """
        Parse SRT timestamp line to get start and end times in seconds.
        
        Args:
            timestamp_line: Timestamp line from SRT file
        
        Returns:
            Tuple of (start_time, end_time) in seconds
        """
        # Split the timestamp line
        start_str, end_str = timestamp_line.split(' --> ')
        
        # Parse start and end times
        start_time = self._srt_timestamp_to_seconds(start_str)
        end_time = self._srt_timestamp_to_seconds(end_str)
        
        return start_time, end_time
    
    def _srt_timestamp_to_seconds(self, timestamp: str) -> float:
        """
        Convert SRT timestamp to seconds.
        
        Args:
            timestamp: SRT timestamp (HH:MM:SS,mmm)
        
        Returns:
            Time in seconds
        """
        # Replace comma with period for milliseconds
        timestamp = timestamp.replace(',', '.')
        
        # Split by colons
        h, m, s = timestamp.split(':')
        
        # Convert to seconds
        return int(h) * 3600 + int(m) * 60 + float(s)
    
    def cleanup(self) -> None:
        """Clean up temporary files."""
        try:
            self.video.close()
            shutil.rmtree(self.output_dir)
        except Exception as e:
            print(f"Error during cleanup: {e}") 