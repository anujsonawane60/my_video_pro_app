import os
import requests
import logging
from typing import Optional, Dict, Any
import json
from datetime import datetime
import tempfile
from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class STSGenerator:
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

    def convert_voice(self, audio_path: str, target_voice_id: str, output_path: str) -> Dict[str, Any]:
        """
        Convert voice in audio file to target voice
        
        Args:
            audio_path (str): Path to input audio file
            target_voice_id (str): ElevenLabs voice ID to convert to
            output_path (str): Path to save the converted audio
            
        Returns:
            Dict containing conversion details
        """
        try:
            # First, convert audio to MP3 if it's not already
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_mp3_path = temp_file.name
            
            audio = AudioSegment.from_file(audio_path)
            audio.export(temp_mp3_path, format="mp3")
            
            # Prepare the API request
            url = f"{self.base_url}/speech-to-speech/{target_voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "xi-api-key": self.api_key
            }
            
            # Read the audio file
            with open(temp_mp3_path, 'rb') as audio_file:
                files = {
                    'audio': ('audio.mp3', audio_file, 'audio/mpeg')
                }
                
                response = requests.post(url, headers=headers, files=files)
                response.raise_for_status()
            
            # Save the converted audio
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            # Clean up temporary file
            os.unlink(temp_mp3_path)
            
            return {
                "status": "success",
                "output_path": output_path,
                "voice_id": target_voice_id,
                "input_duration": len(audio) / 1000.0,  # Convert to seconds
                "converted_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error converting voice: {str(e)}")
            # Clean up temporary file if it exists
            if 'temp_mp3_path' in locals():
                try:
                    os.unlink(temp_mp3_path)
                except:
                    pass
            raise 