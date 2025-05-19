import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Typography, Button, Paper, Box, CircularProgress } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { uploadVideo } from '../services/api';

const HomePage = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const navigate = useNavigate();

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setUploadError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadError('Please select a video file to upload');
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const response = await uploadVideo(selectedFile);
      // Navigate to the processing page with the job ID
      navigate(`/process/${response.job_id}`);
    } catch (error) {
      console.error('Error uploading video:', error);
      setUploadError(
        error.response?.data?.detail || 
        error.message || 
        'An error occurred while uploading the video'
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <Box sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom align="center">
        Video Processing App
      </Typography>
      
      <Typography variant="subtitle1" align="center" color="text.secondary" sx={{ mb: 4 }}>
        Upload a video and process it with subtitles and clean audio
      </Typography>

      <Paper 
        elevation={3} 
        sx={{ 
          p: 4, 
          maxWidth: 600, 
          mx: 'auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          borderRadius: 2,
          backgroundColor: '#f9f9f9'
        }}
      >
        <Box
          sx={{
            width: '100%',
            height: 200,
            border: '2px dashed #ccc',
            borderRadius: 2,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            mb: 3,
            p: 2,
            cursor: 'pointer',
            '&:hover': {
              borderColor: 'primary.main',
            },
          }}
          onClick={() => document.getElementById('file-input').click()}
        >
          <CloudUploadIcon sx={{ fontSize: 50, color: 'primary.main', mb: 2 }} />
          <Typography variant="h6" component="div" align="center">
            {selectedFile ? selectedFile.name : 'Drag & drop your video here or click to browse'}
          </Typography>
          {selectedFile && (
            <Typography variant="body2" color="text.secondary" align="center">
              {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
            </Typography>
          )}
          <input
            id="file-input"
            type="file"
            accept="video/*"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </Box>

        {uploadError && (
          <Typography variant="body2" color="error" align="center" sx={{ mb: 2 }}>
            {uploadError}
          </Typography>
        )}

        <Button
          variant="contained"
          color="primary"
          size="large"
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          startIcon={uploading ? <CircularProgress size={24} color="inherit" /> : null}
          sx={{ minWidth: 200 }}
        >
          {uploading ? 'Uploading...' : 'Upload Video'}
        </Button>
      </Paper>

      <Box sx={{ mt: 4, maxWidth: 800, mx: 'auto' }}>
        <Typography variant="h5" component="h2" gutterBottom>
          How it works
        </Typography>
        
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Paper sx={{ p: 2, borderLeft: 4, borderColor: 'primary.main' }}>
            <Typography variant="h6">1. Upload a video file</Typography>
            <Typography variant="body2" color="text.secondary">
              Start by uploading your video in MP4, AVI, MOV, or MKV format.
            </Typography>
          </Paper>
          
          <Paper sx={{ p: 2, borderLeft: 4, borderColor: 'primary.main' }}>
            <Typography variant="h6">2. Extract audio from the video</Typography>
            <Typography variant="body2" color="text.secondary">
              The system will extract the audio track from your video for processing.
            </Typography>
          </Paper>
          
          <Paper sx={{ p: 2, borderLeft: 4, borderColor: 'primary.main' }}>
            <Typography variant="h6">3. Generate subtitles using AI</Typography>
            <Typography variant="body2" color="text.secondary">
              Advanced AI transcription will create subtitles from your audio in multiple languages.
            </Typography>
          </Paper>
          
          <Paper sx={{ p: 2, borderLeft: 4, borderColor: 'primary.main' }}>
            <Typography variant="h6">4. Clean the audio by removing filler words</Typography>
            <Typography variant="body2" color="text.secondary">
              Our algorithms remove filler words, reduce noise, and enhance speech clarity.
            </Typography>
          </Paper>
          
          <Paper sx={{ p: 2, borderLeft: 4, borderColor: 'primary.main' }}>
            <Typography variant="h6">5. Create a final video with clean audio and subtitles</Typography>
            <Typography variant="body2" color="text.secondary">
              Download your enhanced video with clean audio and embedded subtitles.
            </Typography>
          </Paper>
        </Box>
      </Box>
    </Box>
  );
};

export default HomePage; 