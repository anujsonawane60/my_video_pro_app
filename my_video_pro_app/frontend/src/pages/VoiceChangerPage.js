import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import TextFieldsIcon from '@mui/icons-material/TextFields';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { getAvailableAudio, getAvailableSubtitles, getVoices, generateTTS, generateSTS, getFileUrl } from '../services/api';

const VoiceChangerPage = () => {
  const { projectId } = useParams();
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [audioFiles, setAudioFiles] = useState([]);
  const [subtitleFiles, setSubtitleFiles] = useState([]);
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [generatedAudio, setGeneratedAudio] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioPlayer, setAudioPlayer] = useState(null);
  const [audioHistory, setAudioHistory] = useState([]);
  const [stsHistory, setStsHistory] = useState([]);

  // Fetch available voices
  useEffect(() => {
    const fetchVoices = async () => {
      try {
        const data = await getVoices();
        setVoices(data.voices);
      } catch (err) {
        setError('Failed to fetch available voices');
      }
    };
    fetchVoices();
  }, []);

  // Fetch audio and subtitle files
  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const [audioData, subtitleData] = await Promise.all([
          getAvailableAudio(projectId),
          getAvailableSubtitles(projectId)
        ]);
        setAudioFiles(audioData.available_audio || []);
        setSubtitleFiles(subtitleData.available_subtitles || []);
      } catch (err) {
        setError('Failed to fetch files');
      }
    };
    fetchFiles();
  }, [projectId]);

  // Fetch TTS and STS audio history
  useEffect(() => {
    const fetchAudioHistory = async () => {
      try {
        const data = await getAvailableAudio(projectId);
        console.log('Raw audio data:', data);
        const files = Array.isArray(data) ? data : (data.available_audio || []);
        
        // Filter TTS history
        const ttsFiltered = files.filter(f => 
          f.type === 'tts_generated' && 
          (f.path?.includes(projectId) || f.url?.includes(projectId))
        );
        console.log('Filtered TTS history:', ttsFiltered);
        setAudioHistory(ttsFiltered);

        // Filter STS history
        const stsFiltered = files.filter(f => 
          f.type === 'sts_generated' && 
          (f.path?.includes(projectId) || f.url?.includes(projectId))
        );
        console.log('Filtered STS history:', stsFiltered);
        setStsHistory(stsFiltered);
      } catch (e) {
        console.error('Error fetching audio history:', e);
        // Ignore errors for history
      }
    };
    fetchAudioHistory();
  }, [projectId, generatedAudio]);

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
    setSelectedFile(null);
    setGeneratedAudio(null);
  };

  const handleVoiceChange = (event) => {
    setSelectedVoice(event.target.value);
  };

  const handleFileSelect = (file) => {
    setSelectedFile(file);
    setGeneratedAudio(null);
  };

  const handleGenerate = async () => {
    if (!selectedVoice || !selectedFile) {
      setError('Please select both a voice and a file');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      let data;
      if (activeTab === 0) {
        // TTS
        data = await generateTTS(projectId, selectedFile.id, selectedVoice);
      } else {
        // STS
        data = await generateSTS(projectId, selectedFile.id, selectedVoice);
      }
      setGeneratedAudio(data.audioUrl);
      setSuccess('Audio generated successfully!');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePlayPause = () => {
    if (!audioPlayer) return;

    if (isPlaying) {
      audioPlayer.pause();
    } else {
      audioPlayer.play();
    }
    setIsPlaying(!isPlaying);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1200, mx: 'auto' }}>
      <Typography variant="h4" gutterBottom align="center" sx={{ color: '#d72660', fontWeight: 'bold' }}>
        Voice Changer
      </Typography>

      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          centered
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab 
            icon={<TextFieldsIcon />} 
            label="Text to Speech" 
            iconPosition="start"
          />
          <Tab 
            icon={<SwapHorizIcon />} 
            label="Speech to Speech" 
            iconPosition="start"
          />
        </Tabs>
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              {activeTab === 0 ? 'Select Subtitle File' : 'Select Audio File'}
            </Typography>
            <List sx={{ maxHeight: 400, overflow: 'auto' }}>
              {(activeTab === 0 ? subtitleFiles : audioFiles).map((file) => (
                <ListItem
                  key={file.id}
                  button
                  selected={selectedFile?.id === file.id}
                  onClick={() => handleFileSelect(file)}
                  sx={
                    selectedFile?.id === file.id
                      ? {
                          bgcolor: '#e0f7fa',
                          borderLeft: '4px solid #3f51b5',
                          borderRadius: 2,
                          mb: 1,
                          boxShadow: 2,
                          transition: 'all 0.2s',
                        }
                      : { mb: 1, borderRadius: 2, transition: 'all 0.2s' }
                  }
                >
                  <ListItemText
                    primary={file.name}
                    secondary={new Date(file.created_at).toLocaleString()}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Select Voice
            </Typography>
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Voice</InputLabel>
              <Select
                value={selectedVoice}
                onChange={handleVoiceChange}
                label="Voice"
              >
                {voices.map((voice) => (
                  <MenuItem key={voice.id} value={voice.id}>
                    {voice.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {selectedVoice && voices.find(v => v.id === selectedVoice)?.preview_url && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Voice Preview:
                </Typography>
                <audio
                  src={voices.find(v => v.id === selectedVoice).preview_url}
                  controls
                  style={{ width: '100%' }}
                />
              </Box>
            )}

            <Button
              variant="contained"
              fullWidth
              onClick={handleGenerate}
              disabled={loading || !selectedVoice || !selectedFile}
              sx={{ mt: 2 }}
            >
              {loading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                `Generate ${activeTab === 0 ? 'Speech' : 'Voice'}`
              )}
            </Button>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 4, minHeight: 320, height: '100%', borderRadius: 4, boxShadow: 4, display: 'flex', flexDirection: 'column', justifyContent: 'flex-start' }}>
            <Typography variant="h6" gutterBottom>
              Generated Audio
            </Typography>
            {generatedAudio ? (
              <Box>
                <audio
                  ref={setAudioPlayer}
                  src={getFileUrl(generatedAudio)}
                  controls
                  style={{ width: '100%', minHeight: 80, marginBottom: 24 }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
                  <Tooltip title={isPlaying ? 'Stop' : 'Play'}>
                    <IconButton onClick={handlePlayPause} color="primary">
                      {isPlaying ? <StopIcon /> : <PlayArrowIcon />}
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            ) : (
              <Box
                sx={{
                  height: 180,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'grey.100',
                  borderRadius: 1,
                }}
              >
                <Typography color="text.secondary">
                  Generated audio will appear here
                </Typography>
              </Box>
            )}
            {/* Audio History Section */}
            <Box sx={{ mt: 4 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>
                TTS History
              </Typography>
              {audioHistory.length === 0 ? (
                <Typography variant="body2" color="text.secondary">No TTS generated audios yet.</Typography>
              ) : (
                <Box sx={{ maxHeight: 250, overflowY: 'auto' }}>
                  {audioHistory.map((audio) => (
                    <Paper key={audio.id} sx={{ p: 1.5, mb: 1.5, borderRadius: 2, bgcolor: '#f5f5f5' }}>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>{audio.label || audio.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Voice: {audio.voice_id || 'N/A'} | File: {audio.name} <br/>
                        {audio.created_at ? new Date(audio.created_at).toLocaleString() : ''}
                      </Typography>
                      <audio
                        src={getFileUrl(audio.url || audio.path)}
                        controls
                        style={{ width: '100%', marginTop: 6 }}
                      />
                    </Paper>
                  ))}
                </Box>
              )}
            </Box>

            {/* STS History Section */}
            <Box sx={{ mt: 4 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>
                STS History
              </Typography>
              {stsHistory.length === 0 ? (
                <Typography variant="body2" color="text.secondary">No STS generated audios yet.</Typography>
              ) : (
                <Box sx={{ maxHeight: 250, overflowY: 'auto' }}>
                  {stsHistory.map((audio) => (
                    <Paper key={audio.id} sx={{ p: 1.5, mb: 1.5, borderRadius: 2, bgcolor: '#f5f5f5' }}>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>{audio.label || audio.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Voice: {audio.voice_id || 'N/A'} | File: {audio.name} <br/>
                        {audio.created_at ? new Date(audio.created_at).toLocaleString() : ''}
                      </Typography>
                      <audio
                        src={getFileUrl(audio.url || audio.path)}
                        controls
                        style={{ width: '100%', marginTop: 6 }}
                      />
                    </Paper>
                  ))}
                </Box>
              )}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default VoiceChangerPage; 