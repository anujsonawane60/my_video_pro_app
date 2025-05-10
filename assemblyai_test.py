#!/usr/bin/env python3
"""
Test script for AssemblyAI API connectivity and transcription.
"""

import os
import sys
import time
import argparse
from pydub import AudioSegment
import assemblyai as aai

def test_assemblyai(audio_path, api_key=None):
    """
    Test AssemblyAI API by transcribing a short audio sample.
    
    Args:
        audio_path: Path to audio file or video to extract audio from
        api_key: AssemblyAI API key
    
    Returns:
        True if successful, False if it failed
    """
    print(f"Testing AssemblyAI with {audio_path}")
    
    # Check if file exists
    if not os.path.exists(audio_path):
        print(f"ERROR: File not found: {audio_path}")
        return False
    
    # Check API key
    if not api_key:
        print("ERROR: AssemblyAI API key is required")
        return False
    
    # Set API key
    aai.settings.api_key = api_key
    
    try:
        # If input is a video, extract a short audio sample
        if audio_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            print("Input is a video file. Extracting audio sample...")
            
            # Create temp directory
            os.makedirs('temp', exist_ok=True)
            sample_path = os.path.join('temp', 'sample.wav')
            
            try:
                # Use moviepy to extract audio
                from moviepy.editor import VideoFileClip
                video = VideoFileClip(audio_path)
                
                # Extract only first 10 seconds to make the test faster
                max_duration = min(10, video.duration)
                video.subclip(0, max_duration).audio.write_audiofile(sample_path, verbose=False, logger=None)
                print(f"Extracted {max_duration}s audio sample from video")
                
                # Use this sample for testing
                test_file = sample_path
                
            except Exception as e:
                print(f"Failed to extract audio: {e}")
                return False
        else:
            # For audio files, use directly but consider creating a short sample
            if os.path.getsize(audio_path) > 10 * 1024 * 1024:  # If larger than 10MB
                print("Large audio file detected. Creating a shorter sample...")
                try:
                    audio = AudioSegment.from_file(audio_path)
                    
                    # Take first 10 seconds
                    sample_duration = min(10 * 1000, len(audio))
                    sample = audio[:sample_duration]
                    
                    # Save sample
                    os.makedirs('temp', exist_ok=True)
                    sample_path = os.path.join('temp', 'sample.wav')
                    sample.export(sample_path, format="wav")
                    
                    test_file = sample_path
                    print(f"Created {sample_duration/1000}s audio sample")
                except Exception as e:
                    print(f"Failed to create audio sample: {e}. Using original file.")
                    test_file = audio_path
            else:
                test_file = audio_path
        
        # Test API connectivity
        print("Testing AssemblyAI API connection...")
        try:
            # Simple health check
            aai.api_client.APIClient(api_key=api_key).get("/health", {})
            print("API connection successful!")
        except Exception as e:
            print(f"API connection failed: {e}")
            return False
        
        # Set up transcription
        print("Setting up transcription...")
        config = aai.TranscriptionConfig(
            speech_model=aai.SpeechModel.base,  # Use base model for quick test
            punctuate=True
        )
        
        transcriber = aai.Transcriber(config=config)
        
        # Start transcription
        print(f"Submitting file {test_file} for transcription...")
        start_time = time.time()
        transcript = transcriber.transcribe(test_file)
        
        # Check result
        if transcript.status == "error":
            print(f"Transcription failed: {transcript.error}")
            return False
        
        elapsed = time.time() - start_time
        print(f"Transcription completed in {elapsed:.2f} seconds")
        
        # Display sample text
        if transcript.text:
            sample_text = transcript.text[:100] + ("..." if len(transcript.text) > 100 else "")
            print(f"Sample transcription: \"{sample_text}\"")
            print(f"Total text length: {len(transcript.text)} characters")
            
            # Count words
            word_count = len(transcript.text.split())
            print(f"Word count: {word_count}")
            
            # Check for utterances
            if hasattr(transcript, 'utterances') and transcript.utterances:
                print(f"Utterances: {len(transcript.utterances)}")
            
            return True
        else:
            print("Transcription returned empty result")
            return False
        
    except Exception as e:
        print(f"Error during AssemblyAI test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up temporary files
        try:
            if 'sample_path' in locals() and os.path.exists(sample_path):
                os.remove(sample_path)
                print(f"Removed temporary file: {sample_path}")
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Test AssemblyAI transcription")
    parser.add_argument("audio_file", help="Path to audio or video file")
    parser.add_argument("--api-key", "-k", help="AssemblyAI API key")
    
    args = parser.parse_args()
    
    # If no API key provided via args, check environment variable
    api_key = args.api_key or os.environ.get("ASSEMBLYAI_API_KEY")
    
    if not api_key:
        print("No API key provided. Please provide it via --api-key or ASSEMBLYAI_API_KEY environment variable.")
        return 1
    
    success = test_assemblyai(args.audio_file, api_key)
    
    if success:
        print("\n✅ AssemblyAI test PASSED! The API is working correctly.")
    else:
        print("\n❌ AssemblyAI test FAILED. See above for details.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 