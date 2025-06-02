import os
import traceback
import shutil
import subprocess
import torch
import whisper
import numpy as np
from pydub import AudioSegment
from typing import List, Dict, Any

class SubtitleGenerator:
    def __init__(self, audio_path, video_path, output_dir, subtitles_path, language="en", whisper_model_size="base", debug_mode=False):
        self.audio_path = audio_path
        self.video_path = video_path
        self.output_dir = output_dir
        self.subtitles_path = subtitles_path
        self.language = language
        self.whisper_model_size = whisper_model_size
        self.debug_mode = debug_mode

    def generate_subtitles(self) -> str:
        # Check if audio has been extracted
        if not os.path.exists(self.audio_path):
            print(f"Audio not yet extracted, extracting now... Path: {self.audio_path}")
            return self._create_basic_subtitles()
        if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) < 100:
            print(f"Audio file invalid or too small: {self.audio_path}, size: {os.path.getsize(self.audio_path) if os.path.exists(self.audio_path) else 'N/A'}")
            return self._create_basic_subtitles()
        print(f"Starting subtitle generation process for: {self.audio_path} (size: {os.path.getsize(self.audio_path)})")
        success = False
        try:
            print("Using Whisper Python API for transcription...")
            success = self._generate_subtitles_with_api()
            if os.path.exists(self.subtitles_path):
                with open(self.subtitles_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                print(f"Subtitle file content (first 200 chars): {content[:200]}")
                if len(content) > 50 and not content.startswith("1\n00:00:00,000 --> 00:00:05,000\nError generating"):
                    return self.subtitles_path
            if not success:
                print("Whisper transcription did not succeed, using fallback.")
                return self._create_basic_subtitles()
            return self.subtitles_path
        except Exception as e:
            print(f"Error during subtitle generation: {e}")
            traceback.print_exc()
            return self._create_basic_subtitles()

    def _generate_subtitles_with_api(self) -> bool:
        try:
            print(f"Loading Whisper model: {self.whisper_model_size} ...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Using device: {device}")
            if device == "cuda":
                print(f"CUDA Device Name: {torch.cuda.get_device_name(0)}")
                print(f"CUDA Version: {torch.version.cuda}")
            model = whisper.load_model(self.whisper_model_size, device=device)
            print(f"Model {self.whisper_model_size} loaded successfully.")
            print(f"Transcribing {self.audio_path} ...")
            result = model.transcribe(
                self.audio_path,
                language=self.language,
                verbose=True,
                fp16=torch.cuda.is_available(),
                task="transcribe"
            )
            print(f"Transcription result: Detected language: {result.get('language', 'unknown')}")
            if not result or "segments" not in result or not result["segments"]:
                print("No segments found in Whisper result.")
                return False
            print("Generating SRT file ...")
            with open(self.subtitles_path, "w", encoding="utf-8") as f:
                subtitle_data = self._write_simple_srt(result["segments"], f)
            if subtitle_data:
                return subtitle_data  # Return the subtitle data
            print(f"SRT file saved to: {self.subtitles_path}")
            return True
        except Exception as e:
            print(f"Error during Whisper transcription: {e}")
            traceback.print_exc()
            return False

    def _create_basic_subtitles(self) -> str:
        print("Creating basic subtitles as fallback...")
        duration = 5  # fallback duration
        with open(self.subtitles_path, "w", encoding="utf-8") as f:
            f.write("1\n")
            f.write("00:00:00,000 --> 00:00:05,000\n")
            f.write("[Generated subtitles unavailable - please try with a different model size]")
        print("Basic subtitles created as fallback")
        return self.subtitles_path

    def _format_timestamp(self, seconds: float) -> str:
        import datetime
        delta = datetime.timedelta(seconds=seconds)
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int(delta.microseconds / 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
    
    def _write_simple_srt(self, segments: List[Dict[str, Any]], file) -> List[Dict[str, str]]:
        subtitle_data = []
        for i, segment in enumerate(segments):
            start_time = self._format_timestamp(segment['start'])
            end_time = self._format_timestamp(segment['end'])
            text = segment['text'].strip()
            subtitle_data.append({"index": i + 1, "start": start_time, "end": end_time, "text": text})
            file.write(f"{i + 1}\n")
            file.write(f"{start_time} --> {end_time}\n")
            file.write(f"{text}\n\n")
        return subtitle_data

    def _direct_transcribe_with_command_line(self) -> bool:
        try:
            import subprocess
            import torch
            print("Attempting transcription using command line whisper...")
            try:
                result = subprocess.run([
                    "whisper", "--help"
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                if result.returncode != 0:
                    print("Command line whisper not properly installed.")
                    return False
            except (subprocess.SubprocessError, FileNotFoundError):
                print("Command line whisper not installed or not in PATH.")
                return False
            device_flag = "--device cuda" if torch.cuda.is_available() else "--device cpu"
            try:
                cmd = [
                    "whisper",
                    self.audio_path,
                    "--model", self.whisper_model_size,
                    "--language", self.language,
                    "--output_dir", self.output_dir,
                    "--output_format", "srt"
                ]
                cmd.extend(device_flag.split())
                print(f"Running command: {' '.join(cmd)}")
                timeout = 300
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
                if result.returncode != 0:
                    print(f"Command failed with exit code {result.returncode}")
                    print(f"Error output: {result.stderr}")
                    return False
            except subprocess.TimeoutExpired:
                print(f"Command timed out after {timeout} seconds")
                return False
            except Exception as e:
                print(f"Command execution failed: {e}")
                return False
            srt_files = [f for f in os.listdir(self.output_dir) if f.endswith('.srt')]
            if srt_files:
                generated_srt = os.path.join(self.output_dir, srt_files[0])
                if os.path.exists(generated_srt) and os.path.getsize(generated_srt) > 0:
                    with open(generated_srt, 'r', encoding='utf-8') as src, open(self.subtitles_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                    print("Command line transcription successful!")
                    return True
            print("Command line transcription attempt did not produce usable subtitles.")
            return False
        except Exception as e:
            print(f"Command line transcription failed: {e}")
            return False

    def _transcribe_marathi_with_chunking(self) -> bool:
        try:
            print(f"Transcribing Marathi audio with improved chunking...")
            audio = AudioSegment.from_file(self.audio_path)
            duration_ms = len(audio)
            chunk_size_ms = 30 * 1000
            chunks_dir = os.path.join(self.output_dir, "marathi_chunks")
            os.makedirs(chunks_dir, exist_ok=True)
            chunks = []
            for i in range(0, len(audio), chunk_size_ms):
                chunk = audio[i:min(i + chunk_size_ms, len(audio))]
                chunk_path = os.path.join(chunks_dir, f"chunk_{i//chunk_size_ms}.wav")
                chunk.export(chunk_path, format="wav")
                chunks.append({
                    "path": chunk_path,
                    "start_ms": i,
                    "end_ms": min(i + chunk_size_ms, len(audio))
                })
            print(f"Split audio into {len(chunks)} chunks for Marathi transcription")
            import whisper
            model_size = "small"
            try:
                model = whisper.load_model(model_size)
            except Exception as e:
                print(f"Error loading 'small' model: {e}")
                model = whisper.load_model("base")
            all_segments = []
            for i, chunk in enumerate(chunks):
                print(f"Processing Marathi chunk {i+1}/{len(chunks)}...")
                try:
                    chunk_audio = self._load_audio_for_whisper(chunk["path"])
                    result = model.transcribe(
                        chunk_audio,
                        language="mr",
                        task="transcribe",
                        fp16=False,
                        verbose=True
                    )
                    offset_ms = chunk["start_ms"]
                    offset_sec = offset_ms / 1000
                    if "segments" in result:
                        for segment in result["segments"]:
                            segment["start"] += offset_sec
                            segment["end"] += offset_sec
                            all_segments.append(segment)
                    elif "text" in result and result["text"]:
                        segment = {
                            "start": offset_sec,
                            "end": offset_sec + (chunk["end_ms"] - chunk["start_ms"]) / 1000,
                            "text": result["text"]
                        }
                        all_segments.append(segment)
                except Exception as e:
                    print(f"Error processing Marathi chunk {i+1}: {e}")
            if all_segments:
                all_segments.sort(key=lambda x: x["start"])
                with open(self.subtitles_path, "w", encoding="utf-8") as f:
                    self._write_simple_srt(all_segments, f)
                if os.path.getsize(self.subtitles_path) > 100:
                    print(f"Successfully wrote Marathi subtitles to {self.subtitles_path}")
                    return True
            return False
        except Exception as e:
            print(f"Error in Marathi chunked transcription: {e}")
            traceback.print_exc()
            return False

    def _direct_marathi_transcribe_with_command_line(self) -> bool:
        try:
            import subprocess
            import torch
            print("Attempting Marathi transcription using command line whisper...")
            try:
                result = subprocess.run([
                    "whisper", "--help"
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                if result.returncode != 0:
                    print("Command line whisper not properly installed.")
                    return False
            except (subprocess.SubprocessError, FileNotFoundError):
                print("Command line whisper not installed or not in PATH.")
                return False
            device_flag = "--device cuda" if torch.cuda.is_available() else "--device cpu"
            model_to_use = "small"
            if self.whisper_model_size in ["medium", "large"]:
                model_to_use = self.whisper_model_size
            try:
                cmd = [
                    "whisper",
                    self.audio_path,
                    "--model", model_to_use,
                    "--language", "mr",
                    "--output_dir", self.output_dir,
                    "--output_format", "srt",
                    "--task", "transcribe",
                    "--verbose", "True"
                ]
                cmd.extend(device_flag.split())
                print(f"Running command for Marathi: {' '.join(cmd)}")
                timeout = 600
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
                if result.returncode != 0:
                    print(f"Command failed with exit code {result.returncode}")
                    print(f"Error output: {result.stderr}")
                    return False
                print(f"Command output: {result.stdout}")
            except subprocess.TimeoutExpired:
                print(f"Command timed out after {timeout} seconds")
                return False
            except Exception as e:
                print(f"Command execution failed: {e}")
                return False
            srt_files = [f for f in os.listdir(self.output_dir) if f.endswith('.srt')]
            if srt_files:
                generated_srt = os.path.join(self.output_dir, srt_files[0])
                if os.path.exists(generated_srt) and os.path.getsize(generated_srt) > 0:
                    with open(generated_srt, 'r', encoding='utf-8') as src, open(self.subtitles_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                    print("Command line Marathi transcription successful!")
                    return True
            print("Command line Marathi transcription attempt did not produce usable subtitles.")
            return False
        except Exception as e:
            print(f"Command line Marathi transcription failed: {e}")
            return False

    def _generate_subtitles_with_assemblyai(self) -> bool:
        # AssemblyAI integration removed
        print("AssemblyAI integration removed. Only Whisper is supported.")
        return False
