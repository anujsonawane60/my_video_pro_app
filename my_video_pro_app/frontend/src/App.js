import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import VideoCameraBackIcon from '@mui/icons-material/VideoCameraBack';
import { useParams } from 'react-router-dom';

// Import pages
import HomePage from './pages/HomePage';
import ProcessingPage from './pages/ProcessingPage';
import DashboardPage from './pages/DashboardPage';
import ProjectOverviewPage from './pages/ProjectOverviewPage';
import NewProjectPage from './pages/NewProjectPage';
import CleanAudioPage from './pages/CleanAudioPage';
import MakeSubtitlePage from './pages/MakeSubtitlePage';

// Create a theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#3f51b5',
    },
    secondary: {
      main: '#f50057',
    },
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <div className="App">
          <AppBar position="static">
            <Toolbar>
              <VideoCameraBackIcon sx={{ mr: 2 }} />
              <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                Video Processing App
              </Typography>
            </Toolbar>
          </AppBar>
          
          <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/new-project" element={<NewProjectPage />} />
              <Route path="/projects" element={<ProcessingPage />} />
              <Route path="/process/:jobId" element={<ProcessingPage />} />
              <Route path="/project/:projectId" element={<ProjectOverviewPage />} />
              <Route path="/project/:projectId/clean-audio" element={<CleanAudioPage />} />
              <Route path="/project/:projectId/make-subtitle" element={<MakeSubtitlePageWrapper />} />
              {/* Module routes will be added here */}
            </Routes>
          </Container>
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;

// Wrapper to extract projectId from params and pass as jobId
function MakeSubtitlePageWrapper() {
  const { projectId } = useParams();
  return <MakeSubtitlePage jobId={projectId} />;
}
