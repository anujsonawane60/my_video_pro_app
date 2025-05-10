import streamlit as st
import os
import tempfile
import time
import shutil
from video_processor import VideoProcessor
import torch
import assemblyai as aai

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
            value="7c38a180f4304cef8eb639f3745a6f33",
            type="password"
        )
    
    # Show debug logs option
    st.subheader("Debug Options")
    show_logs = st.checkbox("Show Debug Logs")

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
            st.session_state.processor = VideoProcessor(
                video_path,
                whisper_model_size="base",
                use_assemblyai=True,
                assemblyai_api_key=assemblyai_api_key
            )
        else:
            st.session_state.processor = VideoProcessor(
                video_path,
                whisper_model_size=whisper_model_size,
                use_assemblyai=False
            )
        
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
                except Exception as e:
                    st.error(f"Error playing audio: {str(e)}")
                    add_log(f"Error playing audio: {str(e)}")
        
        # Step 2: Generate Subtitles
        if st.session_state.current_step >= 1:
            step2_col1, step2_col2 = st.columns([1, 2])
            with step2_col1:
                if st.button("2. Generate Subtitles"):
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
            
            with step2_col2:
                if st.session_state.current_step >= 2 and st.session_state.saved_subtitle_path:
                    try:
                        # Show subtitle preview from saved file
                        with open(st.session_state.saved_subtitle_path, 'r', encoding='utf-8') as f:
                            subtitle_content = f.read()
                        st.text_area("Subtitle Preview", subtitle_content, height=100)
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
                    except Exception as e:
                        st.error(f"Error playing cleaned audio: {str(e)}")
                        add_log(f"Error playing cleaned audio: {str(e)}")
        
        # Step 4: Create Final Video
        if st.session_state.current_step >= 3:
            if st.button("4. Create Final Video"):
                with st.spinner("Creating final video with subtitles and clean audio..."):
                    try:
                        add_log("Creating final video")
                        final_video_path = st.session_state.processor.create_final_video()
                        
                        # Copy final video to output directory
                        saved_path = safe_copy_file(final_video_path, "final_video")
                        if saved_path:
                            st.session_state.saved_final_video_path = saved_path
                            st.session_state.current_step = 4
                            st.session_state.processing_complete = True
                            st.success("Final video created!")
                        else:
                            st.error("Failed to save final video")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        add_log(f"Error: {str(e)}")
            
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