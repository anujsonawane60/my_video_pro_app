import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Container, Typography, Paper, Grid, Button, 
         Select, MenuItem, Slider, TextField, CircularProgress,
         Card, CardContent, IconButton, Tooltip, Alert } from '@mui/material';
import { styled } from '@mui/material/styles';
import { 
    MusicNote as AudioIcon,
    Subtitles as SubtitleIcon,
    Settings as SettingsIcon,
    Help as HelpIcon,
    Download as DownloadIcon,
    History as HistoryIcon,
    PlayArrow as PlayArrowIcon
} from '@mui/icons-material';
import { 
    getProjectAudioFiles, 
    getProjectSubtitleFiles, 
    createProjectFinalVideo,
    getProjectVideoStatus,
    downloadProjectVideo,
    getProjectVideoHistory,
    getFileUrl
} from '../services/api';

// Styled components
const StyledPaper = styled(Paper)(({ theme }) => ({
    padding: theme.spacing(3),
    marginBottom: theme.spacing(3),
    borderRadius: 12,
    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
}));

const FileCard = styled(Card)(({ theme }) => ({
    marginBottom: theme.spacing(2),
    cursor: 'pointer',
    transition: 'transform 0.2s',
    '&:hover': {
        transform: 'translateY(-2px)',
    },
    '&.selected': {
        border: `2px solid ${theme.palette.primary.main}`,
    },
}));

const VideoPreview = styled(Box)(({ theme }) => ({
    width: '100%',
    height: 400,
    backgroundColor: '#000',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    marginBottom: theme.spacing(3),
}));

const FinalVideoPage = () => {
    const { projectId } = useParams();
    
    // State management
    const [audioFiles, setAudioFiles] = useState([]);
    const [subtitleFiles, setSubtitleFiles] = useState([]);
    const [selectedAudio, setSelectedAudio] = useState(null);
    const [selectedSubtitle, setSelectedSubtitle] = useState(null);
    const [fontFamily, setFontFamily] = useState('Arial');
    const [fontSize, setFontSize] = useState(24);
    const [subtitleColor, setSubtitleColor] = useState('#FFFFFF');
    const [isCreating, setIsCreating] = useState(false);
    const [videoUrl, setVideoUrl] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [videoHistory, setVideoHistory] = useState([]);

    // Fetch available files and video history
    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const [audioData, subtitleData] = await Promise.all([
                    getProjectAudioFiles(projectId),
                    getProjectSubtitleFiles(projectId)
                ]);
                setAudioFiles(audioData);
                setSubtitleFiles(subtitleData);
                
                // Fetch video history
                const history = await getProjectVideoHistory(projectId);
                setVideoHistory(history);
            } catch (err) {
                setError('Failed to load files. Please try again.');
                console.error('Error loading files:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [projectId]);

    const handleCreateVideo = async () => {
        if (!selectedAudio || !selectedSubtitle) {
            setError('Please select both audio and subtitle files');
            return;
        }

        setIsCreating(true);
        setError(null);

        try {
            const data = {
                audioFile: selectedAudio,
                subtitleFile: selectedSubtitle,
                subtitleStyle: {
                    fontFamily,
                    fontSize,
                    color: subtitleColor
                }
            };

            console.log('Creating video with data:', data);
            const response = await createProjectFinalVideo(projectId, data);
            console.log('Video creation response:', response);
            
            if (!response.job_id) {
                throw new Error('No job ID received from server');
            }
            
            // Poll for video creation status
            const pollStatus = async () => {
                try {
                    console.log('Polling status for job:', response.job_id);
                    const status = await getProjectVideoStatus(projectId, response.job_id);
                    console.log('Status response:', status);
                    
                    if (status.status === 'completed') {
                        const videoPath = status.video_path;
                        setVideoUrl(videoPath);
                        // Refresh video history
                        const history = await getProjectVideoHistory(projectId);
                        setVideoHistory(history);
                        setIsCreating(false);
                    } else if (status.status === 'failed') {
                        throw new Error(status.error_message || 'Video creation failed');
                    } else {
                        // Continue polling if still processing
                        setTimeout(pollStatus, 2000);
                    }
                } catch (error) {
                    console.error('Error polling status:', error);
                    setError(error.message || 'Failed to check video status');
                    setIsCreating(false);
                }
            };

            // Start polling
            pollStatus();
        } catch (err) {
            console.error('Error creating video:', err);
            setError(err.message || 'Failed to create video. Please try again.');
            setIsCreating(false);
        }
    };

    const handleDownload = async (url) => {
        try {
            const videoId = url.split('/').pop(); // Get the filename from the URL
            const blob = await downloadProjectVideo(projectId, videoId);
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = videoId;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            document.body.removeChild(a);
        } catch (err) {
            setError('Failed to download video. Please try again.');
        }
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            {/* Header Section */}
            <Box textAlign="center" mb={4}>
                <Typography variant="h3" component="h1" gutterBottom>
                    🎬 Final Video Creator
                </Typography>
                <Typography variant="subtitle1" color="text.secondary">
                    Select audio and subtitles to generate your final video with custom subtitle styling
                </Typography>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            <Grid container spacing={3}>
                {/* File Selection Section */}
                <Grid item xs={12} md={6}>
                    <StyledPaper>
                        <Typography variant="h6" gutterBottom>
                            <AudioIcon sx={{ mr: 1 }} />
                            Audio Files
                        </Typography>
                        {audioFiles.map((file) => (
                            <FileCard 
                                key={file.id} 
                                onClick={() => setSelectedAudio(file)}
                                className={selectedAudio?.id === file.id ? 'selected' : ''}
                            >
                                <CardContent>
                                    <Typography variant="subtitle1">{file.name}</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Duration: {file.duration} • Added: {new Date(file.date).toLocaleDateString()}
                                    </Typography>
                                </CardContent>
                            </FileCard>
                        ))}
                    </StyledPaper>

                    <StyledPaper>
                        <Typography variant="h6" gutterBottom>
                            <SubtitleIcon sx={{ mr: 1 }} />
                            Subtitle Files
                        </Typography>
                        {subtitleFiles.map((file) => (
                            <FileCard 
                                key={file.id} 
                                onClick={() => setSelectedSubtitle(file)}
                                className={selectedSubtitle?.id === file.id ? 'selected' : ''}
                            >
                                <CardContent>
                                    <Typography variant="subtitle1">{file.name}</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Duration: {file.duration} • Added: {new Date(file.date).toLocaleDateString()}
                                    </Typography>
                                </CardContent>
                            </FileCard>
                        ))}
                    </StyledPaper>
                </Grid>

                {/* Video Preview and Styling Section */}
                <Grid item xs={12} md={6}>
                    <VideoPreview>
                        {videoUrl ? (
                            <video
                                controls
                                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                                src={getFileUrl(videoUrl)}
                            />
                        ) : (
                            <Typography variant="body1" color="white">
                                This is the base video. Audio and subtitles will be added.
                            </Typography>
                        )}
                    </VideoPreview>

                    <StyledPaper>
                        <Typography variant="h6" gutterBottom>
                            <SettingsIcon sx={{ mr: 1 }} />
                            Subtitle Styling
                            <Tooltip title="Customize how your subtitles will appear in the video">
                                <IconButton size="small">
                                    <HelpIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        </Typography>

                        <Grid container spacing={2}>
                            <Grid item xs={12}>
                                <Typography gutterBottom>Font Family</Typography>
                                <Select
                                    fullWidth
                                    value={fontFamily}
                                    onChange={(e) => setFontFamily(e.target.value)}
                                >
                                    <MenuItem value="Arial">Arial</MenuItem>
                                    <MenuItem value="Roboto">Roboto</MenuItem>
                                    <MenuItem value="Open Sans">Open Sans</MenuItem>
                                </Select>
                            </Grid>

                            <Grid item xs={12}>
                                <Typography gutterBottom>Font Size: {fontSize}px</Typography>
                                <Slider
                                    value={fontSize}
                                    onChange={(e, newValue) => setFontSize(newValue)}
                                    min={12}
                                    max={36}
                                    valueLabelDisplay="auto"
                                />
                            </Grid>

                            <Grid item xs={12}>
                                <Typography gutterBottom>Subtitle Color</Typography>
                                <Box display="flex" gap={1}>
                                    <Button
                                        variant="contained"
                                        sx={{ bgcolor: '#FFFFFF', '&:hover': { bgcolor: '#EEEEEE' } }}
                                        onClick={() => setSubtitleColor('#FFFFFF')}
                                    />
                                    <Button
                                        variant="contained"
                                        sx={{ bgcolor: '#FFFF00', '&:hover': { bgcolor: '#EEEE00' } }}
                                        onClick={() => setSubtitleColor('#FFFF00')}
                                    />
                                    <Button
                                        variant="contained"
                                        sx={{ bgcolor: '#FF0000', '&:hover': { bgcolor: '#EE0000' } }}
                                        onClick={() => setSubtitleColor('#FF0000')}
                                    />
                                    <TextField
                                        type="color"
                                        value={subtitleColor}
                                        onChange={(e) => setSubtitleColor(e.target.value)}
                                        sx={{ width: 60 }}
                                    />
                                </Box>
                            </Grid>
                        </Grid>
                    </StyledPaper>

                    {/* Action Button */}
                    <Box textAlign="center" mt={3}>
                        <Button
                            variant="contained"
                            size="large"
                            onClick={handleCreateVideo}
                            disabled={isCreating || !selectedAudio || !selectedSubtitle}
                            startIcon={isCreating ? <CircularProgress size={20} /> : null}
                        >
                            {isCreating ? 'Creating your video...' : 'Create Video'}
                        </Button>
                    </Box>

                    {/* Video History Section */}
                    <StyledPaper sx={{ mt: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            <HistoryIcon sx={{ mr: 1 }} />
                            Video History
                        </Typography>
                        {videoHistory.length > 0 ? (
                            videoHistory.map((video, index) => (
                                <FileCard key={index}>
                                    <CardContent>
                                        <Typography variant="subtitle1">
                                            Video {index + 1}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Created: {new Date(video.created_at).toLocaleString()}
                                        </Typography>
                                        <Box mt={1}>
                                            <Button
                                                variant="outlined"
                                                size="small"
                                                startIcon={<PlayArrowIcon />}
                                                onClick={() => setVideoUrl(video.url)}
                                                sx={{ mr: 1 }}
                                            >
                                                Preview
                                            </Button>
                                            <Button
                                                variant="outlined"
                                                size="small"
                                                startIcon={<DownloadIcon />}
                                                onClick={() => handleDownload(video.url)}
                                            >
                                                Download
                                            </Button>
                                        </Box>
                                    </CardContent>
                                </FileCard>
                            ))
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                No videos created yet
                            </Typography>
                        )}
                    </StyledPaper>
                </Grid>
            </Grid>
        </Container>
    );
};

export default FinalVideoPage;
