import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Paper, TextField, Button, CircularProgress, Alert } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { uploadVideo, extractAudio } from '../services/api';

const NewProjectPage = () => {
  const [projectName, setProjectName] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    console.log('handleSubmit triggered');
    console.log('Project Name:', projectName);
    console.log('Selected File:', selectedFile);
    if (!projectName) {
      setError('Please enter a project name.');
      return;
    }
    if (!selectedFile) {
      setError('Please select a video file.');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      // Upload video and get job/project id
      const response = await uploadVideo(selectedFile); // Only pass the file
      const jobId = response.job_id || response.project_id;
      // Save project info to localStorage
      const newProject = {
        id: jobId,
        name: projectName,
        date: new Date().toISOString().split('T')[0],
      };
      const existing = JSON.parse(localStorage.getItem('projects') || '[]');
      localStorage.setItem('projects', JSON.stringify([newProject, ...existing.filter(p => p.id !== jobId)]));
      // Automatically extract audio after upload
      await extractAudio(jobId);
      // Redirect to project overview
      navigate(`/project/${jobId}`);
    } catch (err) {
      setError(err.message || 'Failed to create project.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Box sx={{ py: 4 }}>
      <Typography variant="h4" align="center" gutterBottom>
        Create New Project
      </Typography>
      <Paper elevation={3} sx={{ p: 4, maxWidth: 500, mx: 'auto', mt: 4 }}>
        <form onSubmit={handleSubmit}>
          <TextField
            label="Project Name"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            fullWidth
            required
            sx={{ mb: 3 }}
          />
          <Button
            variant="outlined"
            component="label"
            startIcon={<CloudUploadIcon />}
            fullWidth
            sx={{ mb: 2 }}
          >
            {selectedFile ? selectedFile.name : 'Select Video File'}
            <input
              type="file"
              accept="video/*"
              hidden
              onChange={handleFileSelect}
            />
          </Button>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Button
            type="submit"
            variant="contained"
            color="primary"
            fullWidth
            disabled={uploading}
            startIcon={uploading ? <CircularProgress size={20} /> : null}
          >
            {uploading ? 'Creating...' : 'Create Project'}
          </Button>
        </form>
      </Paper>
    </Box>
  );
};

export default NewProjectPage;
