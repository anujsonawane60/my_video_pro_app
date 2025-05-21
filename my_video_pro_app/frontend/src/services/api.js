import axios from 'axios';

// Use the environment variable or fall back to default
export const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with timeout and error handling
const api = axios.create({
  baseURL: API_URL,
  timeout: 30000, // 30 seconds timeout
});

// Add request interceptor for error handling
api.interceptors.request.use(
  config => {
    // Add abort controller signal to every request
    const controller = new AbortController();
    config.signal = controller.signal;
    config.abortController = controller;
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    if (axios.isCancel(error)) {
      console.log('Request cancelled:', error.message);
    } else {
      console.error('API error:', error);
    }
    return Promise.reject(error);
  }
);

export const uploadVideo = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload-video/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const extractAudio = async (jobId) => {
  try {
    const response = await api.post(`/extract-audio/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error extracting audio:', error);
    throw error;
  }
};

export const generateSubtitles = async (jobId, settings) => {
  const formData = new FormData();
  
  // Add all settings to form data
  Object.keys(settings).forEach(key => {
    formData.append(key, settings[key]);
  });
  
  try {
    // Generate subtitles can take a long time, so use a longer timeout
    const response = await api.post(`/generate-subtitles/${jobId}`, formData, {
      timeout: 300000, // 5 minutes timeout for subtitle generation, especially for Marathi
      headers: {
        'Content-Type': 'multipart/form-data',
      }
    });
    
    // Log the response for debugging
    console.log('Subtitle generation successful:', response.status);
    console.log('Response data:', response.data);
    
    // Return the response data
    return response.data;
  } catch (error) {
    console.error('Error generating subtitles:', error);
    
    // Provide more detailed error information
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      console.error('Response error data:', error.response.data);
      console.error('Response error status:', error.response.status);
      console.error('Response error headers:', error.response.headers);
    } else if (error.request) {
      // The request was made but no response was received
      console.error('No response received:', error.request);
    } else {
      // Something happened in setting up the request that triggered an Error
      console.error('Error setting up request:', error.message);
    }
    
    throw error;
  }
};

export const changeVoice = async (jobId, settings) => {
  const formData = new FormData();
  
  // Add all settings to form data
  Object.keys(settings).forEach(key => {
    formData.append(key, settings[key]);
  });
  
  try {
    console.log('Sending voice change request with settings:', settings);
    
    const response = await api.post(`/change-voice/${jobId}`, formData, {
      timeout: 180000, // 3 minutes timeout for voice processing
      headers: {
        'Content-Type': 'multipart/form-data',
      }
    });
    
    console.log('Voice change successful:', response.status);
    console.log('Response data:', response.data);
    
    return response.data;
  } catch (error) {
    console.error('Error changing voice:', error);
    
    // Provide detailed error information
    if (error.response) {
      console.error('Response error data:', error.response.data);
      console.error('Response error status:', error.response.status);
    } else if (error.request) {
      console.error('No response received:', error.request);
    } else {
      console.error('Error setting up request:', error.message);
    }
    
    throw error;
  }
};

export const skipVoiceChange = async (jobId) => {
  try {
    console.log('Skipping voice change for job:', jobId);
    
    const response = await api.post(`/skip-voice-change/${jobId}`);
    
    console.log('Voice change skipped successfully:', response.status);
    console.log('Response data:', response.data);
    
    return response.data;
  } catch (error) {
    console.error('Error skipping voice change:', error);
    
    // Provide detailed error information
    if (error.response) {
      console.error('Response error data:', error.response.data);
      console.error('Response error status:', error.response.status);
    } else if (error.request) {
      console.error('No response received:', error.request);
    } else {
      console.error('Error setting up request:', error.message);
    }
    
    throw error;
  }
};

export const cleanAudio = async (jobId, settings) => {
  const formData = new FormData();
  
  // Add all settings to form data
  Object.keys(settings).forEach(key => {
    formData.append(key, settings[key]);
  });
  
  try {
    const response = await api.post(`/clean-audio/${jobId}`, formData);
    return response.data;
  } catch (error) {
    console.error('Error cleaning audio:', error);
    throw error;
  }
};

export const saveEditedSubtitles = async (jobId, subtitleContent) => {
  const formData = new FormData();
  formData.append('subtitle_content', subtitleContent);
  
  try {
    const response = await api.post(`/save-edited-subtitles/${jobId}`, formData);
    return response.data;
  } catch (error) {
    console.error('Error saving edited subtitles:', error);
    throw error;
  }
};

export const createFinalVideo = async (jobId, settings) => {
  const formData = new FormData();
  
  // Add all settings to form data
  Object.keys(settings).forEach(key => {
    formData.append(key, settings[key]);
  });
  
  try {
    const response = await api.post(`/create-final-video/${jobId}`, formData);
    return response.data;
  } catch (error) {
    console.error('Error creating final video:', error);
    throw error;
  }
};

export const getJobStatus = async (jobId) => {
  try {
    const response = await api.get(`/job-status/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting job status:', error);
    throw error;
  }
};

export const getVideoInfo = async (jobId) => {
  try {
    const response = await api.get(`/video-info/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting video info:', error);
    throw error;
  }
};

export const getDownloadUrl = (jobId, fileType) => {
  if (!jobId || !fileType) return '';
  return `${API_URL}/download/${jobId}/${fileType}`;
};

export const getFileUrl = (path) => {
  if (!path) return '';
  
  try {
    console.log('Getting file URL for path:', path);
    
    // Fix backslash issue by converting Windows paths to URL format
    const normalizedPath = path.replace(/\\/g, '/');
    console.log('Normalized path:', normalizedPath);
    
    // Handle absolute URLs (already containing http/https)
    if (normalizedPath.startsWith('http://') || normalizedPath.startsWith('https://')) {
      console.log('Returning absolute URL:', normalizedPath);
      return normalizedPath;
    }
    
    // Handle paths already starting with API_URL
    if (normalizedPath.startsWith(API_URL)) {
      console.log('Path already has API_URL, returning:', normalizedPath);
      return normalizedPath;
    }
    
    // Ensure there's a slash between API_URL and the path
    let finalUrl;
    if (normalizedPath.startsWith('/')) {
      finalUrl = `${API_URL}${normalizedPath}`;
    } else {
      finalUrl = `${API_URL}/${normalizedPath}`;
    }
    
    console.log('Final URL:', finalUrl);
    return finalUrl;
  } catch (error) {
    console.error('Error creating file URL:', error);
    return '';
  }
};

export const getSubtitleContent = async (jobId) => {
  try {
    const response = await api.get(`/subtitle-content/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting subtitle content:', error);
    throw error;
  }
};

export const getVoiceHistory = async (jobId) => {
  try {
    const response = await api.get(`/voice-history/${jobId}`);
    return response.data.voice_history || [];
  } catch (error) {
    console.error('Error getting voice history:', error);
    return [];
  }
};

export const translateSubtitles = async (jobId, settings) => {
  try {
    const formData = new FormData();
    
    // Add all settings to form data
    Object.keys(settings).forEach(key => {
      formData.append(key, settings[key]);
    });
    
    const response = await api.post(`/translate-subtitles/${jobId}`, formData, {
      timeout: 180000, // 3 minutes timeout for translation which can take longer
    });
    return response.data;
  } catch (error) {
    console.error('Error translating subtitles:', error);
    throw error;
  }
};

export const getAvailableAudio = async (jobId) => {
  try {
    const response = await api.get(`/available-audio/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching available audio files:', error);
    throw error;
  }
};

export const getAvailableSubtitles = async (jobId) => {
  try {
    const response = await api.get(`/available-subtitles/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching available subtitle files:', error);
    throw error;
  }
};

const apiService = {
  uploadVideo,
  extractAudio,
  generateSubtitles,
  changeVoice,
  skipVoiceChange,
  cleanAudio,
  saveEditedSubtitles,
  createFinalVideo,
  getJobStatus,
  getVideoInfo,
  getDownloadUrl,
  getFileUrl,
  getSubtitleContent,
  getVoiceHistory,
  translateSubtitles,
  getAvailableAudio,
  getAvailableSubtitles
};

export default apiService; 