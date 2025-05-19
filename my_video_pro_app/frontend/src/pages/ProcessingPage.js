import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Stepper,
  Step,
  StepLabel,
  Button,
  Paper,
  CircularProgress,
  Divider,
  TextField,
  FormControl,
  FormControlLabel,
  Select,
  MenuItem,
  Switch,
  Slider,
  Grid,
  Card,
  CardContent,
  CardActions,
  Alert,
  LinearProgress,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Tooltip,
  Collapse,
  Avatar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormHelperText
} from '@mui/material';
import AudioWaveform from '../components/AudioWaveform';
import WaveformComparison from '../components/WaveformComparison';
import {
  extractAudio,
  generateSubtitles,
  cleanAudio,
  saveEditedSubtitles,
  createFinalVideo,
  getJobStatus,
  getVideoInfo,
  getDownloadUrl,
  getFileUrl,
  getSubtitleContent,
  changeVoice,
  skipVoiceChange,
  getVoiceHistory,
  translateSubtitles
} from '../services/api';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import InfoIcon from '@mui/icons-material/Info';
import BarChartIcon from '@mui/icons-material/BarChart';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AddIcon from '@mui/icons-material/Add';
import SettingsIcon from '@mui/icons-material/Settings';
import CompareIcon from '@mui/icons-material/Compare';

// Define processing steps
const steps = [
  'Upload Video',
  'Extract Audio',
  'Generate Subtitles',
  'Voice Changer',
  'Clean Audio',
  'Create Final Video'
];

// Helper for formatting time
const formatTime = (seconds) => {
  if (!seconds && seconds !== 0) return '0:00';
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

const ProcessingPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  
  // State variables
  const [activeStep, setActiveStep] = useState(1); // Upload is done, starting at Extract Audio
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [videoInfo, setVideoInfo] = useState(null);
  const [job, setJob] = useState(null);
  
  // Audio extraction state
  const [audioPath, setAudioPath] = useState(null);
  
  // Subtitle generation state
  const [transcriptionMethod, setTranscriptionMethod] = useState('whisper');
  const [language, setLanguage] = useState('en');
  const [whisperModelSize, setWhisperModelSize] = useState('base');
  const [assemblyaiApiKey, setAssemblyaiApiKey] = useState('');
  const [subtitlePath, setSubtitlePath] = useState(null);
  const [subtitleContent, setSubtitleContent] = useState('');
  const [editedSubtitleContent, setEditedSubtitleContent] = useState('');
  
  // Voice changer state
  const [voiceCharacter, setVoiceCharacter] = useState('21m00Tcm4TlvDq8ikWAM'); // Default is Rachel
  const [voiceStability, setVoiceStability] = useState(0.5);
  const [voiceClarity, setVoiceClarity] = useState(0.75);
  const [voiceChangedAudioPath, setVoiceChangedAudioPath] = useState(null);
  const [voiceHistory, setVoiceHistory] = useState([]);
  const [customVoiceName, setCustomVoiceName] = useState('');
  const [showVoiceHistory, setShowVoiceHistory] = useState(false);
  const [showCharacterSelector, setShowCharacterSelector] = useState(false);
  const [showVoiceComparisonModal, setShowVoiceComparisonModal] = useState(false);
  const [subtitleSelection, setSubtitleSelection] = useState('original'); // 'original', 'edited', 'marathi', 'hindi'
  const [availableSubtitleOptions, setAvailableSubtitleOptions] = useState([
    { id: 'original', name: 'Original Subtitles (English)', available: true }
  ]);
  
  const [availableVoices, setAvailableVoices] = useState([
    { id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel (Female)' },
    { id: 'AZnzlk1XvdvUeBnXmlld', name: 'Domi (Female)' },
    { id: 'EXAVITQu4vr4xnSDxMaL', name: 'Bella (Female)' },
    { id: 'ErXwobaYiN019PkySvjV', name: 'Antoni (Male)' },
    { id: 'MF3mGyEYCl7XYWbV9V6O', name: 'Elli (Female)' },
    { id: 'TxGEqnHWrfWFTfGW9XjX', name: 'Josh (Male)' },
    { id: 'VR6AewLTigWG4xSOukaG', name: 'Arnold (Male)' },
    { id: 'pNInz6obpgDQGcFmaJgB', name: 'Adam (Male)' },
    { id: 'yoZ06aMxZJJ28mfd3POQ', name: 'Sam (Male)' }
  ]);
  
  // Audio cleaning state
  const [enableNoiseReduction, setEnableNoiseReduction] = useState(true);
  const [noiseReductionSensitivity, setNoiseReductionSensitivity] = useState(0.2);
  const [enableVadCleaning, setEnableVadCleaning] = useState(true);
  const [vadAggressiveness, setVadAggressiveness] = useState(1);
  const [cleanedAudioPath, setCleanedAudioPath] = useState(null);
  
  // Final video state
  const [fontSize, setFontSize] = useState(24);
  const [subtitleColor, setSubtitleColor] = useState('white');
  const [subtitleBgOpacity, setSubtitleBgOpacity] = useState(80);
  const [useDirectFfmpeg, setUseDirectFfmpeg] = useState(true);
  const [finalVideoPath, setFinalVideoPath] = useState(null);
  
  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  // Translation state
  const [translationLanguage, setTranslationLanguage] = useState('mr');
  const [translatedSubtitleContent, setTranslatedSubtitleContent] = useState('');
  const [translationLoading, setTranslationLoading] = useState(false);
  const [translationError, setTranslationError] = useState(null);
  const [translatedSubtitlePath, setTranslatedSubtitlePath] = useState(null);
  const [saveTranslationLoading, setSaveTranslationLoading] = useState(false);
  const [originalSubtitleForTranslation, setOriginalSubtitleForTranslation] = useState('');
  
  // Function to toggle sidebar
  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };
  
  // Load job status on initial render
  useEffect(() => {
    if (jobId) {
      // Fetch job status
      fetchJobStatus();
      
      // Fetch video info
      const fetchVideoInfo = async () => {
        try {
          const videoInfoResult = await getVideoInfo(jobId);
          setVideoInfo(videoInfoResult.video_info);
        } catch (error) {
          console.error('Error fetching video info:', error);
        }
      };
      fetchVideoInfo();
      
      // Fetch subtitle content if available
      fetchSubtitleContent();
      
      // Fetch voice history
      fetchVoiceHistory();
    }
    
    // Cleanup function
    return () => {
      // Cleanup code here
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]); // We're using eslint-disable to avoid circular dependency issues
  
  // Fetch job status function
  const fetchJobStatus = async () => {
    try {
      const jobData = await getJobStatus(jobId);
      setJob(jobData);
      
      // Update subtitle options based on the new job data
      updateSubtitleOptions();
      
      // Set active step based on job status
      if (jobData.status === 'uploaded') {
        setActiveStep(1); // Extract Audio
      } else if (jobData.status === 'audio_extracted') {
        setActiveStep(2); // Generate Subtitles
        setAudioPath(jobData.steps.extract_audio.path);
      } else if (jobData.status === 'subtitles_generated') {
        setActiveStep(3); // Voice Changer
        setAudioPath(jobData.steps.extract_audio.path);
        setSubtitlePath(jobData.steps.generate_subtitles.path);
      } else if (jobData.status === 'voice_changed') {
        setActiveStep(4); // Clean Audio
        setAudioPath(jobData.steps.extract_audio.path);
        setSubtitlePath(jobData.steps.generate_subtitles.path);
        setVoiceChangedAudioPath(jobData.steps.change_voice?.path);
      } else if (jobData.status === 'voice_change_skipped') {
        setActiveStep(4); // Clean Audio
        setAudioPath(jobData.steps.extract_audio.path);
        setSubtitlePath(jobData.steps.generate_subtitles.path);
        // No voiceChangedAudioPath since it was skipped
      } else if (jobData.status === 'audio_cleaned') {
        setActiveStep(5); // Create Final Video
        setAudioPath(jobData.steps.extract_audio.path);
        setSubtitlePath(jobData.steps.generate_subtitles.path);
        setVoiceChangedAudioPath(jobData.steps.change_voice?.path);
        setCleanedAudioPath(jobData.steps.clean_audio.path);
      } else if (jobData.status === 'completed') {
        setActiveStep(6); // Completed
        setAudioPath(jobData.steps.extract_audio.path);
        setSubtitlePath(jobData.steps.generate_subtitles.path);
        setVoiceChangedAudioPath(jobData.steps.change_voice?.path);
        setCleanedAudioPath(jobData.steps.clean_audio.path);
        setFinalVideoPath(jobData.steps.create_final_video.path);
      }
    } catch (error) {
      console.error('Error fetching job status:', error);
      setError('Failed to load job information. Please try again.');
    }
  };
  
  // Fetch subtitle content function
  const fetchSubtitleContent = async () => {
    if (!jobId || !subtitlePath) return;
    
    try {
      const response = await getSubtitleContent(jobId);
      if (response && response.subtitle_content) {
        setSubtitleContent(response.subtitle_content);
        setEditedSubtitleContent(response.subtitle_content);
      }
    } catch (error) {
      console.error('Error fetching subtitle content:', error);
    }
  };
  
  // Effect to fetch subtitle content from URL if API call doesn't work
  useEffect(() => {
    const fetchSubtitleFromUrl = async () => {
      if (subtitlePath && (!subtitleContent || subtitleContent.trim() === '') && !loading) {
        try {
          // Get the full URL
          const subtitleUrl = getFileUrl(subtitlePath);
          console.log('Fetching subtitle content from URL:', subtitleUrl);
          
          // Fetch the content with timeout
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
          
          const response = await fetch(subtitleUrl, {
            signal: controller.signal,
            headers: {
              'Cache-Control': 'no-cache',
              'Pragma': 'no-cache'
            }
          });
          
          clearTimeout(timeoutId);
          
          if (!response.ok) {
            throw new Error(`Failed to fetch subtitles: ${response.status} ${response.statusText}`);
          }
          
          const content = await response.text();
          console.log('Subtitle content fetched, length:', content.length);
          
          // Only update if we actually got content
          if (content && content.trim() !== '') {
            // Update the state
            setSubtitleContent(content);
            setEditedSubtitleContent(content);
            console.log('Successfully updated subtitle content states');
          } else {
            console.warn('Fetched empty subtitle content');
          }
        } catch (error) {
          console.error('Error fetching subtitle content from URL:', error);
        }
      }
    };
    
    fetchSubtitleFromUrl();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subtitlePath, subtitleContent, loading]);
  
  // Handle synchronized scrolling of subtitle boxes
  useEffect(() => {
    if (activeStep > 2 && subtitlePath) {
      // Add a slight delay to ensure elements are rendered
      const setupScrollSync = setTimeout(() => {
        const originalEl = document.getElementById('original-subtitles');
        const editedEl = document.getElementById('edited-subtitles');
        
        if (originalEl && editedEl) {
          const originalInput = originalEl.querySelector('textarea');
          const editedInput = editedEl.querySelector('textarea');
          
          if (originalInput && editedInput) {
            // Store references to listeners so we can remove them later
            const originalScrollHandler = () => {
              editedInput.scrollTop = originalInput.scrollTop;
            };
            
            const editedScrollHandler = () => {
              originalInput.scrollTop = editedInput.scrollTop;
            };
            
            // Add scroll event listeners
            originalInput.addEventListener('scroll', originalScrollHandler);
            editedInput.addEventListener('scroll', editedScrollHandler);
            
            // Return cleanup function to remove listeners when component unmounts
            return () => {
              originalInput.removeEventListener('scroll', originalScrollHandler);
              editedInput.removeEventListener('scroll', editedScrollHandler);
              clearTimeout(setupScrollSync);
            };
          }
        }
      }, 500);
      
      // Cleanup function
      return () => clearTimeout(setupScrollSync);
    }
  }, [activeStep, subtitlePath, subtitleContent, editedSubtitleContent]);
  
  // Handle extract audio
  const handleExtractAudio = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await extractAudio(jobId);
      setAudioPath(response.audio_path);
      setActiveStep(2);
      
      // Update job
      const jobData = await getJobStatus(jobId);
      setJob(jobData);
    } catch (error) {
      console.error('Error extracting audio:', error);
      setError('Failed to extract audio. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  // Handle generate subtitles
  const handleGenerateSubtitles = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const settings = {
        transcription_method: transcriptionMethod,
        language: language,
        whisper_model_size: whisperModelSize,
      };
      
      if (transcriptionMethod === 'assemblyai' && assemblyaiApiKey) {
        settings.assemblyai_api_key = assemblyaiApiKey;
      }
      
      console.log('Sending subtitle generation request with settings:', settings);
      
      // Increase the timeout for subtitle generation which can take longer
      const response = await generateSubtitles(jobId, settings);
      
      console.log('Full subtitle generation response:', response);
      
      // Ensure we're correctly handling the response
      if (response.subtitle_path) {
        console.log('Setting subtitle path to:', response.subtitle_path);
        setSubtitlePath(response.subtitle_path);
      } else {
        console.warn('No subtitle_path in response');
      }
      
      if (response.subtitle_content) {
        console.log('Setting subtitle content, length:', response.subtitle_content.length);
        setSubtitleContent(response.subtitle_content);
        setEditedSubtitleContent(response.subtitle_content);
      } else {
        console.warn('No subtitle_content in response');
        
        // If we have a path but no content, try getting it directly via API
        try {
          console.log('Attempting to get subtitle content via direct API');
          const content = await getSubtitleContent(jobId);
          if (content) {
            console.log('Got subtitle content via API, length:', content.length);
            setSubtitleContent(content);
            setEditedSubtitleContent(content);
          } else {
            console.warn('Got empty content from API');
            
            // Fall back to fetching the file if API doesn't return content
            if (response.subtitle_path) {
              try {
                const subtitleUrl = getFileUrl(response.subtitle_path);
                console.log('Fetching subtitle content from URL:', subtitleUrl);
                
                const contentResponse = await fetch(subtitleUrl);
                if (contentResponse.ok) {
                  const fileContent = await contentResponse.text();
                  console.log('Fetched subtitle content, length:', fileContent.length);
                  setSubtitleContent(fileContent);
                  setEditedSubtitleContent(fileContent);
                } else {
                  console.error('Failed to fetch subtitle content:', contentResponse.status, contentResponse.statusText);
                }
              } catch (fetchError) {
                console.error('Error fetching subtitle content:', fetchError);
              }
            }
          }
        } catch (apiError) {
          console.error('Error getting subtitle content via API:', apiError);
        }
      }
      
      // Update active step regardless of content
      setActiveStep(3);
      
      // Update job data to get latest state
      const jobData = await getJobStatus(jobId);
      console.log('Updated job data after subtitle generation:', jobData);
      setJob(jobData);
      
      // Log success for debugging
      console.log('Subtitles generated successfully');
    } catch (error) {
      console.error('Error generating subtitles:', error);
      console.error('Error details:', error.response?.data || error.message || 'Unknown error');
      setError(`Failed to generate subtitles: ${error.response?.data?.error || error.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Handle voice change
  const handleChangeVoice = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Save edited subtitles first if they're modified
      if (subtitleContent !== editedSubtitleContent) {
        console.log('Saving edited subtitles before voice change...');
        const saveResult = await handleSaveEditedSubtitles();
        if (!saveResult) {
          throw new Error('Failed to save edited subtitles before changing voice');
        }
      }
      
      // Reset any previous voice-related state to prevent conflicts
      setVoiceChangedAudioPath(null);
      
      const settings = {
        voice_id: voiceCharacter,
        stability: voiceStability,
        clarity: voiceClarity,
        subtitle_selection: subtitleSelection
      };
      
      // Add custom voice name if provided
      if (customVoiceName) {
        settings.voice_name = customVoiceName;
      } else {
        // Use the name from availableVoices if no custom name is provided
        const selectedVoice = availableVoices.find(v => v.id === voiceCharacter);
        if (selectedVoice) {
          settings.voice_name = selectedVoice.name;
        }
      }
      
      console.log('Sending voice change request with settings:', settings);
      
      // Show loading state with message
      setLoading(true);
      setError('Voice generation in progress. This may take up to 2 minutes...');
      
      const response = await changeVoice(jobId, settings);
      console.log('Voice change response:', response);
      
      // Clear error message used for loading notification
      setError(null);
      
      // Check if the voice change was skipped
      if (response.status === "voice_change_skipped") {
        const errorMsg = response.message || "Voice changing was skipped";
        console.log('Voice change was skipped:', errorMsg);
        
        // Display the error message to the user
        setError(errorMsg);
        
        // Set voice path to null to ensure UI handles this state
        setVoiceChangedAudioPath(null);
        
        // Update voice history
        if (response.voice_history) {
          setVoiceHistory(response.voice_history);
        } else {
          // Fetch latest history if not included in response
          await fetchVoiceHistory();
        }
        
        // Still proceed to the next step
        setActiveStep(4);
        
        // Update job
        const jobData = await getJobStatus(jobId);
        setJob(jobData);
        
        return;
      }
      
      if (!response || !response.voice_changed_audio_path) {
        throw new Error('No audio path received in response');
      }
      
      // Set the new voice audio path with a cache-busting parameter to force reload
      const cacheBuster = new Date().getTime();
      setVoiceChangedAudioPath(`${response.voice_changed_audio_path}?t=${cacheBuster}`);
      
      // Update voice history
      if (response.voice_history) {
        setVoiceHistory(response.voice_history);
      } else {
        // Fetch latest history if not included in response
        await fetchVoiceHistory();
      }
      
      // Clear the custom voice name field
      setCustomVoiceName('');
      
      setActiveStep(4);
      
      // Update job
      const jobData = await getJobStatus(jobId);
      setJob(jobData);
      
      console.log('Voice changed successfully');
    } catch (error) {
      console.error('Error changing voice:', error);
      let errorMessage = 'Failed to change voice. ';
      
      if (error.response?.data?.detail) {
        const detailError = error.response.data.detail;
        
        // Check for credit-related errors
        if (detailError.includes('Not enough ElevenLabs credits')) {
          // Extract the credit information
          const creditMatch = detailError.match(/(\d+) available, (\d+) required/);
          
          if (creditMatch && creditMatch.length >= 3) {
            const available = parseInt(creditMatch[1]);
            const required = parseInt(creditMatch[2]);
            
            errorMessage = `Insufficient ElevenLabs credits: You have ${available} credits but need ${required}. `;
            
            // Add suggestions based on the situation
            if (required > available * 2) {
              errorMessage += 'Try significantly reducing text length or upgrading your ElevenLabs plan.';
            } else {
              errorMessage += 'Try editing subtitles to reduce length or upgrading your ElevenLabs plan.';
            }
          } else {
            errorMessage += detailError;
          }
        } else {
          errorMessage += detailError;
        }
      } else if (error.message) {
        errorMessage += error.message;
      } else {
        errorMessage += 'Unknown error occurred';
      }
      
      console.error('Error details:', errorMessage);
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };
  
  // Function to update available subtitle options
  const updateSubtitleOptions = () => {
    const subtitleOptions = [
      { id: 'original', name: 'Original Subtitles (English)', available: true }
    ];
    
    // Check for edited subtitles
    if (editedSubtitleContent && editedSubtitleContent !== subtitleContent) {
      subtitleOptions.push({ id: 'edited', name: 'Edited Subtitles (English)', available: true });
    }
    
    // Check for translated subtitles
    if (job?.translated_subtitle_path_mr || (translatedSubtitleContent && translationLanguage === 'mr')) {
      subtitleOptions.push({ id: 'marathi', name: 'Marathi Subtitles', available: true });
    }
    
    if (job?.translated_subtitle_path_hi || (translatedSubtitleContent && translationLanguage === 'hi')) {
      subtitleOptions.push({ id: 'hindi', name: 'Hindi Subtitles', available: true });
    }
    
    console.log("Updated subtitle options:", subtitleOptions);
    setAvailableSubtitleOptions(subtitleOptions);
  };
  
  // Effect to update subtitle options when relevant state changes
  useEffect(() => {
    updateSubtitleOptions();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editedSubtitleContent, subtitleContent, translatedSubtitleContent, translationLanguage, job]);
  
  // Handle save edited subtitles
  const handleSaveEditedSubtitles = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await saveEditedSubtitles(jobId, editedSubtitleContent);
      // Update subtitle path to use edited version
      setSubtitlePath(response.edited_subtitle_path);
      
      // Update subtitle options
      updateSubtitleOptions();
      
      setLoading(false);
      return true;
    } catch (error) {
      console.error('Error saving edited subtitles:', error);
      setError('Failed to save edited subtitles. Please try again.');
      setLoading(false);
      return false;
    }
  };
  
  // Handle clean audio
  const handleCleanAudio = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Save edited subtitles first if they're modified
      if (subtitleContent !== editedSubtitleContent) {
        const saveResult = await handleSaveEditedSubtitles();
        if (!saveResult) {
          throw new Error('Failed to save edited subtitles before cleaning audio');
        }
      }
      
      const settings = {
        enable_noise_reduction: enableNoiseReduction,
        noise_reduction_sensitivity: noiseReductionSensitivity,
        enable_vad_cleaning: enableVadCleaning,
        vad_aggressiveness: vadAggressiveness
      };
      
      const response = await cleanAudio(jobId, settings);
      setCleanedAudioPath(response.cleaned_audio_path);
      setActiveStep(5);
      
      // Update job
      const jobData = await getJobStatus(jobId);
      setJob(jobData);
    } catch (error) {
      console.error('Error cleaning audio:', error);
      setError('Failed to clean audio. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  // Handle create final video
  const handleCreateFinalVideo = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const settings = {
        font_size: fontSize,
        subtitle_color: subtitleColor,
        subtitle_bg_opacity: subtitleBgOpacity,
        use_direct_ffmpeg: useDirectFfmpeg
      };
      
      // Use edited subtitle path if available
      if (job && job.edited_subtitle_path) {
        settings.subtitle_path = job.edited_subtitle_path;
      }
      
      const response = await createFinalVideo(jobId, settings);
      setFinalVideoPath(response.final_video_path);
      setActiveStep(6);
      
      // Update job
      const jobData = await getJobStatus(jobId);
      setJob(jobData);
    } catch (error) {
      console.error('Error creating final video:', error);
      setError('Failed to create final video. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch voice history
  const fetchVoiceHistory = async () => {
    if (!jobId) return;
    
    try {
      const history = await getVoiceHistory(jobId);
      
      if (!history || history.length === 0) {
        console.log('No voice history available');
        return;
      }
      
      console.log('Fetched voice history:', history);
      setVoiceHistory(history);
      
      // If we have voice history, set the current audio path to the latest one
      // with a cache-busting parameter to force reload
      const latestVoice = history[history.length - 1];
      if (latestVoice && latestVoice.url_path) {
        const cacheBuster = new Date().getTime();
        const audioPathWithCacheBuster = `${latestVoice.url_path}?t=${cacheBuster}`;
        console.log('Setting voice changed audio path to:', audioPathWithCacheBuster);
        setVoiceChangedAudioPath(audioPathWithCacheBuster);
      } else {
        console.warn('Latest voice entry does not have a valid url_path');
      }
    } catch (error) {
      console.error('Error fetching voice history:', error);
    }
  };
  
  // Effect to potentially fetch available voices from ElevenLabs
  // This could be implemented in the future to dynamically get voices
  useEffect(() => {
    // This is where we would implement an API call to get voices
    // For now, we're using the predefined list
    // Example implementation for future use:
    /*
    const fetchVoices = async () => {
      try {
        // Would call an API endpoint that returns available voices
        const response = await fetch('/api/voices');
        const voices = await response.json();
        setAvailableVoices(voices);
      } catch (error) {
        console.error('Error fetching voices:', error);
      }
    };
    
    fetchVoices();
    */
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Handle translate subtitles
  const handleTranslateSubtitles = async () => {
    setTranslationLoading(true);
    setTranslationError(null);
    
    try {
      // Show a message to indicate that translation is in progress
      setTranslationError('Translation in progress. This may take a few minutes for large subtitle files...');
      
      const settings = {
        target_language: translationLanguage,
        content: editedSubtitleContent
      };
      
      console.log('Sending translation request with settings:', settings);
      console.log(`Translating approximately ${editedSubtitleContent.split('\n').length} lines to ${translationLanguage === 'mr' ? 'Marathi' : 'Hindi'}`);
      
      const response = await translateSubtitles(jobId, settings);
      
      console.log('Translation response:', response);
      
      // Clear the info message
      setTranslationError(null);
      
      if (response.translated_content) {
        setTranslatedSubtitleContent(response.translated_content);
        if (response.translated_subtitle_path) {
          setTranslatedSubtitlePath(response.translated_subtitle_path);
        }
        
        // Update subtitle options to include the newly translated subtitles
        updateSubtitleOptions();
      } else {
        throw new Error('No translated content received');
      }
    } catch (error) {
      console.error('Error translating subtitles:', error);
      // Provide more detailed error message
      let errorMessage = 'Failed to translate subtitles. ';
      
      if (error.message?.includes('timeout')) {
        errorMessage += 'The translation timed out. Try translating in smaller chunks or try again later.';
      } else if (error.response?.data?.detail) {
        errorMessage += error.response.data.detail;
      } else if (error.message) {
        errorMessage += error.message;
      } else {
        errorMessage += 'Unknown error occurred';
      }
      
      setTranslationError(errorMessage);
    } finally {
      setTranslationLoading(false);
    }
  };
  
  // Handle save translated subtitles
  const handleSaveTranslatedSubtitles = async () => {
    setSaveTranslationLoading(true);
    setTranslationError(null);
    
    try {
      const settings = {
        target_language: translationLanguage,
        content: translatedSubtitleContent
      };
      
      const response = await saveEditedSubtitles(jobId, translatedSubtitleContent, translationLanguage);
      
      if (response.edited_subtitle_path) {
        setTranslatedSubtitlePath(response.edited_subtitle_path);
      }
      
      // Show success message or update UI as needed
    } catch (error) {
      console.error('Error saving translated subtitles:', error);
      setTranslationError(`Failed to save translated subtitles: ${error.message || 'Unknown error'}`);
    } finally {
      setSaveTranslationLoading(false);
    }
  };
  
  // Handle download translated subtitles
  const handleDownloadTranslatedSubtitles = () => {
    if (translatedSubtitlePath) {
      // Create download link
      const downloadUrl = getFileUrl(translatedSubtitlePath);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `subtitles_${translationLanguage === 'mr' ? 'marathi' : 'hindi'}.srt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else if (translatedSubtitleContent) {
      // Create blob from content and download
      const blob = new Blob([translatedSubtitleContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `subtitles_${translationLanguage === 'mr' ? 'marathi' : 'hindi'}.srt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };
  
  // Add a new handler function for skipping voice change
  const handleSkipVoiceChange = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Skipping voice change for job:', jobId);
      const response = await skipVoiceChange(jobId);
      
      // Update job status
      setLoading(false);
      fetchJobStatus(); // Use fetchJobStatus instead of updateJobStatus
      
      // Move to the next step
      setActiveStep(4);
    } catch (error) {
      console.error('Error skipping voice change:', error);
      setError('Failed to skip voice change: ' + (error.response?.data?.detail || error.message));
      setLoading(false);
    }
  };
  
  // Render subtitle generator section
  const renderSubtitleGenerator = () => {
    return (
      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Step 3: Generate Subtitles</Typography>
        
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <Typography variant="subtitle2" gutterBottom>Transcription Method:</Typography>
              <Select
                value={transcriptionMethod}
                onChange={(e) => setTranscriptionMethod(e.target.value)}
                disabled={loading || activeStep > 2}
              >
                <MenuItem value="whisper">Whisper (Local)</MenuItem>
                <MenuItem value="assemblyai">AssemblyAI (Cloud)</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <Typography variant="subtitle2" gutterBottom>Language:</Typography>
              <Select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                disabled={loading || activeStep > 2}
              >
                <MenuItem value="en">English</MenuItem>
                <MenuItem value="es">Spanish</MenuItem>
                <MenuItem value="fr">French</MenuItem>
                <MenuItem value="de">German</MenuItem>
                <MenuItem value="it">Italian</MenuItem>
                <MenuItem value="ja">Japanese</MenuItem>
                <MenuItem value="zh">Chinese</MenuItem>
                <MenuItem value="auto">Auto-detect</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          {transcriptionMethod === 'whisper' && (
            <Grid item xs={12}>
              <FormControl fullWidth>
                <Typography variant="subtitle2" gutterBottom>Whisper Model Size:</Typography>
                <Select
                  value={whisperModelSize}
                  onChange={(e) => setWhisperModelSize(e.target.value)}
                  disabled={loading || activeStep > 2}
                >
                  <MenuItem value="tiny">Tiny (Fast, less accurate)</MenuItem>
                  <MenuItem value="base">Base (Balanced)</MenuItem>
                  <MenuItem value="small">Small (Better quality, slower)</MenuItem>
                  <MenuItem value="medium">Medium (High quality, very slow)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          )}
          
          {transcriptionMethod === 'assemblyai' && (
            <Grid item xs={12}>
              <FormControl fullWidth>
                <Typography variant="subtitle2" gutterBottom>AssemblyAI API Key:</Typography>
                <TextField
                  type="password"
                  placeholder="Enter your AssemblyAI API key"
                  value={assemblyaiApiKey}
                  onChange={(e) => setAssemblyaiApiKey(e.target.value)}
                  disabled={loading || activeStep > 2}
                  fullWidth
                />
              </FormControl>
            </Grid>
          )}
        </Grid>
        
        {error && <Alert severity="error" sx={{ mt: 2, mb: 2 }}>{error}</Alert>}
        
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
          <Button
            variant="outlined"
            onClick={() => setActiveStep(1)}
            disabled={loading}
          >
            Back
          </Button>
          
          {activeStep === 2 ? (
            <Button
              variant="contained"
              color="primary"
              onClick={handleGenerateSubtitles}
              disabled={loading || (transcriptionMethod === 'assemblyai' && !assemblyaiApiKey)}
              startIcon={loading ? <CircularProgress size={24} /> : null}
            >
              {loading ? 'Generating...' : 'Generate Subtitles'}
            </Button>
          ) : (
            <Button
              variant="outlined"
              color="primary"
              onClick={() => setActiveStep(3)}
              disabled={loading}
            >
              Next
            </Button>
          )}
        </Box>
        
        {activeStep > 2 && subtitlePath && (
          <Box sx={{ mt: 3 }}>
            <Typography variant="subtitle1" gutterBottom>Edit Subtitles:</Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              You can edit the auto-generated subtitles below if needed. The edited subtitles will be used for the final video.
            </Typography>
            
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Original:</Typography>
                <Box id="original-subtitles">
                  <TextField
                    multiline
                    fullWidth
                    minRows={12}
                    maxRows={12}
                    value={subtitleContent}
                    InputProps={{
                      readOnly: true,
                      sx: { fontFamily: 'monospace' }
                    }}
                  />
                </Box>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Edited:</Typography>
                <Box id="edited-subtitles">
                  <TextField
                    multiline
                    fullWidth
                    minRows={12}
                    maxRows={12}
                    value={editedSubtitleContent}
                    onChange={(e) => setEditedSubtitleContent(e.target.value)}
                    InputProps={{
                      sx: { fontFamily: 'monospace' }
                    }}
                  />
                </Box>
              </Grid>
            </Grid>
            
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
              <Button
                variant="contained"
                color="success"
                size="large"
                onClick={handleSaveEditedSubtitles}
                disabled={loading || subtitleContent === editedSubtitleContent}
                sx={{ px: 3, py: 1 }}
              >
                Save Edited Subtitles
              </Button>
            </Box>
          </Box>
        )}
      </Paper>
    );
  };
  
  // Render voice changer section
  const renderVoiceChanger = () => {
    const voiceChangeWasSkipped = job?.steps?.change_voice?.status === "skipped";
    
    return (
      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Step 4: Voice Changer</Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Convert the subtitles into speech using ElevenLabs' text-to-speech API. 
          Choose a voice character and adjust settings below.
        </Typography>
        
        {voiceChangeWasSkipped && (
          <Alert 
            severity="warning" 
            sx={{ mt: 2, mb: 2 }}
          >
            Voice change was skipped: {job?.steps?.change_voice?.error || "Unknown reason"}. 
            You may proceed to the next step.
          </Alert>
        )}
        
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <Typography variant="subtitle2" gutterBottom>Voice Character:</Typography>
              <Select
                value={voiceCharacter}
                onChange={(e) => setVoiceCharacter(e.target.value)}
                disabled={loading || activeStep > 3}
                startAdornment={<RecordVoiceOverIcon color="action" sx={{ mr: 1 }} />}
              >
                {availableVoices.map((voice) => (
                  <MenuItem key={voice.id} value={voice.id}>{voice.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <TextField 
              fullWidth
              label="Custom Voice Name (Optional)"
              value={customVoiceName}
              onChange={(e) => setCustomVoiceName(e.target.value)}
              placeholder="e.g., Narrator, Main Character"
              disabled={loading || activeStep > 3}
              helperText="Give this voice a custom name for history"
            />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <Box sx={{ mb: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Voice Stability: {voiceStability.toFixed(2)}
                </Typography>
                <Tooltip title="Higher values (0.8-1.0) make the voice more consistent but less expressive. Lower values (0.0-0.3) make the voice more varied and dynamic.">
                  <InfoIcon fontSize="small" color="action" />
                </Tooltip>
              </Box>
              <Slider
                value={voiceStability}
                onChange={(_, value) => setVoiceStability(value)}
                min={0}
                max={1}
                step={0.01}
                disabled={loading || activeStep > 3}
                marks={[
                  { value: 0, label: 'More Varied' },
                  { value: 0.5, label: 'Balanced' },
                  { value: 1, label: 'More Stable' },
                ]}
              />
            </Box>
            
            <Box sx={{ mb: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Voice Clarity: {voiceClarity.toFixed(2)}
                </Typography>
                <Tooltip title="Higher values (0.8-1.0) enhance voice quality but may sound less natural. Lower values (0.0-0.3) sound more natural but possibly less clear.">
                  <InfoIcon fontSize="small" color="action" />
                </Tooltip>
              </Box>
              <Slider
                value={voiceClarity}
                onChange={(_, value) => setVoiceClarity(value)}
                min={0}
                max={1}
                step={0.01}
                disabled={loading || activeStep > 3}
                marks={[
                  { value: 0, label: 'Natural' },
                  { value: 0.5, label: 'Balanced' },
                  { value: 1, label: 'Enhanced' },
                ]}
              />
            </Box>
          </Grid>
        </Grid>
        
        {error && (
          <Alert 
            severity="error" 
            sx={{ mt: 2, mb: 2 }}
            action={
              error.includes('Insufficient ElevenLabs credits') && (
                <Button 
                  color="inherit" 
                  size="small"
                  onClick={() => {
                    // Extract plain text from SRT content
                    const extractTextFromSrt = (srtContent) => {
                      // Basic regex to extract only text content from SRT
                      const matches = srtContent.match(/\d+\s*\n[\d:,\s>-]+\n(.*?)(?=\n\s*\n\s*\d+|\n\s*\n\s*$|$)/g);
                      if (!matches) return '';
                      
                      // Just get the text part (group 1) from each match
                      const textOnly = matches.map(match => {
                        const lines = match.split('\n');
                        // Skip the first two lines (index and timestamp)
                        return lines.slice(2).join(' ');
                      });
                      
                      return textOnly.join(' ');
                    };
                    
                    // Get the plain text without SRT formatting
                    const plainText = extractTextFromSrt(editedSubtitleContent);
                    
                    // Figure out how much to reduce
                    const creditMatch = error.match(/You have (\d+) credits but need (\d+)/);
                    if (creditMatch && creditMatch.length >= 3) {
                      const available = parseInt(creditMatch[1]);
                      const required = parseInt(creditMatch[2]);
                      
                      // Calculate what percentage of text we can use
                      const ratio = available / required;
                      const wordsToKeep = Math.floor(plainText.split(' ').length * ratio * 0.9); // 10% safety margin
                      
                      // Create a shortened version
                      const shortenedText = plainText.split(' ').slice(0, wordsToKeep).join(' ');
                      
                      // Confirm with user
                      if (window.confirm(
                        `Would you like to automatically shorten the text to fit within your available credits? ` +
                        `This will use only about ${Math.floor(ratio * 100)}% of your subtitles.`
                      )) {
                        // Set custom voice name to indicate it's shortened
                        setCustomVoiceName((prevName) => 
                          prevName ? `${prevName} (Shortened)` : 'Shortened Version'
                        );
                        
                        // Use the shortened text for voice generation directly
                        setLoading(true);
                        
                        // Create settings with the shortened text
                        const settings = {
                          voice_id: voiceCharacter,
                          stability: voiceStability,
                          clarity: voiceClarity,
                          custom_text: shortenedText,
                          voice_name: customVoiceName || `Shortened ${Math.floor(ratio * 100)}%`
                        };
                        
                        // Call API with shortened text
                        changeVoice(jobId, settings)
                          .then(response => {
                            if (response.voice_changed_audio_path) {
                              // Set the new voice audio path with a cache-busting parameter
                              const cacheBuster = new Date().getTime();
                              setVoiceChangedAudioPath(`${response.voice_changed_audio_path}?t=${cacheBuster}`);
                              
                              // Update voice history
                              if (response.voice_history) {
                                setVoiceHistory(response.voice_history);
                              } else {
                                fetchVoiceHistory();
                              }
                              
                              // Clear error
                              setError(null);
                            }
                          })
                          .catch(err => {
                            setError(`Failed to generate with shortened text: ${err.message}`);
                          })
                          .finally(() => {
                            setLoading(false);
                          });
                      }
                    }
                  }}
                >
                  Auto-Shorten
                </Button>
              )
            }
          >
            {error}
          </Alert>
        )}
        
        {voiceChangedAudioPath && (
          <Box sx={{ my: 3 }}>
            <Typography variant="subtitle2" gutterBottom>Preview Changed Voice:</Typography>
            <audio 
              controls 
              src={getFileUrl(voiceChangedAudioPath)} 
              style={{ width: '100%' }} 
              key={voiceChangedAudioPath} // Force audio player to reload when source changes
            />
            <Typography variant="caption" color="text.secondary">
              {voiceHistory.length > 0 ? `${voiceHistory.length} voice(s) generated. Current voice: ${
                voiceHistory[voiceHistory.length-1]?.voice_name || 'Unknown'
              }` : 'No voice history available'}
            </Typography>
          </Box>
        )}
        
        {/* Voice History */}
        {voiceHistory.length > 0 && (
          <Box sx={{ mt: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle2">Voice History:</Typography>
              <Button 
                size="small" 
                onClick={() => setShowVoiceHistory(!showVoiceHistory)}
                startIcon={showVoiceHistory ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              >
                {showVoiceHistory ? 'Hide History' : 'Show History'}
              </Button>
            </Box>
            
            {showVoiceHistory && (
              <List dense sx={{ bgcolor: 'background.paper', border: '1px solid #eee', borderRadius: 1 }}>
                {voiceHistory.map((voice, index) => (
                  <ListItem 
                    key={voice.timestamp || index}
                    secondaryAction={
                      <IconButton 
                        edge="end" 
                        onClick={() => {
                          // Add cache busting to force reload
                          const cacheBuster = new Date().getTime();
                          setVoiceChangedAudioPath(`${voice.url_path}?t=${cacheBuster}`);
                        }}
                      >
                        <PlayArrowIcon />
                      </IconButton>
                    }
                  >
                    <ListItemIcon>
                      <RecordVoiceOverIcon />
                    </ListItemIcon>
                    <ListItemText 
                      primary={voice.voice_name || `Voice ${index + 1}`} 
                      secondary={`Stability: ${voice.stability}, Clarity: ${voice.clarity}`}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        )}

        <Box sx={{ mt: 4, display: 'flex', justifyContent: 'space-between' }}>
          <Button 
            variant="outlined"
            onClick={() => setActiveStep(2)}
            disabled={loading}
          >
            Back
          </Button>
          <Box>
            <Button
              variant="outlined"
              onClick={handleSkipVoiceChange}
              disabled={loading || activeStep > 3}
              sx={{ mr: 2 }}
            >
              Skip Voice Change
            </Button>
            <Button 
              variant="contained" 
              onClick={handleChangeVoice}
              disabled={loading || activeStep > 3}
            >
              Apply Voice Changes
            </Button>
          </Box>
        </Box>
      </Paper>
    );
  };
  
  // Render audio cleaner section
  const renderAudioCleaner = () => {
    return (
      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Step 5: Clean Audio</Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Clean the audio by removing noise and filler words.
        </Typography>
        
        {/* Audio cleaning settings */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Noise Reduction
          </Typography>
          <FormControlLabel
            control={
              <Switch
                checked={enableNoiseReduction}
                onChange={(e) => setEnableNoiseReduction(e.target.checked)}
                disabled={loading || activeStep > 4}
              />
            }
            label="Enable Noise Reduction"
          />
          
          {enableNoiseReduction && (
            <Box sx={{ px: 2, mb: 2 }}>
              <Typography variant="body2" gutterBottom>
                Sensitivity: {noiseReductionSensitivity}
              </Typography>
              <Slider
                value={noiseReductionSensitivity}
                onChange={(_, value) => setNoiseReductionSensitivity(value)}
                min={0.05}
                max={0.5}
                step={0.05}
                disabled={loading || activeStep > 4}
              />
              <Typography variant="caption" color="text.secondary">
                Higher values remove more noise but may affect speech quality.
              </Typography>
            </Box>
          )}
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="subtitle2" gutterBottom>
            Filler Word Removal
          </Typography>
          <FormControlLabel
            control={
              <Switch
                checked={enableVadCleaning}
                onChange={(e) => setEnableVadCleaning(e.target.checked)}
                disabled={loading || activeStep > 4}
              />
            }
            label="Enable Filler Word Removal"
          />
          
          {enableVadCleaning && (
            <Box sx={{ px: 2, mb: 2 }}>
              <Typography variant="body2" gutterBottom>
                Aggressiveness: {vadAggressiveness}
              </Typography>
              <Slider
                value={vadAggressiveness}
                onChange={(_, value) => setVadAggressiveness(value)}
                min={0}
                max={3}
                step={1}
                marks
                disabled={loading || activeStep > 4}
              />
              <Typography variant="caption" color="text.secondary">
                Higher values are more aggressive at detecting speech (0=least, 3=most).
              </Typography>
            </Box>
          )}
        </Box>
        
        {error && <Alert severity="error" sx={{ mt: 2, mb: 2 }}>{error}</Alert>}
        
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
          <Button
            variant="outlined"
            onClick={() => setActiveStep(3)}
            disabled={loading}
          >
            Back
          </Button>
          
          {activeStep === 4 ? (
            <Button
              variant="contained"
              color="primary"
              onClick={handleCleanAudio}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={24} /> : null}
            >
              {loading ? 'Cleaning...' : 'Clean Audio'}
            </Button>
          ) : (
            <Button
              variant="outlined"
              color="primary"
              onClick={() => setActiveStep(5)}
              disabled={loading}
            >
              Next
            </Button>
          )}
        </Box>
      </Paper>
    );
  };
  
  // Render audio extractor section
  const renderAudioExtractor = () => {
    return (
      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Step 1: Extract Audio</Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Extract the audio track from the video for further processing.
        </Typography>
        
        {activeStep === 1 && (
          <Button
            variant="contained"
            color="primary"
            onClick={handleExtractAudio}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={24} /> : null}
          >
            {loading ? 'Extracting...' : 'Extract Audio'}
          </Button>
        )}
        
        {audioPath && activeStep > 1 && (
          <Box sx={{ mt: 3 }}>
            <Typography variant="subtitle2" gutterBottom>Audio Preview:</Typography>
            <audio controls src={getFileUrl(audioPath)} style={{ width: '100%' }} />
          </Box>
        )}
      </Paper>
    );
  };
  
  // Render final video creator section
  const renderFinalVideoCreator = () => {
    return (
      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Step 6: Create Final Video</Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Create the final video with clean audio and subtitles.
        </Typography>
        
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" gutterBottom>
              Font Size: {fontSize}
            </Typography>
            <Slider
              value={fontSize}
              onChange={(_, value) => setFontSize(value)}
              min={18}
              max={36}
              step={1}
              disabled={loading || activeStep > 5}
            />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <Typography variant="subtitle2" gutterBottom>
                Subtitle Color:
              </Typography>
              <Select
                value={subtitleColor}
                onChange={(e) => setSubtitleColor(e.target.value)}
                disabled={loading || activeStep > 5}
              >
                <MenuItem value="white">White</MenuItem>
                <MenuItem value="yellow">Yellow</MenuItem>
                <MenuItem value="cyan">Cyan</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12}>
            <Typography variant="subtitle2" gutterBottom>
              Background Opacity: {subtitleBgOpacity}%
            </Typography>
            <Slider
              value={subtitleBgOpacity}
              onChange={(_, value) => setSubtitleBgOpacity(value)}
              min={0}
              max={100}
              step={5}
              disabled={loading || activeStep > 5}
            />
          </Grid>
        </Grid>
        
        <FormControlLabel
          control={
            <Switch
              checked={useDirectFfmpeg}
              onChange={(e) => setUseDirectFfmpeg(e.target.checked)}
              disabled={loading || activeStep > 5}
            />
          }
          label="Use Direct FFmpeg Method (Recommended)"
        />
        
        {error && <Alert severity="error" sx={{ mt: 2, mb: 2 }}>{error}</Alert>}
        
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
          <Button
            variant="outlined"
            onClick={() => setActiveStep(4)}
            disabled={loading}
          >
            Back
          </Button>
          
          {activeStep === 5 ? (
            <Button
              variant="contained"
              color="primary"
              onClick={handleCreateFinalVideo}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={24} /> : null}
            >
              {loading ? 'Creating...' : 'Create Final Video'}
            </Button>
          ) : (
            <Button
              variant="outlined"
              color="primary"
              onClick={() => setActiveStep(6)}
              disabled={loading}
            >
              Next
            </Button>
          )}
        </Box>
      </Paper>
    );
  };
  
  // Render completion section with downloads
  const renderComplete = () => {
    return (
      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Download Results</Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Your video has been successfully processed. You can now download the results.
        </Typography>
        
        {finalVideoPath && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom>Final Video Preview:</Typography>
            <video 
              controls 
              src={getFileUrl(finalVideoPath)} 
              style={{ width: '100%', borderRadius: '4px' }}
            />
          </Box>
        )}
        
        <Grid container spacing={2} sx={{ mt: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6">Audio</Typography>
              </CardContent>
              <CardActions>
                <Button 
                  size="small" 
                  color="primary"
                  href={getDownloadUrl(jobId, 'audio')}
                  target="_blank"
                >
                  Download
                </Button>
              </CardActions>
            </Card>
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6">Subtitles</Typography>
              </CardContent>
              <CardActions>
                <Button 
                  size="small" 
                  color="primary"
                  href={getDownloadUrl(jobId, 'subtitles')}
                  target="_blank"
                >
                  Download
                </Button>
              </CardActions>
            </Card>
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6">Cleaned Audio</Typography>
              </CardContent>
              <CardActions>
                <Button 
                  size="small" 
                  color="primary"
                  href={getDownloadUrl(jobId, 'cleaned_audio')}
                  target="_blank"
                >
                  Download
                </Button>
              </CardActions>
            </Card>
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6">Final Video</Typography>
              </CardContent>
              <CardActions>
                <Button 
                  size="small" 
                  color="primary"
                  href={getDownloadUrl(jobId, 'final_video')}
                  target="_blank"
                >
                  Download
                </Button>
              </CardActions>
            </Card>
          </Grid>
        </Grid>
        
        <Button
          variant="contained"
          color="primary"
          onClick={() => navigate('/')}
          sx={{ mt: 3 }}
        >
          Process Another Video
        </Button>
      </Paper>
    );
  };
  
  // Render the video information panel for display in the sidebar
  const renderVideoInfoSidebar = () => {
    if (!videoInfo) return null;
    
    return (
      <List>
        <ListItem>
          <ListItemIcon><InfoIcon fontSize="small" /></ListItemIcon>
          <ListItemText 
            primary="Video Info" 
            secondary={`${videoInfo.width}×${videoInfo.height}, ${videoInfo.fps.toFixed(2)} FPS`} 
          />
        </ListItem>
        <ListItem>
          <ListItemIcon><BarChartIcon fontSize="small" /></ListItemIcon>
          <ListItemText 
            primary="Duration" 
            secondary={`${formatTime(videoInfo.duration)} (${videoInfo.duration.toFixed(2)}s)`} 
          />
        </ListItem>
      </List>
    );
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* Sidebar */}
      <Drawer
        variant="permanent"
        sx={{
          width: sidebarOpen ? 280 : 64,
          flexShrink: 0,
          transition: theme => theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
          '& .MuiDrawer-paper': {
            width: sidebarOpen ? 280 : 64,
            boxSizing: 'border-box',
            transition: theme => theme.transitions.create('width', {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
            overflowX: 'hidden',
            backgroundColor: theme => theme.palette.background.default,
            borderRight: '1px solid rgba(0, 0, 0, 0.12)'
          },
        }}
      >
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: sidebarOpen ? 'flex-end' : 'center',
          padding: '8px',
          borderBottom: '1px solid rgba(0, 0, 0, 0.12)'
        }}>
          {sidebarOpen ? (
            <IconButton onClick={toggleSidebar}>
              <ChevronLeftIcon />
            </IconButton>
          ) : (
            <IconButton onClick={toggleSidebar}>
              <MenuIcon />
            </IconButton>
          )}
        </Box>
        <List>
          {/* Video Info Section */}
          <ListItem button onClick={toggleSidebar} disabled={sidebarOpen}>
            <ListItemIcon>
              <Tooltip title="Video Information" placement="right">
                <InfoIcon color="primary" />
              </Tooltip>
            </ListItemIcon>
            <ListItemText primary="Video Information" />
          </ListItem>
          <Collapse in={sidebarOpen} timeout="auto" unmountOnExit>
            <Box sx={{ p: 2 }}>
              {renderVideoInfoSidebar()}
            </Box>
          </Collapse>

          {/* Voice History Section */}
          <ListItem button onClick={toggleSidebar} disabled={sidebarOpen}>
            <ListItemIcon>
              <Tooltip title="Voice History" placement="right">
                <RecordVoiceOverIcon color="primary" />
              </Tooltip>
            </ListItemIcon>
            <ListItemText primary="Voice History" />
          </ListItem>
          <Collapse in={sidebarOpen} timeout="auto" unmountOnExit>
            <Box sx={{ p: 2 }}>
              {voiceHistory.length > 0 ? (
                <>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Voice History ({voiceHistory.length})
                    </Typography>
                    <Tooltip title="Go to Voice Changer">
                      <Button 
                        size="small" 
                        variant="outlined" 
                        color="primary" 
                        onClick={() => setActiveStep(3)}
                        startIcon={<AddIcon />}
                      >
                        New Voice
                      </Button>
                    </Tooltip>
                  </Box>
                  <List dense sx={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1, mb: 1 }}>
                    {voiceHistory.map((voice, index) => (
                      <ListItem 
                        key={index}
                        dense
                        divider
                        sx={{
                          bgcolor: voice.url_path === voiceChangedAudioPath ? 'action.hover' : 'transparent',
                          '&:hover': {
                            bgcolor: 'action.hover',
                          }
                        }}
                        secondaryAction={
                          <Box>
                            <IconButton 
                              size="small" 
                              onClick={() => {
                                setVoiceChangedAudioPath(voice.url_path);
                              }}
                              color="primary"
                              title="Play this voice"
                            >
                              <PlayArrowIcon fontSize="small" />
                            </IconButton>
                            <IconButton 
                              size="small" 
                              onClick={() => {
                                // Use this voice's settings for a new generation
                                setVoiceCharacter(voice.voice_id);
                                setVoiceStability(voice.stability);
                                setVoiceClarity(voice.clarity);
                                setCustomVoiceName('');
                                // Automatically switch to voice changer step
                                setActiveStep(3);
                              }}
                              color="secondary"
                              title="Use these voice settings"
                              sx={{ ml: 0.5 }}
                            >
                              <SettingsIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        }
                      >
                        <ListItemIcon>
                          <Avatar sx={{ bgcolor: voice.voice_name.toLowerCase().includes('female') ? 'secondary.light' : 'primary.light', width: 24, height: 24 }}>
                            <RecordVoiceOverIcon sx={{ fontSize: 14 }} />
                          </Avatar>
                        </ListItemIcon>
                                              <ListItemText 
                        primary={voice.voice_name}
                        secondary={
                          <React.Fragment>
                            <Typography variant="caption" component="div">
                              {new Date(voice.timestamp * 1000).toLocaleTimeString()}
                            </Typography>
                            {voice.subtitle_selection && (
                              <Typography variant="caption" component="div" color="text.secondary">
                                From: {voice.subtitle_selection === 'original' ? 'Original' : 
                                       voice.subtitle_selection === 'edited' ? 'Edited' : 
                                       voice.subtitle_selection === 'marathi' ? 'Marathi' : 
                                       voice.subtitle_selection === 'hindi' ? 'Hindi' : 
                                       voice.subtitle_selection}
                              </Typography>
                            )}
                          </React.Fragment>
                        }
                        primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                      </ListItem>
                    ))}
                  </List>
                  {voiceHistory.length >= 2 && (
                    <Button
                      size="small"
                      fullWidth
                      variant="outlined"
                      onClick={() => setShowVoiceComparisonModal(true)}
                      startIcon={<CompareIcon />}
                    >
                      Compare Voices
                    </Button>
                  )}
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No voice history yet. Generate some voices to see them here.
                </Typography>
              )}
            </Box>
          </Collapse>

          {/* Progress Section */}
          <ListItem button onClick={toggleSidebar} disabled={sidebarOpen}>
            <ListItemIcon>
              <Tooltip title="Progress" placement="right">
                <BarChartIcon color="primary" />
              </Tooltip>
            </ListItemIcon>
            <ListItemText primary="Progress" />
          </ListItem>
          <Collapse in={sidebarOpen} timeout="auto" unmountOnExit>
            <Box sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>Progress</Typography>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" gutterBottom>
                  {activeStep} of {steps.length} completed
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={(activeStep / steps.length) * 100} 
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
              
              <Typography variant="subtitle2" gutterBottom>Steps:</Typography>
              <Box component="ul" sx={{ pl: 2 }}>
                {steps.map((step, index) => (
                  <Box 
                    component="li" 
                    key={index}
                    sx={{ 
                      color: index < activeStep ? 'success.main' : 
                            index === activeStep - 1 ? 'primary.main' : 'text.secondary',
                      fontWeight: index === activeStep - 1 ? 'bold' : 'normal',
                    }}
                  >
                    {step}
                  </Box>
                ))}
              </Box>
            </Box>
          </Collapse>
        </List>
      </Drawer>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          ml: 0,
          transition: theme => theme.transitions.create('margin', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
          width: `calc(100% - ${sidebarOpen ? 280 : 64}px)`,
          overflowY: 'auto',
          height: '100%'
        }}
      >
        <Typography variant="h4" component="h1" gutterBottom align="center">
          Process Video
        </Typography>
        
        {/* Stepper */}
        <Stepper activeStep={activeStep - 1} alternativeLabel sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        
        {/* Error message */}
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}
        
        {/* Main content grid - now full width without right column */}
        <Box>
          {/* Show all steps with proper visibility controls */}
          <Paper elevation={2} sx={{ p: 3, mb: 3, 
            opacity: activeStep < 1 ? 0.7 : 1,
            filter: activeStep < 1 ? 'grayscale(1)' : 'none'
          }}>
            <Typography variant="h6" gutterBottom sx={{ 
              color: activeStep >= 1 ? 'text.primary' : 'text.disabled',
              display: 'flex',
              alignItems: 'center'
            }}>
              Step 1: Extract Audio
              {activeStep > 1 && <Box component="span" sx={{ ml: 1, color: 'success.main' }}>✓</Box>}
            </Typography>
            <Typography variant="body2" color={activeStep >= 1 ? "text.secondary" : "text.disabled"} paragraph>
              Extract the audio track from the video for further processing.
            </Typography>
            
            {activeStep === 1 && (
              <Button
                variant="contained"
                color="primary"
                onClick={handleExtractAudio}
                disabled={loading}
                startIcon={loading && <CircularProgress size={24} color="inherit" />}
              >
                {loading ? 'Extracting...' : 'Extract Audio'}
              </Button>
            )}
            
            {/* Show waveform when audio is extracted */}
            {activeStep > 1 && audioPath && (
              <AudioWaveform audioPath={audioPath} title="Extracted Audio" />
            )}
          </Paper>
          
          {/* Step 2: Generate Subtitles */}
          <Paper elevation={2} sx={{ p: 3, mb: 3, 
            opacity: activeStep < 2 ? 0.7 : 1,
            filter: activeStep < 2 ? 'grayscale(1)' : 'none'
          }}>
            <Typography variant="h6" gutterBottom sx={{ 
              color: activeStep >= 2 ? 'text.primary' : 'text.disabled',
              display: 'flex',
              alignItems: 'center'
            }}>
              Step 2: Generate Subtitles
              {activeStep > 2 && <Box component="span" sx={{ ml: 1, color: 'success.main' }}>✓</Box>}
            </Typography>
            <Typography variant="body2" color={activeStep >= 2 ? "text.secondary" : "text.disabled"} paragraph>
              Generate subtitles from the audio using AI transcription.
            </Typography>
            
            {activeStep >= 2 && (
              <>
                {/* Transcription settings */}
                <Box sx={{ mb: 3 }}>
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Transcription Method
                    </Typography>
                    <Select
                      value={transcriptionMethod}
                      onChange={(e) => setTranscriptionMethod(e.target.value)}
                      disabled={loading || activeStep > 2}
                    >
                      <MenuItem value="whisper">Whisper (Local)</MenuItem>
                      <MenuItem value="assemblyai">AssemblyAI (Cloud)</MenuItem>
                    </Select>
                  </FormControl>
                  
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Language
                    </Typography>
                    <Select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      disabled={loading || activeStep > 2}
                    >
                      <MenuItem value="en">English</MenuItem>
                      <MenuItem value="mr">Marathi</MenuItem>
                    </Select>
                  </FormControl>
                  
                  {transcriptionMethod === 'whisper' && (
                    <FormControl fullWidth sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Whisper Model Size
                      </Typography>
                      <Select
                        value={whisperModelSize}
                        onChange={(e) => setWhisperModelSize(e.target.value)}
                        disabled={loading || activeStep > 2}
                      >
                        <MenuItem value="tiny">Tiny (Fastest, less accurate)</MenuItem>
                        <MenuItem value="base">Base (Fast, good accuracy)</MenuItem>
                        <MenuItem value="small">Small (Medium, better accuracy)</MenuItem>
                        <MenuItem value="medium">Medium (Slow, most accurate)</MenuItem>
                      </Select>
                    </FormControl>
                  )}
                  
                  {transcriptionMethod === 'assemblyai' && (
                    <FormControl fullWidth sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        AssemblyAI API Key
                      </Typography>
                      <TextField
                        type="password"
                        value={assemblyaiApiKey}
                        onChange={(e) => setAssemblyaiApiKey(e.target.value)}
                        disabled={loading || activeStep > 2}
                        placeholder="Enter your AssemblyAI API key"
                      />
                    </FormControl>
                  )}
                </Box>
              </>
            )}
                
            {activeStep === 2 && (
              <Button
                variant="contained"
                color="primary"
                onClick={handleGenerateSubtitles}
                disabled={loading}
                startIcon={loading && <CircularProgress size={24} color="inherit" />}
              >
                {loading ? 'Generating...' : 'Generate Subtitles'}
              </Button>
            )}
            
            {/* Display subtitle content when available */}
            {activeStep > 2 && subtitlePath && (
              <Paper elevation={2} sx={{ p: 3, mb: 4, mt: 4, width: '100%', maxWidth: '100%' }}>
                <Typography variant="subtitle1" gutterBottom sx={{ mb: 2, fontSize: '1.1rem', fontWeight: 500 }}>
                  Edit Subtitles
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph sx={{ mb: 3 }}>
                  Compare and edit the subtitles before proceeding to the next step.
                </Typography>
                
                {/* Side-by-side layout with synchronized scrolling */}
                <Box sx={{ position: 'relative', mb: 4, width: '100%', maxWidth: '100%', overflow: 'hidden' }}>
                  <Grid container spacing={3}>
                    <Grid item xs={12} lg={6}>
                      <Typography variant="subtitle2" gutterBottom sx={{ 
                        color: 'info.main',
                        display: 'flex',
                        alignItems: 'center',
                        '&::before': {
                          content: '""',
                          width: '12px',
                          height: '12px',
                          borderRadius: '50%',
                          backgroundColor: 'info.main',
                          marginRight: '8px',
                          display: 'inline-block'
                        }
                      }}>
                        Original Subtitles
                      </Typography>
                      <TextField
                        id="original-subtitles"
                        fullWidth
                        multiline
                        rows={25}
                        value={subtitleContent}
                        disabled
                        variant="outlined"
                        InputProps={{
                          sx: {
                            fontFamily: 'monospace',
                            fontSize: '0.95rem',
                            letterSpacing: '0.02rem',
                            lineHeight: '1.6',
                            padding: '12px',
                            overflowY: 'auto',
                            overflowX: 'auto',
                            width: '100%',
                            boxSizing: 'border-box',
                            minHeight: '400px',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'normal'
                          }
                        }}
                        sx={{ 
                          mb: { xs: 3, lg: 0 }, 
                          backgroundColor: theme => theme.palette.background.default,
                          '& .MuiInputBase-input': {
                            color: 'info.main'
                          },
                          width: '100%'
                        }}
                      />
                    </Grid>
                    <Grid item xs={12} lg={6}>
                      <Typography variant="subtitle2" gutterBottom sx={{ 
                        color: 'success.main',
                        display: 'flex',
                        alignItems: 'center',
                        '&::before': {
                          content: '""',
                          width: '12px',
                          height: '12px',
                          borderRadius: '50%',
                          backgroundColor: 'success.main',
                          marginRight: '8px',
                          display: 'inline-block'
                        }
                      }}>
                        Edit Subtitles
                      </Typography>
                      <TextField
                        id="edited-subtitles"
                        fullWidth
                        multiline
                        rows={25}
                        value={editedSubtitleContent}
                        onChange={(e) => setEditedSubtitleContent(e.target.value)}
                        variant="outlined"
                        InputProps={{
                          sx: {
                            fontFamily: 'monospace',
                            fontSize: '0.95rem',
                            letterSpacing: '0.02rem',
                            lineHeight: '1.6',
                            padding: '12px',
                            overflowY: 'auto',
                            overflowX: 'auto',
                            width: '100%',
                            boxSizing: 'border-box',
                            minHeight: '400px',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'normal'
                          }
                        }}
                        sx={{ 
                          mb: 0, 
                          backgroundColor: editedSubtitleContent !== subtitleContent 
                            ? theme => theme.palette.success.light + '15' 
                            : 'inherit',
                          width: '100%'
                        }}
                        disabled={activeStep > 3}
                      />
                    </Grid>
                  </Grid>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                  <Button
                    variant="contained"
                    color="success"
                    size="large"
                    onClick={handleSaveEditedSubtitles}
                    disabled={loading || subtitleContent === editedSubtitleContent}
                    sx={{ px: 3, py: 1 }}
                  >
                    Save Edited Subtitles
                  </Button>
                </Box>
              </Paper>
            )}
            
            {/* Translation Section */}
            {activeStep > 2 && subtitlePath && (
              <Paper elevation={2} sx={{ p: 3, mb: 4, mt: 4, width: '100%', maxWidth: '100%' }}>
                <Typography variant="subtitle1" gutterBottom sx={{ mb: 2, fontSize: '1.1rem', fontWeight: 500 }}>
                  Translate Subtitles
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph sx={{ mb: 2 }}>
                  Translate your edited subtitles to Marathi or Hindi using Google Translate API.
                </Typography>
                
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth>
                      <Typography variant="subtitle2" gutterBottom>Target Language:</Typography>
                      <Select
                        value={translationLanguage}
                        onChange={(e) => setTranslationLanguage(e.target.value)}
                        disabled={translationLoading || !editedSubtitleContent}
                      >
                        <MenuItem value="mr">Marathi</MenuItem>
                        <MenuItem value="hi">Hindi</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={6} sx={{ display: 'flex', alignItems: 'flex-end' }}>
                    <Button
                      variant="contained"
                      color="primary"
                      onClick={handleTranslateSubtitles}
                      disabled={translationLoading || !editedSubtitleContent}
                      startIcon={translationLoading ? <CircularProgress size={24} /> : null}
                      fullWidth
                    >
                      {translationLoading ? 'Translating...' : 'Translate Subtitles'}
                    </Button>
                  </Grid>
                </Grid>
                
                {translationError && (
                  <Alert 
                    severity={translationError.includes('in progress') ? "info" : "error"} 
                    sx={{ mb: 2 }}
                  >
                    {translationError}
                  </Alert>
                )}
                
                {translationLoading && (
                  <Box sx={{ width: '100%', mb: 2 }}>
                    <LinearProgress />
                    <Typography variant="caption" align="center" display="block" sx={{ mt: 1 }}>
                      Translation in progress. This may take several minutes for larger subtitle files.
                    </Typography>
                  </Box>
                )}
                
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" gutterBottom>
                  Translation Options
                </Typography>
                <FormControlLabel
                  control={
                    <Switch 
                      checked={editedSubtitleContent === editedSubtitleContent.split('\n').slice(0, 20).join('\n')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          // Store original content if it's not already shortened
                          if (editedSubtitleContent.split('\n').length > 20) {
                            setOriginalSubtitleForTranslation(editedSubtitleContent);
                            // Take only first 20 lines for translation
                            setEditedSubtitleContent(editedSubtitleContent.split('\n').slice(0, 20).join('\n'));
                          }
                        } else {
                          // Restore original content if available
                          if (originalSubtitleForTranslation) {
                            setEditedSubtitleContent(originalSubtitleForTranslation);
                          }
                        }
                      }}
                      disabled={translationLoading}
                    />
                  }
                  label="Only translate first 20 subtitle entries (recommended for testing)"
                />
                
                {translatedSubtitleContent && (
                  <>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Translated Subtitles ({translationLanguage === 'mr' ? 'Marathi' : 'Hindi'}):
                      </Typography>
                      <TextField
                        multiline
                        fullWidth
                        rows={12}
                        value={translatedSubtitleContent}
                        InputProps={{
                          sx: {
                            fontFamily: 'monospace',
                            fontSize: '0.95rem',
                            lineHeight: '1.6',
                          }
                        }}
                        disabled={saveTranslationLoading}
                        onChange={(e) => setTranslatedSubtitleContent(e.target.value)}
                      />
                    </Box>
                    
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                      <Button
                        variant="outlined"
                        color="primary"
                        onClick={handleSaveTranslatedSubtitles}
                        disabled={saveTranslationLoading}
                        startIcon={saveTranslationLoading ? <CircularProgress size={20} /> : null}
                      >
                        {saveTranslationLoading ? 'Saving...' : 'Save Translation'}
                      </Button>
                      
                      <Button
                        variant="outlined"
                        color="secondary"
                        onClick={handleDownloadTranslatedSubtitles}
                        disabled={translationLoading || saveTranslationLoading}
                      >
                        Download Translation
                      </Button>
                    </Box>
                  </>
                )}
              </Paper>
            )}
          </Paper>
          
          {/* Step 3: Voice Changer */}
          <Paper elevation={2} sx={{ p: 3, mb: 3, 
            opacity: activeStep < 3 ? 0.7 : 1,
            filter: activeStep < 3 ? 'grayscale(1)' : 'none'
          }}>
            <Typography variant="h6" gutterBottom sx={{ 
              color: activeStep >= 3 ? 'text.primary' : 'text.disabled',
              display: 'flex',
              alignItems: 'center'
            }}>
              Step 3: Voice Changer
              {activeStep > 3 && <Box component="span" sx={{ ml: 1, color: 'success.main' }}>✓</Box>}
            </Typography>
            <Typography variant="body2" color={activeStep >= 3 ? "text.secondary" : "text.disabled"} paragraph>
              Change the voice of the audio.
            </Typography>
            
            {activeStep >= 3 && (
              <>
                {/* Voice changer settings */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Voice Character
                  </Typography>
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <Select
                      value={voiceCharacter}
                      onChange={(e) => setVoiceCharacter(e.target.value)}
                      disabled={loading || activeStep > 3}
                      startAdornment={<RecordVoiceOverIcon color="action" sx={{ mr: 1 }} />}
                    >
                      {availableVoices.map((voice) => (
                        <MenuItem key={voice.id} value={voice.id}>{voice.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Box>
                
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Subtitle Selection
                  </Typography>
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <Select
                      value={subtitleSelection}
                      onChange={(e) => setSubtitleSelection(e.target.value)}
                      disabled={loading || activeStep > 3}
                    >
                      {availableSubtitleOptions.map((option) => (
                        <MenuItem 
                          key={option.id} 
                          value={option.id}
                          disabled={!option.available}
                        >
                          {option.name}
                        </MenuItem>
                      ))}
                    </Select>
                    <FormHelperText>
                      Select which subtitle file to use for voice generation
                    </FormHelperText>
                  </FormControl>
                </Box>
                
                <Box sx={{ mb: 3 }}>
                  <TextField 
                    fullWidth
                    label="Custom Voice Name (Optional)"
                    value={customVoiceName}
                    onChange={(e) => setCustomVoiceName(e.target.value)}
                    placeholder="e.g., Narrator, Main Character"
                    disabled={loading || activeStep > 3}
                    helperText="Give this voice a custom name for history"
                  />
                </Box>
                
                {/* Generate Voice Button */}
                {activeStep === 3 && (
                  <Box sx={{ display: 'flex', justifyContent: 'center', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
                    <Button
                      variant="contained"
                      color="primary"
                      size="large"
                      onClick={handleChangeVoice}
                      disabled={loading}
                      startIcon={loading ? <CircularProgress size={24} /> : <RecordVoiceOverIcon />}
                      sx={{ px: 4, py: 1, mb: 2, minWidth: '250px' }}
                    >
                      {loading ? 'Generating Voice...' : voiceHistory.length > 0 ? 'Generate New Voice' : 'Generate Voice'}
                    </Button>
                    
                    {voiceHistory.length > 0 && (
                      <Typography variant="caption" color="text.secondary">
                        Voice history is available in the sidebar
                      </Typography>
                    )}
                  </Box>
                )}
                
                {voiceChangedAudioPath && (
                  <Box sx={{ mt: 2, mb: 4, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="subtitle2" gutterBottom>Current Voice Preview:</Typography>
                    <audio controls src={getFileUrl(voiceChangedAudioPath)} style={{ width: '100%' }} />
                    {loading ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                        <CircularProgress size={16} sx={{ mr: 1 }} />
                        <Typography variant="caption">Processing...</Typography>
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                        <Button 
                          size="small" 
                          variant="outlined" 
                          onClick={handleChangeVoice}
                          disabled={loading}
                          startIcon={<RecordVoiceOverIcon />}
                        >
                          Try Selected Character
                        </Button>
                        <Button 
                          size="small" 
                          variant="outlined" 
                          color="secondary"
                          onClick={() => {
                            // Open character selection dialog
                            setShowCharacterSelector(true);
                          }}
                          startIcon={<AddIcon />}
                        >
                          Change Character
                        </Button>
                      </Box>
                    )}
                  </Box>
                )}
                
                {/* Navigation Buttons */}
                <Box sx={{ mt: 4, display: 'flex', justifyContent: 'space-between' }}>
                  <Button 
                    variant="outlined"
                    onClick={() => setActiveStep(2)}
                    disabled={loading}
                  >
                    Back
                  </Button>
                  <Box>
                    <Button
                      variant="outlined"
                      color="secondary"
                      onClick={handleSkipVoiceChange}
                      disabled={loading || activeStep > 3}
                      sx={{ mr: 2 }}
                    >
                      Skip Voice Change
                    </Button>
                    <Button 
                      variant="contained" 
                      color="primary"
                      onClick={handleChangeVoice}
                      disabled={loading}
                      startIcon={loading ? <CircularProgress size={24} /> : <RecordVoiceOverIcon />}
                    >
                      {loading ? 'Generating Voice...' : voiceHistory.length > 0 ? 'Regenerate Voice' : 'Generate Voice'}
                    </Button>
                  </Box>
                </Box>
              </>
            )}
          </Paper>
          
          {/* Step 4: Clean Audio */}
          <Paper elevation={2} sx={{ p: 3, mb: 3, 
            opacity: activeStep < 4 ? 0.7 : 1,
            filter: activeStep < 4 ? 'grayscale(1)' : 'none'
          }}>
            <Typography variant="h6" gutterBottom sx={{ 
              color: activeStep >= 4 ? 'text.primary' : 'text.disabled',
              display: 'flex',
              alignItems: 'center'
            }}>
              Step 4: Clean Audio
              {activeStep > 4 && <Box component="span" sx={{ ml: 1, color: 'success.main' }}>✓</Box>}
            </Typography>
            <Typography variant="body2" color={activeStep >= 4 ? "text.secondary" : "text.disabled"} paragraph>
              Clean the audio by removing noise and filler words.
            </Typography>
            
            {activeStep >= 4 && (
              <>
                {/* Audio cleaning settings */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Noise Reduction
                  </Typography>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={enableNoiseReduction}
                        onChange={(e) => setEnableNoiseReduction(e.target.checked)}
                        disabled={loading || activeStep > 4}
                      />
                    }
                    label="Enable Noise Reduction"
                  />
                  
                  {enableNoiseReduction && (
                    <Box sx={{ px: 2, mb: 2 }}>
                      <Typography variant="body2" gutterBottom>
                        Sensitivity: {noiseReductionSensitivity}
                      </Typography>
                      <Slider
                        value={noiseReductionSensitivity}
                        onChange={(_, value) => setNoiseReductionSensitivity(value)}
                        min={0.05}
                        max={0.5}
                        step={0.05}
                        disabled={loading || activeStep > 4}
                      />
                      <Typography variant="caption" color="text.secondary">
                        Higher values remove more noise but may affect speech quality.
                      </Typography>
                    </Box>
                  )}
                  
                  <Divider sx={{ my: 2 }} />
                  
                  <Typography variant="subtitle2" gutterBottom>
                    Filler Word Removal
                  </Typography>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={enableVadCleaning}
                        onChange={(e) => setEnableVadCleaning(e.target.checked)}
                        disabled={loading || activeStep > 4}
                      />
                    }
                    label="Enable Filler Word Removal"
                  />
                  
                  {enableVadCleaning && (
                    <Box sx={{ px: 2, mb: 2 }}>
                      <Typography variant="body2" gutterBottom>
                        Aggressiveness: {vadAggressiveness}
                      </Typography>
                      <Slider
                        value={vadAggressiveness}
                        onChange={(_, value) => setVadAggressiveness(value)}
                        min={0}
                        max={3}
                        step={1}
                        marks
                        disabled={loading || activeStep > 4}
                      />
                      <Typography variant="caption" color="text.secondary">
                        Higher values are more aggressive at detecting speech (0=least, 3=most).
                      </Typography>
                    </Box>
                  )}
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                  <Button
                    variant="outlined"
                    onClick={() => setActiveStep(3)}
                    disabled={loading}
                  >
                    Back
                  </Button>
                  
                  {activeStep === 4 ? (
                    <Button
                      variant="contained"
                      color="primary"
                      onClick={handleCleanAudio}
                      disabled={loading}
                      startIcon={loading ? <CircularProgress size={24} /> : null}
                    >
                      {loading ? 'Cleaning...' : 'Clean Audio'}
                    </Button>
                  ) : (
                    <Button
                      variant="outlined"
                      color="primary"
                      onClick={() => setActiveStep(5)}
                      disabled={loading}
                    >
                      Next
                    </Button>
                  )}
                </Box>
                
                {/* Show comparison when cleaned audio is available */}
                {activeStep > 4 && audioPath && cleanedAudioPath && (
                  <WaveformComparison
                    originalAudioPath={audioPath}
                    cleanedAudioPath={cleanedAudioPath}
                  />
                )}
              </>
            )}
          </Paper>
          
          {/* Step 5: Create Final Video */}
          <Paper elevation={2} sx={{ p: 3, mb: 3, 
            opacity: activeStep < 5 ? 0.7 : 1,
            filter: activeStep < 5 ? 'grayscale(1)' : 'none'
          }}>
            <Typography variant="h6" gutterBottom sx={{ 
              color: activeStep >= 5 ? 'text.primary' : 'text.disabled',
              display: 'flex',
              alignItems: 'center'
            }}>
              Step 5: Create Final Video
              {activeStep > 5 && <Box component="span" sx={{ ml: 1, color: 'success.main' }}>✓</Box>}
            </Typography>
            <Typography variant="body2" color={activeStep >= 5 ? "text.secondary" : "text.disabled"} paragraph>
              Create the final video with clean audio and subtitles.
            </Typography>
            
            {activeStep >= 5 && (
              <>
                {/* Final video settings */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Subtitle Settings
                  </Typography>
                  
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" gutterBottom>
                        Font Size: {fontSize}
                      </Typography>
                      <Slider
                        value={fontSize}
                        onChange={(_, value) => setFontSize(value)}
                        min={18}
                        max={36}
                        step={1}
                        disabled={loading || activeStep > 5}
                      />
                    </Grid>
                    
                    <Grid item xs={12} sm={6}>
                      <FormControl fullWidth sx={{ mb: 2 }}>
                        <Typography variant="body2" gutterBottom>
                          Subtitle Color
                        </Typography>
                        <Select
                          value={subtitleColor}
                          onChange={(e) => setSubtitleColor(e.target.value)}
                          disabled={loading || activeStep > 5}
                        >
                          <MenuItem value="white">White</MenuItem>
                          <MenuItem value="yellow">Yellow</MenuItem>
                          <MenuItem value="cyan">Cyan</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                    
                    <Grid item xs={12}>
                      <Typography variant="body2" gutterBottom>
                        Background Opacity: {subtitleBgOpacity}%
                      </Typography>
                      <Slider
                        value={subtitleBgOpacity}
                        onChange={(_, value) => setSubtitleBgOpacity(value)}
                        min={0}
                        max={100}
                        step={5}
                        disabled={loading || activeStep > 5}
                      />
                    </Grid>
                  </Grid>
                  
                  <FormControlLabel
                    control={
                      <Switch
                        checked={useDirectFfmpeg}
                        onChange={(e) => setUseDirectFfmpeg(e.target.checked)}
                        disabled={loading || activeStep > 5}
                      />
                    }
                    label="Use Direct FFmpeg Method (Recommended)"
                  />
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                  <Button
                    variant="outlined"
                    onClick={() => setActiveStep(4)}
                    disabled={loading}
                  >
                    Back
                  </Button>
                  
                  {activeStep === 5 ? (
                    <Button
                      variant="contained"
                      color="primary"
                      onClick={handleCreateFinalVideo}
                      disabled={loading}
                      startIcon={loading ? <CircularProgress size={24} /> : null}
                    >
                      {loading ? 'Creating...' : 'Create Final Video'}
                    </Button>
                  ) : (
                    <Button
                      variant="outlined"
                      color="primary"
                      onClick={() => setActiveStep(6)}
                      disabled={loading}
                    >
                      Next
                    </Button>
                  )}
                </Box>
              </>
            )}
          </Paper>
          
          {/* Step 6: Complete - Downloads */}
          <Paper elevation={2} sx={{ p: 3, mb: 3, 
            opacity: activeStep < 6 ? 0.7 : 1,
            filter: activeStep < 6 ? 'grayscale(1)' : 'none'
          }}>
            <Typography variant="h6" gutterBottom sx={{ 
              color: activeStep >= 6 ? 'text.primary' : 'text.disabled'
            }}>
              Download Results
            </Typography>
            <Typography variant="body2" color={activeStep >= 6 ? "text.secondary" : "text.disabled"} paragraph>
              Download processed files when available.
            </Typography>
            
            {activeStep === 6 && finalVideoPath && (
              <>
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Final Video
                  </Typography>
                  <video 
                    controls 
                    width="100%" 
                    src={getFileUrl(finalVideoPath)}
                    style={{ borderRadius: '4px' }}
                  />
                </Box>
                
                <Grid container spacing={2} sx={{ mt: 2 }}>
                  <Grid item xs={12} sm={6} md={3}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="h6">Audio</Typography>
                      </CardContent>
                      <CardActions>
                        <Button 
                          size="small" 
                          color="primary"
                          href={getDownloadUrl(jobId, 'audio')}
                          target="_blank"
                        >
                          Download
                        </Button>
                      </CardActions>
                    </Card>
                  </Grid>
                  
                  <Grid item xs={12} sm={6} md={3}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="h6">Subtitles</Typography>
                      </CardContent>
                      <CardActions>
                        <Button 
                          size="small" 
                          color="primary"
                          href={getDownloadUrl(jobId, 'subtitles')}
                          target="_blank"
                        >
                          Download
                        </Button>
                      </CardActions>
                    </Card>
                  </Grid>
                  
                  <Grid item xs={12} sm={6} md={3}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="h6">Cleaned Audio</Typography>
                      </CardContent>
                      <CardActions>
                        <Button 
                          size="small" 
                          color="primary"
                          href={getDownloadUrl(jobId, 'cleaned_audio')}
                          target="_blank"
                        >
                          Download
                        </Button>
                      </CardActions>
                    </Card>
                  </Grid>
                  
                  <Grid item xs={12} sm={6} md={3}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="h6">Final Video</Typography>
                      </CardContent>
                      <CardActions>
                        <Button 
                          size="small" 
                          color="primary"
                          href={getDownloadUrl(jobId, 'final_video')}
                          target="_blank"
                        >
                          Download
                        </Button>
                      </CardActions>
                    </Card>
                  </Grid>
                </Grid>
                
                <Button
                  variant="contained"
                  color="primary"
                  onClick={() => navigate('/')}
                  sx={{ mt: 3 }}
                >
                  Process Another Video
                </Button>
              </>
            )}
          </Paper>
        </Box>
      </Box>
      
      {/* Character Selector Dialog */}
      <Dialog 
        open={showCharacterSelector} 
        onClose={() => setShowCharacterSelector(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Select Voice Character
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" paragraph>
            Choose a voice character to try. You can preview different voices before making your final selection.
          </Typography>
          <Grid container spacing={2}>
            {availableVoices.map((voice) => (
              <Grid item xs={12} sm={6} md={4} key={voice.id}>
                <Card 
                  variant={voiceCharacter === voice.id ? "outlined" : "elevation"}
                  sx={{ 
                    height: '100%', 
                    cursor: 'pointer',
                    bgcolor: voiceCharacter === voice.id ? 'primary.50' : 'background.paper',
                    borderColor: voiceCharacter === voice.id ? 'primary.main' : 'divider',
                    '&:hover': {
                      borderColor: 'primary.main',
                      boxShadow: 1
                    }
                  }}
                  onClick={() => setVoiceCharacter(voice.id)}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                      <Avatar 
                        sx={{ 
                          bgcolor: voice.name.includes('Female') ? 'secondary.light' : 'primary.light',
                          width: 32, 
                          height: 32,
                          mr: 1
                        }}
                      >
                        <RecordVoiceOverIcon sx={{ fontSize: 18 }} />
                      </Avatar>
                      <Typography variant="subtitle1">{voice.name.split(' ')[0]}</Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {voice.name.includes('Female') ? 'Female Voice' : 'Male Voice'}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCharacterSelector(false)}>Cancel</Button>
          <Button 
            variant="contained" 
            onClick={() => {
              handleChangeVoice();
              setShowCharacterSelector(false);
            }}
            startIcon={<RecordVoiceOverIcon />}
          >
            Generate with Selected Voice
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Voice Comparison Dialog */}
      <Dialog
        open={showVoiceComparisonModal}
        onClose={() => setShowVoiceComparisonModal(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Compare Voices</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" paragraph>
            Listen to different voices side by side to compare them.
          </Typography>
          
          <Grid container spacing={2}>
            {voiceHistory.slice(-4).map((voice, index) => (
              <Grid item xs={12} sm={6} key={index}>
                <Card variant="outlined" sx={{ mb: 2 }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <Avatar 
                        sx={{ 
                          bgcolor: voice.voice_name.toLowerCase().includes('female') ? 'secondary.light' : 'primary.light',
                          mr: 1 
                        }}
                      >
                        <RecordVoiceOverIcon />
                      </Avatar>
                      <Box>
                        <Typography variant="subtitle1">{voice.voice_name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Stability: {voice.stability.toFixed(2)} | Clarity: {voice.clarity.toFixed(2)}
                        </Typography>
                        {voice.subtitle_selection && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            Source: {voice.subtitle_selection === 'original' ? 'Original Subtitles' : 
                                     voice.subtitle_selection === 'edited' ? 'Edited Subtitles' : 
                                     voice.subtitle_selection === 'marathi' ? 'Marathi Subtitles' : 
                                     voice.subtitle_selection === 'hindi' ? 'Hindi Subtitles' : 
                                     voice.subtitle_selection}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                    <audio controls src={getFileUrl(voice.url_path)} style={{ width: '100%' }} />
                  </CardContent>
                  <CardActions>
                    <Button 
                      size="small" 
                      onClick={() => {
                        setVoiceChangedAudioPath(voice.url_path);
                        setShowVoiceComparisonModal(false);
                      }}
                    >
                      Select This Voice
                    </Button>
                    <Button 
                      size="small" 
                      color="secondary"
                      onClick={() => {
                        // Use this voice's settings for a new generation
                        setVoiceCharacter(voice.voice_id);
                        setVoiceStability(voice.stability);
                        setVoiceClarity(voice.clarity);
                        setActiveStep(3);
                        setShowVoiceComparisonModal(false);
                      }}
                    >
                      Use Settings
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowVoiceComparisonModal(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ProcessingPage; 