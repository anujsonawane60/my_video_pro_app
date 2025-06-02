import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Grid, Card, CardContent, CardActions, Button } from '@mui/material';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import SubtitlesIcon from '@mui/icons-material/Subtitles';
import TranslateIcon from '@mui/icons-material/Translate';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';

const modules = [
  {
    id: 'clean-audio',
    name: 'Clean Audio',
    description: 'Remove noise, filler words, and enhance audio quality.',
    icon: <VolumeUpIcon fontSize="large" color="primary" />,
  },
  {
    id: 'voice-changer',
    name: 'Voice Changer',
    description: 'Change the voice in your audio using AI.',
    icon: <RecordVoiceOverIcon fontSize="large" color="primary" />,
  },
  {
    id: 'make-subtitle',
    name: 'Make Subtitle',
    description: 'Generate subtitles for your video/audio.',
    icon: <SubtitlesIcon fontSize="large" color="primary" />,
  },
  {
    id: 'translate-subtitle',
    name: 'Translate Subtitle',
    description: 'Translate subtitles into different languages.',
    icon: <TranslateIcon fontSize="large" color="primary" />,
  },
];

const ProjectOverviewPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();

  return (
    <Box sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom align="center">
        Project Modules
      </Typography>
      <Typography variant="subtitle1" align="center" color="text.secondary" sx={{ mb: 4 }}>
        Select a module to work on for this project.
      </Typography>
      <Grid container spacing={4} justifyContent="center">
        {modules.map((mod) => (
          <Grid item xs={12} sm={6} md={3} key={mod.id}>
            <Card sx={{ minHeight: 220, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                  {mod.icon}
                </Box>
                <Typography variant="h6" align="center">{mod.name}</Typography>
                <Typography variant="body2" color="text.secondary" align="center">{mod.description}</Typography>
              </CardContent>
              <CardActions sx={{ justifyContent: 'center' }}>
                <Button variant="contained" color="primary" onClick={() => navigate(`/project/${projectId}/${mod.id}`)}>
                  Open
                </Button>
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default ProjectOverviewPage;
