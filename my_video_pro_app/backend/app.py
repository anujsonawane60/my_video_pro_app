from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import tempfile
from werkzeug.utils import secure_filename
import json
from video_processor import VideoProcessor

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
PROJECTS_FOLDER = 'projects'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wav', 'mp3', 'srt', 'vtt'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['PROJECTS_FOLDER'] = PROJECTS_FOLDER

# Ensure directories exist
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, PROJECTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Initialize video processor
video_processor = VideoProcessor(output_dir=OUTPUT_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_project_files(project_id):
    """Get all available audio and subtitle files for a project."""
    project_dir = os.path.join(app.config['PROJECTS_FOLDER'], str(project_id))
    if not os.path.exists(project_dir):
        return {'audio_files': [], 'subtitle_files': []}

    audio_files = []
    subtitle_files = []

    for filename in os.listdir(project_dir):
        file_path = os.path.join(project_dir, filename)
        if os.path.isfile(file_path):
            ext = filename.lower().split('.')[-1]
            if ext in ['mp3', 'wav']:
                audio_files.append({
                    'name': filename,
                    'path': os.path.relpath(file_path, os.getcwd()),
                    'type': 'audio'
                })
            elif ext in ['srt', 'vtt']:
                subtitle_files.append({
                    'name': filename,
                    'path': os.path.relpath(file_path, os.getcwd()),
                    'type': 'subtitle'
                })

    return {
        'audio_files': audio_files,
        'subtitle_files': subtitle_files
    }

def find_default_video(project_id):
    """Find the first video file in the project directory."""
    project_dir = os.path.join(app.config['PROJECTS_FOLDER'], str(project_id))
    if not os.path.exists(project_dir):
        return None

    for filename in os.listdir(project_dir):
        file_path = os.path.join(project_dir, filename)
        if os.path.isfile(file_path):
            ext = filename.lower().split('.')[-1]
            if ext in ALLOWED_VIDEO_EXTENSIONS:
                return file_path
    return None

@app.route('/api/project/<project_id>/files', methods=['GET'])
def get_project_files_endpoint(project_id):
    try:
        files = get_project_files(project_id)
        return jsonify({
            'success': True,
            'data': files
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/project/<project_id>/create-final-video', methods=['POST'])
def create_project_final_video(project_id):
    try:
        data = request.get_json()
        audio_path = data.get('audio_path')
        subtitle_path = data.get('subtitle_path')
        subtitle_style = data.get('subtitle_style', {})

        if not audio_path or not subtitle_path:
             return jsonify({'error': 'Missing required audio or subtitle file paths'}), 400

        video_path = find_default_video(project_id)
        if not video_path:
            return jsonify({'error': 'No default video file found for this project'}), 404
            
        # Ensure selected file paths are within the project directory for security
        project_dir = os.path.join(app.config['PROJECTS_FOLDER'], str(project_id))
        if not os.path.abspath(audio_path).startswith(os.path.abspath(project_dir)) or \
           not os.path.abspath(subtitle_path).startswith(os.path.abspath(project_dir)):
             return jsonify({'error': 'Invalid file path provided'}), 400

        try:
            # Create output filename
            output_filename = f"final_video_{os.path.basename(video_path)}"

            # Process video using VideoProcessor
            output_path = video_processor.create_final_video(
                video_path=video_path,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                subtitle_style=subtitle_style,
                output_filename=output_filename
            )

            # Return relative path for the frontend
            relative_path = os.path.relpath(output_path, os.getcwd())
            return jsonify({
                'success': True,
                'output_path': relative_path,
                'message': 'Video created successfully'
            })

        except Exception as e:
            return jsonify({
                'error': str(e)
            }), 500

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/create-final-video', methods=['POST'])
def create_final_video():
    # This endpoint is kept for compatibility or alternative flow if needed
    # Based on the latest request, the /api/project/<project_id>/create-final-video
    # endpoint is the preferred one for the Final Video Creation page.
    try:
        if 'video' not in request.files or 'audio' not in request.files or 'subtitle' not in request.files:
            return jsonify({'error': 'Missing required files'}), 400

        video_file = request.files['video']
        audio_file = request.files['audio']
        subtitle_file = request.files['subtitle']
        
        # Get subtitle styling preferences
        subtitle_style = json.loads(request.form.get('subtitleStyle', '{}'))
        
        if not all([video_file.filename, audio_file.filename, subtitle_file.filename]):
            return jsonify({'error': 'No selected files'}), 400

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded files
            video_path = os.path.join(temp_dir, secure_filename(video_file.filename))
            audio_path = os.path.join(temp_dir, secure_filename(audio_file.filename))
            subtitle_path = os.path.join(temp_dir, secure_filename(subtitle_file.filename))
            
            video_file.save(video_path)
            audio_file.save(audio_path)
            subtitle_file.save(subtitle_path)

            try:
                # Create output filename
                output_filename = f"final_video_{os.path.basename(video_path)}"
                
                # Process video using VideoProcessor
                output_path = video_processor.create_final_video(
                    video_path=video_path,
                    audio_path=audio_path,
                    subtitle_path=subtitle_path,
                    subtitle_style=subtitle_style,
                    output_filename=output_filename
                )

                # Return relative path for the frontend
                relative_path = os.path.relpath(output_path, os.getcwd())
                return jsonify({
                    'success': True,
                    'output_path': relative_path,
                    'message': 'Video created successfully'
                })

            except Exception as e:
                return jsonify({
                    'error': str(e)
                }), 500

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

# Serve video files
@app.route('/outputs/<path:filename>')
def serve_video(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

# Cleanup old files periodically
@app.route('/api/cleanup', methods=['POST'])
def cleanup_files():
    try:
        max_age_days = request.json.get('max_age_days', 7)
        video_processor.cleanup_old_files(max_age_days)
        return jsonify({
            'success': True,
            'message': 'Cleanup completed successfully'
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 