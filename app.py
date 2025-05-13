import streamlit as st
import os
import tempfile
import time
import shutil
from video_processor import VideoProcessor
import torch
import assemblyai as aai
import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

# Set page configuration
st.set_page_config(
    page_title="Video Processing App",
    page_icon="🎬",
    layout="wide"
)

# Add custom CSS for better styling
st.markdown("""
<style>
    .main { padding: 1rem 1rem; }
    .stButton button { min-width: 120px; }
    .success-box { padding: 1rem; background-color: #e6f7e6; border-radius: 5px; }
    .video-box { padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# Create directory for saved files
output_dir = "app_output"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Initialize session state variables
if 'processor' not in st.session_state:
    st.session_state.processor = None
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'temp_video_path' not in st.session_state:
    st.session_state.temp_video_path = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'saved_audio_path' not in st.session_state:
    st.session_state.saved_audio_path = None
if 'saved_subtitle_path' not in st.session_state:
    st.session_state.saved_subtitle_path = None
if 'saved_cleaned_audio_path' not in st.session_state:
    st.session_state.saved_cleaned_audio_path = None
if 'saved_final_video_path' not in st.session_state:
    st.session_state.saved_final_video_path = None
if 'edited_subtitle_path' not in st.session_state:
    st.session_state.edited_subtitle_path = None
if 'show_logs' not in st.session_state:
    st.session_state.show_logs = False

# Function to add logs
def add_log(message):
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    # Keep logs manageable
    if len(st.session_state.logs) > 100:
        st.session_state.logs = st.session_state.logs[-100:]

# Function to safely copy file to output directory
def safe_copy_file(source_path, file_type):
    try:
        if source_path and os.path.exists(source_path):
            filename = os.path.basename(source_path)
            # Generate unique filename based on timestamp
            base, ext = os.path.splitext(filename)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            new_filename = f"{file_type}_{timestamp}{ext}"
            destination = os.path.join(output_dir, new_filename)

            # Copy the file
            shutil.copy2(source_path, destination)
            add_log(f"Copied {file_type} to {destination}")
            return destination
    except Exception as e:
        add_log(f"Error copying file: {e}")
    return None

# Function to display audio waveform
def display_waveform(audio_path):
    try:
        y, sr = librosa.load(audio_path)
        fig, ax = plt.subplots()
        librosa.display.waveshow(y, sr=sr, ax=ax)
        ax.set(title='Audio Waveform')
        ax.label_outer()
        st.pyplot(fig)
    except Exception as e:
        st.error(f"Error displaying waveform: {e}")
        add_log(f"Error displaying waveform: {e}")

# Main title
st.title("🎬 Video Processing App")
st.write("Upload a video and process it with subtitles and clean audio")

# Sidebar for settings
with st.sidebar:
    st.title("Settings")

    # Transcription method selection
    st.subheader("Transcription Method")
    transcription_method = st.radio(
        "Select method:",
        ["Whisper (Local)", "AssemblyAI (Cloud)"]
    )

    # Set variables based on selection
    use_assemblyai = transcription_method == "AssemblyAI (Cloud)"

    # Language selection
    st.subheader("Language")
    language = st.selectbox(
        "Select language:",
        ["English", "Marathi"],
        index=0
    )

    # Map language selection to language code
    language_code = "en" if language == "English" else "mr"

    # Model selection for Whisper
    if not use_assemblyai:
        st.subheader("Whisper Settings")
        whisper_model_size = st.selectbox(
            "Model Size",
            ["tiny", "base", "small", "medium"],
            index=1
        )

    # API key for AssemblyAI
    if use_assemblyai:
        st.subheader("AssemblyAI Settings")
        assemblyai_api_key = st.text_input(
            "API Key",
            value="YOUR_ASSEMBLYAI_API_KEY",  # Replace with your actual API key
            type="password"
        )

    # Audio Cleaning Settings
    st.subheader("Audio Cleaning")
    enable_noise_reduction = st.checkbox("Enable Noise Reduction", value=True)

    if enable_noise_reduction:
        noise_reduction_sensitivity = st.slider(
            "Noise Reduction Sensitivity",
            min_value=0.0,
            max_value=1.0,
            value=0.2,
            step=0.05,
            help="Higher values remove more noise but may affect speech quality"
        )

    enable_vad_cleaning = st.checkbox("Use Advanced Filler Removal (VAD)", value=True)

    if enable_vad_cleaning:
        vad_aggressiveness = st.select_slider(
            "VAD Aggressiveness",
            options=[0, 1, 2, 3],
            value=1,
            help="Higher values are more aggressive at detecting speech (0=least, 3=most)"
        )

    # Show debug logs option
    st.subheader("Debug Options")
    show_logs = st.checkbox("Show Debug Logs", value=True)
    debug_mode = st.checkbox("Enable Debug Mode", value=True,
                                 help="Enable detailed logs to diagnose issues")

    # Advanced options expander for Video Creation
    with st.expander("Video Creation Settings", expanded=False):
        use_direct_ffmpeg = st.checkbox("Use Direct FFmpeg Method", value=True,
                                             help="Use FFmpeg directly for more reliable video creation")

        font_size = st.slider("Subtitle Font Size", 18, 36, 24)

        subtitle_color = st.selectbox(
            "Subtitle Text Color",
            ["white", "yellow", "cyan"],
            index=0
        )

        subtitle_bg_opacity = st.slider(
            "Subtitle Background Opacity",
            min_value=0,
            max_value=100,
            value=80
        )

# Main content area
main_col1, main_col2 = st.columns([2, 1])

with main_col1:
    # Video upload section
    st.subheader("Upload Video")
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "avi", "mov", "mkv"])

    # If a file is uploaded
    if uploaded_file is not None:
        # Save to a persistent location
        upload_time = time.strftime("%Y%m%d_%H%M%S")
        file_ext = os.path.splitext(uploaded_file.name)[1]
        video_filename = f"input_video_{upload_time}{file_ext}"
        video_path = os.path.join(output_dir, video_filename)

        with open(video_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        # Store file path
        st.session_state.temp_video_path = video_path
        add_log(f"Saved uploaded video to {video_path}")

        # Initialize processor
        if use_assemblyai:
            if not assemblyai_api_key or assemblyai_api_key == "YOUR_ASSEMBLYAI_API_KEY":
                st.error("Please enter your AssemblyAI API key in the sidebar settings.")
                st.stop()
            st.session_state.processor = VideoProcessor(
                video_path,
                whisper_model_size="base",
                use_assemblyai=True,
                assemblyai_api_key=assemblyai_api_key,
                debug_mode=debug_mode,
                language=language_code
            )
        else:
            st.session_state.processor = VideoProcessor(
                video_path,
                whisper_model_size=whisper_model_size,
                use_assemblyai=False,
                debug_mode=debug_mode,
                language=language_code
            )

        # Set audio cleaning options
        if 'enable_noise_reduction' in locals():
            st.session_state.processor.noise_reduction_enabled = enable_noise_reduction
            if enable_noise_reduction and 'noise_reduction_sensitivity' in locals():
                st.session_state.processor.noise_reduction_sensitivity = noise_reduction_sensitivity

        if 'enable_vad_cleaning' in locals():
            st.session_state.processor.vad_cleaning_enabled = enable_vad_cleaning
            if enable_vad_cleaning and 'vad_aggressiveness' in locals():
                st.session_state.processor.vad_aggressiveness = vad_aggressiveness

        # Set subtitle options
        if 'font_size' in locals():
            st.session_state.processor.subtitle_font_size = font_size
        if 'subtitle_color' in locals():
            st.session_state.processor.subtitle_color = subtitle_color
        if 'subtitle_bg_opacity' in locals():
            st.session_state.processor.subtitle_bg_opacity = subtitle_bg_opacity
        if 'use_direct_ffmpeg' in locals():
            st.session_state.processor.use_direct_ffmpeg = use_direct_ffmpeg

        # Show uploaded video
        st.video(video_path)

        # Processing steps
        st.subheader("Processing Steps")

        # Step 1: Extract Audio
        step1_col1, step1_col2 = st.columns([1, 2])
        with step1_col1:
            if st.button("1. Extract Audio"):
                with st.spinner("Extracting audio..."):
                    try:
                        add_log("Starting audio extraction")
                        audio_path = st.session_state.processor.extract_audio()

                        # Copy audio to output directory
                        saved_path = safe_copy_file(audio_path, "audio")
                        if saved_path:
                            st.session_state.saved_audio_path = saved_path
                            st.session_state.current_step = 1
                            st.success("Audio extracted!")
                        else:
                            st.error("Failed to save extracted audio")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        add_log(f"Error: {str(e)}")

        with step1_col2:
            if st.session_state.current_step >= 1 and st.session_state.saved_audio_path:
                try:
                    # Use saved audio path instead of temporary one
                    st.audio(st.session_state.saved_audio_path)
                    display_waveform(st.session_state.saved_audio_path)
                except Exception as e:
                    st.error(f"Error playing audio: {str(e)}")
                    add_log(f"Error playing audio: {str(e)}")

        # Step 2: Generate and Edit Subtitles
        if st.session_state.current_step >= 1:
            st.subheader("2. Generate and Edit Subtitles")
            if st.button("Generate Subtitles"):
                with st.spinner("Generating subtitles... This may take a while"):
                    try:
                        add_log("Starting subtitle generation")
                        subtitle_path = st.session_state.processor.generate_subtitles()

                        # Copy subtitle file to output directory
                        saved_path = safe_copy_file(subtitle_path, "subtitles")
                        if saved_path:
                            st.session_state.saved_subtitle_path = saved_path
                            st.session_state.current_step = 2
                            st.success("Subtitles generated!")
                        else:
                            st.error("Failed to save subtitles")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        add_log(f"Error: {str(e)}")

            if st.session_state.current_step >= 2 and st.session_state.saved_subtitle_path:
                try:
                    # Show subtitle preview from saved file
                    with open(st.session_state.saved_subtitle_path, 'r', encoding='utf-8') as f:
                        subtitle_content = f.read()

                    # Create two columns for original and editable subtitles
                    sub_col1, sub_col2 = st.columns(2)

                    with sub_col1:
                        st.subheader("Original Subtitles")
                        st.text_area("Original", subtitle_content, height=300, disabled=True, key="original_subtitles")

                    with sub_col2:
                        st.subheader("Edit Subtitles")
                        st.session_state.editable_subtitles = st.text_area(
                            "Editable",
                            subtitle_content,
                            height=300,
                            key="editable_subtitle_area"
                        )

                        # Add button to save edited subtitles
                        if st.button("Save Edited Subtitles"):
                            try:
                                # Generate a filename for edited subtitles
                                edited_subtitle_path = os.path.join(output_dir, f"edited_subtitles_{time.strftime('%Y%m%d_%H%M%S')}.srt")

                                # Save the edited subtitles
                                with open(edited_subtitle_path, 'w', encoding='utf-8') as f:
                                    f.write(st.session_state.editable_subtitles)

                                # Store the path in session state for use in video creation
                                st.session_state.edited_subtitle_path = edited_subtitle_path
                                st.success(f"Edited subtitles saved to {edited_subtitle_path}")
                            except Exception as e:
                                st.error(f"Error saving edited subtitles: {str(e)}")
                                add_log(f"Error saving edited subtitles: {str(e)}")

                except Exception as e:
                    st.error(f"Error displaying subtitles: {str(e)}")
                    add_log(f"Error displaying subtitles: {str(e)}")

        # Step 3: Clean Audio
        if st.session_state.current_step >= 2:
            step3_col1, step3_col2 = st.columns([1, 2])
            with step3_col1:
                if st.button("3. Clean Audio"):
                    with st.spinner("Cleaning audio..."):
                        try:
                            add_log("Starting audio cleaning")
                            cleaned_audio_path = st.session_state.processor.clean_audio()

                            # Copy cleaned audio to output directory
                            saved_path = safe_copy_file(cleaned_audio_path, "cleaned_audio")
                            if saved_path:
                                st.session_state.saved_cleaned_audio_path = saved_path
                                st.session_state.current_step = 3
                                st.success("Audio cleaned!")
                            else:
                                st.error("Failed to save cleaned audio")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            add_log(f"Error: {str(e)}")

            with step3_col2:
                if st.session_state.current_step >= 3 and st.session_state.saved_cleaned_audio_path:
                    try:
                        # Use saved clean audio path
                        st.audio(st.session_state.saved_cleaned_audio_path)
                        display_waveform(st.session_state.saved_cleaned_audio_path)
                    except Exception as e:
                        st.error(f"Error playing cleaned audio: {str(e)}")
                        add_log(f"Error playing cleaned audio: {str(e)}")

        # Step 4: Create Final Video
        if st.session_state.current_step >= 3:
            step4_col1, step4_col2 = st.columns([1, 1])
            with step4_col1:
                if st.button("4. Create Final Video"):
                    with st.spinner("Creating final video with subtitles and clean audio..."):
                        try:
                            add_log("Creating final video")

                            # Show progress message
                            progress_placeholder = st.empty()
                            progress_placeholder.info("Step 1/3: Checking for required files...")

                            # Check for required files
                            video_path_ok = os.path.exists(st.session_state.temp_video_path)
                            audio_path_ok = False
                            subtitle_path_ok = False
                            
                            # Check for audio file
                            if hasattr(st.session_state, 'saved_cleaned_audio_path') and st.session_state.saved_cleaned_audio_path:
                                audio_path_ok = os.path.exists(st.session_state.saved_cleaned_audio_path)
                                add_log(f"Found cleaned audio at {st.session_state.saved_cleaned_audio_path}")
                            elif hasattr(st.session_state, 'saved_audio_path') and st.session_state.saved_audio_path:
                                audio_path_ok = os.path.exists(st.session_state.saved_audio_path)
                                add_log(f"Found original audio at {st.session_state.saved_audio_path}")
                            
                            # If no audio is found, try to extract it
                            if not audio_path_ok and video_path_ok:
                                add_log("No audio found, will attempt to extract during video creation")
                            
                            # Check for subtitle file
                            subtitle_path_to_use = None
                            if "edited_subtitle_path" in st.session_state and os.path.exists(st.session_state.edited_subtitle_path):
                                subtitle_path_to_use = st.session_state.edited_subtitle_path
                                subtitle_path_ok = True
                                add_log(f"Using edited subtitles for final video: {subtitle_path_to_use}")
                            elif hasattr(st.session_state, 'saved_subtitle_path') and st.session_state.saved_subtitle_path and os.path.exists(st.session_state.saved_subtitle_path):
                                subtitle_path_to_use = st.session_state.saved_subtitle_path
                                subtitle_path_ok = True
                                add_log(f"Using original subtitles for final video: {subtitle_path_to_use}")
                            else:
                                add_log("No subtitle file found, video will be created without subtitles")
                            
                            # Update progress
                            progress_placeholder.info("Step 2/3: Processing video...")
                            
                            # Pass the subtitle path to the processor
                            final_video_path = st.session_state.processor.create_final_video(subtitle_path_to_use)
                            
                            # Update progress
                            progress_placeholder.info("Step 3/3: Saving final video...")
                            
                            # Check if the final video was created successfully
                            if os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 1000000:
                                # Copy final video to output directory
                                saved_path = safe_copy_file(final_video_path, "final_video")
                                if saved_path:
                                    st.session_state.saved_final_video_path = saved_path
                                    st.session_state.current_step = 4
                                    st.session_state.processing_complete = True
                                    progress_placeholder.success("Video created successfully!")
                                else:
                                    progress_placeholder.error("Failed to save final video to output directory")
                            else:
                                # Try direct FFmpeg method if it failed
                                if 'use_direct_ffmpeg' in locals() and use_direct_ffmpeg:
                                    progress_placeholder.warning("Standard method failed, trying direct FFmpeg approach...")
                                    
                                    # Set option to force FFmpeg use
                                    st.session_state.processor.use_direct_ffmpeg = True
                                    
                                    # Try again with FFmpeg directly
                                    final_video_path = st.session_state.processor.create_final_video(subtitle_path_to_use)
                                    
                                    if os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 1000000:
                                        # Copy final video to output directory
                                        saved_path = safe_copy_file(final_video_path, "final_video")
                                        if saved_path:
                                            st.session_state.saved_final_video_path = saved_path
                                            st.session_state.current_step = 4
                                            st.session_state.processing_complete = True
                                            progress_placeholder.success("Video created successfully with FFmpeg!")
                                        else:
                                            progress_placeholder.error("Failed to save final video to output directory")
                                    else:
                                        progress_placeholder.error("Final video creation failed even with FFmpeg")
                                else:
                                    progress_placeholder.error("Final video creation failed or produced invalid file")
                        except FileNotFoundError as e:
                            st.error(f"Error: {str(e)}")
                            add_log(f"Error: {str(e)}")
                            st.info("Make sure you complete steps 1-3 before creating the final video.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            add_log(f"Error: {str(e)}")
                            st.info("Try completing steps 1-3 again to ensure all files are properly created.")
            
            with step4_col2:
                # Show message about what's happening
                st.info("This step will create a final video with clean audio and embedded subtitles.")
            
            # Show final video
            if st.session_state.processing_complete and st.session_state.saved_final_video_path:
                try:
                    st.subheader("Final Video")
                    st.video(st.session_state.saved_final_video_path)
                    
                    # Download button
                    with open(st.session_state.saved_final_video_path, "rb") as file:
                        btn = st.download_button(
                            label="Download Video",
                            data=file,
                            file_name="processed_video.mp4",
                            mime="video/mp4"
                        )
                except Exception as e:
                    st.error(f"Error displaying final video: {str(e)}")
                    add_log(f"Error displaying final video: {str(e)}")

with main_col2:
    # Video information panel
    if st.session_state.processor is not None:
        st.subheader("Video Information")
        video_info = st.session_state.processor.get_video_info()
        st.write(f"Duration: {video_info['duration']:.2f} seconds")
        st.write(f"Resolution: {video_info['width']}x{video_info['height']}")
        st.write(f"FPS: {video_info['fps']:.2f}")
        
        # Progress indicator
        st.subheader("Progress")
        total_steps = 4
        st.progress(st.session_state.current_step / total_steps)
        st.write(f"Step {st.session_state.current_step} of {total_steps} completed")
    
    # Show logs if enabled
    if show_logs and st.session_state.logs:
        st.subheader("Debug Logs")
        log_text = "\n".join(st.session_state.logs)
        st.text_area("Logs", log_text, height=400)

# Instructions if no file is uploaded
if uploaded_file is None:
    st.info("👆 Please upload a video file to begin processing")
    
    # Show sample output
    st.subheader("How it works")
    st.write("""
    1. Upload a video file
    2. Extract audio from the video
    3. Generate subtitles using Whisper AI or AssemblyAI
    4. Clean the audio by removing filler words
    5. Create a final video with clean audio and subtitles
    """) 
    
    # Show language support information
    st.subheader("Language Support")
    st.write("""
    This app supports generating subtitles in:
    - English (Default)
    - Marathi (मराठी)
    
    **For Marathi videos:**
    - Select 'Marathi' from the language dropdown in the settings sidebar
    - The app uses advanced chunking with OpenAI Whisper for better Marathi recognition
    - For best results, use clear audio with minimal background noise
    """) 