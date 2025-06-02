import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Select, MenuItem, FormControl, InputLabel, CircularProgress } from '@mui/material';
import WaveformComparison from './WaveformComparison';
import { TextField, Switch, FormControlLabel, Slider, InputAdornment, Tooltip } from '@mui/material';
import LinearProgress from '@mui/material/LinearProgress';
import AudioWaveform from './AudioWaveform';

// Simple audio player for comparison
const AudioPlayer = ({ src, label }) => (
  <Box sx={{ mb: 2 }}>
    <Typography variant="subtitle2">{label}</Typography>
    <audio controls src={src} style={{ width: '100%' }} />
  </Box>
);

const AudioCleaner = ({ projectId, fetchAudioFilesApi, cleanAudioApi }) => {
  const [audioFiles, setAudioFiles] = useState([]);
  const [selectedAudio, setSelectedAudio] = useState('');
  const [cleanedAudio, setCleanedAudio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Advanced noise reduction and filler removal state
  const [propDecrease, setPropDecrease] = useState(0.8);
  const [stationary, setStationary] = useState(true);
  const [nFft, setNFft] = useState(2048);
  const [hopLength, setHopLength] = useState(512);
  const [nStdThreshStationary, setNStdThreshStationary] = useState(1.5);
  const [timeMaskSmoothMs, setTimeMaskSmoothMs] = useState(50);
  const [freqMaskSmoothHz, setFreqMaskSmoothHz] = useState(500);
  const [nJobs, setNJobs] = useState(1);
  const [fillerWords, setFillerWords] = useState('um, uh, erm, hmm, like, you know');
  const [whisperModelSize, setWhisperModelSize] = useState('base.en');

  // UI state for operation selection and progress
  const [operation, setOperation] = useState('full_clean'); // 'noise', 'filler', 'full_clean'
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('Idle.');

  // Fetch audio files for this project
  useEffect(() => {
    const fetchAudioFiles = async () => {
      setLoading(true);
      setError(null);
      try {
        const files = await fetchAudioFilesApi(projectId);
        setAudioFiles(files);
        if (files.length > 0) setSelectedAudio(files[0].path);
      } catch (e) {
        setError('Failed to fetch audio files.');
      }
      setLoading(false);
    };
    fetchAudioFiles();
  }, [projectId, fetchAudioFilesApi]);

  // Unified handler for all operations
  const handleOperation = async (op) => {
    setOperation(op);
    setLoading(true);
    setError(null);
    setCleanedAudio(null);
    setProgress(10);
    setStatus('Starting...');
    try {
      let cleaned = null;
      if (op === 'noise') {
        setStatus('Reducing background noise...');
        cleaned = await cleanAudioApi(selectedAudio, {
          prop_decrease: propDecrease,
          stationary,
          n_fft: nFft,
          hop_length: hopLength,
          n_std_thresh_stationary: nStdThreshStationary,
          time_mask_smooth_ms: timeMaskSmoothMs,
          freq_mask_smooth_hz: freqMaskSmoothHz,
          n_jobs: nJobs,
          mode: 'noise',
        }, setProgress, setStatus);
        setStatus('Noise reduction complete.');
      } else if (op === 'filler') {
        setStatus('Removing filler words...');
        cleaned = await cleanAudioApi(selectedAudio, {
          filler_words: fillerWords,
          whisper_model_size: whisperModelSize,
          mode: 'filler',
        }, setProgress, setStatus);
        setStatus('Filler word removal complete.');
      } else if (op === 'full_clean') {
        setStatus('Running full clean: noise reduction + filler removal...');
        cleaned = await cleanAudioApi(selectedAudio, {
          prop_decrease: propDecrease,
          stationary,
          n_fft: nFft,
          hop_length: hopLength,
          n_std_thresh_stationary: nStdThreshStationary,
          time_mask_smooth_ms: timeMaskSmoothMs,
          freq_mask_smooth_hz: freqMaskSmoothHz,
          n_jobs: nJobs,
          filler_words: fillerWords,
          whisper_model_size: whisperModelSize,
          mode: 'full_clean',
        }, setProgress, setStatus);
        setStatus('Full clean complete.');
      }
      setCleanedAudio(cleaned);
      setProgress(100);
    } catch (e) {
      setError('Audio cleaning failed.');
      setStatus('Error during cleaning.');
      setProgress(0);
    }
    setLoading(false);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1000, width: '100%', mx: 'auto', background: 'linear-gradient(135deg, #f8fbff 0%, #e6f0fa 100%)', borderRadius: 4, boxShadow: 3 }}>
      <Typography variant="h4" align="center" gutterBottom sx={{ fontWeight: 'bold', color: '#2056c7', mb: 3, letterSpacing: 1 }}>
        Clean Your Audio
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
        <Typography variant="subtitle1" sx={{ color: '#2056c7', mb: 1 }}>
          Select Audio File
        </Typography>
        <FormControl fullWidth sx={{ my: 1, maxWidth: 400 }}>
          <InputLabel>Audio File</InputLabel>
          <Select
            value={selectedAudio}
            label="Audio File"
            onChange={e => setSelectedAudio(e.target.value)}
            sx={{ borderRadius: 2, background: '#fff' }}
          >
            {audioFiles.map(file => (
              <MenuItem key={file.path} value={file.path}>{file.name}</MenuItem>
            ))}
          </Select>
        </FormControl>
        {/* Operation Buttons */}
        <Box sx={{ display: 'flex', gap: 2, mt: 2, mb: 2 }}>
          <Button
            variant={operation === 'noise' ? 'contained' : 'outlined'}
            color="primary"
            onClick={() => handleOperation('noise')}
            disabled={!selectedAudio || loading}
          >
            1. Reduce Background Noise
          </Button>
          <Button
            variant={operation === 'filler' ? 'contained' : 'outlined'}
            color="success"
            onClick={() => handleOperation('filler')}
            disabled={!selectedAudio || loading}
          >
            2. Remove Filler Words
          </Button>
          <Button
            variant={operation === 'full_clean' ? 'contained' : 'outlined'}
            color="secondary"
            onClick={() => handleOperation('full_clean')}
            disabled={!selectedAudio || loading}
          >
            3. Full Clean
          </Button>
        </Box>
        {/* Show parameter controls for the selected operation */}
        {operation === 'noise' || operation === 'full_clean' ? (
          <Box sx={{ width: '100%', maxWidth: 700, mt: 2, mb: 2, p: 2, borderRadius: 2, background: '#f4f8ff', boxShadow: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: '#2056c7', mb: 1 }}>
              Noise Reduction (noisereduce)
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
              <Box sx={{ flex: 1, minWidth: 180 }}>
                <Typography variant="body2">Proportion Decrease (prop_decrease)</Typography>
                <Slider
                  value={propDecrease}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(_, v) => setPropDecrease(v)}
                  valueLabelDisplay="auto"
                  sx={{ mt: 1 }}
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 180 }}>
                <FormControlLabel
                  control={<Switch checked={stationary} onChange={e => setStationary(e.target.checked)} />}
                  label={<Tooltip title="True: For steady-state noise (hum, fan). False: For dynamic noise."><span>Stationary</span></Tooltip>}
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 120 }}>
                <TextField
                  label="n_fft"
                  type="number"
                  value={nFft}
                  onChange={e => setNFft(Number(e.target.value))}
                  size="small"
                  InputProps={{ endAdornment: <InputAdornment position="end">samples</InputAdornment> }}
                  sx={{ width: '100%' }}
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 120 }}>
                <TextField
                  label="hop_length"
                  type="number"
                  value={hopLength}
                  onChange={e => setHopLength(Number(e.target.value))}
                  size="small"
                  InputProps={{ endAdornment: <InputAdornment position="end">samples</InputAdornment> }}
                  sx={{ width: '100%' }}
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 120 }}>
                <TextField
                  label="n_std_thresh_stationary"
                  type="number"
                  value={nStdThreshStationary}
                  onChange={e => setNStdThreshStationary(Number(e.target.value))}
                  size="small"
                  sx={{ width: '100%' }}
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 120 }}>
                <TextField
                  label="time_mask_smooth_ms"
                  type="number"
                  value={timeMaskSmoothMs}
                  onChange={e => setTimeMaskSmoothMs(Number(e.target.value))}
                  size="small"
                  InputProps={{ endAdornment: <InputAdornment position="end">ms</InputAdornment> }}
                  sx={{ width: '100%' }}
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 120 }}>
                <TextField
                  label="freq_mask_smooth_hz"
                  type="number"
                  value={freqMaskSmoothHz}
                  onChange={e => setFreqMaskSmoothHz(Number(e.target.value))}
                  size="small"
                  InputProps={{ endAdornment: <InputAdornment position="end">Hz</InputAdornment> }}
                  sx={{ width: '100%' }}
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 120 }}>
                <TextField
                  label="n_jobs"
                  type="number"
                  value={nJobs}
                  onChange={e => setNJobs(Number(e.target.value))}
                  size="small"
                  sx={{ width: '100%' }}
                />
              </Box>
            </Box>
          </Box>
        ) : null}
        {operation === 'filler' || operation === 'full_clean' ? (
          <Box sx={{ width: '100%', maxWidth: 700, mb: 2, p: 2, borderRadius: 2, background: '#f4fff4', boxShadow: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: '#2ca02c', mb: 1 }}>
              Filler Word Removal (Whisper + Pydub)
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
              <Box sx={{ flex: 2, minWidth: 220 }}>
                <TextField
                  label="Filler Words (comma-separated)"
                  value={fillerWords}
                  onChange={e => setFillerWords(e.target.value)}
                  size="small"
                  fullWidth
                  helperText="Words to remove, e.g. um, uh, like, you know"
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 180 }}>
                <TextField
                  label="Whisper Model Size"
                  value={whisperModelSize}
                  onChange={e => setWhisperModelSize(e.target.value)}
                  size="small"
                  fullWidth
                  helperText="e.g. tiny.en, base.en, small, medium, large"
                />
              </Box>
            </Box>
          </Box>
        ) : null}
        {/* Progress and status */}
        <Box sx={{ width: '100%', maxWidth: 700, mt: 2 }}>
          {loading && <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 2, mb: 1 }} />}
          <Typography variant="body2" color="text.secondary" sx={{ minHeight: 24 }}>{status}</Typography>
        </Box>
      </Box>
      {error && <Typography color="error" align="center" sx={{ mb: 2 }}>{error}</Typography>}
      <Box sx={{ mt: 4, p: 2, borderRadius: 3, background: 'linear-gradient(135deg, #eaf3ff 0%, #f6fff6 100%)', boxShadow: 1, maxWidth: 900, width: '100%', mx: 'auto' }}>
        <Typography variant="h5" align="center" sx={{ fontWeight: 'bold', color: '#2056c7', mb: 2 }}>
          Comparison View
        </Typography>
        {/* Show waveform comparison if both audios are available */}
        {selectedAudio && cleanedAudio ? (
          <WaveformComparison
            originalAudioPath={selectedAudio}
            cleanedAudioPath={cleanedAudio}
          />
        ) : (
          <Box>
            <Box sx={{ mb: 3, p: 2, borderRadius: 2, background: '#f0f6ff', boxShadow: 1 }}>
              <Typography variant="subtitle1" sx={{ color: '#2056c7', fontWeight: 'bold', mb: 1 }}>
                Original Audio
              </Typography>
              <audio controls src={selectedAudio} style={{ width: '100%', borderRadius: 8, background: '#fff' }} />
            </Box>
            {cleanedAudio && (
              <Box sx={{ p: 2, borderRadius: 2, background: '#eaffea', boxShadow: 1 }}>
                <Typography variant="subtitle1" sx={{ color: '#2ca02c', fontWeight: 'bold', mb: 1 }}>
                  Cleaned Audio
                </Typography>
                <AudioWaveform src={cleanedAudio} label="Cleaned Audio Waveform" />
              </Box>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default AudioCleaner;
