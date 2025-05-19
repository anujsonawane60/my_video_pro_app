import React, { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Box, Button, Slider, Typography, Paper } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import { getFileUrl } from '../services/api';

const formatTime = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

const AudioWaveform = ({ audioPath, color = '#3f51b5', title = 'Audio Waveform' }) => {
  const waveformRef = useRef(null);
  const wavesurfer = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const mountedRef = useRef(true);
  const [isLoading, setIsLoading] = useState(true);
  const abortControllerRef = useRef(null);

  // Safe cleanup function that won't change
  const safeCleanupWavesurfer = useCallback((wavesurferInstance) => {
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
        console.log('Error removing event listeners:', error);
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
        console.log('Error cancelling operations:', error);
      }
      
      // Finally destroy the instance with a small delay to ensure all operations are complete
      setTimeout(() => {
        try {
          if (wavesurferInstance && typeof wavesurferInstance.destroy === 'function') {
            wavesurferInstance.destroy();
          }
        } catch (error) {
          console.log('Error destroying wavesurfer:', error);
        }
      }, 100);
    } catch (error) {
      console.error('Error during wavesurfer cleanup:', error);
    }
  }, []);

  // Initialize WaveSurfer
  useEffect(() => {
    // Set mounted flag
    mountedRef.current = true;
    setIsLoading(true);

    // Create a new abort controller for this effect run
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;

    // Exit early if requirements aren't met
    if (!waveformRef.current || !audioPath) {
      setIsLoading(false);
      return;
    }

    // Clear any existing instance
    if (wavesurfer.current) {
      safeCleanupWavesurfer(wavesurfer.current);
      wavesurfer.current = null;
    }

    // Create a new WaveSurfer instance
    const initializeWavesurfer = async () => {
      try {
        wavesurfer.current = WaveSurfer.create({
          container: waveformRef.current,
          waveColor: color,
          progressColor: color === '#3f51b5' ? '#f50057' : '#3f51b5',
          cursorColor: '#999',
          height: 80,
          barWidth: 2,
          barGap: 1,
          responsive: true,
          normalize: true,
        });

        // Check if component is still mounted after initialization
        if (signal.aborted || !mountedRef.current) {
          if (wavesurfer.current) {
            safeCleanupWavesurfer(wavesurfer.current);
            wavesurfer.current = null;
          }
          return;
        }

        // Add event listeners
        wavesurfer.current.on('ready', () => {
          if (mountedRef.current && !signal.aborted) {
            setDuration(wavesurfer.current.getDuration());
            setIsLoading(false);
          }
        });

        wavesurfer.current.on('audioprocess', () => {
          if (mountedRef.current && !signal.aborted && wavesurfer.current) {
            try {
              setCurrentTime(wavesurfer.current.getCurrentTime());
            } catch (error) {
              console.error('Error during audioprocess:', error);
            }
          }
        });

        wavesurfer.current.on('seek', () => {
          if (mountedRef.current && !signal.aborted && wavesurfer.current) {
            try {
              setCurrentTime(wavesurfer.current.getCurrentTime());
            } catch (error) {
              console.error('Error during seek:', error);
            }
          }
        });

        wavesurfer.current.on('play', () => {
          if (mountedRef.current && !signal.aborted) {
            setIsPlaying(true);
          }
        });

        wavesurfer.current.on('pause', () => {
          if (mountedRef.current && !signal.aborted) {
            setIsPlaying(false);
          }
        });

        wavesurfer.current.on('finish', () => {
          if (mountedRef.current && !signal.aborted) {
            setIsPlaying(false);
          }
        });
        
        wavesurfer.current.on('error', (err) => {
          console.error('Error in wavesurfer instance:', err);
          if (mountedRef.current && !signal.aborted) {
            setIsLoading(false);
          }
        });

        // Load the audio file
        if (!signal.aborted) {
          try {
            const audioUrl = getFileUrl(audioPath);
            wavesurfer.current.load(audioUrl);
          } catch (error) {
            console.error('Error loading audio:', error);
            if (mountedRef.current && !signal.aborted) {
              setIsLoading(false);
            }
          }
        }
      } catch (error) {
        console.error('Error initializing WaveSurfer:', error);
        if (mountedRef.current && !signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    initializeWavesurfer();

    // Cleanup function
    return () => {
      mountedRef.current = false;
      
      // Abort any pending operations
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      
      // Clean up wavesurfer
      if (wavesurfer.current) {
        safeCleanupWavesurfer(wavesurfer.current);
        wavesurfer.current = null;
      }
    };
  }, [audioPath, color, safeCleanupWavesurfer]);

  const handlePlayPause = () => {
    if (wavesurfer.current) {
      try {
        wavesurfer.current.playPause();
      } catch (error) {
        console.error('Error in playPause:', error);
      }
    }
  };

  const handleSeek = (_, newValue) => {
    if (wavesurfer.current) {
      try {
        wavesurfer.current.seekTo(newValue / 100);
        setCurrentTime(wavesurfer.current.getCurrentTime());
      } catch (error) {
        console.error('Error in seek:', error);
      }
    }
  };

  // Calculate slider position
  const sliderPosition = duration ? (currentTime / duration) * 100 : 0;

  return (
    <Paper elevation={2} sx={{ p: 2, mb: 3, borderRadius: 2 }}>
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      
      <Box ref={waveformRef} sx={{ width: '100%', mb: 2 }} />
      
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button
          variant="contained"
          color={isPlaying ? 'secondary' : 'primary'}
          startIcon={isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
          onClick={handlePlayPause}
          disabled={!duration || isLoading}
          size="small"
        >
          {isLoading ? 'Loading...' : (isPlaying ? 'Pause' : 'Play')}
        </Button>
        
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
    </Paper>
  );
};

export default AudioWaveform; 