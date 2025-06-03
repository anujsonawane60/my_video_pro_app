import os
import json
import logging
import subprocess
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path
import ffmpeg

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

class VideoCreator:
    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self.temp_dir = tempfile.mkdtemp()
        logging.info(f"VideoCreator initialized with project_dir: {project_dir}")
        logging.info(f"Temporary directory created at: {self.temp_dir}")
        
    def create_final_video(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: str,
        subtitle_style: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """
        Create final video with custom subtitles and audio.
        
        Args:
            video_path: Path to the base video file
            audio_path: Path to the audio file
            subtitle_path: Path to the subtitle file
            subtitle_style: Dictionary containing subtitle styling options
            output_path: Optional path for the output video
            
        Returns:
            Path to the created video file
        """
        try:
            logging.info("Starting final video creation process")
            logging.info(f"Input video path: {video_path}")
            logging.info(f"Input audio path: {audio_path}")
            logging.info(f"Input subtitle path: {subtitle_path}")
            logging.info(f"Subtitle style: {json.dumps(subtitle_style, indent=2)}")
            
            if not output_path:
                output_path = os.path.join(self.project_dir, 'final_video.mp4')
            logging.info(f"Output path: {output_path}")
            
            # Validate input files
            for path, name in [(video_path, "video"), (audio_path, "audio"), (subtitle_path, "subtitle")]:
                if not os.path.exists(path):
                    raise FileNotFoundError(f"{name.capitalize()} file not found at: {path}")
                logging.info(f"Verified {name} file exists at: {path}")
            
            # Extract video duration
            logging.info("Probing video file for duration")
            probe = ffmpeg.probe(video_path)
            video_duration = float(probe['format']['duration'])
            logging.info(f"Video duration: {video_duration} seconds")
            
            # Determine subtitle format and create appropriate filter
            subtitle_ext = os.path.splitext(subtitle_path)[1].lower()
            logging.info(f"Subtitle file extension: {subtitle_ext}")
            
            # Create the final video using different methods based on subtitle format
            if subtitle_ext == '.srt':
                return self._create_video_with_srt_subtitles(
                    video_path, audio_path, subtitle_path, subtitle_style, output_path
                )
            elif subtitle_ext == '.ass':
                return self._create_video_with_ass_subtitles(
                    video_path, audio_path, subtitle_path, subtitle_style, output_path
                )
            else:
                # Convert to SRT and process
                logging.info("Converting subtitle file to SRT format")
                srt_path = self._convert_to_srt(subtitle_path)
                return self._create_video_with_srt_subtitles(
                    video_path, audio_path, srt_path, subtitle_style, output_path
                )
            
        except Exception as e:
            logging.error(f"Error creating final video: {str(e)}", exc_info=True)
            raise
    
    def _create_video_with_srt_subtitles(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: str,
        subtitle_style: Dict[str, Any],
        output_path: str
    ) -> str:
        """Create video with SRT subtitles using subtitles filter."""
        try:
            logging.info("Creating video with SRT subtitles using subtitles filter")
            
            # Normalize paths for cross-platform compatibility
            # Convert to absolute paths and ensure forward slashes
            subtitle_path_normalized = str(Path(subtitle_path).resolve()).replace('\\', '/')
            video_path_normalized = str(Path(video_path).resolve()).replace('\\', '/')
            audio_path_normalized = str(Path(audio_path).resolve()).replace('\\', '/')
            output_path_normalized = str(Path(output_path).resolve()).replace('\\', '/')
            
            # Remove drive letter prefix for FFmpeg compatibility
            if subtitle_path_normalized[1:3] == ':/':
                subtitle_path_normalized = subtitle_path_normalized[2:]
            if video_path_normalized[1:3] == ':/':
                video_path_normalized = video_path_normalized[2:]
            if audio_path_normalized[1:3] == ':/':
                audio_path_normalized = audio_path_normalized[2:]
            if output_path_normalized[1:3] == ':/':
                output_path_normalized = output_path_normalized[2:]
            
            logging.info(f"Normalized subtitle path: {subtitle_path_normalized}")
            
            # Create subtitle filter options
            subtitle_options = self._create_subtitle_filter_options(subtitle_style)
            
            # Build the filter string with proper escaping
            escaped_path = subtitle_path_normalized.replace("'", "\\'")
            filter_string = f"subtitles='{escaped_path}'"
            if subtitle_options:
                filter_string += f":{subtitle_options}"
            
            logging.info(f"Subtitle filter string: {filter_string}")
            
            # Create FFmpeg streams with normalized paths
            video_input = ffmpeg.input(video_path_normalized)
            audio_input = ffmpeg.input(audio_path_normalized)
            
            # Apply subtitle filter to video
            video_with_subs = video_input.video.filter('subtitles', subtitle_path_normalized, **self._parse_subtitle_options(subtitle_style))
            
            # Combine video with subtitles and new audio
            output = ffmpeg.output(
                video_with_subs,
                audio_input.audio,
                output_path_normalized,
                vcodec='libx264',
                acodec='aac',
                preset='medium',
                crf=23,
                movflags='faststart',
                **{'map_metadata': 0}
            )
            
            # Run the command
            logging.info("Executing FFmpeg command for SRT subtitles")
            ffmpeg.run(output, overwrite_output=True, quiet=False)
            
            if not os.path.exists(output_path):
                raise FileNotFoundError(f"Output video was not created at: {output_path}")
            
            logging.info(f"Video with SRT subtitles created successfully at: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error creating video with SRT subtitles: {str(e)}", exc_info=True)
            raise
    
    def _create_video_with_ass_subtitles(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: str,
        subtitle_style: Dict[str, Any],
        output_path: str
    ) -> str:
        """Create video with ASS subtitles using ass filter."""
        try:
            logging.info("Creating video with ASS subtitles using ass filter")
            
            # Normalize paths
            subtitle_path_normalized = os.path.abspath(subtitle_path).replace('\\', '/')
            
            # Create FFmpeg streams
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(audio_path)
            
            # Apply ASS subtitle filter
            video_with_subs = video_input.video.filter('ass', subtitle_path_normalized)
            
            # Combine video with subtitles and new audio
            output = ffmpeg.output(
                video_with_subs,
                audio_input.audio,
                output_path,
                vcodec='libx264',
                acodec='aac',
                preset='medium',
                crf=23,
                movflags='faststart'
            )
            
            # Run the command
            logging.info("Executing FFmpeg command for ASS subtitles")
            ffmpeg.run(output, overwrite_output=True, quiet=False)
            
            if not os.path.exists(output_path):
                raise FileNotFoundError(f"Output video was not created at: {output_path}")
            
            logging.info(f"Video with ASS subtitles created successfully at: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error creating video with ASS subtitles: {str(e)}", exc_info=True)
            raise
    
    def _parse_subtitle_options(self, style: Dict[str, Any]) -> Dict[str, Any]:
        """Parse subtitle styling options for FFmpeg subtitles filter."""
        options = {}
        
        # Font family
        if 'fontFamily' in style:
            options['force_style'] = f"FontName={style['fontFamily']}"
        
        # Font size
        if 'fontSize' in style:
            font_size = style['fontSize']
            if 'force_style' in options:
                options['force_style'] += f",FontSize={font_size}"
            else:
                options['force_style'] = f"FontSize={font_size}"
        
        # Color
        if 'color' in style:
            color = self._hex_to_ass_color(style['color'])
            if 'force_style' in options:
                options['force_style'] += f",PrimaryColour={color}"
            else:
                options['force_style'] = f"PrimaryColour={color}"
        
        # Add default styling if no force_style was set
        if 'force_style' not in options:
            options['force_style'] = "FontSize=24,PrimaryColour=&H00FFFFFF"
        
        logging.info(f"Parsed subtitle options: {options}")
        return options
    
    def _create_subtitle_filter_options(self, style: Dict[str, Any]) -> str:
        """Create subtitle filter options string."""
        options = []
        
        # Font family
        if 'fontFamily' in style:
            options.append(f"force_style='FontName={style['fontFamily']}'")
        
        # Font size  
        if 'fontSize' in style:
            options.append(f"force_style='FontSize={style['fontSize']}'")
        
        # Color
        if 'color' in style:
            color = self._hex_to_ass_color(style['color'])
            options.append(f"force_style='PrimaryColour={color}'")
        
        return ':'.join(options)
    
    def _convert_to_srt(self, subtitle_path: str) -> str:
        """Convert subtitle file to SRT format if needed."""
        try:
            srt_path = os.path.join(self.temp_dir, 'converted_subtitles.srt')
            
            # Read the original subtitle file
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple conversion for basic subtitle formats
            # This is a basic implementation - you might need more sophisticated parsing
            # depending on your subtitle format
            if content.strip():
                with open(srt_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logging.info(f"Subtitle file converted to SRT: {srt_path}")
                return srt_path
            else:
                raise ValueError("Subtitle file is empty or invalid")
                
        except Exception as e:
            logging.error(f"Error converting subtitle file: {str(e)}")
            raise
    
    def _hex_to_ass_color(self, hex_color: str) -> str:
        """Convert hex color to ASS format (AABBGGRR)."""
        try:
            logging.info(f"Converting hex color {hex_color} to ASS format")
            hex_color = hex_color.lstrip('#')
            
            # Ensure we have a valid 6-character hex color
            if len(hex_color) != 6:
                hex_color = "FFFFFF"  # Default to white
                
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            ass_color = f'&H00{b:02x}{g:02x}{r:02x}'
            logging.info(f"Converted color: {ass_color}")
            return ass_color
            
        except Exception as e:
            logging.warning(f"Error converting color {hex_color}: {str(e)}")
            return '&H00FFFFFF'  # Default to white
    
    def create_video_with_burned_subtitles(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: str,
        subtitle_style: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """
        Alternative method using drawtext filter for more control over subtitle appearance.
        This method burns subtitles directly into the video.
        """
        try:
            logging.info("Creating video with burned-in subtitles using drawtext")
            
            if not output_path:
                output_path = os.path.join(self.project_dir, 'final_video_burned_subs.mp4')
            
            # Parse SRT file to extract subtitle information
            subtitles = self._parse_srt_file(subtitle_path)
            
            # Create video input
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(audio_path)
            
            # Apply drawtext filters for each subtitle
            current_stream = video_input.video
            
            for subtitle in subtitles:
                # Create drawtext filter for this subtitle
                drawtext_options = {
                    'text': subtitle['text'].replace('\n', '\\n'),
                    'fontfile': self._get_font_path(subtitle_style.get('fontFamily', 'Arial')),
                    'fontsize': subtitle_style.get('fontSize', 24),
                    'fontcolor': subtitle_style.get('color', 'white'),
                    'x': '(w-text_w)/2',  # Center horizontally
                    'y': 'h-th-50',      # Position near bottom
                    'enable': f"between(t,{subtitle['start']},{subtitle['end']})"
                }
                
                current_stream = current_stream.filter('drawtext', **drawtext_options)
            
            # Combine with audio and output
            output = ffmpeg.output(
                current_stream,
                audio_input.audio,
                output_path,
                vcodec='libx264',
                acodec='aac',
                preset='medium',
                crf=23,
                movflags='faststart'
            )
            
            logging.info("Executing FFmpeg command for burned subtitles")
            ffmpeg.run(output, overwrite_output=True)
            
            logging.info(f"Video with burned subtitles created at: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error creating video with burned subtitles: {str(e)}", exc_info=True)
            raise
    
    def _parse_srt_file(self, srt_path: str) -> list:
        """Parse SRT subtitle file."""
        subtitles = []
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            blocks = content.split('\n\n')
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # Parse timing
                    time_line = lines[1]
                    start_time, end_time = time_line.split(' --> ')
                    
                    # Convert to seconds
                    start_seconds = self._time_to_seconds(start_time)
                    end_seconds = self._time_to_seconds(end_time)
                    
                    # Get text
                    text = '\n'.join(lines[2:])
                    
                    subtitles.append({
                        'start': start_seconds,
                        'end': end_seconds,
                        'text': text
                    })
            
            logging.info(f"Parsed {len(subtitles)} subtitle blocks")
            return subtitles
            
        except Exception as e:
            logging.error(f"Error parsing SRT file: {str(e)}")
            return []
    
    def _time_to_seconds(self, time_str: str) -> float:
        """Convert SRT time format to seconds."""
        try:
            time_parts = time_str.replace(',', '.').split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            seconds = float(time_parts[2])
            
            return hours * 3600 + minutes * 60 + seconds
        except Exception:
            return 0.0
    
    def _get_font_path(self, font_family: str) -> str:
        """Get system font path for the specified font family."""
        # This is a simplified implementation
        # You might need to expand this based on your system and requirements
        font_paths = {
            'Arial': '/System/Library/Fonts/Arial.ttf',  # macOS
            'Times': '/System/Library/Fonts/Times.ttf',
        }
        
        return font_paths.get(font_family, font_paths.get('Arial', ''))
    
    def cleanup(self):
        """Clean up temporary files."""
        try:
            import shutil
            logging.info(f"Cleaning up temporary directory: {self.temp_dir}")
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logging.info("Cleanup completed successfully")
        except Exception as e:
            logging.warning(f"Error cleaning up temporary files: {str(e)}", exc_info=True) 