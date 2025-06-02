import React, { useEffect, useState } from 'react';
import { Box, Typography, Paper, Button, Grid } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { deleteProject, fetchProjects } from '../services/api';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';

const DashboardPage = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const fetchedProjects = await fetchProjects();
        setProjects(fetchedProjects);
        console.log('Fetched projects:', fetchedProjects);
        console.log('Projects state:', projects);
      } catch (e) {
        console.error('Failed to fetch projects:', e);
      }
    };

    loadProjects();
  }, []);

  const handleDeleteClick = (proj) => {
    setProjectToDelete(proj);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!projectToDelete) return;
    setDeleting(true);
    try {
      await deleteProject(projectToDelete.id);
      const fetchedProjects = await fetchProjects();
      setProjects(fetchedProjects);
      setDeleteDialogOpen(false);
      setProjectToDelete(null);
    } catch (e) {
      alert('Failed to delete project.');
    }
    setDeleting(false);
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
    setProjectToDelete(null);
  };

  return (
    <Box sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom align="center">
        Dashboard
      </Typography>
      <Grid container spacing={4} justifyContent="center">
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h6">Total Projects</Typography>
            <Typography variant="h3" color="primary">{projects.length}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Recent Projects</Typography>
            {projects.length === 0 ? (
              <Typography color="text.secondary">No projects yet.</Typography>
            ) : ( // Parenthesis for the "else" block of the ternary
              projects.slice(0, 5).map((proj) => (
                <Box key={proj.id} sx={{ mb: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography>{proj.filename}</Typography>
                  <Typography color="text.secondary">{proj.upload_time ? new Date(proj.upload_time).toLocaleDateString() : ''}</Typography>
                  <Box>
                    <Button size="small" onClick={() => navigate(`/project/${proj.id}`)}>Open</Button>
                    <Button size="small" color="error" onClick={() => handleDeleteClick(proj)} disabled={deleting}>Delete</Button>
                  </Box>
                </Box>
              )) // map() call ends
            ) /* <<< This was the missing closing parenthesis */
            }
          </Paper>
        </Grid>
      </Grid>
      <Box sx={{ mt: 4, textAlign: 'center' }}>
        <Button variant="contained" color="primary" sx={{ mr: 2 }} onClick={() => navigate('/new-project')}>
          Create New Project
        </Button>
        <Button variant="outlined" color="primary" onClick={() => navigate('/projects')}>
          View All Projects
        </Button>
      </Box>
      <Dialog open={deleteDialogOpen} onClose={handleCancelDelete}>
        <DialogTitle>Delete Project</DialogTitle>
        <DialogContent>
          Are you sure you want to delete the project "{projectToDelete?.filename}"? This will remove all data for this project and cannot be undone.
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelDelete} disabled={deleting}>Cancel</Button>
          <Button onClick={handleConfirmDelete} color="error" disabled={deleting}>{deleting ? 'Deleting...' : 'Delete'}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DashboardPage;