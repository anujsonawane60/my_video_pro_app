import os
import requests
import logging
from typing import Optional, Dict, Any
import json
from datetime import datetime

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