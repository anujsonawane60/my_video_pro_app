import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
export const API_URL = API_BASE_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper function to get file URL
export const getFileUrl = (path) => {
  if (!path) return '';
  // If the path is already a full URL, return it
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  // If the path starts with /outputs, it's already relative to the API base
  if (path.startsWith('/outputs')) {
    return `${API_BASE_URL}${path}`;
  }
  // Otherwise, assume it's a relative path from the API base
  return `${API_BASE_URL}/${path}`;
};

// Helper function to get download URL
export const getDownloadUrl = (jobId, fileType) => {
  return `${API_BASE_URL}/download/${jobId}/${fileType}`;
};

// Project related endpoints
export const uploadVideo = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await api.post('/upload-video/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    console.error('Error uploading video:', error);
    if (error.response) {
      throw new Error(error.response.data.detail || 'Failed to upload video');
    }
    throw new Error('Failed to upload video');
  }
};

// Define getAllProjects first
export const getAllProjects = async () => {
  const response = await api.get('/projects');
  return response.data;
};

// Then create the alias
export const fetchProjects = getAllProjects;

export const getProjectStatus = async (jobId) => {
  const response = await api.get(`/job-status/${jobId}`);
  return response.data;
};

// Alias for getProjectStatus
export const getJobStatus = getProjectStatus;

export const deleteProject = async (jobId) => {
  const response = await api.delete(`/project/${jobId}`);
  return response.data;
};

// Video related endpoints
export const getVideoInfo = async (jobId) => {
  const response = await api.get(`/job-status/${jobId}`);
  return response.data;
};

export const createFinalVideo = async (jobId) => {
  const response = await api.post(`/create-final-video/${jobId}`);
  return response.data;
};

// Audio related endpoints
export const extractAudio = async (jobId) => {
  const response = await api.post(`/extract-audio/${jobId}`);
  return response.data;
};

export const cleanAudio = async (jobId, params) => {
  const formData = new FormData();
  if (params.audioFileId) formData.append('audio_file_id', params.audioFileId);
  formData.append('noise_reduction_sensitivity', params.noiseReductionSensitivity || 0.8);
  formData.append('vad_aggressiveness', params.vadAggressiveness || 1);
  
  const response = await api.post(`/clean-audio/${jobId}`, formData);
  return response.data;
};

export const getAvailableAudio = async (jobId) => {
  try {
    console.log('Fetching available audio for job:', jobId);
    const response = await api.get(`/available-audio/${jobId}`);
    console.log('Available audio response:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error in getAvailableAudio:', error);
    if (error.response) {
      throw new Error(error.response.data.detail || 'Failed to fetch available audio');
    }
    throw new Error('Failed to fetch available audio');
  }
};

export const getCleanedAudioFiles = async (jobId) => {
  const response = await api.get(`/project/${jobId}/clean-audio-files`);
  return response.data;
};

// Voice related endpoints
export const changeVoice = async (jobId, params) => {
  const formData = new FormData();
  formData.append('voice_id', params.voiceId);
  if (params.subtitleId) formData.append('subtitle_id', params.subtitleId);
  
  const response = await api.post(`/change-voice/${jobId}`, formData);
  return response.data;
};

export const skipVoiceChange = async (jobId) => {
  const response = await api.post(`/skip-voice-change/${jobId}`);
  return response.data;
};

export const getVoiceHistory = async (jobId) => {
  const response = await api.get(`/voice-history/${jobId}`);
  return response.data;
};

// Subtitle related endpoints
export const generateSubtitles = async (jobId, params) => {
  const formData = new FormData();
  formData.append('transcription_method', params.transcriptionMethod || 'whisper');
  formData.append('language', params.language || 'en');
  formData.append('whisper_model_size', params.whisperModelSize || 'base');
  if (params.assemblyaiApiKey) formData.append('assemblyai_api_key', params.assemblyaiApiKey);
  
  const response = await api.post(`/generate-subtitles/${jobId}`, formData);
  return response.data;
};

export const saveEditedSubtitles = async (jobId, subtitleContent) => {
  try {
    console.log('Saving subtitles for job:', jobId);
    const formData = new FormData();
    formData.append('subtitle_content', subtitleContent);
    
    const response = await api.post(`/save-edited-subtitles/${jobId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    console.log('Save subtitles response:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error in saveEditedSubtitles:', error);
    if (error.response) {
      throw new Error(error.response.data.detail || 'Failed to save subtitles');
    }
    throw error;
  }
};

export const getSubtitleContent = async (jobId) => {
  const response = await api.get(`/subtitle-content/${jobId}`);
  return response.data;
};

export const getAvailableSubtitles = async (jobId) => {
  const response = await api.get(`/available-subtitles/${jobId}`);
  return response.data;
};

export const translateSubtitles = async (jobId, params) => {
  const formData = new FormData();
  formData.append('target_language', params.targetLanguage);
  if (params.subtitleId) formData.append('subtitle_id', params.subtitleId);
  
  const response = await api.post(`/translate-subtitles/${jobId}`, formData);
  return response.data;
};

// File download endpoints
export const downloadFile = async (jobId, fileType) => {
  const response = await api.get(`/download/${jobId}/${fileType}`, {
    responseType: 'blob'
  });
  return response.data;
};

export default api; 