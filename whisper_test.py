#!/usr/bin/env python3
"""
Test script for Whisper transcription.
This script provides a simple way to test if Whisper is working correctly.
"""

import os
import sys
import time
import argparse
import whisper
import torch
import numpy as np
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

def load_audio_direct(audio_path):
    """
    Load audio directly without using ffmpeg, which can be a source of errors.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Numpy array of audio data ready for Whisper
    """
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

def test_whisper(audio_path, model_size="base"):
    """
    Test Whisper transcription with a simple approach.
    
    Args:
        audio_path: Path to audio file or video to extract audio from
        model_size: Size of the Whisper model to use
    
    Returns:
        True if successful, False if it failed
    """
    print(f"Testing Whisper with {audio_path}")
    
    # Check if file exists
    if not os.path.exists(audio_path):
        print(f"ERROR: File not found: {audio_path}")
        return False
    
    # Extract audio if input is a video
    if audio_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
        print("Input is a video file. Extracting audio sample...")
        
        # Create temp directory
        os.makedirs('temp', exist_ok=True)
        sample_path = os.path.join('temp', 'whisper_test_sample.wav')
        
        try:
            # Use moviepy to extract audio
            video = VideoFileClip(audio_path)
            
            # Extract only first 10 seconds
            max_duration = min(10, video.duration)
            video.subclip(0, max_duration).audio.write_audiofile(
                sample_path, 
                codec='pcm_s16le',
                fps=16000
            )
            print(f"Extracted {max_duration}s audio sample from video")
            
            # Use this sample for testing
            test_file = sample_path
            
        except Exception as e:
            print(f"Failed to extract audio: {e}")
            return False
    else:
        test_file = audio_path
    
    # System info
    print("System information:")
    print(f"Python: {sys.version.split()[0]}")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    
    try:
        # Load model (simplified approach)
        print(f"Loading {model_size} model...")
        start_time = time.time()
        
        try:
            model = whisper.load_model(model_size)
            load_time = time.time() - start_time
            print(f"Model loaded in {load_time:.2f} seconds")
        except Exception as e:
            print(f"ERROR: Failed to load model: {e}")
            return False
        
        # Load audio directly
        try:
            audio_data = load_audio_direct(test_file)
        except Exception as e:
            print(f"ERROR: Failed to load audio: {e}")
            return False
        
        # Transcribe
        print("Starting transcription...")
        start_time = time.time()
        
        try:
            result = model.transcribe(audio_data, language="en")
            transcribe_time = time.time() - start_time
            print(f"Transcription completed in {transcribe_time:.2f} seconds")
        except Exception as e:
            print(f"ERROR: Transcription failed: {e}")
            return False
        
        # Check result
        if not result or "text" not in result or not result["text"]:
            print("ERROR: Transcription returned empty result")
            return False
        
        # Output sample
        text = result["text"]
        sample = text[:100] + ("..." if len(text) > 100 else "")
        print(f"Sample transcription: \"{sample}\"")
        print(f"Total text length: {len(text)} characters")
        
        # Check segments
        if "segments" in result:
            segment_count = len(result["segments"])
            print(f"Segments: {segment_count}")
        
        # Create sample SRT
        sample_srt_path = os.path.join('temp', 'whisper_test_sample.srt')
        if "segments" in result and result["segments"]:
            with open(sample_srt_path, "w", encoding="utf-8") as f:
                for i, segment in enumerate(result["segments"]):
                    # SRT index
                    f.write(f"{i+1}\n")
                    
                    # Format timestamps
                    start_time = format_timestamp(segment["start"])
                    end_time = format_timestamp(segment["end"])
                    f.write(f"{start_time} --> {end_time}\n")
                    
                    # Text
                    f.write(f"{segment['text'].strip()}\n\n")
                    
            print(f"Sample SRT file created: {sample_srt_path}")
        
        return True
        
    except Exception as e:
        print(f"Error during Whisper test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            if 'sample_path' in locals() and os.path.exists(sample_path):
                os.remove(sample_path)
                print(f"Removed temporary file: {sample_path}")
        except Exception:
            pass

def format_timestamp(seconds):
    """Format seconds to SRT timestamp (HH:MM:SS,mmm)."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"

def main():
    parser = argparse.ArgumentParser(description="Test Whisper transcription")
    parser.add_argument("audio_file", help="Path to audio or video file")
    parser.add_argument("--model", "-m", choices=["tiny", "base", "small", "medium"], 
                        default="base", help="Whisper model size")
    
    args = parser.parse_args()
    
    success = test_whisper(args.audio_file, args.model)
    
    if success:
        print("\n✅ Whisper test PASSED! Transcription is working correctly.")
    else:
        print("\n❌ Whisper test FAILED. See above for details.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 