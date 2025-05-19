import React, { useState, useEffect, useRef, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Box, Button, Slider, Typography, Paper, IconButton, Grid, Divider } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SyncIcon from '@mui/icons-material/Sync';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import { getFileUrl } from '../services/api';

const formatTime = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

const WaveformComparison = ({ originalAudioPath, cleanedAudioPath }) => {
  const originalWaveformRef = useRef(null);
  const cleanedWaveformRef = useRef(null);
  const originalWavesurfer = useRef(null);
  const cleanedWavesurfer = useRef(null);
  const mountedRef = useRef(true);
  const abortControllerRef = useRef(null);
  const animationFrameRef = useRef(null);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [syncedPlayback, setSyncedPlayback] = useState(false); // Default to independent playback
  const [isLoading, setIsLoading] = useState(true);

  // Add state for audio metrics
  const [originalDb, setOriginalDb] = useState(null);
  const [cleanedDb, setCleanedDb] = useState(null);
  const [originalPlaying, setOriginalPlaying] = useState(false);
  const [cleanedPlaying, setCleanedPlaying] = useState(false);
  const [originalPeakDb, setOriginalPeakDb] = useState(-100);
  const [cleanedPeakDb, setCleanedPeakDb] = useState(-100);
  const [originalNoiseFloor, setOriginalNoiseFloor] = useState(-100);
  const [cleanedNoiseFloor, setCleanedNoiseFloor] = useState(-100);
  const [originalSnr, setOriginalSnr] = useState(0);
  const [cleanedSnr, setCleanedSnr] = useState(0);

  // Safe cleanup function as a callback that won't change
  const safeCleanupWavesurfer = useCallback((wavesurferInstance, instanceName) => {
    if (!wavesurferInstance) return;
    
    try {
      // First cancel any pending operations using the abort controller
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      
      // Remove all event listeners first
      try {
        wavesurferInstance.unAll();
      } catch (error) {
        console.log(`Error removing event listeners from ${instanceName}:`, error);
      }
      
      // Handle media cleanup
      try {
        if (wavesurferInstance.backend && wavesurferInstance.backend.media) {
          const media = wavesurferInstance.backend.media;
          if (media.pause && typeof media.pause === 'function') {
            media.pause();
          }
          // Clear any src attribute to prevent further loading
          if ('src' in media) {
            media.src = '';
          }
          // If any events are attached to media, remove them
          if (media.removeEventListener) {
            media.removeEventListener('abort', () => {});
            media.removeEventListener('error', () => {});
            media.removeEventListener('loadstart', () => {});
            media.removeEventListener('loadedmetadata', () => {});
            media.removeEventListener('canplay', () => {});
            media.removeEventListener('play', () => {});
            media.removeEventListener('pause', () => {});
            media.removeEventListener('ended', () => {});
          }
        }
      } catch (error) {
        console.log(`Error cancelling operations on ${instanceName}:`, error);
      }
      
      // Finally destroy the instance with a small delay
      setTimeout(() => {
        try {
          if (wavesurferInstance && typeof wavesurferInstance.destroy === 'function') {
            wavesurferInstance.destroy();
          }
        } catch (error) {
          console.log(`Error destroying ${instanceName}:`, error);
        }
      }, 100);
    } catch (error) {
      console.error(`Error during ${instanceName} cleanup:`, error);
    }
  }, []);

  // Add decibel calculation function
  const calculateDbLevels = useCallback((instance, setDb, setPeakDb, setNoiseFloor, setSnr, samplesBuffer = []) => {
    if (!instance || !instance.backend || !instance.backend.analyser) return samplesBuffer;
    
    try {
      const analyser = instance.backend.analyser;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(dataArray);
      
      // Calculate RMS value
      const rms = Math.sqrt(dataArray.reduce((sum, val) => sum + (val * val), 0) / dataArray.length);
      
      // Convert to dB (assuming 16-bit audio)
      const db = 20 * Math.log10(rms / 32768);
      const currentDb = Math.max(-100, db);
      setDb(currentDb);
      
      // Add to samples buffer for noise metrics calculation (keep last 100 samples)
      samplesBuffer.push(currentDb);
      if (samplesBuffer.length > 100) {
        samplesBuffer.shift();
      }
      
      // Calculate peak (max dB) from buffer
      const peak = Math.max(...samplesBuffer);
      setPeakDb(peak);
      
      // Calculate noise floor (20th percentile of samples)
      const sortedSamples = [...samplesBuffer].sort((a, b) => a - b);
      const noiseFloorIndex = Math.floor(sortedSamples.length * 0.2);
      const noiseFloor = sortedSamples[noiseFloorIndex] || -100;
      setNoiseFloor(noiseFloor);
      
      // Calculate SNR (Signal to Noise Ratio)
      const snr = peak - noiseFloor;
      setSnr(snr);
      
      return samplesBuffer;
    } catch (error) {
      console.error('Error calculating dB levels:', error);
      return samplesBuffer;
    }
  }, []);

  // Set up continuous analysis using requestAnimationFrame
  useEffect(() => {
    let originalSamplesBuffer = [];
    let cleanedSamplesBuffer = [];
    
    const updateMetrics = () => {
      if (!mountedRef.current) return;
      
      try {
        // Update metrics for original audio if playing or if its waveform is ready
        if (originalWavesurfer.current && originalWavesurfer.current.isReady) {
          originalSamplesBuffer = calculateDbLevels(
            originalWavesurfer.current,
            setOriginalDb,
            setOriginalPeakDb,
            setOriginalNoiseFloor,
            setOriginalSnr,
            originalSamplesBuffer
          );
        }
        
        // Update metrics for cleaned audio if playing or if its waveform is ready
        if (cleanedWavesurfer.current && cleanedWavesurfer.current.isReady) {
          cleanedSamplesBuffer = calculateDbLevels(
            cleanedWavesurfer.current,
            setCleanedDb,
            setCleanedPeakDb,
            setCleanedNoiseFloor,
            setCleanedSnr,
            cleanedSamplesBuffer
          );
        }
        
        // Continue the animation loop
        animationFrameRef.current = requestAnimationFrame(updateMetrics);
      } catch (error) {
        console.error('Error in animation frame:', error);
        animationFrameRef.current = requestAnimationFrame(updateMetrics);
      }
    };
    
    // Start the animation loop
    animationFrameRef.current = requestAnimationFrame(updateMetrics);
    
    // Cleanup function
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [calculateDbLevels]);

  // Initialize WaveSurfer instances
  useEffect(() => {
    // Set the mounted flag to true when the component mounts
    mountedRef.current = true;
    setIsLoading(true);
    
    // Create a new abort controller for this effect run
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;

    // Exit early if we don't have all requirements
    if (!originalWaveformRef.current || !cleanedWaveformRef.current || 
        !originalAudioPath || !cleanedAudioPath) {
      setIsLoading(false);
      return;
    }
      
    // Clear any existing instances
    if (originalWavesurfer.current) {
      safeCleanupWavesurfer(originalWavesurfer.current, 'originalWavesurfer');
      originalWavesurfer.current = null;
    }
    
    if (cleanedWavesurfer.current) {
      safeCleanupWavesurfer(cleanedWavesurfer.current, 'cleanedWavesurfer');
      cleanedWavesurfer.current = null;
    }

    const initializeWaveforms = async () => {
      try {
        originalWavesurfer.current = WaveSurfer.create({
          container: originalWaveformRef.current,
          waveColor: '#ff7f0e',
          progressColor: '#f44336',
          cursorColor: '#999',
          height: 80,
          barWidth: 2,
          barGap: 1,
          responsive: true,
          normalize: false, // Don't normalize to better show dB levels
          scrollParent: true, // Enable horizontal scrolling
          minPxPerSec: 100, // Minimum pixels per second for detailed view
          plugins: []
        });

        cleanedWavesurfer.current = WaveSurfer.create({
          container: cleanedWaveformRef.current,
          waveColor: '#2ca02c',
          progressColor: '#4caf50',
          cursorColor: '#999',
          height: 80,
          barWidth: 2,
          barGap: 1,
          responsive: true,
          normalize: false,
          scrollParent: true,
          minPxPerSec: 100,
          plugins: []
        });

        // Set up events for both waveforms
        const setupWavesurferEvents = (instance, isOriginal) => {
          if (!instance) return;
          
          instance.on('ready', () => {
            if (mountedRef.current && !signal.aborted) {
              setDuration(instance.getDuration());
              setIsLoading(false);
            }
          });

          instance.on('audioprocess', () => {
            if (!mountedRef.current || signal.aborted) return;
            
            try {
              const newTime = instance.getCurrentTime();
              
              // Update time for the current instance
              if (isOriginal) {
                setCurrentTime(newTime);
              }
              
              // Sync the other waveform if needed
              if (syncedPlayback) {
                const otherInstance = isOriginal ? cleanedWavesurfer.current : originalWavesurfer.current;
                if (otherInstance && otherInstance.isReady) {
                  const currentPosition = instance.getCurrentTime();
                  const otherPosition = otherInstance.getCurrentTime();
                  
                  // Only sync if the difference is significant (>100ms)
                  if (Math.abs(currentPosition - otherPosition) > 0.1) {
                    otherInstance.setCurrentTime(currentPosition);
                  }
                }
              }
            } catch (e) {
              console.error(`Error in audioprocess:`, e);
            }
          });

          instance.on('play', () => {
            if (!mountedRef.current || signal.aborted) return;
            
            if (isOriginal) {
              setOriginalPlaying(true);
              
              // If sync is enabled, also play the other one
              if (syncedPlayback && cleanedWavesurfer.current) {
                cleanedWavesurfer.current.play();
              }
            } else {
              setCleanedPlaying(true);
              
              // If sync is enabled, also play the other one
              if (syncedPlayback && originalWavesurfer.current) {
                originalWavesurfer.current.play();
              }
            }
          });

          instance.on('pause', () => {
            if (!mountedRef.current || signal.aborted) return;
            
            if (isOriginal) {
              setOriginalPlaying(false);
              
              // If sync is enabled, also pause the other one
              if (syncedPlayback && cleanedWavesurfer.current) {
                cleanedWavesurfer.current.pause();
              }
            } else {
              setCleanedPlaying(false);
              
              // If sync is enabled, also pause the other one
              if (syncedPlayback && originalWavesurfer.current) {
                originalWavesurfer.current.pause();
              }
            }
          });
        };

        // Set up events for both waveforms if still mounted
        if (!signal.aborted && mountedRef.current) {
          setupWavesurferEvents(originalWavesurfer.current, true);
          setupWavesurferEvents(cleanedWavesurfer.current, false);

          // Load audio files if still mounted
          try {
            if (originalWavesurfer.current && !signal.aborted) {
              const originalAudioUrl = getFileUrl(originalAudioPath);
              originalWavesurfer.current.load(originalAudioUrl);
            }
          } catch (error) {
            console.error('Error loading original audio:', error);
            if (mountedRef.current && !signal.aborted) {
              setIsLoading(false);
            }
          }

          try {
            if (cleanedWavesurfer.current && !signal.aborted) {
              const cleanedAudioUrl = getFileUrl(cleanedAudioPath);
              cleanedWavesurfer.current.load(cleanedAudioUrl);
            }
          } catch (error) {
            console.error('Error loading cleaned audio:', error);
            if (mountedRef.current && !signal.aborted) {
              setIsLoading(false);
            }
          }
        }
      } catch (error) {
        console.error('Error initializing waveforms:', error);
      }
    };

    initializeWaveforms();

    // Cleanup function
    return () => {
      // Set mounted flag to false first
      mountedRef.current = false;
      
      // Abort any pending operations
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      
      // Cancel any animation frames
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      
      // Then safely destroy instances
      if (originalWavesurfer.current) {
        safeCleanupWavesurfer(originalWavesurfer.current, 'originalWavesurfer');
        originalWavesurfer.current = null;
      }
      
      if (cleanedWavesurfer.current) {
        safeCleanupWavesurfer(cleanedWavesurfer.current, 'cleanedWavesurfer');
        cleanedWavesurfer.current = null;
      }
    };
  }, [originalAudioPath, cleanedAudioPath, syncedPlayback, safeCleanupWavesurfer]);

  const handleSeek = (_, newValue) => {
    try {
      const seekPosition = (newValue / 100) * duration;
      
      // Seek both if synced, otherwise only the active one
      if (syncedPlayback) {
        if (originalWavesurfer.current) {
          originalWavesurfer.current.seekTo(newValue / 100);
        }
        if (cleanedWavesurfer.current) {
          cleanedWavesurfer.current.seekTo(newValue / 100);
        }
      } else {
        // Seek only the one that's playing or both if none are playing
        if (originalPlaying && originalWavesurfer.current) {
          originalWavesurfer.current.seekTo(newValue / 100);
        } else if (cleanedPlaying && cleanedWavesurfer.current) {
          cleanedWavesurfer.current.seekTo(newValue / 100);
        } else {
          // If none are playing, seek both
          if (originalWavesurfer.current) {
            originalWavesurfer.current.seekTo(newValue / 100);
          }
          if (cleanedWavesurfer.current) {
            cleanedWavesurfer.current.seekTo(newValue / 100);
          }
        }
      }
      
      setCurrentTime(seekPosition);
    } catch (error) {
      console.error('Error in seek:', error);
    }
  };

  const toggleSyncedPlayback = () => {
    setSyncedPlayback(!syncedPlayback);

    // If we're enabling sync and both are playing, we need to sync positions
    if (!syncedPlayback) {
      if (originalPlaying && cleanedPlaying) {
        // Use the position from the original as the master
        if (originalWavesurfer.current && cleanedWavesurfer.current) {
          const currentPosition = originalWavesurfer.current.getCurrentTime();
          cleanedWavesurfer.current.setCurrentTime(currentPosition);
        }
      }
    }
  };

  // Calculate slider position
  const sliderPosition = duration ? (currentTime / duration) * 100 : 0;

  // Handle individual play/pause for waveforms
  const handlePlayPauseOriginal = () => {
    if (originalWavesurfer.current) {
      // If this one is already playing, pause it
      if (originalPlaying) {
        originalWavesurfer.current.pause();
      } else {
        // If the other one is playing and we're not in sync mode, pause it first
        if (!syncedPlayback && cleanedPlaying && cleanedWavesurfer.current) {
          cleanedWavesurfer.current.pause();
        }
        originalWavesurfer.current.play();
      }
    }
  };

  const handlePlayPauseCleaned = () => {
    if (cleanedWavesurfer.current) {
      // If this one is already playing, pause it
      if (cleanedPlaying) {
        cleanedWavesurfer.current.pause();
      } else {
        // If the other one is playing and we're not in sync mode, pause it first
        if (!syncedPlayback && originalPlaying && originalWavesurfer.current) {
          originalWavesurfer.current.pause();
        }
        cleanedWavesurfer.current.play();
      }
    }
  };

  // Render waveform with audio metrics
  const renderWaveform = (ref, currentDb, peakDb, noiseFloor, snr, isPlaying, onPlayPause, title, color) => (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ color: color, fontWeight: 'bold' }}>
          {title}
        </Typography>
        <IconButton 
          onClick={onPlayPause}
          color="primary"
          size="small"
          sx={{ ml: 'auto' }}
        >
          {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
        </IconButton>
      </Box>
      
      <Box 
        ref={ref} 
        sx={{ 
          width: '100%', 
          overflowX: 'auto',
          '& wave': {
            overflowX: 'auto !important',
            minWidth: '100%'
          }
        }} 
      />
      
      <Box sx={{ mt: 1, display: 'flex', alignItems: 'center' }}>
        <VolumeUpIcon fontSize="small" sx={{ mr: 0.5, color }} />
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Current: <strong>{currentDb !== null ? currentDb.toFixed(1) : '--'} dB</strong>
          &nbsp;&nbsp;Peak: <strong>{peakDb !== null ? peakDb.toFixed(1) : '--'} dB</strong>
          &nbsp;&nbsp;Noise floor: <strong>{noiseFloor !== null ? noiseFloor.toFixed(1) : '--'} dB</strong>
          &nbsp;&nbsp;SNR: <strong>{snr !== null ? snr.toFixed(1) : '--'} dB</strong>
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Paper elevation={2} sx={{ p: 2, mb: 3, borderRadius: 2 }}>
      <Typography variant="h6" gutterBottom sx={{ fontWeight: 'bold' }}>
        Audio Comparison
      </Typography>
      
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, justifyContent: 'flex-end' }}>
        <Button
          size="small"
          startIcon={<SyncIcon />}
          color={syncedPlayback ? "secondary" : "primary"}
          onClick={toggleSyncedPlayback}
          variant={syncedPlayback ? "contained" : "outlined"}
        >
          {syncedPlayback ? "SYNCED PLAYBACK" : "INDEPENDENT PLAYBACK"}
        </Button>
      </Box>
      
      <Divider sx={{ mb: 2 }} />
      
      {renderWaveform(
        originalWaveformRef,
        originalDb,
        originalPeakDb,
        originalNoiseFloor,
        originalSnr,
        originalPlaying,
        handlePlayPauseOriginal,
        "Original Audio",
        '#ff7f0e'
      )}
      
      {renderWaveform(
        cleanedWaveformRef,
        cleanedDb,
        cleanedPeakDb,
        cleanedNoiseFloor,
        cleanedSnr,
        cleanedPlaying,
        handlePlayPauseCleaned,
        "Cleaned Audio",
        '#2ca02c'
      )}
      
      <Divider sx={{ mb: 2 }} />
      
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Slider
          value={sliderPosition}
          onChange={handleSeek}
          aria-labelledby="audio-position-slider"
          sx={{ mx: 2, flexGrow: 1 }}
          disabled={!duration || isLoading}
        />
        
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 80, textAlign: 'right' }}>
          {formatTime(currentTime)} / {formatTime(duration)}
        </Typography>
      </Box>
      
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
        Use the individual play controls to compare each audio track. 
        Toggle synchronized playback to compare the audio at the same positions.
        Audio metrics show the noise levels and quality improvements in the cleaned version.
      </Typography>
    </Paper>
  );
};

export default WaveformComparison; 