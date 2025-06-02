import os
import requests
import logging
from typing import Optional, Dict, Any
import json
from datetime import datetime
import io
import pysrt
from pydub import AudioSegment
import tempfile
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TTSGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("Eleven Labs API key is not set")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key
        }

    def get_available_voices(self) -> list:
        """Get list of available voices from ElevenLabs"""
        try:
            response = requests.get(f"{self.base_url}/voices", headers=self.headers)
            response.raise_for_status()
            voices = response.json().get("voices", [])
            return [{
                "id": voice["voice_id"],
                "name": voice["name"],
                "category": voice.get("category", "premade"),
                "description": voice.get("labels", {}).get("description", ""),
                "preview_url": voice.get("preview_url", "")
            } for voice in voices]
        except Exception as e:
            logging.error(f"Error fetching voices: {str(e)}")
            raise

    def generate_speech(self, text: str, voice_id: str, output_path: str) -> Dict[str, Any]:
        """
        Generate speech from text using specified voice
        
        Args:
            text (str): Text to convert to speech
            voice_id (str): ElevenLabs voice ID
            output_path (str): Path to save the generated audio
            
        Returns:
            Dict containing generation details
        """
        try:
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            # Save the audio file
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return {
                "status": "success",
                "output_path": output_path,
                "voice_id": voice_id,
                "text_length": len(text),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error generating speech: {str(e)}")
            raise

    def extract_text_from_srt(self, srt_content: str) -> str:
        """Extract plain text from SRT content"""
        try:
            # Split into subtitle blocks
            blocks = srt_content.strip().split('\n\n')
            text_parts = []
            
            for block in blocks:
                lines = block.split('\n')
                if len(lines) >= 3:  # Valid subtitle block has at least 3 lines
                    # The text is after the timing line
                    text = ' '.join(lines[2:])
                    text_parts.append(text)
            
            return ' '.join(text_parts)
        except Exception as e:
            logging.error(f"Error extracting text from SRT: {str(e)}")
            raise

    def _clean_srt_file(self, srt_path: str) -> str:
        logging.info(f"Cleaning SRT file: {srt_path}")
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logging.info(f"Raw SRT file contents before cleaning:\n{content}")
        # Build blocks: a block ends when we see two or more consecutive blank lines
        lines = content.splitlines()
        blocks = []
        block = []
        blank_count = 0
        for line in lines:
            if line.strip() == '':
                blank_count += 1
                if blank_count >= 2:
                    if block:
                        block_no_blanks = [l for l in block if l.strip() != '']
                        if block_no_blanks:
                            blocks.append('\n'.join(block_no_blanks))
                        block = []
                # Don't add blank lines to block
            else:
                blank_count = 0
                block.append(line)
        if block:
            block_no_blanks = [l for l in block if l.strip() != '']
            if block_no_blanks:
                blocks.append('\n'.join(block_no_blanks))
        cleaned_content = '\n\n'.join(blocks) + '\n'
        temp = tempfile.NamedTemporaryFile(delete=False, suffix='.srt', mode='w', encoding='utf-8')
        temp.write(cleaned_content)
        temp.close()
        logging.info(f"Cleaned SRT written to: {temp.name}")
        return temp.name

    def generate_speech_from_srt(self, srt_path: str, output_path: str, voice_id: str) -> dict:
        logging.info(f"Starting TTS generation from SRT: {srt_path}, output: {output_path}, voice: {voice_id}")
        try:
            cleaned_srt = self._clean_srt_file(srt_path)
            logging.info(f"Parsing cleaned SRT: {cleaned_srt}")
            # Print cleaned SRT contents for debugging
            with open(cleaned_srt, 'r', encoding='utf-8') as f:
                cleaned_content = f.read()
            logging.info(f"Cleaned SRT file contents:\n{cleaned_content}")
            subs = pysrt.open(cleaned_srt, encoding='utf-8')
            logging.info(f"Parsed {len(subs)} subtitle segments.")
            combined_audio = AudioSegment.empty()
            last_end_time_ms = 0
            for i, sub in enumerate(subs):
                start_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
                end_ms = (sub.end.hours * 3600 + sub.end.minutes * 60 + sub.end.seconds) * 1000 + sub.end.milliseconds
                text = sub.text_without_tags.strip()
                logging.info(f"Segment {i+1}: {start_ms}ms to {end_ms}ms, text: '{text}'")
                if not text:
                    logging.info(f"Segment {i+1} skipped (empty text)")
                    continue
                silence_duration = start_ms - last_end_time_ms
                if silence_duration > 0:
                    logging.info(f"Adding {silence_duration}ms silence before segment {i+1}")
                    combined_audio += AudioSegment.silent(duration=silence_duration)
                try:
                    audio_bytes = self._generate_speech_bytes(text, voice_id)
                    segment_audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                except Exception as seg_err:
                    logging.error(f"Failed to generate or load audio for segment {i+1}: {seg_err}")
                    raise
                srt_duration = end_ms - start_ms
                actual_duration = len(segment_audio)
                if abs(actual_duration - srt_duration) > 100:
                    if actual_duration > srt_duration:
                        logging.info(f"Trimming segment {i+1} from {actual_duration}ms to {srt_duration}ms")
                        segment_audio = segment_audio[:srt_duration]
                    else:
                        logging.info(f"Padding segment {i+1} with {srt_duration - actual_duration}ms silence")
                        segment_audio += AudioSegment.silent(duration=srt_duration - actual_duration)
                combined_audio += segment_audio
                last_end_time_ms = end_ms
            logging.info(f"Exporting combined audio to {output_path}")
            combined_audio.export(output_path, format="mp3")
            logging.info(f"TTS generation complete: {output_path}")
            return {"status": "success", "output_path": output_path}
        except Exception as e:
            logging.error(f"Error in generate_speech_from_srt: {str(e)}", exc_info=True)
            raise

    def _generate_speech_bytes(self, text: str, voice_id: str) -> bytes:
        logging.info(f"Requesting TTS for text: '{text[:50]}...' (length: {len(text)}) with voice: {voice_id}")
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        logging.info(f"TTS API call successful for text: '{text[:50]}...'")
        return response.content 