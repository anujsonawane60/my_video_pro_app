import os
import tempfile
import subprocess
import re
import shutil
import traceback
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import whisper
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_nonsilent
import torch
import assemblyai as aai  # Import AssemblyAI
import noisereduce as nr  # Import noise reduction library
import librosa  # Import librosa for audio processing
import webrtcvad  # Import WebRTC Voice Activity Detection
import pysrt  # Import pysrt for subtitle handling
import speech_recognition as sr

class VideoProcessor:
    """
    A class for processing video files, extracting audio, generating subtitles,
    cleaning audio, and creating a final video with subtitles.
    """
    
    def __init__(self, video_path: str, whisper_model_size: str = "base", use_assemblyai: bool = False, 
                 assemblyai_api_key: str = None, debug_mode: bool = False, language: str = "en"):
        """
        Initialize the VideoProcessor with a video file.
        
        Args:
            video_path: Path to the video file
            whisper_model_size: Size of the Whisper model to use ("tiny", "base", "small", "medium")
            use_assemblyai: Whether to use AssemblyAI instead of Whisper
            assemblyai_api_key: API key for AssemblyAI (required if use_assemblyai is True)
            debug_mode: Whether to enable detailed debug logging
            language: Language code for transcription (e.g., "en" for English, "mr" for Marathi)
        """
        self.video_path = video_path
        self.output_dir = self._create_output_dir()
        self.audio_path = os.path.join(self.output_dir, "extracted_audio.wav")
        self.subtitles_path = os.path.join(self.output_dir, "subtitles.srt")
        self.cleaned_audio_path = os.path.join(self.output_dir, "cleaned_audio.wav")
        self.noise_reduced_audio_path = os.path.join(self.output_dir, "noise_reduced_audio.wav")
        self.vad_cleaned_audio_path = os.path.join(self.output_dir, "vad_cleaned_audio.wav")
        self.final_video_path = os.path.join(self.output_dir, "final_video.mp4")
        
        # Transcription settings
        self.use_assemblyai = use_assemblyai
        self.assemblyai_api_key = assemblyai_api_key
        self.language = language
        
        # Whisper model parameters
        self.whisper_model_size = whisper_model_size
        self.whisper_model = None
        
        # Audio cleaning settings
        self.noise_reduction_enabled = True
        self.vad_cleaning_enabled = True
        self.vad_aggressiveness = 1  # Range 0-3, higher = more aggressive
        self.noise_reduction_sensitivity = 0.2  # Default sensitivity
        
        # Debug and logging settings
        self.debug_mode = debug_mode
        self.verbose = debug_mode
        
        # Subtitle settings
        self.subtitle_font_size = 24
        self.subtitle_color = "white"
        self.subtitle_bg_opacity = 80  # 0-100
        self.use_direct_ffmpeg = True
        self.subtitle_font = "Arial"
        
        # Load the video file
        self.video = VideoFileClip(video_path)
        
        # Filler words to remove based on language
        self.filler_words = ["um", "uh", "hmm", "uhh", "err", "ah", "like", "you know"]
        
        # Add Marathi filler words if language is Marathi
        if self.language == "mr":
            # Common Marathi filler words and sounds
            self.filler_words = ["अं", "हं", "म्हणजे", "असं", "तसं", "आता", "बघा", "ते", "असेल तर", "आणि", "तर", "नंतर"]
            
            # Use larger model for Marathi if not specified otherwise
            if self.whisper_model_size == "base" or self.whisper_model_size == "tiny":
                print("Using 'small' model for better Marathi transcription accuracy")
                self.whisper_model_size = "small"
        
        # Log initialization
        if self.debug_mode:
            print(f"VideoProcessor initialized with:")
            print(f"  Video path: {video_path}")
            print(f"  Output directory: {self.output_dir}")
            print(f"  Whisper model: {whisper_model_size}")
            print(f"  Use AssemblyAI: {use_assemblyai}")
            print(f"  Language: {language}")
            print(f"  Video duration: {self.video.duration} seconds")
            print(f"  Video resolution: {self.video.size}")
            print(f"  Audio track present: {self.video.audio is not None}")
            print(f"  Debug mode: {debug_mode}")
    
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
                    "--language", self.language,
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
                language_code=self.language         # Use specified language
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
            print("Audio not yet extracted, extracting now...")
            try:
                self.extract_audio()
            except Exception as e:
                print(f"Error extracting audio: {e}")
                traceback.print_exc()
                return self._create_basic_subtitles()
        
        if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) < 100:
            print(f"Audio file invalid or too small: {self.audio_path}")
            return self._create_basic_subtitles()
        
        print("Starting subtitle generation process...")
        
        success = False
        
        try:
            # Check if language is Marathi and use specialized approach
            if self.language == "mr":
                print("Marathi language detected, using specialized Marathi transcription...")
                
                # For Marathi, try multiple approaches
                print("Attempt 1: Using optimized chunking approach for Marathi")
                success = self._transcribe_marathi_with_chunking()
                
                # Check if we got successful Marathi transcription
                if success:
                    try:
                        with open(self.subtitles_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Look for Marathi characters
                            if len(content) > 100 and any(ord(c) > 2304 and ord(c) < 2432 for c in content):
                                print("Marathi characters detected in subtitles, returning result")
                                return self.subtitles_path
                            else:
                                print("No Marathi characters detected, trying another approach")
                                success = False
                    except Exception as e:
                        print(f"Error checking Marathi content: {e}")
                
                # If first approach failed, try command line approach
                if not success:
                    print("Attempt 2: Using command line approach for Marathi")
                    success = self._direct_marathi_transcribe_with_command_line()
                    
                    # Check if command line approach worked
                    if success:
                        try:
                            with open(self.subtitles_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                # Look for Marathi characters
                                if len(content) > 100 and any(ord(c) > 2304 and ord(c) < 2432 for c in content):
                                    print("Marathi characters detected in subtitles from command line approach, returning result")
                                    return self.subtitles_path
                                else:
                                    print("No Marathi characters detected, trying another approach")
                                    success = False
                        except Exception as e:
                            print(f"Error checking Marathi content: {e}")
                
                # If above approaches failed, try standard Whisper API with Marathi settings
                if not success:
                    print("Attempt 3: Using standard Whisper API with Marathi settings")
                    
                    # Ensure we try with a good model for Marathi
                    if self.whisper_model_size in ["tiny", "base"]:
                        print("Using 'small' model for better accuracy with Marathi")
                        prev_size = self.whisper_model_size
                        self.whisper_model_size = "small"
                        self.whisper_model = None  # Force reload
                    
                    success = self._generate_subtitles_with_api()
                    
                    # If we got successful transcription, check for Marathi content
                    if success:
                        try:
                            with open(self.subtitles_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                # Look for Marathi characters
                                if len(content) > 100 and any(ord(c) > 2304 and ord(c) < 2432 for c in content):
                                    print("Marathi characters detected in subtitles from standard API, returning result")
                                    return self.subtitles_path
                        except Exception as e:
                            print(f"Error checking Marathi content: {e}")
                
                # If all Marathi-specific approaches failed, continue with standard approaches
                if not success:
                    print("All Marathi-specific approaches failed, trying standard transcription...")
            
            # Use AssemblyAI if specified (but not for Marathi)
            if self.use_assemblyai and self.language != "mr":
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
                        language=self.language
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
            result = model.transcribe(audio_data, language=self.language)
            
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
        Clean the audio by applying noise reduction and removing filler words and sounds.
        
        Returns:
            Path to the cleaned audio file
        """
        # Check if audio has been extracted
        if not os.path.exists(self.audio_path):
            print("Audio not extracted yet, extracting now...")
            try:
                self.extract_audio()
            except Exception as e:
                print(f"Error extracting audio: {e}")
                raise FileNotFoundError("Unable to extract audio from video. Please check the video file.")
        
        if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) < 100:
            print(f"Audio file invalid or too small: {self.audio_path}")
            raise FileNotFoundError("Invalid audio file. Please extract the audio again.")
            
        current_audio_path = self.audio_path
        
        # Apply noise reduction if enabled
        if self.noise_reduction_enabled:
            try:
                print("Applying noise reduction...")
                current_audio_path = self.reduce_noise(current_audio_path)
            except Exception as e:
                print(f"Error during noise reduction: {e}")
                # Continue with original audio if noise reduction fails
        
        cleaned_audio_path = current_audio_path
        
        # Apply filler word removal using different methods
        if self.vad_cleaning_enabled:
            try:
                print("Applying VAD-based filler removal...")
                cleaned_audio_path = self.remove_fillers_with_vad(current_audio_path)
            except Exception as e:
                print(f"Error during VAD-based filler removal: {e}")
                # Fall back to traditional filler word removal if VAD fails
                try:
                    print("Falling back to subtitle-based filler word removal...")
                    # Load the subtitles if they exist, otherwise generate them
                    if not os.path.exists(self.subtitles_path):
                        self.generate_subtitles()
                    
                    # Parse the subtitles to identify filler words
                    filler_word_timestamps = self._find_filler_words_in_subtitles()
                    
                    # Only proceed if we found some filler words
                    if filler_word_timestamps:
                        # Load the audio
                        audio = AudioSegment.from_file(current_audio_path)
                        
                        # Remove the filler words from audio
                        cleaned_audio = self._remove_segments(audio, filler_word_timestamps)
                        
                        # Export the cleaned audio
                        cleaned_audio.export(self.cleaned_audio_path, format="wav")
                        cleaned_audio_path = self.cleaned_audio_path
                except Exception as e2:
                    print(f"Error during subtitle-based filler removal: {e2}")
                    # Keep the noise-reduced audio if filler removal fails
        else:
            try:
                # Traditional subtitle-based filler word removal
                # Load the subtitles if they exist, otherwise generate them
                if not os.path.exists(self.subtitles_path):
                    self.generate_subtitles()
                
                # Parse the subtitles to identify filler words
                filler_word_timestamps = self._find_filler_words_in_subtitles()
                
                # Only proceed if we found some filler words
                if filler_word_timestamps:
                    # Load the audio
                    audio = AudioSegment.from_file(current_audio_path)
                    
                    # Remove the filler words from audio
                    cleaned_audio = self._remove_segments(audio, filler_word_timestamps)
                    
                    # Export the cleaned audio
                    cleaned_audio.export(self.cleaned_audio_path, format="wav")
                    cleaned_audio_path = self.cleaned_audio_path
            except Exception as e:
                print(f"Error during subtitle-based filler removal: {e}")
                # Keep the noise-reduced audio if filler removal fails
        
        # If no processing was done or all processing failed, copy original audio to cleaned path
        if cleaned_audio_path == self.audio_path:
            try:
                print(f"No processing done, copying original audio to {self.cleaned_audio_path}")
                import shutil
                shutil.copy2(self.audio_path, self.cleaned_audio_path)
                cleaned_audio_path = self.cleaned_audio_path
            except Exception as e:
                print(f"Error copying audio: {e}")
                # Just return the original audio path if copy fails
                return self.audio_path
        
        # Verify the cleaned audio file exists
        if not os.path.exists(cleaned_audio_path):
            print(f"Warning: Cleaned audio file not found at {cleaned_audio_path}")
            return self.audio_path
        
        print(f"Audio cleaning complete. Final output at {cleaned_audio_path}")
        return cleaned_audio_path
    
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
                "language": self.language, 
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
    
    def _load_subtitles(self, subtitle_path):
        """
        Load subtitles from SRT file using pysrt library.
        
        Args:
            subtitle_path: Path to the subtitle file
            
        Returns:
            List of subtitle objects or None if loading fails
        """
        try:
            print(f"Loading subtitles from {subtitle_path} using pysrt")
            subtitles = pysrt.open(subtitle_path, encoding='utf-8')
            print(f"Successfully loaded {len(subtitles)} subtitle items")
            return subtitles
        except Exception as e:
            print(f"Error loading subtitles with pysrt: {e}")
            traceback.print_exc()
            return None
            
    def _time_to_seconds(self, time_obj):
        """
        Convert pysrt time object to seconds.
        
        Args:
            time_obj: A pysrt time object
            
        Returns:
            Time in seconds with milliseconds
        """
        return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000

    def create_final_video(self, custom_subtitle_path=None, custom_audio_path=None) -> str:
        """
        Create a final video with selected audio and subtitles.
        
        Args:
            custom_subtitle_path: Optional path to custom subtitle file. If provided, uses this instead of the default.
            custom_audio_path: Optional path to custom audio file. If provided, uses this instead of the default.
            
        Returns:
            Path to the final video file
        """
        print("=" * 50)
        print("STARTING FINAL VIDEO CREATION")
        print("=" * 50)
        
        # Debug logging for file paths
        print(f"DEBUG - Looking for audio files:")
        print(f"DEBUG - Custom audio path provided: {custom_audio_path}")
        if custom_audio_path:
            print(f"DEBUG - Custom audio exists: {os.path.exists(custom_audio_path)}")
            if os.path.exists(custom_audio_path):
                print(f"DEBUG - Custom audio size: {os.path.getsize(custom_audio_path)} bytes")
        
        print(f"DEBUG - Cleaned audio path: {self.cleaned_audio_path}, exists: {os.path.exists(self.cleaned_audio_path)}")
        print(f"DEBUG - Original audio path: {self.audio_path}, exists: {os.path.exists(self.audio_path)}")
        print(f"DEBUG - Video path: {self.video_path}, exists: {os.path.exists(self.video_path)}")
        
        # Try to find any available audio file
        available_audio = None
        
        # First check if custom audio path was provided
        if custom_audio_path and os.path.exists(custom_audio_path) and os.path.getsize(custom_audio_path) > 0:
            available_audio = custom_audio_path
            print(f"DEBUG - Using custom audio: {available_audio}")
        # Then check the cleaned audio path
        elif os.path.exists(self.cleaned_audio_path) and os.path.getsize(self.cleaned_audio_path) > 0:
            available_audio = self.cleaned_audio_path
            print(f"DEBUG - Using cleaned audio: {available_audio}")
        # Then check the original extracted audio
        elif os.path.exists(self.audio_path) and os.path.getsize(self.audio_path) > 0:
            available_audio = self.audio_path
            print(f"DEBUG - Using original extracted audio: {available_audio}")
        # If we don't have any audio files yet, try to extract audio now
        elif os.path.exists(self.video_path):
            try:
                print("DEBUG - No audio found, attempting to extract audio now")
                self.extract_audio()
                if os.path.exists(self.audio_path) and os.path.getsize(self.audio_path) > 0:
                    available_audio = self.audio_path
                    print(f"DEBUG - Successfully extracted audio: {available_audio}")
            except Exception as e:
                print(f"DEBUG - Failed to extract audio: {e}")
        
        # If we still don't have audio, raise an error
        if not available_audio:
            print("ERROR - No audio files could be found or extracted")
            raise FileNotFoundError("No audio found. Please extract audio first.")
        
        # Which subtitle file to use - verify it exists
        subtitle_path_to_use = None
        if custom_subtitle_path and os.path.exists(custom_subtitle_path) and os.path.getsize(custom_subtitle_path) > 0:
            subtitle_path_to_use = custom_subtitle_path
            print(f"Using custom subtitle file: {subtitle_path_to_use}")
        elif os.path.exists(self.subtitles_path) and os.path.getsize(self.subtitles_path) > 0:
            subtitle_path_to_use = self.subtitles_path
            print(f"Using default subtitle file: {subtitle_path_to_use}")
        else:
            print(f"Warning: No valid subtitle file found. Video will not have subtitles.")
        
        if subtitle_path_to_use:
            # Debug: Read first few lines of subtitle file to verify content
            try:
                with open(subtitle_path_to_use, 'r', encoding='utf-8') as f:
                    content = f.read(500)  # Read first 500 chars
                    print(f"Subtitle file content preview: {content[:200]}...")
                    print(f"Subtitle file size: {os.path.getsize(subtitle_path_to_use)} bytes")
            except Exception as e:
                print(f"Error reading subtitle file: {e}")
        
        try:
            # Try using direct FFmpeg approach first - more reliable for subtitle integration
            if self.use_direct_ffmpeg and subtitle_path_to_use:
                print("Using direct FFmpeg approach for better subtitle integration")
                try:
                    output_path = os.path.join(self.output_dir, "ffmpeg_final_video.mp4")
                    
                    # Ensure subtitle file path is properly formatted for ffmpeg
                    subtitle_path_norm = os.path.normpath(subtitle_path_to_use)
                    subtitle_path_ffmpeg = subtitle_path_norm.replace('\\', '/')  # FFmpeg prefers forward slashes
                    print(f"Formatted subtitle path for FFmpeg: {subtitle_path_ffmpeg}")
                    
                    # Create FFmpeg subtitle styling options based on user preferences
                    subtitle_style = f"fontsize={self.subtitle_font_size},fontcolor={self.subtitle_color},alpha={self.subtitle_bg_opacity/100}"
                    print(f"Using subtitle style: {subtitle_style}")
                    
                    command = [
                        "ffmpeg", "-y",
                        "-i", self.video_path,     # Input video
                        "-i", available_audio,     # Input audio
                        "-map", "0:v",             # Use video from first input
                        "-map", "1:a",             # Use audio from second input
                        "-c:v", "libx264",         # Use H.264 codec for video
                        "-crf", "23",              # Quality setting
                        "-c:a", "aac",             # Convert audio to AAC
                        "-b:a", "192k",            # Audio bitrate
                        "-vf", f"subtitles={subtitle_path_ffmpeg}:force_style='{subtitle_style}'",  # Use prepared path with styling
                        "-shortest"                # Use shortest input length
                    ]
                    
                    # Add output file
                    command.append(output_path)
                    
                    # Join command for display (but don't run the joined version)
                    print(f"Running FFmpeg command: {' '.join(command)}")
                    
                    # Run the command with proper argument list
                    result = subprocess.run(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False  # Don't raise exception, we'll check manually
                    )
                    
                    # Check if command succeeded
                    if result.returncode == 0:
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                            print(f"FFmpeg successfully created video with subtitles at {output_path}")
                            # Copy to final path
                            shutil.copy2(output_path, self.final_video_path)
                        print(f"Copied FFmpeg output to final path: {self.final_video_path}")
                        
                        # Close video resources to avoid memory leaks
                        try:
                            if 'original_video' in locals():
                                original_video.close()
                            if 'audio_clip' in locals():
                                audio_clip.close()
                        except Exception as close_error:
                            print(f"Warning: Could not close video resources: {close_error}")
                            
                        return self.final_video_path
                    else:
                        print(f"FFmpeg command failed with return code {result.returncode}")
                        if result.returncode != 0:
                            print(f"Error output: {result.stderr}")
                        elif not os.path.exists(output_path):
                            print(f"Error: Output file not created: {output_path}")
                        elif os.path.getsize(output_path) < 1000000:
                            print(f"Warning: Output file size too small: {os.path.getsize(output_path)} bytes")
                        # Continue to MoviePy approach
                except Exception as e:
                    print(f"Error during FFmpeg processing: {e}")
                    # Continue to MoviePy approach
            
            print(f"Creating final video with audio from {available_audio} using MoviePy")
            
            # Load original video
            original_video = VideoFileClip(self.video_path)
            print(f"Loaded original video: {self.video_path}, duration: {original_video.duration}s")
            
            # Load the audio - make sure it's loaded as a separate file
            audio_clip = AudioFileClip(available_audio)
            print(f"Loaded audio: {available_audio}, duration: {audio_clip.duration}s")
            
            # Create video with clean audio - force replacement
            # Important: We must set_audio with copy=False to ensure audio is actually replaced
            video_with_clean_audio = original_video.set_audio(audio_clip)
            print("Set clean audio to video")
            
            # Process subtitles if available
            final_video = None
            if subtitle_path_to_use:
                print(f"Processing subtitles from {subtitle_path_to_use}")
                try:
                    # Parse the SRT file for subtitles
                    subtitles = []
                    try:
                        # Try with pysrt first
                        print(f"Attempting to load subtitles with pysrt from {subtitle_path_to_use}")
                        # Try with different encodings
                        for encoding in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']:
                            try:
                                print(f"Trying encoding: {encoding}")
                                subs = pysrt.open(subtitle_path_to_use, encoding=encoding)
                                if len(subs) > 0:
                                    print(f"Successfully loaded {len(subs)} subtitles with pysrt using {encoding} encoding")
                                    for sub in subs:
                                        start_time = self._time_to_seconds(sub.start)
                                        end_time = self._time_to_seconds(sub.end)
                                        text = sub.text.replace('\\N', '\n')
                                        subtitles.append((start_time, end_time, text))
                                    break
                            except Exception as e:
                                print(f"pysrt failed with {encoding}: {e}")
                        
                        # If pysrt didn't work, fall back to manual parsing
                        if not subtitles:
                            print("pysrt failed, using manual parsing")
                            # Try manual parsing with different encodings
                            for encoding in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']:
                                try:
                                    print(f"Manual parsing with encoding: {encoding}")
                                    with open(subtitle_path_to_use, 'r', encoding=encoding) as f:
                                        content = f.read()
                                    
                                    # Debugging: Show the content
                                    print(f"Content preview: {content[:200]}")
                                    
                                    # Parse SRT format
                                    blocks = content.split('\n\n')
                                    for block in blocks:
                                        if block.strip():
                                            lines = block.strip().split('\n')
                                            if len(lines) >= 3:
                                                try:
                                                    # Extract times
                                                    times = lines[1].split(' --> ')
                                                    start_str = times[0].strip()
                                                    end_str = times[1].strip()
                                                    
                                                    # Parse times
                                                    start_time = self._srt_timestamp_to_seconds(start_str)
                                                    end_time = self._srt_timestamp_to_seconds(end_str)
                                                    
                                                    # Get text (join all remaining lines)
                                                    text = '\n'.join(lines[2:])
                                                    
                                                    subtitles.append((start_time, end_time, text))
                                                    print(f"Parsed subtitle: {start_time}-{end_time}: {text[:30]}...")
                                                except Exception as e:
                                                    print(f"Error parsing subtitle block: {e}")
                                    
                                    if subtitles:
                                        print(f"Successfully parsed {len(subtitles)} subtitles manually")
                                        break
                                except Exception as e:
                                    print(f"Manual parsing failed with {encoding}: {e}")
                    except Exception as e:
                        print(f"Error loading subtitles: {e}")
                        traceback.print_exc()
                    
                    print(f"Parsed {len(subtitles)} subtitle entries")
                    
                    # Create subtitle clips
                    if subtitles:
                        subtitle_clips = []
                        
                        video_width, video_height = original_video.w, original_video.h
                        
                        for start_time, end_time, text in subtitles:
                            # Create subtitle with better visibility settings
                            try:
                                # Create a text clip with contrasting colors and outline for better visibility
                                # Convert background opacity (0-100) to an RGBA color string with alpha
                                bg_alpha = self.subtitle_bg_opacity / 100.0
                                bg_color = f'rgba(0,0,0,{bg_alpha})'
                                
                                txt_clip = TextClip(
                                    text, 
                                    fontsize=self.subtitle_font_size, 
                                    color=self.subtitle_color,
                                    bg_color=bg_color,
                                    # Use the font specified in settings
                                    font=self.subtitle_font,
                                    size=(video_width * 0.9, None),  # Use 90% of video width
                                    method='caption',
                                    align='center',
                                    stroke_color='black',
                                    stroke_width=1
                                )
                            except Exception as clip_error:
                                print(f"Error creating TextClip with specified settings: {clip_error}")
                                try:
                                    # First fallback with minimal font specification
                                    print("Trying fallback font rendering...")
                                    # Still try to use custom settings in fallback
                                    bg_alpha = self.subtitle_bg_opacity / 100.0
                                    bg_color = f'rgba(0,0,0,{bg_alpha})'
                                    txt_clip = TextClip(
                                        text, 
                                        fontsize=self.subtitle_font_size, 
                                        color=self.subtitle_color,
                                        bg_color=bg_color,
                                        size=(video_width * 0.9, None),
                                        method='caption',
                                        align='center'
                                    )
                                except Exception as fallback_error:
                                    print(f"Fallback font rendering failed: {fallback_error}")
                                    # Ultimate fallback with minimum settings
                                    print("Using ultimate fallback font rendering")
                                    txt_clip = TextClip(
                                        text, 
                                        fontsize=self.subtitle_font_size, 
                                        color=self.subtitle_color,
                                        size=(video_width * 0.9, None)
                                    )
                            
                            # Position at bottom of the screen with a bit of margin
                            subtitle_y_position = video_height * 0.85
                            text_position = ('center', subtitle_y_position)
                            
                            # Set timing and position
                            txt_clip = txt_clip.set_position(text_position)
                            txt_clip = txt_clip.set_start(start_time).set_duration(end_time - start_time)
                            
                            # Add to clips list
                            subtitle_clips.append(txt_clip)
                            print(f"Created subtitle clip: {text[:30]}... at position {text_position}")
                        
                        # Create composite with subtitles
                        print(f"Creating composite with {len(subtitle_clips)} subtitle clips")
                        # IMPORTANT: Make sure to use the video with clean audio as the base
                        final_video = CompositeVideoClip([video_with_clean_audio] + subtitle_clips)
                        print(f"Final video created with subtitles")
                    else:
                        print("No valid subtitles found, using video with clean audio only")
                        final_video = video_with_clean_audio
                
                except Exception as e:
                    print(f"Error processing subtitles: {e}")
                    traceback.print_exc()
                    final_video = video_with_clean_audio
            
            # If we haven't set final_video yet, use the video with clean audio
            if final_video is None:
                print("No subtitles processed, using video with clean audio only")
                final_video = video_with_clean_audio
            
            # Write the final video with parameters that maximize compatibility
            print(f"Writing final video to {self.final_video_path}")
            final_video.write_videofile(
                self.final_video_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.output_dir, "temp_audio.m4a"),
                remove_temp=True,
                fps=original_video.fps,  # Use original FPS
                threads=2,               # Use fewer threads for better stability
                ffmpeg_params=["-crf", "23", "-b:a", "192k"]  # Set quality parameters
            )
            
            # Close to free resources
            if final_video is not video_with_clean_audio:
                final_video.close()
            video_with_clean_audio.close()
            audio_clip.close()
            original_video.close()
            
            print(f"Final video created successfully at {self.final_video_path}")
            return self.final_video_path
            
        except Exception as e:
            print(f"Error creating final video: {e}")
            traceback.print_exc()
            
            # Try to return a usable video even after error
            if os.path.exists(self.final_video_path) and os.path.getsize(self.final_video_path) > 1000000:
                return self.final_video_path
            
            # If that didn't work, try a very simple approach with FFmpeg directly
            try:
                print("Attempting direct FFmpeg approach as fallback")
                output_path = os.path.join(self.output_dir, "ffmpeg_fallback_output.mp4")
                
                # Use FFmpeg to combine video with audio
                command = [
                    "ffmpeg", "-y",
                    "-i", self.video_path,  # Input video
                    "-i", available_audio,  # Input audio
                    "-map", "0:v",          # Use video from first input
                    "-map", "1:a",          # Use audio from second input
                    "-c:v", "copy",         # Copy video stream without re-encoding
                    "-c:a", "aac",          # Convert audio to AAC
                    "-shortest"             # Use shortest input length
                ]
                
                # Add subtitles in fallback method too if available
                if subtitle_path_to_use:
                    print(f"Adding subtitles in fallback method: {subtitle_path_to_use}")
                    subtitle_path_norm = os.path.normpath(subtitle_path_to_use)
                    subtitle_path_ffmpeg = subtitle_path_norm.replace('\\', '/')  # FFmpeg prefers forward slashes
                    print(f"Formatted subtitle path for FFmpeg fallback: {subtitle_path_ffmpeg}")
                    
                    # Create subtitle styling options based on user preferences
                    subtitle_style = f"fontsize={self.subtitle_font_size},fontcolor={self.subtitle_color},alpha={self.subtitle_bg_opacity/100}"
                    
                    command.extend(["-vf", f"subtitles={subtitle_path_ffmpeg}:force_style='{subtitle_style}'"])
                    # If we're adding subtitles, we can't copy the video stream
                    command[8] = "libx264"  # Replace "copy" with "libx264"
                
                # Add output file
                command.append(output_path)
                
                print(f"Running fallback command: {' '.join(command)}")
                subprocess.run(command, check=True, capture_output=True)
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
                    # Copy to final path
                    shutil.copy2(output_path, self.final_video_path)
                    return self.final_video_path
                else:
                    print("FFmpeg fallback approach failed")
                
            except Exception as e2:
                print(f"Error in FFmpeg fallback approach: {e2}")
                traceback.print_exc()
            
            # If all else fails, just copy the original video
            try:
                print("Copying original video as last resort")
                shutil.copy2(self.video_path, self.final_video_path)
                return self.final_video_path
            except Exception as e3:
                print(f"Could not copy original video: {e3}")
                # Last resort - return original video path
                return self.video_path
    
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
    
    def reduce_noise(self, audio_path: str = None) -> str:
        """
        Apply noise reduction to the audio file.
        
        Args:
            audio_path: Path to the audio file to process, or use self.audio_path if None
            
        Returns:
            Path to the noise-reduced audio file
        """
        if audio_path is None:
            audio_path = self.audio_path
            
        # Check if audio has been extracted
        if not os.path.exists(audio_path):
            self.extract_audio()
            audio_path = self.audio_path
            
        print(f"Applying noise reduction to {audio_path}")
        
        try:
            # Load the audio file using librosa
            audio, sr = librosa.load(audio_path, sr=None)
            
            # Apply noise reduction
            print("Applying noise reduction algorithm...")
            reduced_noise = nr.reduce_noise(
                y=audio, 
                sr=sr,
                stationary=True,  # Assume stationary noise (constant background)
                prop_decrease=self.noise_reduction_sensitivity
            )
            
            # Save the processed audio
            import soundfile as sf
            sf.write(self.noise_reduced_audio_path, reduced_noise, sr)
            
            print(f"Noise reduction complete. Saved to {self.noise_reduced_audio_path}")
            return self.noise_reduced_audio_path
            
        except Exception as e:
            print(f"Error during noise reduction: {e}")
            print(traceback.format_exc())
            # Return original audio path if processing fails
            return audio_path
    
    def remove_fillers_with_vad(self, audio_path: str = None) -> str:
        """
        Remove filler sounds and hesitations using Voice Activity Detection.
        This is more sophisticated than the simple filler word detection.
        
        Args:
            audio_path: Path to the audio file to process, or use self.audio_path if None
            
        Returns:
            Path to the VAD-cleaned audio file
        """
        if audio_path is None:
            audio_path = self.audio_path
            
        # Check if audio has been extracted
        if not os.path.exists(audio_path):
            self.extract_audio()
            audio_path = self.audio_path
            
        print(f"Removing fillers with VAD from {audio_path}")
        
        try:
            # Load the audio file using librosa (ensures 16kHz, which VAD requires)
            audio, sr = librosa.load(audio_path, sr=16000)
            
            # Initialize VAD
            vad = webrtcvad.Vad(self.vad_aggressiveness)
            
            # Set frame parameters
            frame_duration = 30  # ms (typical values are 10, 20, 30 ms)
            frame_size = int(sr * frame_duration / 1000)
            
            # Create frames from audio
            frames = []
            for i in range(0, len(audio) - frame_size, frame_size):
                frame = audio[i:i + frame_size]
                frames.append(frame)
                
            # Convert frames to PCM (for VAD)
            pcm_frames = []
            for frame in frames:
                # Ensure the frame is the right size
                if len(frame) == frame_size:
                    # Scale to int16 range and convert to bytes
                    pcm_frame = (frame * 32767).astype(np.int16).tobytes()
                    pcm_frames.append(pcm_frame)
            
            # Process frames to find speech segments
            speech_segments = []
            is_speech = False
            start_frame = 0
            
            # Parameters for VAD processing
            min_speech_frames = 3  # Minimum frames for a speech segment (~90ms)
            min_silence_frames = 5  # Minimum frames for a silence segment (~150ms)
            speech_padding_frames = 2  # Padding frames around speech segments
            
            # First pass - simple VAD detection
            frame_speech_status = []
            for i, frame in enumerate(pcm_frames):
                try:
                    is_frame_speech = vad.is_speech(frame, sr)
                    frame_speech_status.append(is_frame_speech)
                except:
                    # If frame processing fails, assume it's not speech
                    frame_speech_status.append(False)
            
            # Second pass - apply minimum segment durations and padding
            is_speech = False
            speech_frame_count = 0
            silence_frame_count = 0
            
            for i, is_frame_speech in enumerate(frame_speech_status):
                if is_frame_speech:
                    speech_frame_count += 1
                    silence_frame_count = 0
                    
                    if not is_speech and speech_frame_count >= min_speech_frames:
                        # Start a new speech segment
                        is_speech = True
                        # Include padding frames before, if possible
                        start_frame = max(0, i - speech_padding_frames)
                else:
                    silence_frame_count += 1
                    
                    if is_speech and silence_frame_count >= min_silence_frames:
                        # End the current speech segment
                        is_speech = False
                        end_frame = min(len(frame_speech_status), i + speech_padding_frames)
                        
                        # Convert frame indices to time
                        start_time = start_frame * frame_duration / 1000  # in seconds
                        end_time = end_frame * frame_duration / 1000  # in seconds
                        
                        speech_segments.append((start_time, end_time))
                        speech_frame_count = 0
            
            # Handle the case where audio ends during speech
            if is_speech:
                end_frame = len(frame_speech_status)
                start_time = start_frame * frame_duration / 1000
                end_time = end_frame * frame_duration / 1000
                speech_segments.append((start_time, end_time))
            
            print(f"Found {len(speech_segments)} speech segments")
            
            # Create a mask of speech regions
            audio_duration = len(audio) / sr
            mask = np.zeros(len(audio))
            
            for start_time, end_time in speech_segments:
                # Convert time to sample indices
                start_idx = int(start_time * sr)
                end_idx = int(end_time * sr)
                
                # Ensure indices are within bounds
                start_idx = max(0, start_idx)
                end_idx = min(len(audio), end_idx)
                
                # Mark this region as speech
                mask[start_idx:end_idx] = 1
            
            # Apply the mask to the audio
            audio_masked = audio * mask
            
            # Save the processed audio
            import soundfile as sf
            sf.write(self.vad_cleaned_audio_path, audio_masked, sr)
            
            print(f"VAD-based filler removal complete. Saved to {self.vad_cleaned_audio_path}")
            return self.vad_cleaned_audio_path
            
        except Exception as e:
            print(f"Error during VAD-based filler removal: {e}")
            print(traceback.format_exc())
            # Return original audio path if processing fails
            return audio_path
    
    def _transcribe_with_speech_recognition(self) -> bool:
        """
        Use SpeechRecognition library to transcribe Marathi or other languages.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"Transcribing audio using SpeechRecognition with language: {self.language}")
            
            # Check the audio length
            audio_duration = self.video.duration
            
            # For longer videos, use chunking approach for better results
            if audio_duration > 30:  # If longer than 30 seconds
                print(f"Long audio detected ({audio_duration:.2f}s), using chunking approach")
                if self.language == "mr":
                    return self._transcribe_marathi_with_chunking()
            
            # For shorter videos or if chunking failed, use the simple approach
            r = sr.Recognizer()
            with sr.AudioFile(self.audio_path) as source:
                audio = r.record(source)
            
            # Initialize segments list
            segments = []
            
            # For full audio (this would need to be chunked for long files)
            try:
                # Use whisper API from SpeechRecognition for Marathi
                text = r.recognize_whisper(audio, language=self.language)
                
                # Create a basic segment (this is simplified)
                segment = {
                    "start": 0,
                    "end": self.video.duration,
                    "text": text
                }
                segments.append(segment)
                
                # Write segments to SRT file
                with open(self.subtitles_path, 'w', encoding='utf-8') as f:
                    self._write_simple_srt(segments, f)
                
                print(f"Successfully transcribed audio to {self.subtitles_path}")
                return True
                
            except sr.UnknownValueError:
                print("Speech Recognition could not understand audio")
            except sr.RequestError as e:
                print(f"Speech Recognition error: {e}")
            
            return False
            
        except Exception as e:
            print(f"Error in SpeechRecognition transcription: {e}")
            traceback.print_exc()
            return False
    
    def _transcribe_marathi_with_chunking(self) -> bool:
        """
        Transcribe Marathi audio by splitting it into smaller chunks for better accuracy.
        Uses Whisper directly for better Marathi language support.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"Transcribing Marathi audio with improved chunking...")
            
            # Load audio using pydub
            audio = AudioSegment.from_file(self.audio_path)
            duration_ms = len(audio)
            
            # Define chunk size (30 seconds seems to work well for Marathi)
            chunk_size_ms = 30 * 1000
            
            # Create temp directory for chunks
            chunks_dir = os.path.join(self.output_dir, "marathi_chunks")
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
            
            print(f"Split audio into {len(chunks)} chunks for Marathi transcription")
            
            # Load Whisper model specifically for Marathi
            print("Loading Whisper model for Marathi transcription...")
            model_size = "small"  # Using small model for better accuracy with Marathi
            try:
                model = whisper.load_model(model_size)
            except Exception as e:
                print(f"Error loading 'small' model: {e}")
                model = whisper.load_model("base")
            
            # Process each chunk
            all_segments = []
            
            for i, chunk in enumerate(chunks):
                print(f"Processing Marathi chunk {i+1}/{len(chunks)}...")
                
                try:
                    # Load audio for Whisper
                    chunk_audio = self._load_audio_for_whisper(chunk["path"])
                    
                    # Use specific Marathi transcription settings
                    result = model.transcribe(
                        chunk_audio,
                        language="mr",
                        task="transcribe",
                        fp16=False,
                        verbose=True
                    )
                    
                    # Calculate timestamps
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
                    print(f"Error processing Marathi chunk {i+1}: {e}")
            
            # If we got some segments, write them to SRT
            if all_segments:
                # Sort segments by start time
                all_segments.sort(key=lambda x: x["start"])
                
                # Write to SRT file
                with open(self.subtitles_path, "w", encoding="utf-8") as f:
                    self._write_simple_srt(all_segments, f)
                
                # Verify file has content
                if os.path.getsize(self.subtitles_path) > 100:
                    print(f"Successfully wrote Marathi subtitles to {self.subtitles_path}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error in Marathi chunked transcription: {e}")
            traceback.print_exc()
            return False
    
    def _direct_marathi_transcribe_with_command_line(self) -> bool:
        """
        Try transcribing Marathi audio using the command line whisper tool as a fallback.
        This can work better in some cases than the Python API.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            print("Attempting Marathi transcription using command line whisper...")
            
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
            
            # For Marathi, always use the small model or larger
            model_to_use = "small"
            if self.whisper_model_size in ["medium", "large"]:
                model_to_use = self.whisper_model_size
            
            # Try to execute whisper command line with timeout and proper error handling
            try:
                cmd = [
                    "whisper", 
                    self.audio_path, 
                    "--model", model_to_use,
                    "--language", "mr",  # Explicitly specify Marathi
                    "--output_dir", self.output_dir,
                    "--output_format", "srt",
                    "--task", "transcribe",  # Explicitly set task to transcribe
                    "--verbose", "True"  # Get more info for debugging
                ]
                
                # Add device flag
                cmd.extend(device_flag.split())
                
                print(f"Running command for Marathi: {' '.join(cmd)}")
                
                # Set a reasonable timeout based on audio length and model size
                # Marathi needs more time due to its complexity
                timeout = max(600, int(self.video.duration * 3))  # At least 10 minutes, and longer for longer videos
                
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
                
                print(f"Command output: {result.stdout}")
                
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
                    print("Command line Marathi transcription successful!")
                    return True
            
            print("Command line Marathi transcription attempt did not produce usable subtitles.")
            return False
            
        except Exception as e:
            print(f"Command line Marathi transcription failed: {e}")
            return False
    
    def get_available_files(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get a list of available audio and subtitle files for selection.
        
        Returns:
            Dictionary containing lists of audio and subtitle files with their metadata
        """
        audio_files = []
        subtitle_files = []
        
        # Add original audio if it exists
        if os.path.exists(self.audio_path):
            audio_files.append({
                "path": self.audio_path,
                "name": "Original Extracted Audio",
                "size": os.path.getsize(self.audio_path),
                "type": "original"
            })
        
        # Add cleaned audio if it exists
        if os.path.exists(self.cleaned_audio_path):
            audio_files.append({
                "path": self.cleaned_audio_path,
                "name": "Cleaned Audio",
                "size": os.path.getsize(self.cleaned_audio_path),
                "type": "cleaned"
            })
        
        # Add noise reduced audio if it exists
        if os.path.exists(self.noise_reduced_audio_path):
            audio_files.append({
                "path": self.noise_reduced_audio_path,
                "name": "Noise Reduced Audio",
                "size": os.path.getsize(self.noise_reduced_audio_path),
                "type": "noise_reduced"
            })
        
        # Add VAD cleaned audio if it exists
        if os.path.exists(self.vad_cleaned_audio_path):
            audio_files.append({
                "path": self.vad_cleaned_audio_path,
                "name": "Voice Activity Detected Audio",
                "size": os.path.getsize(self.vad_cleaned_audio_path),
                "type": "vad_cleaned"
            })
        
        # Add original subtitle file if it exists
        if os.path.exists(self.subtitles_path):
            subtitle_files.append({
                "path": self.subtitles_path,
                "name": "Generated Subtitles",
                "size": os.path.getsize(self.subtitles_path),
                "type": "generated"
            })
        
        # Find any additional subtitle files in the output directory
        for file in os.listdir(self.output_dir):
            if file.endswith('.srt') and os.path.join(self.output_dir, file) != self.subtitles_path:
                subtitle_path = os.path.join(self.output_dir, file)
                subtitle_files.append({
                    "path": subtitle_path,
                    "name": f"Subtitle: {file}",
                    "size": os.path.getsize(subtitle_path),
                    "type": "additional"
                })
        
        return {
            "audio_files": audio_files,
            "subtitle_files": subtitle_files
        }
    
    def save_uploaded_file(self, file, file_type: str) -> Optional[str]:
        """
        Save an uploaded file (audio or subtitle) to the output directory.
        
        Args:
            file: The uploaded file object
            file_type: Type of file ('audio' or 'subtitle')
            
        Returns:
            Path to the saved file or None if failed
        """
        try:
            # Create filename based on type
            if file_type == 'audio':
                extension = os.path.splitext(file.filename)[1].lower()
                if extension not in ['.wav', '.mp3', '.m4a', '.aac']:
                    print(f"Unsupported audio format: {extension}")
                    return None
                output_path = os.path.join(self.output_dir, f"uploaded_audio{extension}")
            elif file_type == 'subtitle':
                extension = os.path.splitext(file.filename)[1].lower()
                if extension != '.srt':
                    print(f"Unsupported subtitle format: {extension}")
                    return None
                output_path = os.path.join(self.output_dir, f"uploaded_subtitle{extension}")
            else:
                print(f"Unsupported file type: {file_type}")
                return None
            
            # Save the file
            with open(output_path, 'wb') as f:
                f.write(file.read())
            
            print(f"Saved uploaded {file_type} to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error saving uploaded file: {e}")
            return None 

    def update_subtitle_settings(self, font_size: int = None, font_color: str = None, 
                              bg_opacity: int = None, font: str = None) -> None:
        """
        Update subtitle appearance settings.
        
        Args:
            font_size: Font size for subtitles (10 or above)
            font_color: Font color for subtitles (e.g., "white", "yellow", etc.)
            bg_opacity: Background opacity (0-100)
            font: Font name to use
        """
        if font_size is not None:
            if font_size < 10:
                print(f"Warning: Font size {font_size} too small, setting to minimum value of 10")
                font_size = 10
            self.subtitle_font_size = font_size
            print(f"Subtitle font size updated to {self.subtitle_font_size}")
            
        if font_color is not None:
            self.subtitle_color = font_color
            print(f"Subtitle color updated to {self.subtitle_color}")
            
        if bg_opacity is not None:
            if bg_opacity < 0:
                bg_opacity = 0
            elif bg_opacity > 100:
                bg_opacity = 100
            self.subtitle_bg_opacity = bg_opacity
            print(f"Subtitle background opacity updated to {self.subtitle_bg_opacity}")
            
        if font is not None:
            self.subtitle_font = font
            print(f"Subtitle font updated to {self.subtitle_font}")