import os
import shutil
import traceback
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
import webrtcvad # Top-level import is fine
import pysrt # Top-level import

class AudioCleaner:
    def __init__(self, audio_path, output_dir, noise_reduction_sensitivity=0.2, vad_aggressiveness=1):
        self.audio_path = audio_path
        self.output_dir = output_dir # General output directory for this cleaner instance
        # Ensure output_dir exists (though it should be created by the caller job logic)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Use unique names for intermediate files to avoid conflicts if multiple instances run concurrently on same output_dir (less likely with job-specific dirs)
        # Or, better, use a temporary directory for intermediates if not specified.
        # For now, assuming output_dir is specific enough or job structure handles uniqueness.
        self.noise_reduced_audio_path = os.path.join(self.output_dir, f"intermediate_noise_reduced_{os.path.basename(audio_path)}")
        self.vad_cleaned_audio_path = os.path.join(self.output_dir, f"intermediate_vad_cleaned_{os.path.basename(audio_path)}")
        
        self.noise_reduction_sensitivity = noise_reduction_sensitivity
        self.vad_aggressiveness = vad_aggressiveness

    def reduce_noise(self, audio_path=None):
        input_audio_to_process = audio_path if audio_path is not None else self.audio_path
        
        if not os.path.exists(input_audio_to_process):
            # This check is important. If audio_path is None, self.audio_path is used.
            # self.audio_path is set in __init__ and should be the primary source audio.
            print(f"Error: Audio file not found for noise reduction: {input_audio_to_process}")
            raise FileNotFoundError(f"Audio file not found for noise reduction: {input_audio_to_process}")
            
        print(f"Applying noise reduction to {input_audio_to_process}")
        try:
            import noisereduce as nr # Keep local to allow graceful failure if not installed
            audio, sr = librosa.load(input_audio_to_process, sr=None)
            
            # Ensure audio is float for noisereduce
            if audio.dtype != np.float32 and audio.dtype != np.float64:
                audio = audio.astype(np.float32) / (np.iinfo(audio.dtype).max if audio.dtype.kind == 'i' else 1.0)


            # noisereduce can handle multi-channel by default
            reduced_noise = nr.reduce_noise(
                y=audio,
                sr=sr,
                stationary=True, # This is hardcoded; frontend has a switch not used here.
                prop_decrease=self.noise_reduction_sensitivity
            )
            sf.write(self.noise_reduced_audio_path, reduced_noise, sr)
            print(f"Noise reduction complete. Saved to {self.noise_reduced_audio_path}")
            return self.noise_reduced_audio_path
        except ImportError:
            print(f"noisereduce library not found. Skipping noise reduction.")
            print(traceback.format_exc())
            # If noise reduction fails, return the original (or input) path to allow VAD to proceed on it
            if os.path.exists(input_audio_to_process): # Ensure it exists before returning
                 shutil.copy2(input_audio_to_process, self.noise_reduced_audio_path) # "Copy" to intermediate path
                 return self.noise_reduced_audio_path
            return input_audio_to_process # Fallback
        except Exception as e:
            print(f"Error during noise reduction: {e}")
            print(traceback.format_exc())
            if os.path.exists(input_audio_to_process):
                 shutil.copy2(input_audio_to_process, self.noise_reduced_audio_path)
                 return self.noise_reduced_audio_path
            return input_audio_to_process # Fallback

    def remove_fillers_with_vad(self, audio_path=None):
        input_audio_to_process = audio_path if audio_path is not None else self.audio_path
        # If called after reduce_noise, audio_path will be self.noise_reduced_audio_path

        if not os.path.exists(input_audio_to_process):
            print(f"Error: Audio file not found for VAD: {input_audio_to_process}")
            raise FileNotFoundError(f"Audio file not found for VAD: {input_audio_to_process}")

        print(f"Removing fillers with VAD from {input_audio_to_process}")
        try:
            # Load as mono, 16kHz as required by typical VAD setups and this code's frame logic
            audio, sr = librosa.load(input_audio_to_process, sr=16000, mono=True) 
            
            if len(audio) == 0:
                print("Warning: Audio for VAD is empty. Skipping VAD.")
                sf.write(self.vad_cleaned_audio_path, audio, sr) # Write empty audio
                return self.vad_cleaned_audio_path

            vad = webrtcvad.Vad(self.vad_aggressiveness)
            frame_duration = 30  # ms
            frame_size = int(sr * frame_duration / 1000) # Samples per frame (e.g., 480 for 16kHz, 30ms)
            
            num_frames = (len(audio) - frame_size) // frame_size # Calculate number of full frames
            if num_frames <= 0 : # handle short audio
                print("Warning: Audio too short for VAD processing. Skipping VAD.")
                shutil.copy2(input_audio_to_process, self.vad_cleaned_audio_path)
                return self.vad_cleaned_audio_path


            frames = [audio[i:i + frame_size] for i in range(0, len(audio) - frame_size +1 , frame_size)] # ensure all audio is processed

            # Convert to 16-bit PCM bytes
            pcm_frames = []
            for frame_audio in frames:
                if len(frame_audio) == frame_size: # ensure frame has correct size
                    # Scale float audio from [-1.0, 1.0] to int16 range
                    int16_frame = (frame_audio * 32767).astype(np.int16)
                    pcm_frames.append(int16_frame.tobytes())

            if not pcm_frames:
                print("Warning: No valid PCM frames generated for VAD. Skipping VAD.")
                shutil.copy2(input_audio_to_process, self.vad_cleaned_audio_path)
                return self.vad_cleaned_audio_path

            frame_speech_status = []
            for frame_bytes in pcm_frames:
                try:
                    is_frame_speech = vad.is_speech(frame_bytes, sr)
                    frame_speech_status.append(is_frame_speech)
                except webrtcvad.Error as e_vad: # Catch specific webrtcvad errors
                    print(f"WebRTC VAD error processing frame: {e_vad}. Marking as non-speech.")
                    print(traceback.format_exc())
                    frame_speech_status.append(False) # Assume non-speech on error
                except Exception as e_gen_vad: # Catch any other unexpected error
                    print(f"Unexpected error during VAD.is_speech: {e_gen_vad}. Marking as non-speech.")
                    print(traceback.format_exc())
                    frame_speech_status.append(False)

            is_speech = False
            speech_frame_count = 0
            silence_frame_count = 0
            min_speech_frames = 3 
            min_silence_frames = 5  
            speech_padding_frames = 2 
            speech_segments = []
            current_speech_start_frame = -1

            for i, is_current_frame_speech in enumerate(frame_speech_status):
                if is_current_frame_speech:
                    speech_frame_count += 1
                    silence_frame_count = 0
                    if not is_speech and speech_frame_count >= min_speech_frames:
                        is_speech = True
                        current_speech_start_frame = max(0, i - speech_frame_count + 1 - speech_padding_frames) # Adjusted start
                else: # current frame is silence
                    silence_frame_count += 1
                    if is_speech and silence_frame_count >= min_silence_frames:
                        # End of a speech segment
                        end_frame = i - silence_frame_count + speech_padding_frames # Adjusted end
                        start_time = current_speech_start_frame * frame_duration / 1000.0
                        end_time = end_frame * frame_duration / 1000.0
                        if end_time > start_time:
                             speech_segments.append((start_time, end_time))
                        is_speech = False
                        speech_frame_count = 0 # Reset for next segment
                    # If not is_speech, silence_frame_count just accumulates
            
            # If speech was active until the end of audio
            if is_speech:
                end_frame = len(frame_speech_status) + speech_padding_frames
                start_time = current_speech_start_frame * frame_duration / 1000.0
                end_time = end_frame * frame_duration / 1000.0
                if end_time > start_time:
                    speech_segments.append((start_time, end_time))

            print(f"Found {len(speech_segments)} speech segments")
            
            # Create a mask for speech segments
            # Mask should be applied to the original 'audio' loaded by this function (at 16kHz mono)
            mask = np.zeros_like(audio, dtype=np.float32) 
            for start_time, end_time in speech_segments:
                start_idx = int(start_time * sr)
                end_idx = min(len(audio), int(end_time * sr))
                if start_idx < end_idx: # Ensure valid segment
                    mask[start_idx:end_idx] = 1.0
            
            audio_masked = audio * mask # Element-wise multiplication
            
            sf.write(self.vad_cleaned_audio_path, audio_masked, sr)
            print(f"VAD-based filler removal complete. Saved to {self.vad_cleaned_audio_path}")
            return self.vad_cleaned_audio_path
        except Exception as e:
            print(f"Error during VAD-based filler removal: {e}")
            print(traceback.format_exc())
            if os.path.exists(input_audio_to_process):
                shutil.copy2(input_audio_to_process, self.vad_cleaned_audio_path)
                return self.vad_cleaned_audio_path
            return input_audio_to_process # Fallback

    def _remove_segments(self, audio: AudioSegment, segments):
        # This method is not used by the clean() flow currently.
        if not segments:
            return audio
        segments.sort(key=lambda x: x[0])
        merged_segments = []
        current_start, current_end = segments[0]
        for start, end in segments[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                merged_segments.append((current_start, current_end))
                current_start, current_end = start, end
        merged_segments.append((current_start, current_end))
        cleaned_audio = AudioSegment.empty()
        last_end = 0
        for start, end in merged_segments:
            start_ms = int(start * 1000)
            end_ms = int(end * 1000)
            if start_ms > last_end:
                cleaned_audio += audio[last_end:start_ms]
            last_end = end_ms
        if last_end < len(audio):
            cleaned_audio += audio[last_end:]
        return cleaned_audio

    def _load_subtitles(self, subtitle_path):
        # This method is not used by the clean() flow currently.
        try:
            print(f"Loading subtitles from {subtitle_path} using pysrt")
            subtitles = pysrt.open(subtitle_path, encoding='utf-8')
            print(f"Successfully loaded {len(subtitles)} subtitle items")
            return subtitles
        except Exception as e:
            print(f"Error loading subtitles with pysrt: {e}")
            traceback.print_exc()
            return None

    def _time_to_seconds(self, time_obj):
        # This method is not used by the clean() flow currently.
        return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000

    def clean(self, output_path=None):
        """
        Run noise reduction and VAD, then save the final cleaned audio to output_path.
        If output_path is None, use self.vad_cleaned_audio_path.
        Returns the path to the cleaned audio file.
        """
        final_output_target = output_path if output_path else self.vad_cleaned_audio_path
        
        try:
            # Step 1: Noise reduction
            # self.audio_path is the initial audio given to the constructor
            noise_reduced_interim_path = self.reduce_noise(self.audio_path) 
            
            # Step 2: VAD-based filler removal (operates on the noise_reduced audio)
            vad_cleaned_interim_path = self.remove_fillers_with_vad(noise_reduced_interim_path)
            
            # Step 3: Copy the result of VAD to the final output_path if specified
            if vad_cleaned_interim_path != final_output_target:
                if not os.path.exists(vad_cleaned_interim_path):
                    # This means VAD step might have had an issue and returned its input.
                    # Or the file it said it created wasn't actually created.
                    raise FileNotFoundError(f"Intermediate VAD cleaned file not found: {vad_cleaned_interim_path}")
                
                os.makedirs(os.path.dirname(final_output_target), exist_ok=True) # Ensure target dir exists
                shutil.copy2(vad_cleaned_interim_path, final_output_target)
                print(f"Final cleaned audio copied to {final_output_target}")
            
            # Clean up intermediate files if they are different from final output
            # Only if they are not the same as self.audio_path (in case a step was skipped and returned original)
            # And if they are not the final_output_target
            if self.noise_reduced_audio_path != self.audio_path and self.noise_reduced_audio_path != final_output_target and os.path.exists(self.noise_reduced_audio_path):
                if self.noise_reduced_audio_path != vad_cleaned_interim_path: # don't delete if it's the input to next step
                    try: os.remove(self.noise_reduced_audio_path)
                    except OSError as e_os: print(f"Could not remove intermediate file {self.noise_reduced_audio_path}: {e_os}")

            if self.vad_cleaned_audio_path != self.audio_path and self.vad_cleaned_audio_path != final_output_target and os.path.exists(self.vad_cleaned_audio_path):
                # If vad_cleaned_interim_path is self.vad_cleaned_audio_path, and it has been copied to final_output_target, it can be removed.
                if vad_cleaned_interim_path == self.vad_cleaned_audio_path and vad_cleaned_interim_path != final_output_target:
                     try: os.remove(self.vad_cleaned_audio_path)
                     except OSError as e_os: print(f"Could not remove intermediate file {self.vad_cleaned_audio_path}: {e_os}")

            return final_output_target

        except Exception as e_clean:
            print(f"Error during the main clean() process: {e_clean}")
            print(traceback.format_exc())
            # In case of a major error in clean(), attempt to return the original audio path
            # The endpoint in main.py will catch this and return a 500 error to frontend.
            raise # Re-raise the exception to be caught by the FastAPI endpoint handler