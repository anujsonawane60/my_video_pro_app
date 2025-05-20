import React, { useEffect, useRef, useState } from 'react';
import { Card, CardContent, Typography, Box, Grid, Button, Slider, IconButton, Paper } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import SyncIcon from '@mui/icons-material/Sync';
import WaveSurfer from 'wavesurfer.js';

const AudioComparison = ({ 
    originalAudioUrl, 
    generatedAudioUrl, 
    subtitleTiming = [],
    onClose
}) => {
    const originalWavesurferRef = useRef(null);
    const generatedWavesurferRef = useRef(null);
    const originalContainerRef = useRef(null);
    const generatedContainerRef = useRef(null);
    const originalTimelineRef = useRef(null);
    const generatedTimelineRef = useRef(null);
    
    const [originalPlaying, setOriginalPlaying] = useState(false);
    const [generatedPlaying, setGeneratedPlaying] = useState(false);
    const [syncPlay, setSyncPlay] = useState(false);
    const [originalTime, setOriginalTime] = useState(0);
    const [generatedTime, setGeneratedTime] = useState(0);
    const [originalDuration, setOriginalDuration] = useState(0);
    const [generatedDuration, setGeneratedDuration] = useState(0);
    const [activeSubtitle, setActiveSubtitle] = useState(null);
    
    // Initialize WaveSurfer instances
    useEffect(() => {
        // Create original audio waveform
        originalWavesurferRef.current = WaveSurfer.create({
            container: originalContainerRef.current,
            waveColor: '#3f51b5',
            progressColor: '#1e88e5',
            cursorColor: '#333',
            height: 120,
            normalize: true,
            responsive: true,
            barWidth: 2,
            barHeight: 1,
            barGap: 1
        });
        
        // Create generated audio waveform
        generatedWavesurferRef.current = WaveSurfer.create({
            container: generatedContainerRef.current,
            waveColor: '#4caf50',
            progressColor: '#2e7d32',
            cursorColor: '#333',
            height: 120,
            normalize: true,
            responsive: true,
            barWidth: 2,
            barHeight: 1,
            barGap: 1
        });
        
        // Load audio files
        originalWavesurferRef.current.load(originalAudioUrl);
        generatedWavesurferRef.current.load(generatedAudioUrl);
        
        // Setup event listeners for original audio
        originalWavesurferRef.current.on('ready', () => {
            setOriginalDuration(originalWavesurferRef.current.getDuration());
            
            // Add subtitle regions to original audio (disabled)
            /* Temporarily disabled regions since we removed the RegionsPlugin
            subtitleTiming.forEach((subtitle, index) => {
                originalWavesurferRef.current.addRegion({
                    id: `subtitle-${index}`,
                    start: subtitle.start,
                    end: subtitle.end,
                    color: 'rgba(63, 81, 181, 0.2)',
                    data: {
                        text: subtitle.text,
                        index: subtitle.index
                    }
                });
            });
            */
        });
        
        originalWavesurferRef.current.on('audioprocess', (time) => {
            setOriginalTime(time);
            if (syncPlay && generatedWavesurferRef.current) {
                // Update subtitle display based on time
                const matchingSubtitle = subtitleTiming.find(
                    sub => time >= sub.start && time <= sub.end
                );
                if (matchingSubtitle && (!activeSubtitle || activeSubtitle.index !== matchingSubtitle.index)) {
                    setActiveSubtitle(matchingSubtitle);
                } else if (!matchingSubtitle && activeSubtitle) {
                    setActiveSubtitle(null);
                }
            }
        });
        
        originalWavesurferRef.current.on('play', () => {
            setOriginalPlaying(true);
            if (syncPlay && generatedWavesurferRef.current && !generatedPlaying) {
                generatedWavesurferRef.current.play();
            }
        });
        
        originalWavesurferRef.current.on('pause', () => {
            setOriginalPlaying(false);
            if (syncPlay && generatedWavesurferRef.current && generatedPlaying) {
                generatedWavesurferRef.current.pause();
            }
        });
        
        originalWavesurferRef.current.on('seeking', (time) => {
            if (syncPlay && generatedWavesurferRef.current) {
                // Calculate equivalent position in generated audio
                const ratio = generatedDuration / originalDuration;
                const syncedTime = time * ratio;
                generatedWavesurferRef.current.seekTo(syncedTime / generatedDuration);
            }
        });
        
        // Setup event listeners for generated audio
        generatedWavesurferRef.current.on('ready', () => {
            setGeneratedDuration(generatedWavesurferRef.current.getDuration());
        });
        
        generatedWavesurferRef.current.on('audioprocess', (time) => {
            setGeneratedTime(time);
        });
        
        generatedWavesurferRef.current.on('play', () => {
            setGeneratedPlaying(true);
            if (syncPlay && originalWavesurferRef.current && !originalPlaying) {
                originalWavesurferRef.current.play();
            }
        });
        
        generatedWavesurferRef.current.on('pause', () => {
            setGeneratedPlaying(false);
            if (syncPlay && originalWavesurferRef.current && originalPlaying) {
                originalWavesurferRef.current.pause();
            }
        });
        
        generatedWavesurferRef.current.on('seeking', (time) => {
            if (syncPlay && originalWavesurferRef.current) {
                // Calculate equivalent position in original audio
                const ratio = originalDuration / generatedDuration;
                const syncedTime = time * ratio;
                originalWavesurferRef.current.seekTo(syncedTime / originalDuration);
            }
        });
        
        // Cleanup on unmount
        return () => {
            if (originalWavesurferRef.current) {
                originalWavesurferRef.current.destroy();
            }
            if (generatedWavesurferRef.current) {
                generatedWavesurferRef.current.destroy();
            }
        };
    }, [originalAudioUrl, generatedAudioUrl]);
    
    // Update sync behavior when syncPlay changes
    useEffect(() => {
        if (syncPlay) {
            // If one is playing and the other isn't, sync them
            if (originalPlaying && !generatedPlaying && generatedWavesurferRef.current) {
                generatedWavesurferRef.current.play();
            } else if (!originalPlaying && generatedPlaying && originalWavesurferRef.current) {
                originalWavesurferRef.current.play();
            }
        }
    }, [syncPlay, originalPlaying, generatedPlaying]);
    
    // Format time display
    const formatTime = (seconds) => {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${mins}:${secs}`;
    };
    
    return (
        <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
                Audio Comparison
            </Typography>
            
            <Box mb={2}>
                <Grid container spacing={2} alignItems="center">
                    <Grid item>
                        <IconButton 
                            color={syncPlay ? "primary" : "default"}
                            onClick={() => setSyncPlay(!syncPlay)}
                            title={syncPlay ? "Disable synchronized playback" : "Enable synchronized playback"}
                        >
                            <SyncIcon />
                        </IconButton>
                    </Grid>
                    <Grid item xs>
                        <Typography variant="body2" color={syncPlay ? "primary" : "textSecondary"}>
                            {syncPlay ? "Synchronized playback enabled" : "Synchronized playback disabled"}
                        </Typography>
                    </Grid>
                </Grid>
            </Box>
            
            {/* Original Audio Waveform */}
            <Card variant="outlined" sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="subtitle1" color="primary" gutterBottom>
                        Original Audio
                    </Typography>
                    
                    <Box ref={originalContainerRef} />
                    <Box ref={originalTimelineRef} sx={{ mb: 2 }} />
                    
                    <Grid container spacing={2} alignItems="center">
                        <Grid item>
                            <IconButton 
                                onClick={() => {
                                    if (originalPlaying) {
                                        originalWavesurferRef.current.pause();
                                    } else {
                                        originalWavesurferRef.current.play();
                                    }
                                }}
                            >
                                {originalPlaying ? <PauseIcon /> : <PlayArrowIcon />}
                            </IconButton>
                            
                            <IconButton 
                                onClick={() => {
                                    originalWavesurferRef.current.stop();
                                    setOriginalPlaying(false);
                                }}
                            >
                                <StopIcon />
                            </IconButton>
                        </Grid>
                        
                        <Grid item xs>
                            <Typography variant="body2">
                                {formatTime(originalTime)} / {formatTime(originalDuration)}
                            </Typography>
                        </Grid>
                    </Grid>
                </CardContent>
            </Card>
            
            {/* Generated Audio Waveform */}
            <Card variant="outlined" sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="subtitle1" color="success" gutterBottom>
                        Generated Voice Audio
                    </Typography>
                    
                    <Box ref={generatedContainerRef} />
                    <Box ref={generatedTimelineRef} sx={{ mb: 2 }} />
                    
                    <Grid container spacing={2} alignItems="center">
                        <Grid item>
                            <IconButton 
                                onClick={() => {
                                    if (generatedPlaying) {
                                        generatedWavesurferRef.current.pause();
                                    } else {
                                        generatedWavesurferRef.current.play();
                                    }
                                }}
                            >
                                {generatedPlaying ? <PauseIcon /> : <PlayArrowIcon />}
                            </IconButton>
                            
                            <IconButton 
                                onClick={() => {
                                    generatedWavesurferRef.current.stop();
                                    setGeneratedPlaying(false);
                                }}
                            >
                                <StopIcon />
                            </IconButton>
                        </Grid>
                        
                        <Grid item xs>
                            <Typography variant="body2">
                                {formatTime(generatedTime)} / {formatTime(generatedDuration)}
                            </Typography>
                        </Grid>
                    </Grid>
                </CardContent>
            </Card>
            
            {/* Active Subtitle Display */}
            {activeSubtitle && (
                <Paper elevation={1} sx={{ p: 2, mb: 2, bgcolor: 'rgba(63, 81, 181, 0.1)' }}>
                    <Typography variant="body1">
                        {activeSubtitle.text}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                        {formatTime(activeSubtitle.start)} - {formatTime(activeSubtitle.end)}
                    </Typography>
                </Paper>
            )}
            
            <Box display="flex" justifyContent="flex-end" mt={2}>
                <Button variant="outlined" onClick={onClose}>
                    Close Comparison
                </Button>
            </Box>
        </Paper>
    );
};

export default AudioComparison; 