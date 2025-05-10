# Video Pro App

A video processing application built with Streamlit that enables users to:
1. Extract audio from videos
2. Generate subtitles automatically using either local Whisper AI or cloud-based AssemblyAI
3. Clean audio by removing filler words like "umm", "uhh", etc.
4. Create a final video with clean audio and subtitles

## Features

- **User-friendly interface**: Easy-to-use web interface for all processing steps
- **Step-by-step workflow**: Process videos in a logical sequence
- **Multiple transcription options**: 
  - Local transcription with Whisper AI (no API key needed)
  - Cloud-based transcription with AssemblyAI (requires API key)
- **Audio cleaning**: Removes common filler words to create cleaner audio
- **Instant preview**: Preview and download at each processing step
- **Diagnostic tools**: Test transcription options to ensure proper functionality

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/video-pro-app.git
   cd video-pro-app
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the Streamlit application:
   ```
   streamlit run app.py
   ```

2. Open your web browser and go to http://localhost:8501

3. Follow the step-by-step interface:
   - Upload a video file
   - Select transcription method (Whisper or AssemblyAI)
   - Extract audio
   - Generate subtitles
   - Clean audio
   - Create final video with clean audio and subtitles

4. Download the processed files at any stage

## System Requirements

- Python 3.8 or higher
- 4GB RAM minimum (8GB or more recommended)
- For GPU acceleration: CUDA-compatible GPU (optional but recommended for faster processing)

## Technical Details

The application uses:
- **Streamlit**: For the web interface
- **MoviePy**: For video processing
- **PyDub**: For audio processing
- **Whisper AI**: For local speech-to-text transcription
- **AssemblyAI**: For cloud-based speech-to-text transcription (requires API key)

## Project Structure

- `app.py` - Main Streamlit application
- `video_processor.py` - Core video processing and transcription class
- `whisper_test.py` - Test script for Whisper transcription
- `assemblyai_test.py` - Test script for AssemblyAI transcription
- `requirements.txt` - Package dependencies

## License

MIT License 