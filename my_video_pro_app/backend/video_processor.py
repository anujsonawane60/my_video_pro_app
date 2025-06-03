import os
import subprocess
import shutil
import json
import tempfile
from typing import Optional, Dict, Any
import logging

class VideoProcessor:
    def __init__(self, output_dir: str = 'outputs'):
        """
        Initialize the VideoProcessor.
        
        Args:
            output_dir: Directory where processed videos will be saved
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def create_final_video(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: str,
        subtitle_style: Optional[Dict[str, Any]] = None,
        output_filename: Optional[str] = None
    ) -> str:
        """
        Create a final video with selected audio and subtitles.
        
        Args:
            video_path: Path to the input video file
            audio_path: Path to the input audio file
            subtitle_path: Path to the subtitle file (SRT or VTT)
            subtitle_style: Dictionary containing subtitle styling options
            output_filename: Optional custom output filename
            
        Returns:
            Path to the created video file
            
        Raises:
            FileNotFoundError: If any of the input files don't exist
            ValueError: If the subtitle style is invalid
            RuntimeError: If video creation fails
        """
        self.logger.info("Starting final video creation")
        
        # Validate input files
        for file_path, file_type in [
            (video_path, "video"),
            (audio_path, "audio"),
            (subtitle_path, "subtitle")
        ]:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"{file_type.capitalize()} file not found: {file_path}")
            if os.path.getsize(file_path) == 0:
                raise ValueError(f"{file_type.capitalize()} file is empty: {file_path}")

        # Set default subtitle style if not provided
        if subtitle_style is None:
            subtitle_style = {
                'size': 24,
                'color': '#ffffff',
                'alpha': 0.5
            }

        # Create output filename if not provided
        if output_filename is None:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_filename = f"final_video_{base_name}.mp4"

        output_path = os.path.join(self.output_dir, output_filename)

        try:
            # Prepare FFmpeg command
            subtitle_style_str = (
                f"fontsize={subtitle_style.get('size', 24)},"
                f"fontcolor={subtitle_style.get('color', '#ffffff')},"
                f"alpha={subtitle_style.get('alpha', 0.5)}"
            )

            command = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-vf", f"subtitles={subtitle_path}:force_style='{subtitle_style_str}'",
                "-shortest",
                output_path
            ]

            self.logger.info(f"Running FFmpeg command: {' '.join(command)}")

            # Run FFmpeg command
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Wait for process to complete
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                self.logger.error(f"FFmpeg command failed: {stderr}")
                raise RuntimeError(f"Video creation failed: {stderr}")

            # Verify output file
            if not os.path.exists(output_path):
                raise RuntimeError("Output file was not created")
            
            if os.path.getsize(output_path) < 1000:
                raise RuntimeError("Output file is too small, processing may have failed")

            self.logger.info(f"Video created successfully: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Error creating video: {str(e)}")
            # Clean up output file if it exists
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

    def cleanup_old_files(self, max_age_days: int = 7):
        """
        Clean up old video files from the output directory.
        
        Args:
            max_age_days: Maximum age of files in days before they are deleted
        """
        import time
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        for filename in os.listdir(self.output_dir):
            file_path = os.path.join(self.output_dir, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Deleted old file: {filename}")
                    except Exception as e:
                        self.logger.error(f"Error deleting file {filename}: {str(e)}")

# Example usage
if __name__ == "__main__":
    # Create processor instance
    processor = VideoProcessor()
    
    # Example subtitle style
    subtitle_style = {
        'size': 24,
        'color': '#ffffff',
        'alpha': 0.5
    }
    
    try:
        # Create video
        output_path = processor.create_final_video(
            video_path="input_video.mp4",
            audio_path="input_audio.mp3",
            subtitle_path="subtitles.srt",
            subtitle_style=subtitle_style
        )
        print(f"Video created successfully: {output_path}")
        
        # Clean up old files
        processor.cleanup_old_files()
        
    except Exception as e:
        print(f"Error: {str(e)}") 