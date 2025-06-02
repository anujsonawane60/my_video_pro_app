import React, { useEffect, useState, useCallback } from 'react';
import { Box, Typography, Button, Card, CardContent, Grid, TextField, Paper, List, ListItem, ListItemText, CircularProgress, Alert } from '@mui/material';
import AudiotrackIcon from '@mui/icons-material/Audiotrack';
import { 
  getAvailableAudio, 
  getAvailableSubtitles, 
  generateSubtitles, 
  saveEditedSubtitles,
  getJobStatus,
  getSubtitleContent
} from '../services/api';
import SrtParser from 'srt-parser-2'; // Import the library

const MakeSubtitlePage = ({ jobId }) => {
  const [audioFiles, setAudioFiles] = useState([]);
  const [selectedAudio, setSelectedAudio] = useState(null);
  const [editedSubtitles, setEditedSubtitles] = useState([]); 
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [audioCurrentTime, setAudioCurrentTime] = useState(0);
  const [subtitleFiles, setSubtitleFiles] = useState([]);
  const [feedbackMessage, setFeedbackMessage] = useState({ type: '', text: '' });
  const [selectedSubtitleFile, setSelectedSubtitleFile] = useState(null);

  // Add new state for audio control
  const [audioPlayer, setAudioPlayer] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [loopStart, setLoopStart] = useState(null);
  const [loopEnd, setLoopEnd] = useState(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // CORRECTED INSTANTIATION:
  const parser = new SrtParser(); 

  // ... rest of your component code ...

  // Example usage of the parser (already correct in your code, just ensure instantiation is fixed)
  // const parsedSrt = parser.fromSrt(srtContent);
  // const srt = parser.toSrt(editedSubtitles.map(...));


  // ... rest of your component code ...

  // Helper to clear feedback messages
  const clearFeedback = () => setFeedbackMessage({ type: '', text: '' });

  const fetchAudioFiles = useCallback(async () => {
    if (!jobId) return;
    try {
      console.log('Fetching audio files for job:', jobId);
      const data = await getAvailableAudio(jobId); // Use named import directly
      console.log('Received audio data:', data);
      
      // Handle different response formats
      let files = [];
      if (Array.isArray(data)) {
        files = data;
      } else if (data && data.available_audio) {
        files = data.available_audio;
      } else if (data && typeof data === 'object') {
        // If it's a single audio file object
        files = [data];
      }

      console.log('Processed audio files:', files);
      
      setAudioFiles(
        files.map(f => ({
          name: f.label || f.name || (f.path ? f.path.split(/[/\\]/).pop() : 'Unknown Audio'),
          path: f.path, // Absolute backend path
          id: f.id,     // ID from AudioFile table
          url: f.url ? `${API_BASE_URL}${f.url}` : f.path, // Handle both relative and absolute paths
          duration: f.duration,
          type: f.type || 'unknown',
          created_at: f.created_at
        }))
      );
    } catch (e) {
      console.error("Error fetching audio files:", e);
      setFeedbackMessage({ type: 'error', text: 'Failed to load audio files: ' + (e.message || 'Unknown error') });
      setAudioFiles([]);
    }
  }, [jobId, API_BASE_URL]);

  // Add a debug effect to log audio files state
  useEffect(() => {
    console.log('Current audio files state:', audioFiles);
  }, [audioFiles]);

  const fetchSubtitleFiles = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await getAvailableSubtitles(jobId); // Use named import directly
      const files = Array.isArray(data) ? data : (data.available_subtitles || []);
      setSubtitleFiles(files.map(sub => ({
        ...sub, 
      })));
    } catch (e) {
      console.error("Error fetching subtitle files history:", e);
      setFeedbackMessage({ type: 'error', text: 'Failed to load subtitle history: ' + (e.message || 'Unknown error') });
      setSubtitleFiles([]);
    }
  }, [jobId]);


  useEffect(() => {
    fetchAudioFiles();
    fetchSubtitleFiles();
  }, [jobId, fetchAudioFiles, fetchSubtitleFiles]);

  useEffect(() => {
    const audio = document.getElementById('audio-player');
    if (!audio) return;
    const onTimeUpdate = () => setAudioCurrentTime(audio.currentTime);
    audio.addEventListener('timeupdate', onTimeUpdate);
    return () => {
      if (audio) { 
        audio.removeEventListener('timeupdate', onTimeUpdate);
      }
    }
  }, [audioUrl]);

  // Update audio player reference and add event listeners
  useEffect(() => {
    if (audioUrl) {
      const player = document.getElementById('audio-player');
      if (player) {
        setAudioPlayer(player);
        
        const handlePlay = () => setIsPlaying(true);
        const handlePause = () => setIsPlaying(false);
        const handleTimeUpdate = () => {
          const currentTime = player.currentTime;
          setAudioCurrentTime(currentTime);
          
          // Handle looping
          if (isLooping && loopStart !== null && loopEnd !== null) {
            if (currentTime >= loopEnd) {
              player.currentTime = loopStart;
            }
          }
        };
        
        player.addEventListener('play', handlePlay);
        player.addEventListener('pause', handlePause);
        player.addEventListener('timeupdate', handleTimeUpdate);
        
        return () => {
          player.removeEventListener('play', handlePlay);
          player.removeEventListener('pause', handlePause);
          player.removeEventListener('timeupdate', handleTimeUpdate);
        };
      }
    }
  }, [audioUrl, isLooping, loopStart, loopEnd]);

  // Function to control audio playback
  const controlAudio = (action) => {
    if (!audioPlayer) return;
    
    switch (action) {
      case 'play':
        audioPlayer.play();
        break;
      case 'pause':
        audioPlayer.pause();
        break;
      case 'stop':
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        break;
      default:
        break;
    }
  };

  // Function to set loop points
  const setLoopPoints = (start, end) => {
    setLoopStart(start);
    setLoopEnd(end);
    setIsLooping(true);
  };

  // Function to clear loop points
  const clearLoopPoints = () => {
    setLoopStart(null);
    setLoopEnd(null);
    setIsLooping(false);
  };

  // Function to seek audio to subtitle time
  const seekToSubtitle = (startTime, endTime) => {
    if (audioPlayer) {
      audioPlayer.currentTime = startTime;
      if (endTime) {
        setLoopPoints(startTime, endTime);
      }
      audioPlayer.play();
    }
  };

  const pollForSubtitles = useCallback(async (jobIdToPoll) => {
    const pollInterval = 5000; 
    const maxAttempts = 60; 
    let attempts = 0;

    return new Promise((resolve, reject) => {
      const intervalId = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
          clearInterval(intervalId);
          reject(new Error("Timeout waiting for subtitles. Please check job status manually or try refreshing subtitle history."));
          return;
        }
        try {
          const statusData = await getJobStatus(jobIdToPoll);
          const subtitleStep = statusData.steps?.generate_subtitles;

          if (subtitleStep?.status === 'completed' || statusData.status === 'subtitles_generated') {
            clearInterval(intervalId);
            const subtitleData = await getSubtitleContent(jobIdToPoll);
            if (subtitleData && typeof subtitleData.subtitle_content === 'string') {
              resolve(subtitleData.subtitle_content);
            } else {
              reject(new Error("Subtitles reported as generated, but content is missing or invalid."));
            }
          } else if (subtitleStep?.status === 'failed' || statusData.status === 'generate_subtitles_failed') {
            clearInterval(intervalId);
            reject(new Error("Subtitle generation failed. Check job status page for more details."));
          }
        } catch (error) {
          console.error("Polling error:", error);
        }
      }, pollInterval);
    });
  }, []);


  const handleGenerateSubtitle = async (audio) => {
    clearFeedback();
    setLoading(true);
    setSelectedAudio(audio);
    setAudioUrl(audio.url); 
    setEditedSubtitles([]); 
    setSelectedSubtitleFile(null); 

    try {
      const settings = {
        transcription_method: 'whisper',
        language: 'en', 
        whisper_model_size: 'base', 
      };
      await generateSubtitles(jobId, settings); // Use named import directly
      setFeedbackMessage({ type: 'info', text: 'Subtitle generation started... This may take a few minutes. Please wait.' });

      const srtContent = await pollForSubtitles(jobId);
      
      const parsedSrt = parser.fromSrt(srtContent);
      setEditedSubtitles(parsedSrt.map(s => ({
        id: s.id, 
        start: parseFloat(s.startSeconds),
        end: parseFloat(s.endSeconds),
        text: s.text,
      })));
      setFeedbackMessage({ type: 'success', text: 'Subtitles generated and loaded!' });
      await fetchSubtitleFiles(); 
    } catch (error) {
      console.error("Error during subtitle generation process:", error);
      setFeedbackMessage({ type: 'error', text: error.message || 'An unknown error occurred during subtitle generation.' });
    } finally {
      setLoading(false);
    }
  };

  const handleEditSubtitle = (idx, field, value) => {
    setEditedSubtitles(prev => prev.map((s, i) =>
      i === idx ? { ...s, [field]: (field === 'start' || field === 'end') ? parseFloat(value) || 0 : value } : s
    ));
  };

  const handleAddSubtitle = (idx) => {
    setEditedSubtitles(prev => {
      const newId = `new-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
      const prevEnd = prev[idx]?.end || (prev[prev.length -1]?.end || audioCurrentTime || 0) ;
      const newSeg = { id: newId, start: prevEnd, end: prevEnd + 2, text: '' };
      const newArray = [...prev];
      newArray.splice(idx + 1, 0, newSeg);
      return newArray;
    });
  };

  const handleDeleteSubtitle = (idx) => {
    setEditedSubtitles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSplitSubtitle = (idx) => {
    setEditedSubtitles(prev => {
      const seg = prev[idx];
      if (!seg) return prev;
      const splitTime = Math.max(seg.start + 0.1, Math.min(audioCurrentTime, seg.end - 0.1));
      if (splitTime <= seg.start || splitTime >= seg.end) {
        setFeedbackMessage({ type: 'warning', text: 'Split time is outside the segment boundaries or too close to edges.' });
        return prev;
      }
      const firstId = `split-${seg.id}-1-${Date.now()}`;
      const secondId = `split-${seg.id}-2-${Date.now()}`;
      const first = { ...seg, id: firstId, end: splitTime };
      const secondText = ""; 
      const second = { ...seg, id: secondId, start: splitTime, text: secondText };
      
      const newArray = [...prev];
      newArray.splice(idx, 1, first, second);
      return newArray;
    });
  };
  
  const handleMergeSubtitle = (idx) => {
    setEditedSubtitles(prev => {
      if (idx >= prev.length - 1) {
        setFeedbackMessage({ type: 'warning', text: 'Cannot merge the last segment with a next one.' });
        return prev;
      }
      const mergedId = `merged-${prev[idx].id}-${prev[idx+1].id}-${Date.now()}`;
      const merged = {
        id: mergedId,
        start: prev[idx].start,
        end: prev[idx + 1].end,
        text: (prev[idx].text.trim() + ' ' + prev[idx + 1].text.trim()).trim()
      };
      const newArray = [...prev];
      newArray.splice(idx, 2, merged);
      return newArray;
    });
  };

  const handleLoadSubtitleFile = async (fileToLoad) => {
    clearFeedback();
    setLoading(true);
    setSelectedSubtitleFile(fileToLoad);
    setSelectedAudio(null); 
    setAudioUrl(null); 
    setEditedSubtitles([]);

    try {
      const fullSrtUrl = `${API_BASE_URL}${fileToLoad.url}`;
      const resp = await fetch(fullSrtUrl);
      if (!resp.ok) {
        throw new Error(`Failed to fetch SRT content from ${fullSrtUrl}. Status: ${resp.status}`);
      }
      const srt = await resp.text();
      
      const parsedSrt = parser.fromSrt(srt || '');
      setEditedSubtitles(parsedSrt.map(s => ({ 
        id: s.id, 
        start: parseFloat(s.startSeconds), 
        end: parseFloat(s.endSeconds), 
        text: s.text 
      })));
      setFeedbackMessage({ type: 'success', text: `Loaded subtitle file: ${fileToLoad.name}` });

      const audioForSrt = audioFiles.find(af => fileToLoad.name.includes(af.id) || fileToLoad.label.includes(af.name.split('.')[0]));
      if(audioForSrt){
        setSelectedAudio(audioForSrt);
        setAudioUrl(audioForSrt.url);
        setFeedbackMessage({ type: 'success', text: `Loaded subtitle file: ${fileToLoad.name}. Associated audio also loaded.` });
      } else {
         setFeedbackMessage({ type: 'success', text: `Loaded subtitle file: ${fileToLoad.name}. Select an audio file to play alongside.` });
      }

    } catch (err) {
      console.error('Failed to load subtitle file:', err);
      setFeedbackMessage({ type: 'error', text: 'Failed to load subtitle file: ' + (err?.message || 'Unknown error') });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSubtitles = async () => {
    clearFeedback();
    if (!editedSubtitles.length) {
      setFeedbackMessage({ type: 'warning', text: 'No subtitles to save.' });
      return;
    }
    setLoading(true);
    try {
      // Convert subtitles to SRT format
      const srt = parser.toSrt(editedSubtitles.map((s, i) => ({
        id: (i + 1).toString(), 
        startTime: formatTimeSRT(s.start),
        endTime: formatTimeSRT(s.end),
        text: s.text,
      })));

      console.log('Saving subtitles:', srt); // Debug log
      
      const response = await saveEditedSubtitles(jobId, srt);
      console.log('Save response:', response); // Debug log
      
      if (response && response.status === 'subtitles_edited') {
        setFeedbackMessage({ type: 'success', text: 'Subtitles saved successfully!' });
        await fetchSubtitleFiles(); // Refresh the subtitle files list
      } else {
        throw new Error(response?.detail || 'Failed to save subtitles');
      }
    } catch (err) {
      console.error('Failed to save subtitles:', err);
      let errorMessage = 'Failed to save subtitles: ';
      if (err.response?.data?.detail) {
        errorMessage += err.response.data.detail;
      } else if (err.message) {
        errorMessage += err.message;
      } else {
        errorMessage += 'Unknown error occurred';
      }
      setFeedbackMessage({ type: 'error', text: errorMessage });
    } finally {
      setLoading(false);
    }
  };
  
  function formatTimeSRT(seconds) {
    if (isNaN(seconds) || seconds < 0) seconds = 0;
    const d = new Date(0);
    d.setUTCSeconds(Math.floor(seconds));
    const ms = Math.floor((seconds % 1) * 1000);
    return `${d.toISOString().substr(11, 8)},${ms.toString().padStart(3, '0')}`;
  }
// ----- JSX follows (no changes needed here from previous version, only showing context) -------
  return (
    <Box sx={{ p: 3, maxWidth: 1100, mx: 'auto' }}>
      {feedbackMessage.text && (
        <Alert severity={feedbackMessage.type || 'info'} onClose={clearFeedback} sx={{ mb: 2 }}>
          {feedbackMessage.text}
        </Alert>
      )}

      {/* Subtitle history section */}
      <Paper sx={{ p: {xs:1, sm:2, md:3}, mb: 4, background: 'linear-gradient(135deg, #f8eafc 0%, #eaf6fb 100%)', borderRadius: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h5" sx={{ color: '#2056c7', fontWeight: 'bold' }}>
            <AudiotrackIcon sx={{ mr: 1, color: '#d72660', verticalAlign: 'middle' }} /> Available Subtitle Files
          </Typography>
          <Button size="small" variant="outlined" onClick={fetchSubtitleFiles} disabled={loading} sx={{ ml: 2 }}>Refresh</Button>
        </Box>
        {subtitleFiles.length === 0 ? (
          <Typography variant="body2" color="text.secondary">No subtitle files available yet. Generate new ones or refresh.</Typography>
        ) : (
          <List dense sx={{ maxHeight: 200, overflowY: 'auto' }}>
            {subtitleFiles.map((sub) => (
              <ListItem
                key={sub.id || sub.path} 
                button
                selected={selectedSubtitleFile?.id === sub.id}
                onClick={() => handleLoadSubtitleFile(sub)}
                sx={{ borderRadius: 2, mb: 1, bgcolor: selectedSubtitleFile?.id === sub.id ? '#e0f7fa' : 'background.paper' }}
              >
                <ListItemText
                  primary={sub.label || sub.name || sub.path.split(/[/\\]/).pop()}
                  secondary={
                    `${sub.type ? sub.type.replace('_', ' ') : ''} ` +
                    (sub.created_at ? `| Created: ${new Date(sub.created_at).toLocaleString()}` : '')
                  }
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>
      
      <Typography variant="h3" align="center" sx={{ fontWeight: 'bold', mb: 1, color: '#d72660' }}>
        <span role="img" aria-label="subtitle">📝</span> Subtitle Editor
      </Typography>
      <Typography align="center" sx={{ mb: 3, color: '#555' }}>
        Generate new subtitles or load from history, then edit and play alongside your audio.
      </Typography>

      {/* Available Clean Audio section */}
      <Paper sx={{ p: {xs:1, sm:2, md:3}, mb: 4, background: 'linear-gradient(135deg, #eaf6fb 0%, #f8eafc 100%)', borderRadius: 4 }}>
        <Typography variant="h5" sx={{ mb: 2, color: '#2056c7', fontWeight: 'bold' }}>
          <AudiotrackIcon sx={{ mr: 1, color: '#d72660', verticalAlign: 'middle' }} /> Select Audio to Generate Subtitles
        </Typography>
        <Grid container spacing={2}>
          {audioFiles.length === 0 && !loading && <Grid item xs={12}><Typography>No audio files found for this job. Please process a video first.</Typography></Grid>}
          {audioFiles.map((audio) => (
            <Grid item xs={12} sm={6} md={4} key={audio.id || audio.path}> 
              <Card sx={{ 
                  boxShadow: selectedAudio?.id === audio.id ? 6 : 2, 
                  border: selectedAudio?.id === audio.id ? '2px solid #d72660' : '1px solid #ddd' 
                }}>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ color: '#2056c7', fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <AudiotrackIcon sx={{ fontSize: 20, mr: 0.5, verticalAlign: 'middle' }} /> {audio.name}
                  </Typography>
                  {audio.duration && <Typography variant="caption" sx={{ color: '#888' }}>Duration: {formatTimeSRT(audio.duration).substring(0,8)}</Typography>}
                  <Button
                    fullWidth
                    variant={selectedAudio?.id === audio.id ? 'contained' : 'outlined'}
                    sx={{ 
                      mt: 2, 
                      bgcolor: selectedAudio?.id === audio.id ? '#d72660' : undefined,
                      color: selectedAudio?.id === audio.id ? '#fff' : undefined, // ensure text is white on dark background
                      '&:hover': {
                        bgcolor: selectedAudio?.id === audio.id ? '#b71c50' : undefined,
                      }
                    }}
                    onClick={() => handleGenerateSubtitle(audio)}
                    disabled={loading}
                  >
                    {loading && selectedAudio?.id === audio.id ? <CircularProgress size={24} color="inherit" /> : 
                     selectedAudio?.id === audio.id ? 'Generating...' : 'Generate Subtitles'}
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* Audio Player and Subtitle Editor */}
      {(selectedAudio || editedSubtitles.length > 0) && ( 
        <Paper sx={{ p: {xs:1, sm:2, md:3}, background: 'linear-gradient(120deg, #e0f7fa 0%, #fce4ec 100%)', borderRadius: 4, boxShadow: 3 }}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={selectedAudio ? 5 : 12}> 
              {selectedAudio && audioUrl && (
                <Paper elevation={2} sx={{p:2, mb: {xs:2, md:0}}}>
                  <Typography variant="h6" sx={{ color: '#2056c7', fontWeight: 'bold', mb: 1 }}>Audio Player</Typography>
                  <audio 
                    id="audio-player" 
                    src={audioUrl} 
                    controls 
                    style={{ 
                      width: '100%', 
                      borderRadius: 8, 
                      background: '#fff',
                      marginBottom: '10px'
                    }} 
                  />
                  <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => controlAudio('stop')}
                      sx={{ flex: 1 }}
                    >
                      Stop
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => setIsLooping(!isLooping)}
                      color={isLooping ? 'secondary' : 'primary'}
                      sx={{ flex: 1 }}
                    >
                      {isLooping ? 'Disable Loop' : 'Enable Loop'}
                    </Button>
                  </Box>
                  <Typography variant="body2" sx={{ color: '#555', mt: 1, fontSize: '0.8rem' }}>
                    Click subtitle entries to jump audio. Use controls for playback.
                    {isLooping && loopStart !== null && loopEnd !== null && (
                      <span style={{ display: 'block', marginTop: '4px' }}>
                        Looping: {loopStart.toFixed(2)}s - {loopEnd.toFixed(2)}s
                      </span>
                    )}
                  </Typography>
                </Paper>
              )}
            </Grid>
            <Grid item xs={12} md={selectedAudio ? 7 : 12}>
              <Paper elevation={2} sx={{p:2}}>
                <Typography variant="h6" sx={{ color: '#2056c7', fontWeight: 'bold', mb: 2 }}>
                  Editing: {selectedSubtitleFile ? selectedSubtitleFile.name : (selectedAudio ? selectedAudio.name + " - New Subtitles" : "Subtitles")}
                </Typography>
                <List sx={{ 
                  maxHeight: {xs:300, sm:400, md:500}, 
                  overflowY: 'auto', 
                  pr: 1,  
                  bgcolor: 'rgba(255,255,255,0.7)', 
                  borderRadius: 2, 
                  p: 1 
                }}>
                  {editedSubtitles.length === 0 && !loading && (
                    <Typography sx={{p:2}}>No subtitles loaded or generated yet.</Typography>
                  )}
                  {loading && editedSubtitles.length === 0 && (
                    <Box sx={{display:'flex', justifyContent:'center', p:2}}>
                      <CircularProgress />
                    </Box>
                  )}
                  
                  {editedSubtitles.map((s, idx) => {
                    const isActive = selectedAudio && audioCurrentTime >= s.start && audioCurrentTime < s.end;
                    return (
                      <ListItem
                        key={s.id} 
                        selected={isActive}
                        onClick={() => seekToSubtitle(s.start, s.end)}
                        sx={{
                          bgcolor: isActive ? 'rgba(215, 38, 96, 0.2)' : 'rgba(255,255,255,0.9)',
                          borderLeft: isActive ? '4px solid #d72660' : '4px solid transparent',
                          borderRadius: 1, 
                          mb: 1, 
                          boxShadow: 1,
                          transition: 'all 0.3s ease',
                          p: 1.5, 
                          display: 'block',
                          cursor: 'pointer',
                          '&:hover': {
                            bgcolor: isActive ? 'rgba(215, 38, 96, 0.3)' : 'rgba(255,255,255,1)',
                            transform: 'translateX(4px)'
                          }
                        }}
                      >
                        <Grid container spacing={1} alignItems="center">
                          <Grid item xs={6} sm={3} md={2}>
                            <TextField 
                              label="Start (s)" 
                              type="number" 
                              value={s.start.toFixed(3)}
                              onChange={e => handleEditSubtitle(idx, 'start', e.target.value)}
                              size="small" 
                              inputProps={{ step: 0.001, min: 0 }} 
                              sx={{ width: '100%' }} 
                            />
                          </Grid>
                          <Grid item xs={6} sm={3} md={2}>
                            <TextField 
                              label="End (s)" 
                              type="number" 
                              value={s.end.toFixed(3)}
                              onChange={e => handleEditSubtitle(idx, 'end', e.target.value)}
                              size="small" 
                              inputProps={{ step: 0.001, min: 0 }} 
                              sx={{ width: '100%' }} 
                            />
                          </Grid>
                          <Grid item xs={12} sm={6} md={8}>
                            <TextField 
                              label="Text" 
                              value={s.text}
                              onChange={e => handleEditSubtitle(idx, 'text', e.target.value)}
                              fullWidth 
                              multiline 
                              minRows={2}
                              maxRows={4}
                              sx={{ 
                                '& .MuiInputBase-root': {
                                  fontSize: '1.1rem',
                                  lineHeight: 1.5
                                },
                                '& .MuiInputBase-input': {
                                  padding: '12px'
                                }
                              }}
                            />
                          </Grid>
                        </Grid>
                        <Box sx={{ 
                          mt: 1, 
                          display: 'flex', 
                          gap: 0.5, 
                          flexWrap: 'wrap', 
                          justifyContent: 'flex-start' 
                        }}>
                          <Button 
                            size="small" 
                            onClick={e => { e.stopPropagation(); handleAddSubtitle(idx); }} 
                            variant="text"
                          >
                            Add After
                          </Button>
                          <Button 
                            size="small" 
                            onClick={e => { e.stopPropagation(); handleDeleteSubtitle(idx); }} 
                            variant="text" 
                            color="error"
                          >
                            Delete
                          </Button>
                          <Button 
                            size="small" 
                            onClick={e => { e.stopPropagation(); handleSplitSubtitle(idx); }} 
                            variant="text" 
                            disabled={!selectedAudio}
                          >
                            Split @ Playhead
                          </Button>
                          <Button 
                            size="small" 
                            onClick={e => { e.stopPropagation(); handleMergeSubtitle(idx); }} 
                            variant="text" 
                            disabled={idx >= editedSubtitles.length - 1}
                          >
                            Merge Next
                          </Button>
                          {selectedAudio && (
                            <>
                              <Button 
                                size="small" 
                                onClick={e => {
                                  e.stopPropagation();
                                  seekToSubtitle(s.start, s.end);
                                }} 
                                variant="text"
                              >
                                Play Segment
                              </Button>
                              <Button 
                                size="small" 
                                onClick={e => {
                                  e.stopPropagation();
                                  controlAudio('stop');
                                }} 
                                variant="text"
                                color="error"
                              >
                                Stop
                              </Button>
                            </>
                          )}
                        </Box>
                      </ListItem>
                    );
                  })}
                </List>
                <Button
                  variant="contained"
                  color="primary" 
                  fullWidth
                  sx={{ 
                    mt: 3, 
                    fontWeight: 'bold', 
                    fontSize: {xs:14, sm:16}, 
                    py: 1.2, 
                    borderRadius: 2, 
                    boxShadow: 2 
                  }}
                  onClick={handleSaveSubtitles}
                  disabled={loading || editedSubtitles.length === 0}
                >
                  {loading ? <CircularProgress size={24} color="inherit" /> : 'Save Edited Subtitles'}
                </Button>
              </Paper>
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
};

export default MakeSubtitlePage;