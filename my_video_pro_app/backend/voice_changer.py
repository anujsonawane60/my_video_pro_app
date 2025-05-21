import os
import requests
import re
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from pydub import AudioSegment
import datetime
import time
import shutil
import numpy as np
try:
    import librosa
    import librosa.display
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("Librosa not available. Advanced audio alignment features will be disabled.")

# Load environment variables from .env file
load_dotenv()

# Set path for ffmpeg for pydub
def ensure_ffmpeg_paths():
    """Make sure pydub can find ffmpeg/ffprobe"""
    try:
        # Try to find ffmpeg in the system path
        ffmpeg_paths = []
        
        # Function to try running a command and check if it works
        def try_ffmpeg_command(command):
            try:
                result = subprocess.run(command, 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      text=True,
                                      timeout=2)
                return result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                return False
        
        # Check if ffmpeg is directly in PATH
        if try_ffmpeg_command(["ffmpeg", "-version"]):
            print("Found ffmpeg in system PATH")
            # In PATH, so no need to set explicit path
            return True
        
        # List of potential ffmpeg locations
        potential_locations = [
            "C:/ffmpeg/bin/ffmpeg.exe",
            "C:/Program Files/ffmpeg/bin/ffmpeg.exe", 
            "C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe",
            os.path.join(os.getcwd(), "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(os.getcwd(), "ffmpeg.exe"),
            # Add more paths if needed
        ]
        
        for location in potential_locations:
            if os.path.exists(location):
                print(f"Found ffmpeg at: {location}")
                ffmpeg_dir = os.path.dirname(location)
                
                # Set paths for pydub
                AudioSegment.converter = os.path.join(ffmpeg_dir, "ffmpeg.exe")
                AudioSegment.ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe")
                
                # Verify it works
                if try_ffmpeg_command([AudioSegment.converter, "-version"]):
                    print(f"Successfully set ffmpeg for pydub to: {AudioSegment.converter}")
                    return True
        
        print("WARNING: Could not find ffmpeg. Audio processing will attempt to use direct methods.")
        
        # Set a fallback approach using direct API calls when no ffmpeg is available
        # This will prevent complete failure but with reduced functionality
        AudioSegment.converter = "not_found_workaround"
        return False
        
    except Exception as e:
        print(f"Error setting ffmpeg paths: {e}")
        return False

# Try to set ffmpeg paths
ensure_ffmpeg_paths()

# Extract the function to get plain text from subtitles
from main import extract_text_from_srt

class VoiceChanger:
    """
    Class to handle changing voice using ElevenLabs API based on subtitles.
    Uses the ElevenLabs API to generate speech from subtitle text.
    """
    
    def __init__(self):
        """
        Initialize the VoiceChanger with API key from environment variables.
        """
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is not set")
        
        # Default voice ID (Rachel)
        self.default_voice_id = "21m00Tcm4TlvDq8ikWAM"
        
        # API base URL
        self.api_base_url = "https://api.elevenlabs.io/v1"

    def list_available_voices(self):
        """
        Lists available voices from the ElevenLabs API.
        
        Returns:
            list: A list of voice dictionaries with id and name
        """
        url = f"{self.api_base_url}/voices"
        headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            voices_data = response.json()
            print(f"Found {len(voices_data.get('voices', []))} voices")
            return voices_data.get("voices", [])
        except requests.exceptions.RequestException as e:
            print(f"API Request Error while fetching voices: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while fetching voices: {e}")
            return []
    
    def check_user_credits(self):
        """
        Check the user's available credits on ElevenLabs.
        
        Returns:
            dict: Information about user subscription including available credits,
                  or None if request failed
        """
        url = f"{self.api_base_url}/user/subscription"
        headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            subscription_data = response.json()
            character_limit = subscription_data.get('character_limit', 0)
            characters_used = subscription_data.get('character_count', 0)
            available_chars = character_limit - characters_used
            print(f"User has {available_chars} characters remaining (used {characters_used} of {character_limit})")
            return subscription_data
        except requests.exceptions.RequestException as e:
            print(f"Error checking user credits: {e}")
            return None
    
    def calculate_required_credits(self, text):
        """
        Calculate how many credits are required for the provided text.
        
        Args:
            text (str): The text to estimate credit usage for
            
        Returns:
            int: Estimated number of credits required
        """
        # Each character typically counts as 1 credit in ElevenLabs
        return len(text)
    
    def generate_voice_from_text(self, text, voice_id=None, output_filename="output.mp3", 
                              stability=0.5, similarity_boost=0.75):
        """
        Generates audio from the given text using the ElevenLabs API and saves it to a file.
        
        Args:
            text (str): The text to convert to speech.
            voice_id (str): The ID of the voice to use. Defaults to self.default_voice_id.
            output_filename (str): The name of the file to save the audio to.
            stability (float): Voice stability (0.0 to 1.0)
            similarity_boost (float): Voice clarity/similarity boost (0.0 to 1.0)
            
        Returns:
            bool: True if audio generation was successful, False otherwise.
        """
        if not voice_id:
            voice_id = self.default_voice_id
        
        # Check available credits first
        required_credits = self.calculate_required_credits(text)
        print(f"Required credits for this text: {required_credits}")
        
        subscription_data = self.check_user_credits()
        if subscription_data:
            character_limit = subscription_data.get('character_limit', 0)
            characters_used = subscription_data.get('character_count', 0)
            available_chars = character_limit - characters_used
            
            if required_credits > available_chars:
                print(f"Not enough credits: {available_chars} available, {required_credits} required")
                raise ValueError(f"Not enough ElevenLabs credits: {available_chars} available, {required_credits} required. Please upgrade your plan or reduce text length.")
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }

        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost
            }
        }

        # Construct the specific URL for the chosen voice
        tts_url = f"{self.api_base_url}/text-to-speech/{voice_id}"

        try:
            print(f"Sending request to ElevenLabs API for voice: {voice_id}...")
            response = requests.post(tts_url, json=data, headers=headers, stream=True)
            response.raise_for_status()

            # Save the audio content to a file
            with open(output_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):  # 8KB chunks
                    f.write(chunk)
            print(f"Audio successfully generated and saved to {output_filename}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"API Request Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    # Try to print more detailed error from API if available
                    error_details = e.response.json()
                    if "detail" in error_details:
                        if isinstance(error_details["detail"], dict) and "message" in error_details["detail"]:
                            print(f"API Error Message: {error_details['detail']['message']}")
                        elif isinstance(error_details["detail"], str):
                            print(f"API Error Message: {error_details['detail']}")
                    else:
                        print(f"Full API error response: {error_details}")
                except ValueError:  # If response is not JSON
                    print(f"API Error Response (not JSON): {e.response.text}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return False
    
    def parse_srt_timing(self, time_str):
        """
        Parse SRT timestamp into milliseconds
        
        Args:
            time_str (str): SRT timestamp (HH:MM:SS,mmm)
            
        Returns:
            int: Timestamp in milliseconds
        """
        hours, minutes, seconds = time_str.replace(',', '.').split(':')
        hours = int(hours)
        minutes = int(minutes)
        seconds = float(seconds)
        
        return int((hours * 3600 + minutes * 60 + seconds) * 1000)
    
    def generate_voice_with_timing(self, subtitle_path, voice_id=None, output_filename="output.mp3",
                                stability=0.5, similarity_boost=0.75):
        """
        Generate voice audio from subtitle file, preserving timing/pauses between sentences.
        
        Args:
            subtitle_path (str): Path to subtitle file (.srt)
            voice_id (str): ElevenLabs voice ID (optional)
            output_filename (str): Path to save the audio output
            stability (float): Voice stability (0.0 to 1.0)
            similarity_boost (float): Voice clarity (0.0 to 1.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read the subtitle file
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            
            # Regular expression to match subtitle entries with timing info
            subtitle_pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)(?=\n\s*\n\s*\d+|\n\s*\n\s*$|$)')
            
            matches = subtitle_pattern.findall(subtitle_content)
            
            if not matches:
                print("Failed to parse subtitle format, falling back to simple method")
                return self.generate_voice_from_subtitles(subtitle_path, voice_id, output_filename, 
                                                        stability, similarity_boost)
            
            # If there's only one subtitle segment, we need to handle it differently
            # to preserve the original duration
            if len(matches) == 1:
                print("Single subtitle segment detected, preserving original duration...")
                idx, start_time, end_time, text = matches[0]
                
                # Parse timing to calculate total duration
                start_ms = self.parse_srt_timing(start_time)
                end_ms = self.parse_srt_timing(end_time)
                duration_ms = end_ms - start_ms
                
                print(f"Original subtitle duration: {duration_ms/1000:.2f} seconds (from {start_time} to {end_time})")
                
                # Clean up text
                text = text.strip()
                text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
                
                # Generate audio for this segment
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_audio_path = temp_file.name
                
                success = self.generate_voice_from_text(
                    text=text,
                    voice_id=voice_id,
                    output_filename=temp_audio_path,
                    stability=stability,
                    similarity_boost=similarity_boost
                )
                
                if not success:
                    print("Failed to generate voice for single subtitle")
                    return False
                
                try:
                    # Try to create final audio with proper timing
                    print(f"Creating final audio with proper timing...")
                    final_audio = AudioSegment.silent(duration=start_ms)  # Start with silence up to start time
                    
                    # Load the generated audio
                    voice_audio = AudioSegment.from_file(temp_audio_path)
                    
                    # Add the voice
                    final_audio += voice_audio
                    
                    # Add silence at the end if needed to match original duration
                    generated_duration = len(voice_audio)
                    padding_needed = max(0, duration_ms - generated_duration)
                    if padding_needed > 0:
                        print(f"Adding {padding_needed}ms silence at the end to match original timing")
                        final_audio += AudioSegment.silent(duration=padding_needed)
                    
                    # Export the final audio
                    final_audio.export(output_filename, format="mp3")
                    print(f"Successfully created audio with original timing")
                    
                    # Clean up temp file
                    try:
                        os.unlink(temp_audio_path)
                    except:
                        pass
                    
                    return True
                except Exception as e:
                    print(f"Error processing with pydub: {e}")
                    # Fall back to direct method
                    try:
                        # Get the full duration of the subtitle in seconds
                        full_duration = (end_ms - start_ms) / 1000
                        
                        # Try a different approach - manually create a new audio file
                        # with proper silences using ffmpeg directly
                        print("Attempting direct FFmpeg approach...")
                        try:
                            # Check if we can find ffmpeg ourselves
                            ffmpeg_found = False
                            ffmpeg_cmd = None
                            
                            for possible_ffmpeg in [
                                "ffmpeg", 
                                "ffmpeg.exe",
                                "C:/ffmpeg/bin/ffmpeg.exe", 
                                "C:/Program Files/ffmpeg/bin/ffmpeg.exe",
                                os.path.join(os.getcwd(), "ffmpeg.exe"),
                                os.path.join(os.getcwd(), "ffmpeg", "bin", "ffmpeg.exe")
                            ]:
                                try:
                                    result = subprocess.run([possible_ffmpeg, "-version"], 
                                                          stdout=subprocess.PIPE, 
                                                          stderr=subprocess.PIPE,
                                                          text=True)
                                    if result.returncode == 0:
                                        ffmpeg_cmd = possible_ffmpeg
                                        ffmpeg_found = True
                                        print(f"Found ffmpeg at: {ffmpeg_cmd}")
                                        break
                                except:
                                    continue
                            
                            # If we found ffmpeg, use it to process the audio directly
                            if ffmpeg_found:
                                # Create a silent audio file for the beginning
                                start_silence = os.path.join(os.path.dirname(temp_audio_path), "start_silence.mp3")
                                if start_ms > 0:
                                    subprocess.run([
                                        ffmpeg_cmd, "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono", 
                                        "-t", f"{start_ms/1000}", "-c:a", "libmp3lame", "-y", start_silence
                                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                
                                # Create a silent audio file for the end
                                end_silence = os.path.join(os.path.dirname(temp_audio_path), "end_silence.mp3")
                                if padding_needed > 0:
                                    subprocess.run([
                                        ffmpeg_cmd, "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono", 
                                        "-t", f"{padding_needed/1000}", "-c:a", "libmp3lame", "-y", end_silence
                                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                
                                # Create a concat file
                                concat_file = os.path.join(os.path.dirname(temp_audio_path), "concat.txt")
                                with open(concat_file, "w") as f:
                                    if start_ms > 0:
                                        f.write(f"file '{start_silence}'\n")
                                    f.write(f"file '{temp_audio_path}'\n")
                                    if padding_needed > 0:
                                        f.write(f"file '{end_silence}'\n")
                                
                                # Concatenate all files
                                subprocess.run([
                                    ffmpeg_cmd, "-f", "concat", "-safe", "0", "-i", concat_file,
                                    "-c", "copy", "-y", output_filename
                                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                
                                print("Successfully created audio with FFmpeg direct approach")
                                return True
                        except Exception as ffmpeg_err:
                            print(f"Direct FFmpeg approach failed: {ffmpeg_err}")
                        
                        # If all direct methods fail, try the special silent padding text approach
                        try:
                            print("Trying silent padding text approach...")
                            
                            # Create a text with special silent padding characters
                            # ". . ." tends to create slight pauses in TTS
                            
                            # Calculate needed pauses
                            chars_per_second = 15  # Approximate rate of speech
                            expected_text_duration = len(text) / chars_per_second
                            
                            # Calculate how many seconds of silence we need at the start and end
                            total_silence_needed = max(0, full_duration - expected_text_duration)
                            start_silence_seconds = start_ms / 1000
                            end_silence_seconds = max(0, total_silence_needed - start_silence_seconds)
                            
                            print(f"Need about {start_silence_seconds:.1f}s of silence at start, {end_silence_seconds:.1f}s at end")
                            
                            # Function to generate padding text for N seconds of silence
                            def generate_silence_text(seconds):
                                if seconds < 0.5:
                                    return ""
                                    
                                # Each ". . ." creates about 1 second of pause
                                silence_units = int(seconds + 0.5)  # Round to nearest
                                return ". . . " * silence_units
                            
                            # Create padded text
                            padded_text = generate_silence_text(start_silence_seconds) + text + generate_silence_text(end_silence_seconds)
                            
                            # Generate TTS with the padded text
                            success = self.generate_voice_from_text(
                                text=padded_text,
                                voice_id=voice_id,
                                output_filename=output_filename,
                                stability=stability,
                                similarity_boost=similarity_boost
                            )
                            
                            if success:
                                print("Successfully generated audio with silent padding text")
                                return True
                        except Exception as padding_err:
                            print(f"Silent padding approach failed: {padding_err}")
                        
                        # If the full duration is significantly longer than what would be expected,
                        # we need to add silences
                        expected_duration = len(text) / 15  # Rough estimate: 15 chars per second
                        if full_duration > expected_duration * 1.5:
                            print(f"Adding pauses to match original timing (expected: {expected_duration:.2f}s, original: {full_duration:.2f}s)")
                            
                            # Add pauses at natural sentence breaks if possible
                            if "." in text or "!" in text or "?" in text:
                                # Split at sentence breaks and add pauses
                                sentences = re.split(r'([.!?])', text)
                                
                                # Recombine with appropriate spacing
                                processed_text = ""
                                for i in range(0, len(sentences), 2):
                                    if i < len(sentences) - 1:
                                        # Add the sentence with its punctuation
                                        processed_text += sentences[i] + sentences[i+1] + "\n\n"
                                    else:
                                        # Last part might not have punctuation
                                        processed_text += sentences[i]
                                
                                # Generate audio with pauses
                                success = self.generate_voice_from_text(
                                    text=processed_text,
                                    voice_id=voice_id,
                                    output_filename=output_filename,
                                    stability=stability,
                                    similarity_boost=similarity_boost
                                )
                                
                                if success:
                                    print("Successfully generated audio with sentence pauses")
                                    return True
                            
                            # If we can't add pauses at sentence breaks, just copy the original TTS output
                            shutil.copy2(temp_audio_path, output_filename)
                            print("Copied original TTS output without timing adjustments")
                            return True
                    except Exception as inner_e:
                        print(f"Error in fallback timing approach: {inner_e}")
                    
                    # If all else fails, just use the generated audio
                    shutil.copy2(temp_audio_path, output_filename)
                    return True
            
            # Create a temporary directory for segment audio files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                final_audio = AudioSegment.silent(duration=0)  # Start with empty audio
                prev_end_time = 0
                
                print(f"Processing {len(matches)} subtitle segments...")
                
                # Calculate total character count for credit check
                total_text = " ".join(match[3].strip() for match in matches)
                required_credits = self.calculate_required_credits(total_text)
                
                # Check credits before starting
                subscription_data = self.check_user_credits()
                if subscription_data:
                    character_limit = subscription_data.get('character_limit', 0)
                    characters_used = subscription_data.get('character_count', 0)
                    available_chars = character_limit - characters_used
                    
                    if required_credits > available_chars:
                        print(f"Not enough credits: {available_chars} available, {required_credits} required")
                        raise ValueError(f"Not enough ElevenLabs credits: {available_chars} available, {required_credits} required. Please upgrade your plan or reduce text length.")
                
                # Process each subtitle segment
                for i, (idx, start_time, end_time, text) in enumerate(matches):
                    # Clean up text
                    text = text.strip()
                    text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                    text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
                    
                    if not text:
                        continue  # Skip empty segments
                    
                    # Parse timing
                    start_ms = self.parse_srt_timing(start_time)
                    end_ms = self.parse_srt_timing(end_time)
                    
                    # Generate filename for this segment
                    segment_file = os.path.join(temp_dir, f"segment_{i:03d}.mp3")
                    
                    print(f"Generating audio for segment {i+1}/{len(matches)}: {text[:30]}...")
                    
                    # Generate audio for this segment
                    success = self.generate_voice_from_text(
                        text=text,
                        voice_id=voice_id,
                        output_filename=segment_file,
                        stability=stability,
                        similarity_boost=similarity_boost
                    )
                    
                    # Give some time for file operations to complete
                    time.sleep(0.5)
                    
                    if not success or not os.path.exists(segment_file):
                        print(f"Failed to generate audio for segment {i+1}")
                        continue
                    
                    try:
                        # Load the generated audio using string path
                        print(f"Loading audio segment from {segment_file}")
                        segment_audio = AudioSegment.from_file(segment_file)
                        
                        # Calculate the target duration for this segment based on original SRT
                        target_duration_ms = end_ms - start_ms
                        
                        # Get the actual generated audio duration
                        actual_duration_ms = len(segment_audio)
                        
                        # If there's a significant difference, adjust speed
                        if abs(actual_duration_ms - target_duration_ms) > 50:  # 50ms tolerance
                            print(f"Adjusting segment duration: target={target_duration_ms}ms, actual={actual_duration_ms}ms")
                            
                            if LIBROSA_AVAILABLE:
                                # Use advanced librosa-based time stretching if available
                                self._adjust_audio_duration_librosa(segment_file, target_duration_ms)
                            else:
                                # Use simple time stretching as fallback
                                self._adjust_audio_duration_simple(segment_file, target_duration_ms, actual_duration_ms)
                            
                            # Reload the adjusted audio segment
                            segment_audio = AudioSegment.from_file(segment_file)
                            print(f"Adjusted segment new duration: {len(segment_audio)}ms")
                        
                        # Calculate silence needed before this segment
                        if i > 0:  # Not the first segment
                            # Add silence to match the subtitle timing
                            silence_duration = max(0, start_ms - prev_end_time)
                            silence = AudioSegment.silent(duration=silence_duration)
                            final_audio += silence
                            print(f"Added {silence_duration}ms silence")
                        
                        # Add the audio segment
                        final_audio += segment_audio
                        
                        # Update previous end time
                        prev_end_time = end_ms
                    except Exception as seg_error:
                        print(f"Error processing segment {i+1}: {seg_error}")
                        import traceback
                        traceback.print_exc()
                
                # If pydub approach failed (empty final_audio), try sequential approach
                if len(final_audio) == 0:
                    print("Pydub approach failed. Trying sequential direct approach...")
                    try:
                        # Create a combined text file with proper spacing between segments
                        segments_to_process = []
                        for i, (idx, start_time, end_time, text) in enumerate(matches):
                            text = text.strip()
                            text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                            text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
                            
                            # Store the segment text with its timing info
                            segments_to_process.append({
                                "text": text,
                                "start_ms": self.parse_srt_timing(start_time),
                                "end_ms": self.parse_srt_timing(end_time)
                            })
                        
                        # Generate individual segments and combine with proper timing
                        try:
                            print("Generating individual segments and combining with proper silences...")
                            with tempfile.TemporaryDirectory() as temp_dir:
                                final_audio = AudioSegment.silent(duration=0)
                                last_end_time = 0
                                
                                for i, segment in enumerate(segments_to_process):
                                    # Generate audio for just this segment
                                    segment_file = os.path.join(temp_dir, f"seq_segment_{i}.mp3")
                                    
                                    # Generate TTS for just this segment
                                    success = self.generate_voice_from_text(
                                        text=segment["text"],
                                        voice_id=voice_id,
                                        output_filename=segment_file,
                                        stability=stability,
                                        similarity_boost=similarity_boost
                                    )
                                    
                                    if not success or not os.path.exists(segment_file):
                                        print(f"Failed to generate segment {i} in sequential mode")
                                        continue
                                    
                                    # If this isn't the first segment, add silence based on timing
                                    if i > 0 and segment["start_ms"] > last_end_time:
                                        silence_duration = segment["start_ms"] - last_end_time
                                        print(f"Adding {silence_duration}ms silence before segment {i+1}")
                                        silence = AudioSegment.silent(duration=silence_duration)
                                        final_audio += silence
                                    
                                    try:
                                        # Wait for file operations to complete
                                        time.sleep(0.2)
                                        
                                        # Load and add this segment
                                        segment_audio = AudioSegment.from_file(segment_file)
                                        final_audio += segment_audio
                                        
                                        # Update last end time
                                        last_end_time = segment["end_ms"]
                                    except Exception as err:
                                        print(f"Error processing sequential segment {i}: {err}")
                                
                                # If we processed at least one segment successfully
                                if len(final_audio) > 0:
                                    # Export the combined audio
                                    final_audio.export(output_filename, format="mp3")
                                    print(f"Sequential combined approach successful")
                                    return True
                        except Exception as e:
                            print(f"Sequential combined approach failed: {e}")
                            # Continue to text-only approach
                        
                        # If the combined approach failed, use simple newlines
                        # Eleven Labs adds natural pauses between sentences and paragraphs
                        print("Trying text-only approach with newlines for pauses...")
                        combined_text = []
                        
                        for segment in segments_to_process:
                            # Add each segment with proper spacing
                            combined_text.append(segment["text"])
                        
                        # Join with double newlines to create paragraph breaks
                        full_text = "\n\n".join(combined_text)
                        
                        # Generate audio for the full text with paragraph breaks
                        print(f"Generating audio with newline-separated text ({len(full_text)} chars)")
                        success = self.generate_voice_from_text(
                            text=full_text,
                            voice_id=voice_id,
                            output_filename=output_filename,
                            stability=stability,
                            similarity_boost=similarity_boost
                        )
                        
                        if success:
                            print(f"Successfully generated audio with text-only approach")
                            return True
                        else:
                            # Try one more approach - each segment separately with time.sleep between
                            print("Trying TTS with sleep-based timing...")
                            try:
                                # Final approach using direct TTS with sleep timing
                                # Create all segments in one file
                                all_segments_audio = []
                                
                                # Process each segment
                                last_end_time = 0
                                for i, segment in enumerate(segments_to_process):
                                    # Calculate how long to pause before this segment
                                    if i > 0 and segment["start_ms"] > last_end_time:
                                        # Calculate gap between segments in seconds
                                        gap_seconds = (segment["start_ms"] - last_end_time) / 1000
                                        print(f"Pausing for {gap_seconds:.2f} seconds...")
                                        time.sleep(gap_seconds)
                                    
                                    # Use a temporary file for this segment
                                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                                        segment_file = temp_file.name
                                    
                                    # Generate audio for this segment
                                    success = self.generate_voice_from_text(
                                        text=segment["text"],
                                        voice_id=voice_id,
                                        output_filename=segment_file,
                                        stability=stability,
                                        similarity_boost=similarity_boost
                                    )
                                    
                                    # Save this file path for later concatenation
                                    if success and os.path.exists(segment_file):
                                        all_segments_audio.append(segment_file)
                                        # Update the last end time
                                        last_end_time = segment["end_ms"]
                                
                                # If we have at least one segment, try to concatenate them
                                if all_segments_audio:
                                    # Try concatenating using direct file copy (as fallback when pydub fails)
                                    with open(output_filename, 'wb') as output_file:
                                        for segment_file in all_segments_audio:
                                            with open(segment_file, 'rb') as input_file:
                                                output_file.write(input_file.read())
                                            # Delete temp file after use
                                            try:
                                                os.unlink(segment_file)
                                            except:
                                                pass
                                    
                                    print(f"Successfully created audio with sleep-based timing approach")
                                    return True
                            except Exception as sleep_error:
                                print(f"Sleep-based approach failed: {sleep_error}")
                            
                            # As a last resort, fall back to standard method
                            print("All sequential approaches failed, falling back to standard method")
                            return self.generate_voice_from_subtitles(
                                subtitle_path=subtitle_path,
                                voice_id=voice_id,
                                output_filename=output_filename,
                                stability=stability,
                                similarity_boost=similarity_boost
                            )
                    except Exception as e:
                        print(f"Sequential approach failed: {e}")
                        traceback.print_exc()
                        # Fall back to standard method
                        return self.generate_voice_from_subtitles(
                            subtitle_path=subtitle_path,
                            voice_id=voice_id,
                            output_filename=output_filename,
                            stability=stability,
                            similarity_boost=similarity_boost
                        )
                
                # Export the final audio file (if pydub approach succeeded)
                try:
                    print(f"Exporting final audio to {output_filename}")
                    final_audio.export(output_filename, format="mp3")
                    print(f"Complete audio successfully generated and saved to {output_filename}")
                    return True
                except Exception as export_error:
                    print(f"Error exporting final audio: {export_error}")
                    traceback.print_exc()
                    # Fall back to standard method
                    return self.generate_voice_from_subtitles(
                        subtitle_path=subtitle_path,
                        voice_id=voice_id,
                        output_filename=output_filename,
                        stability=stability,
                        similarity_boost=similarity_boost
                    )
                
        except Exception as e:
            print(f"Error generating voice with timing: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_voice_from_subtitles(self, subtitle_path, voice_id=None, output_filename="output.mp3",
                                   stability=0.5, similarity_boost=0.75):
        """
        Generate voice audio from subtitle file.
        
        Args:
            subtitle_path (str): Path to subtitle file (.srt)
            voice_id (str): ElevenLabs voice ID (optional)
            output_filename (str): Path to save the audio output
            stability (float): Voice stability (0.0 to 1.0)
            similarity_boost (float): Voice clarity (0.0 to 1.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read the subtitle file
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            
            # Extract plain text from subtitles
            script_text = extract_text_from_srt(subtitle_content)
            
            if not script_text:
                print("Failed to extract text from subtitles")
                return False
            
            print(f"Extracted script text ({len(script_text)} characters)")
            
            # Generate voice audio from the script text
            return self.generate_voice_from_text(
                text=script_text,
                voice_id=voice_id,
                output_filename=output_filename,
                stability=stability,
                similarity_boost=similarity_boost
            )
            
        except Exception as e:
            print(f"Error generating voice from subtitles: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _adjust_audio_duration_simple(self, audio_file, target_duration_ms, actual_duration_ms=None):
        """
        Adjust audio duration using simple methods (time stretching or silence padding).
        
        Args:
            audio_file (str): Path to audio file
            target_duration_ms (int): Target duration in milliseconds
            actual_duration_ms (int, optional): Actual duration in milliseconds, will be measured if not provided
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            audio = AudioSegment.from_file(audio_file)
            
            # If actual_duration_ms was not provided, measure it
            if actual_duration_ms is None:
                actual_duration_ms = len(audio)
            
            # If actual is too short, we can add silence
            if actual_duration_ms < target_duration_ms:
                # Calculate silence to add (distribute at beginning and end)
                silence_to_add = target_duration_ms - actual_duration_ms
                silence_start = int(silence_to_add * 0.2)  # 20% at start
                silence_end = silence_to_add - silence_start
                
                # Add silence
                new_audio = AudioSegment.silent(duration=silence_start) + audio + AudioSegment.silent(duration=silence_end)
                
                # Export to file
                new_audio.export(audio_file, format="mp3")
                print(f"Added {silence_to_add}ms of silence ({silence_start}ms at start, {silence_end}ms at end)")
                return True
                
            # If actual is too long, we need to speed up (time stretch)
            elif actual_duration_ms > target_duration_ms:
                # Try using PyDub's speed change
                speed_factor = actual_duration_ms / target_duration_ms
                
                # Limit speed factor to avoid artifacts
                if speed_factor > 1.5:
                    speed_factor = 1.5
                    print(f"Limiting speed factor to {speed_factor} to avoid artifacts")
                
                try:
                    # Create a temporary file for ffmpeg output
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                        temp_path = temp_file.name
                    
                    # Use ffmpeg for time stretching
                    subprocess.run([
                        "ffmpeg", "-y", "-i", audio_file, 
                        "-filter:a", f"atempo={speed_factor}", 
                        "-vn", temp_path
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Copy back to original file
                    shutil.copy2(temp_path, audio_file)
                    
                    # Clean up
                    os.unlink(temp_path)
                    
                    print(f"Adjusted speed by factor {speed_factor}")
                    return True
                    
                except Exception as e:
                    print(f"Error in ffmpeg time stretching: {e}")
                    # Just return original file if speed adjustment fails
                    return True
            
            return True
                
        except Exception as e:
            print(f"Error in simple audio adjustment: {e}")
            return False
    
    def _adjust_audio_duration_librosa(self, audio_file, target_duration_ms):
        """
        Adjust audio duration using librosa's more advanced time stretching.
        
        Args:
            audio_file (str): Path to audio file
            target_duration_ms (int): Target duration in milliseconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Load the audio file
            y, sr = librosa.load(audio_file, sr=None)
            
            # Calculate current duration
            current_duration_sec = librosa.get_duration(y=y, sr=sr)
            target_duration_sec = target_duration_ms / 1000.0
            
            # Calculate stretch factor
            stretch_factor = target_duration_sec / current_duration_sec
            
            # Apply time stretching
            y_stretched = librosa.effects.time_stretch(y, rate=1/stretch_factor)
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Save the stretched audio using soundfile
            sf.write(temp_path, y_stretched, sr)
            
            # Convert back to mp3
            subprocess.run([
                "ffmpeg", "-y", "-i", temp_path, "-c:a", "libmp3lame", "-q:a", "2", audio_file
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Clean up
            os.unlink(temp_path)
            
            print(f"Applied advanced time stretching with factor {stretch_factor}")
            return True
            
        except Exception as e:
            print(f"Error in librosa time stretching: {e}")
            # Fall back to simple method
            actual_duration_ms = int(current_duration_sec * 1000) if 'current_duration_sec' in locals() else None
            return self._adjust_audio_duration_simple(audio_file, target_duration_ms, actual_duration_ms)

if __name__ == "__main__":
    # Example usage
    changer = VoiceChanger()
    
    # List available voices
    voices = changer.list_available_voices()
    for voice in voices:
        print(f"Voice: {voice.get('name')} (ID: {voice.get('voice_id')})")
    
    # Example text
    text = "Hello, this is a test of the ElevenLabs voice changer integration."
    
    # Generate voice from text
    changer.generate_voice_from_text(text, output_filename="test_voice.mp3") 

# Add the new enhanced audio synchronization functions
class EnhancedSyncVoiceChanger(VoiceChanger):
    """
    Enhanced version of VoiceChanger with better synchronization techniques
    for aligning generated audio with original timings.
    """
    
    def __init__(self):
        """Initialize the enhanced voice changer"""
        super().__init__()
        self.advanced_alignment = LIBROSA_AVAILABLE
    
    def generate_synchronized_voice(self, subtitle_path, voice_id=None, output_filename="output.mp3",
                                  stability=0.5, similarity_boost=0.75):
        """
        Generate voice audio from subtitle file with enhanced synchronization.
        
        Args:
            subtitle_path (str): Path to subtitle file (.srt)
            voice_id (str): ElevenLabs voice ID (optional)
            output_filename (str): Path to save the audio output
            stability (float): Voice stability (0.0 to 1.0)
            similarity_boost (float): Voice clarity (0.0 to 1.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parse subtitle file with precise timing information
            subtitle_segments = self._parse_subtitle_file(subtitle_path)
            if not subtitle_segments:
                print("Failed to parse subtitle file")
                return False
            
            print(f"Parsed {len(subtitle_segments)} subtitle segments with precise timing")
            
            # Generate audio segments with precise timing anchors
            return self._generate_sync_audio(subtitle_segments, voice_id, output_filename, stability, similarity_boost)
            
        except Exception as e:
            print(f"Error in enhanced synchronized voice generation: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_subtitle_file(self, subtitle_path):
        """
        Parse SRT subtitle file with precise timing information.
        
        Args:
            subtitle_path (str): Path to subtitle file
            
        Returns:
            list: List of subtitle segments with text and timing information
        """
        segments = []
        
        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            
            # Regular expression to match subtitle entries with timing info
            subtitle_pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)(?=\n\s*\n\s*\d+|\n\s*\n\s*$|$)')
            
            matches = subtitle_pattern.findall(subtitle_content)
            
            for idx, start_time, end_time, text in matches:
                # Clean up text
                text = text.strip()
                text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
                
                # Parse timing
                start_ms = self.parse_srt_timing(start_time)
                end_ms = self.parse_srt_timing(end_time)
                
                # Calculate duration
                duration_ms = end_ms - start_ms
                
                # Store segment data
                segment = {
                    "id": int(idx),
                    "text": text,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "duration_ms": duration_ms
                }
                
                segments.append(segment)
            
            # Sort segments by start time (just in case they're not in order)
            segments.sort(key=lambda x: x["start_ms"])
            
            return segments
            
        except Exception as e:
            print(f"Error parsing subtitle file: {e}")
            traceback.print_exc()
            return []
    
    def _generate_sync_audio(self, subtitle_segments, voice_id=None, output_filename="output.mp3",
                          stability=0.5, similarity_boost=0.75):
        """
        Generate synchronized audio from subtitle segments.
        
        Args:
            subtitle_segments (list): List of subtitle segments with timing info
            voice_id (str): ElevenLabs voice ID
            output_filename (str): Output file path
            stability (float): Voice stability
            similarity_boost (float): Voice clarity
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Calculate total text length for credit check
            total_text = " ".join([segment["text"] for segment in subtitle_segments])
            required_credits = self.calculate_required_credits(total_text)
            
            # Check available credits
            subscription_data = self.check_user_credits()
            if subscription_data:
                character_limit = subscription_data.get('character_limit', 0)
                characters_used = subscription_data.get('character_count', 0)
                available_chars = character_limit - characters_used
                
                if required_credits > available_chars:
                    print(f"Not enough credits: {available_chars} available, {required_credits} required")
                    raise ValueError(f"Not enough ElevenLabs credits: {available_chars} available, {required_credits} required")
            
            # Create a temporary directory for segment audio files
            with tempfile.TemporaryDirectory() as temp_dir:
                segment_files = []
                
                # Generate audio for each segment separately
                for i, segment in enumerate(subtitle_segments):
                    print(f"Generating audio for segment {i+1}/{len(subtitle_segments)}: {segment['text'][:30]}...")
                    
                    # Generate segment audio file path
                    segment_file = os.path.join(temp_dir, f"segment_{i:03d}.mp3")
                    
                    # Generate audio for this segment with precise rate control
                    success = self._generate_segment_with_duration_control(
                        text=segment["text"],
                        target_duration_ms=segment["duration_ms"],
                        voice_id=voice_id,
                        output_filename=segment_file,
                        stability=stability,
                        similarity_boost=similarity_boost
                    )
                    
                    if not success:
                        print(f"Failed to generate audio for segment {i+1}")
                        continue
                    
                    # Add to segment files list
                    segment_files.append({
                        "file": segment_file,
                        "segment": segment
                    })
                
                # If no segments were generated successfully, fail
                if not segment_files:
                    print("No audio segments were generated successfully")
                    return False
                
                # Combine segments into final audio with precise timing
                success = self._assemble_final_audio(segment_files, output_filename)
                
                return success
                
        except Exception as e:
            print(f"Error generating synchronized audio: {e}")
            traceback.print_exc()
            return False
    
    def _generate_segment_with_duration_control(self, text, target_duration_ms, voice_id=None,
                                             output_filename="output.mp3", stability=0.5, similarity_boost=0.75):
        """
        Generate audio for a text segment with controls to try to match the target duration.
        
        Args:
            text (str): Text to generate speech for
            target_duration_ms (int): Target duration in milliseconds
            voice_id (str): ElevenLabs voice ID
            output_filename (str): Output file path
            stability (float): Voice stability
            similarity_boost (float): Voice clarity
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate initial audio
            success = self.generate_voice_from_text(
                text=text,
                voice_id=voice_id,
                output_filename=output_filename,
                stability=stability,
                similarity_boost=similarity_boost
            )
            
            if not success:
                return False
            
            # Check if we need to adjust the duration
            try:
                # Measure actual duration
                audio = AudioSegment.from_file(output_filename)
                actual_duration_ms = len(audio)
                
                # If the durations are close enough, no need to adjust
                duration_diff = abs(actual_duration_ms - target_duration_ms)
                if duration_diff < 50:  # Using a tighter tolerance (50ms) for better synchronization
                    return True
                
                print(f"Duration adjustment needed: target={target_duration_ms}ms, actual={actual_duration_ms}ms, diff={duration_diff}ms")
                
                # Try to adjust duration
                if self.advanced_alignment and LIBROSA_AVAILABLE:
                    # Use librosa for more advanced time stretching
                    return self._adjust_audio_duration_librosa(output_filename, target_duration_ms)
                else:
                    # Use simpler methods
                    return self._adjust_audio_duration_simple(output_filename, target_duration_ms, actual_duration_ms)
                
            except Exception as e:
                print(f"Error adjusting audio duration: {e}")
                return True  # Return original audio as is
                
        except Exception as e:
            print(f"Error generating segment with duration control: {e}")
            return False
    
    def _assemble_final_audio(self, segment_files, output_filename):
        """
        Assemble the final audio from individual segments with precise timing.
        
        Args:
            segment_files (list): List of segment files with timing information
            output_filename (str): Output file path
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"Assembling final audio from {len(segment_files)} segments...")
            
            # Sort segments by start time
            segment_files.sort(key=lambda x: x["segment"]["start_ms"])
            
            # Create a silent audio track with the full duration
            last_segment = segment_files[-1]["segment"]
            full_duration_ms = last_segment["end_ms"]
            final_audio = AudioSegment.silent(duration=full_duration_ms)
            
            # Overlay each segment at its exact start time
            for i, segment_data in enumerate(segment_files):
                segment = segment_data["segment"]
                segment_file = segment_data["file"]
                
                try:
                    # Load the segment audio
                    segment_audio = AudioSegment.from_file(segment_file)
                    
                    # Overlay at the exact start time
                    final_audio = final_audio.overlay(segment_audio, position=segment["start_ms"])
                    
                    print(f"Added segment {i+1} at position {segment['start_ms']}ms")
                    
                except Exception as e:
                    print(f"Error overlaying segment {i+1}: {e}")
            
            # Export the final audio
            final_audio.export(output_filename, format="mp3")
            print(f"Successfully assembled final audio to {output_filename}")
            return True
            
        except Exception as e:
            print(f"Error assembling final audio: {e}")
            traceback.print_exc()
            return False 