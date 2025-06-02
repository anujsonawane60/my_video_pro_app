import React, { useCallback, useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography, List, ListItem, ListItemText, IconButton, Divider, Paper, Drawer, Tooltip } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import CloseIcon from '@mui/icons-material/Close';
import AudioCleaner from '../components/AudioCleaner';
import { getAvailableAudio, cleanAudio, getFileUrl, getDownloadUrl } from '../services/api';

// This page wires up the AudioCleaner component to the backend API
const CleanAudioPage = () => {
  const { projectId } = useParams();
  const [audioHistory, setAudioHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Fetch audio files for this project (jobId)
  const fetchAudioFilesApi = useCallback(async (jobId) => {
    const data = await getAvailableAudio(jobId);
    // Support both {available_audio: [...]} and [...] directly
    const files = Array.isArray(data) ? data : (data.available_audio || []);
    
    console.log("Available audio files:", files);
    
    // Update audio history with cleaned audio files - improved filtering logic
    const cleanedFiles = files.filter(file => {
      const isCleanedType = file.type === 'cleaned';
      const hasCleanLabel = file.label && file.label.toLowerCase().includes('clean');
      const hasCleanPath = file.path && file.path.toLowerCase().includes('clean');
      
      return isCleanedType || hasCleanLabel || hasCleanPath;
    });
    
    console.log("Filtered cleaned audio files:", cleanedFiles);
    
    setAudioHistory(cleanedFiles);
    
    return files.map(f => ({
      name: f.label || f.name || f.path.split('/').pop(),  // Ensure audio name is displayed
      path: getFileUrl(f.path)
    }));
  }, []);

  // Clean audio API
  const cleanAudioApi = useCallback(async (audioPath, settings = {}) => {
    setLoading(true);
    try {
      const params = { audio_path: audioPath, ...settings };
      const result = await cleanAudio(projectId, params);
      // The backend returns a path that starts with /outputs/...
      // We need to make sure we're using the full URL
      const cleanedAudioUrl = getFileUrl(result.cleaned_audio_path);
      
      // Refresh audio files to update history
      await fetchAudioFilesApi(projectId);
      
      return cleanedAudioUrl;
    } finally {
      setLoading(false);
    }
  }, [projectId, fetchAudioFilesApi]);

  // Load audio history when component mounts
  useEffect(() => {
    fetchAudioFilesApi(projectId);
  }, [projectId, fetchAudioFilesApi]);

  // Handle download of audio file
  const handleDownload = (audioFile) => {
    // Create a temporary anchor element to trigger download
    const link = document.createElement('a');
    link.href = getFileUrl(audioFile.path);
    link.download = audioFile.label || `cleaned_audio_${new Date().toISOString().slice(0,10)}.wav`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Format timestamp from filename or path
  const formatTimestamp = (file) => {
    // Try to extract date from the path or use creation date
    const dateMatch = file.path.match(/\d{4}-\d{2}-\d{2}/);
    return dateMatch ? dateMatch[0] : new Date().toLocaleDateString();
  };

  // Toggle sidebar open/closed
  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh', position: 'relative' }}>
      {/* Three dots toggle button */}
      <Tooltip title="Clean Audio History">
        <IconButton 
          onClick={toggleSidebar}
          sx={{ 
            position: 'absolute', 
            top: 10, 
            left: 10, 
            zIndex: 1200,
            bgcolor: '#2056c7',
            color: 'white',
            '&:hover': { bgcolor: '#1845a0' }
          }}
        >
          <MoreVertIcon />
        </IconButton>
      </Tooltip>
      
      {/* Collapsible Sidebar */}
      <Drawer
        variant="temporary"
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          '& .MuiDrawer-paper': { 
            width: 250,
            boxSizing: 'border-box',
            bgcolor: '#f5f8fa'
          },
        }}
      >
        <Box sx={{ 
          p: 2, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between'
        }}>
          <Typography variant="h6" sx={{ color: '#2056c7', fontWeight: 'bold' }}>
            Clean Audio History
          </Typography>
          <IconButton onClick={() => setSidebarOpen(false)}>
            <CloseIcon />
          </IconButton>
        </Box>
        <Divider sx={{ mb: 2 }} />
        
        {audioHistory.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
            No cleaned audio files yet
          </Typography>
        ) : (
          <List sx={{ overflow: 'auto', flexGrow: 1 }}>
            {audioHistory.map((file, index) => (
              <ListItem 
                key={index}
                secondaryAction={
                  <IconButton edge="end" onClick={() => handleDownload(file)}>
                    <DownloadIcon />
                  </IconButton>
                }
                sx={{ 
                  mb: 1, 
                  bgcolor: 'white', 
                  borderRadius: 1,
                  '&:hover': { bgcolor: '#e3f2fd' } 
                }}
              >
                <ListItemText 
                  primary={file.label || 'Cleaned Audio'} 
                  secondary={formatTimestamp(file)}
                  primaryTypographyProps={{ noWrap: true, fontSize: '0.9rem' }}
                  secondaryTypographyProps={{ fontSize: '0.75rem' }}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Drawer>
      
      {/* Main content */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <AudioCleaner
          projectId={projectId}
          fetchAudioFilesApi={fetchAudioFilesApi}
          cleanAudioApi={cleanAudioApi}
        />
      </Box>
    </Box>
  );
};

export default CleanAudioPage;
