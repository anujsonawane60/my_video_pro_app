# Video Processing App

A full-stack application for processing videos with AI transcription, audio cleaning, voice changing, and subtitle generation.

## Architecture

This application consists of two main components:

1. **Backend** - A FastAPI Python application that handles video processing
2. **Frontend** - A React application that provides the user interface

## Features

- Upload videos in various formats (MP4, AVI, MOV, MKV)
- Extract audio from videos
- Generate subtitles using AI (Whisper)
- Clean audio by removing filler words and noise
- Voice changing capabilities with timing preservation
- Interactive audio waveforms with visual comparison
- Create final videos with embedded subtitles

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Node.js 14 or higher
- npm or yarn
- FFmpeg (for video processing)

### Backend Setup

1. Navigate to the backend directory:
```
cd backend
```

2. Create a virtual environment:
```
python -m venv venv
```

3. Activate the virtual environment:
- Windows: `venv\Scripts\activate`
- macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
```
pip install -r requirements.txt
```

5. Start the FastAPI server:
```
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`. You can access the interactive API documentation at `http://localhost:8000/docs`.

### Frontend Setup

1. Navigate to the frontend directory:
```
cd frontend
```

2. Install dependencies:
```
npm install
```

3. Start the development server:
```
npm start
```

The React application will be available at `http://localhost:3000`.

## Using the Application

1. Open the React application in your browser at `http://localhost:3000`
2. Upload a video using the file upload interface
3. Follow the step-by-step process to extract audio, generate subtitles, clean audio, and create the final video
4. Download the processed files at any stage

## API Reference

The backend API provides the following endpoints:

- `POST /upload-video/` - Upload a video file
- `POST /extract-audio/{job_id}` - Extract audio from a video
- `POST /generate-subtitles/{job_id}` - Generate subtitles for a video
- `POST /clean-audio/{job_id}` - Clean the audio by removing noise and filler words
- `POST /voice-change/{job_id}` - Change voice in audio while preserving timing
- `POST /save-edited-subtitles/{job_id}` - Save edited subtitles
- `POST /create-final-video/{job_id}` - Create a final video with clean audio and subtitles
- `GET /job-status/{job_id}` - Get the status of a processing job
- `GET /video-info/{job_id}` - Get information about a video
- `GET /download/{job_id}/{file_type}` - Download a processed file

## Project Structure

### Backend
- `main.py` - FastAPI application with endpoint definitions
- `video_processor.py` - Core video processing functionality
- `voice_changer.py` - Voice changing capabilities 
- `uploads/` - Directory for uploaded video files
- `outputs/` - Directory for processed files

### Frontend
- `src/components/` - React components
- `src/pages/` - Page components
- `src/services/` - API service layers

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [FFmpeg](https://ffmpeg.org/) for video processing
- [OpenAI Whisper](https://github.com/openai/whisper) for transcription
- [ElevenLabs](https://elevenlabs.io/) for voice changing capabilities
- [WaveSurfer.js](https://wavesurfer-js.org/) for audio visualization
- [React](https://reactjs.org/) for the frontend
- [FastAPI](https://fastapi.tiangolo.com/) for the backend API 