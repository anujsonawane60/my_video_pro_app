import os
from voice_changer import VoiceChanger
from dotenv import load_dotenv
import argparse

# Load environment variables from .env file
load_dotenv()

def main():
    """
    Test script to verify the timing-preserving TTS generation
    """
    parser = argparse.ArgumentParser(description='Test voice generation with timing preservation')
    parser.add_argument('--srt', required=True, help='Path to SRT subtitle file')
    parser.add_argument('--output', default='output_with_timing.mp3', help='Output audio file path')
    parser.add_argument('--voice_id', default=None, help='ElevenLabs voice ID (defaults to Rachel)')
    parser.add_argument('--test_both', action='store_true', help='Test both methods for comparison')
    args = parser.parse_args()
    
    # Check if the subtitle file exists
    if not os.path.exists(args.srt):
        print(f"Error: Subtitle file '{args.srt}' not found")
        return
    
    try:
        # Initialize the voice changer
        voice_changer = VoiceChanger()
        
        # Make sure we have a valid API key
        if not voice_changer.api_key:
            print("Error: ELEVENLABS_API_KEY environment variable is not set")
            return
        
        # Test the new method with timing preservation
        output_timed = args.output
        print(f"\nGenerating audio with timing preservation: {output_timed}")
        success = voice_changer.generate_voice_with_timing(
            subtitle_path=args.srt,
            voice_id=args.voice_id,
            output_filename=output_timed
        )
        
        if success:
            print(f"Successfully generated timed audio: {output_timed}")
        else:
            print(f"Failed to generate timed audio")
            
        # Also test the original method for comparison if requested
        if args.test_both:
            output_plain = 'output_without_timing.mp3'
            print(f"\nGenerating audio without timing preservation: {output_plain}")
            success = voice_changer.generate_voice_from_subtitles(
                subtitle_path=args.srt,
                voice_id=args.voice_id,
                output_filename=output_plain
            )
            
            if success:
                print(f"Successfully generated plain audio: {output_plain}")
            else:
                print(f"Failed to generate plain audio")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 