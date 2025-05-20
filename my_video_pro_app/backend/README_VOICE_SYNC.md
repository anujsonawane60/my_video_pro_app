# Enhanced Voice Synchronization

This module provides advanced voice synchronization capabilities for better alignment between generated audio and original subtitle timings.

## Features

### 1. Precise Subtitle Timing

- The system parses SRT files with frame-accurate timing information
- Each subtitle segment maintains its exact start and end times
- All timing information is preserved throughout the generation process

### 2. Timing-Preserved TTS

- ElevenLabs API is used to generate high-quality voice for each subtitle segment
- Each segment's audio is generated separately to maintain precise timing control
- Multiple fallback approaches ensure the best possible synchronization

### 3. Audio Alignment Techniques

- **Duration Control**: Generated audio segments are analyzed and adjusted to match the original subtitle duration
- **Time Stretching**: Audio is stretched or compressed using advanced algorithms to match target timing
- **Smart Silence Padding**: When needed, silence is intelligently added at segment boundaries

### 4. Chunking and Reassembly

- Subtitles are split by natural segment boundaries
- Each chunk is processed individually with its own timing constraints
- Final audio is assembled with precise positioning of each segment

## Requirements

- Python 3.6+
- ElevenLabs API key (set in .env file as ELEVENLABS_API_KEY)
- FFmpeg installed on your system
- Required Python packages (see requirements.txt)

For advanced audio alignment features:
- librosa
- numpy
- soundfile

## How to Use

### Basic Usage

```python
from voice_changer import EnhancedSyncVoiceChanger

# Initialize the voice changer
voice_changer = EnhancedSyncVoiceChanger()

# Generate synchronized voice
success = voice_changer.generate_synchronized_voice(
    subtitle_path="path/to/subtitles.srt",
    voice_id="eleven_labs_voice_id",  # Optional, uses default if not specified
    output_filename="output.mp3"
)
```

### Command Line Demo

Run the included demo script:

```bash
python sync_voice_demo.py --srt path/to/subtitles.srt --output output.mp3
```

Optional arguments:
- `--voice VOICE_ID`: Specify ElevenLabs voice ID
- `--stability VALUE`: Voice stability (0.0-1.0, default: 0.5)
- `--similarity VALUE`: Voice similarity boost (0.0-1.0, default: 0.75)
- `--list-voices`: List available ElevenLabs voices and exit

## Synchronization Process

1. **Parse Subtitles**: Extract precise timing information from SRT file
2. **Generate Audio Segments**: Generate audio for each subtitle segment
3. **Adjust Duration**: Match each segment's duration to its subtitle timing
4. **Assemble Final Audio**: Position each segment at its exact start time

## Troubleshooting

- **Missing FFmpeg**: Install FFmpeg and ensure it's in your system PATH
- **API Errors**: Check your ElevenLabs API key and quota
- **Audio Quality Issues**: Adjust stability and similarity parameters
- **Sync Problems**: For difficult cases, consider:
  - Manual fine-tuning in an audio editor
  - Adjusting subtitle timing for problematic segments
  - Breaking longer segments into smaller chunks 