
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
import AudioComparison from '../components/AudioComparison';
import {
  API_URL,
  extractAudio,
  generateSubtitles,
  cleanAudio,
  createFinalVideo,
  getJobStatus,
  getVideoInfo,
  getDownloadUrl,
  getFileUrl,
  getSubtitleContent,
  changeVoice,
  skipVoiceChange,
  getVoiceHistory,
  translateSubtitles,
  getAvailableAudio,
  getAvailableSubtitles,
  // Removed saveEditedSubtitles import
} from '../services/api';
import api from '../services/api'; // Import api for saveEditedSubtitles
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
  const [availableAudioFiles, setAvailableAudioFiles] = useState([]);
  const [selectedAudioId, setSelectedAudioId] = useState('cleaned');
  const [availableSubtitleFiles, setAvailableSubtitleFiles] = useState([]);
  const [selectedSubtitleId, setSelectedSubtitleId] = useState(null);
  
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
  
  // Audio comparison state
  const [showAudioComparison, setShowAudioComparison] = useState(false);
  const [comparisonData, setComparisonData] = useState(null);
  
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
      
      // Fetch available audio files
      fetchAvailableAudio();
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
        subtitle_selection: subtitleSelection,
        compare_with_original: true  // Enable comparison with original audio
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
      
      // If comparison data is included, show audio comparison
      if (response.comparison_data) {
        setComparisonData({
          original_audio: {
            path: response.comparison_data.original_audio_path,
            duration: response.comparison_data.original_duration
          },
          generated_audio: {
            path: response.comparison_data.generated_audio_path,
            duration: response.comparison_data.generated_duration,
            voice_name: response.voice_history[response.voice_history.length - 1].voice_name
          },
          subtitle_timing: []
        });
        setShowAudioComparison(true);
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
      // Determine the correct audio path to use
      let audioPath = null;
      if (job && job.steps && job.steps.extract_audio && job.steps.extract_audio.status === 'completed') {
        audioPath = job.steps.extract_audio.path;
      } else if (job && job.steps && job.steps.clean_audio && job.steps.clean_audio.status === 'completed') {
        audioPath = job.steps.clean_audio.path;
      }
      if (!audioPath) {
        throw new Error('No audio file available for saving subtitles.');
      }
      
      const response = await api.saveEditedSubtitles(audioPath, editedSubtitleContent, jobId);
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
      
      // Fetch available audio files after cleaning
      fetchAvailableAudio();
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
    
    console.log("Creating final video with settings:");
    console.log("- Selected audio ID:", selectedAudioId);
    console.log("- Selected subtitle ID:", selectedSubtitleId);
    console.log("- Font size:", fontSize);
    console.log("- Subtitle color:", subtitleColor);
    console.log("- Subtitle background opacity:", subtitleBgOpacity);
    console.log("- Use direct FFmpeg:", useDirectFfmpeg);
    
    try {
      // Force fetch available audio if not already set
      if (availableAudioFiles.length === 0) {
        await fetchAvailableAudio();
      }
      
      // Force fetch available subtitles if not already set
      if (availableSubtitleFiles.length === 0) {
        await fetchAvailableSubtitles();
      }
      
      const settings = {
        font_size: fontSize,
        subtitle_color: subtitleColor,
        subtitle_bg_opacity: subtitleBgOpacity,
        use_direct_ffmpeg: useDirectFfmpeg,
        audio_id: selectedAudioId || "cleaned", // Default to cleaned if nothing selected
        subtitle_id: selectedSubtitleId || null  // Include selected subtitle ID
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
  useEffect(() => {
    // Placeholder for future dynamic voice fetching
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Effect to fetch available audio files when job is updated
  useEffect(() => {
    if (jobId && (job?.status === 'audio_cleaned' || job?.status === 'completed' || job?.voice_history?.length > 0)) {
      console.log("Job data changed, fetching available audio files");
      fetchAvailableAudio();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, job?.status, job?.voice_history?.length]);
  
  // Effect to fetch available audio files when moving to final video step
  useEffect(() => {
    if (activeStep === 5) {
      console.log("Moved to Step 5, fetching available audio files and subtitles");
      setTimeout(() => {
        fetchAvailableAudio();
        fetchAvailableSubtitles();
      }, 500);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStep]);
  
  // Handle translate subtitles
  const handleTranslateSubtitles = async () => {
    setTranslationLoading(true);
    setTranslationError(null);
    
    try {
      setTranslationError('Translation in progress. This may take a few minutes for large subtitle files...');
      
      const settings = {
        target_language: translationLanguage,
        content: editedSubtitleContent
      };
      
      console.log('Sending translation request with settings:', settings);
      console.log(`Translating approximately ${editedSubtitleContent.split('\n').length} lines to ${translationLanguage === 'mr' ? 'Marathi' : 'Hindi'}`);
      
      const response = await translateSubtitles(jobId, settings);
      
      console.log('Translation response:', response);
      setTranslationError(null);
      
      if (response.translated_content) {
        setTranslatedSubtitleContent(response.translated_content);
        if (response.translated_subtitle_path) {
          setTranslatedSubtitlePath(response.translated_subtitle_path);
        }
        updateSubtitleOptions();
      } else {
        throw new Error('No translated content received');
      }
    } catch (error) {
      console.error('Error translating subtitles:', error);
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
      let audioPath = null;
      if (job?.steps?.extract_audio?.status === 'completed') {
        audioPath = job.steps.extract_audio.path;
      } else if (job?.steps?.clean_audio?.status === 'completed') {
        audioPath = job.steps.clean_audio.path;
      }
      if (!audioPath) {
        throw new Error('No audio file available for saving subtitles.');
      }
      
      const response = await api.saveEditedSubtitles(audioPath, translatedSubtitleContent, jobId);
      if (response.edited_subtitle_path) {
        setTranslatedSubtitlePath(response.edited_subtitle_path);
      }
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
      const downloadUrl = getFileUrl(translatedSubtitlePath);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `subtitles_${translationLanguage === 'mr' ? 'marathi' : 'hindi'}.srt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else if (translatedSubtitleContent) {
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
  
  // Handle skip voice change
  const handleSkipVoiceChange = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('Skipping voice change for job:', jobId);
      await skipVoiceChange(jobId);
      setLoading(false);
      fetchJobStatus();
      setActiveStep(4);
    } catch (error) {
      console.error('Error skipping voice change:', error);
      setError('Failed to skip voice change: ' + (error.response?.data?.detail || error.message));
      setLoading(false);
    }
  };

  const fetchAvailableAudio = async () => {
    if (!jobId) return;
    try {
      console.log("Fetching available audio for job:", jobId);
      const data = await getAvailableAudio(jobId);
      console.log("Received available audio:", data);
      if (data && data.audio_files) {
        setAvailableAudioFiles(data.audio_files);
        // Ensure selectedAudioId is valid, default to cleaned if available
        const cleanedAvailable = data.audio_files.find(f => f.id === 'cleaned');
        const voiceChangedAvailable = data.audio_files.find(f => f.type === 'voice_changed');
        if (!selectedAudioId || !data.audio_files.find(f => f.id === selectedAudioId)) {
            if (cleanedAvailable) setSelectedAudioId('cleaned');
            else if (voiceChangedAvailable) setSelectedAudioId(voiceChangedAvailable.id);
            else if (data.audio_files.length > 0) setSelectedAudioId(data.audio_files[0].id);
            else setSelectedAudioId(null);
        }

      } else {
        setAvailableAudioFiles([]);
        setSelectedAudioId(null);
      }
    } catch (error) {
      console.error('Error fetching available audio files:', error);
      setAvailableAudioFiles([]);
      setSelectedAudioId(null);
    }
  };

  const fetchAvailableSubtitles = async () => {
    if (!jobId) return;
    try {
        console.log("Fetching available subtitles for job:", jobId);
        const data = await getAvailableSubtitles(jobId);
        console.log("Received available subtitles:", data);
        if (data && data.subtitle_files) {
            setAvailableSubtitleFiles(data.subtitle_files);
             // Ensure selectedSubtitleId is valid, default to original 'en' if available
            const originalEnAvailable = data.subtitle_files.find(f => f.id === 'original_en_srt');
            if (!selectedSubtitleId || !data.subtitle_files.find(f => f.id === selectedSubtitleId)) {
                if (originalEnAvailable) setSelectedSubtitleId('original_en_srt');
                else if (data.subtitle_files.length > 0) setSelectedSubtitleId(data.subtitle_files[0].id);
                else setSelectedSubtitleId(null);
            }
        } else {
            setAvailableSubtitleFiles([]);
            setSelectedSubtitleId(null);
        }
    } catch (error) {
        console.error('Error fetching available subtitle files:', error);
        setAvailableSubtitleFiles([]);
        setSelectedSubtitleId(null);
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
        
         {/* Subtitle Editor & Translator Section - now shown when activeStep === 3 or for editing before other steps */}
         {/* This original subtitle editor should likely be tied to activeStep 3 (Voice Changer step) */}
         {/* The logic for showing it activeStep > 2 within renderSubtitleGenerator (called for activeStep===2) was problematic */}
         {/* For now, keeping it as it was, but this needs review for UX flow */}
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
                    const extractTextFromSrt = (srtContent) => {
                      const matches = srtContent.match(/\d+\s*\n[\d:,\s>-]+\n(.*?)(?=\n\s*\n\s*\d+|\n\s*\n\s*$|$)/g);
                      if (!matches) return '';
                      const textOnly = matches.map(match => {
                        const lines = match.split('\n');
                        return lines.slice(2).join(' ');
                      });
                      return textOnly.join(' ');
                    };
                    
                    const plainText = extractTextFromSrt(editedSubtitleContent);
                    const creditMatch = error.match(/You have (\d+) credits but need (\d+)/);

                    if (creditMatch && creditMatch.length >= 3) {
                      const available = parseInt(creditMatch[1]);
                      const required = parseInt(creditMatch[2]);
                      const ratio = available / required;
                      const wordsToKeep = Math.floor(plainText.split(' ').length * ratio * 0.9); 
                      const shortenedText = plainText.split(' ').slice(0, wordsToKeep).join(' ');
                      
                      if (window.confirm(
                        `Would you like to automatically shorten the text to fit within your available credits? ` +
                        `This will use only about ${Math.floor(ratio * 100)}% of your subtitles.`
                      )) {
                        setCustomVoiceName((prevName) => 
                          prevName ? `${prevName} (Shortened)` : 'Shortened Version'
                        );
                        setLoading(true);
                        
                        const settings = {
                          voice_id: voiceCharacter,
                          stability: voiceStability,
                          clarity: voiceClarity,
                          custom_text: shortenedText,
                          voice_name: customVoiceName || `Shortened ${Math.floor(ratio * 100)}%`
                        };
                        
                        changeVoice(jobId, settings)
                          .then(response => {
                            if (response.voice_changed_audio_path) {
                              const cacheBuster = new Date().getTime();
                              setVoiceChangedAudioPath(`${response.voice_changed_audio_path}?t=${cacheBuster}`);
                              if (response.voice_history) {
                                setVoiceHistory(response.voice_history);
                              } else {
                                fetchVoiceHistory();
                              }
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
          <>
            <Box sx={{ my: 3 }}>
              <Typography variant="subtitle2" gutterBottom>Preview Changed Voice:</Typography>
              <audio 
                controls 
                src={getFileUrl(voiceChangedAudioPath)} 
                style={{ width: '100%' }} 
                key={voiceChangedAudioPath} 
              />
              <Typography variant="caption" color="text.secondary">
                {voiceHistory.length > 0 ? `${voiceHistory.length} voice(s) generated. Current voice: ${
                  voiceHistory[voiceHistory.length-1]?.voice_name || 'Unknown'
                }` : 'No voice history available'}
              </Typography>
            </Box>
          </>
        )}
        
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
              <>
                <Grid container spacing={2}>
                  {voiceHistory.map((voice, index) => (
                    <Grid item xs={12} sm={6} md={4} key={voice.timestamp || index}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography variant="subtitle1">
                            {voice.voice_name || `Voice ${index + 1}`}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Stability: {voice.stability.toFixed(2)}, Clarity: {voice.clarity.toFixed(2)}
                          </Typography>
                          
                          <Box sx={{ mt: 2, mb: 2 }}>
                            <audio
                              controls
                              style={{ width: '100%' }}
                              src={`${API_URL}${voice.url_path}`}
                            />
                          </Box>
                          
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button 
                              size="small" 
                              variant="outlined" 
                              onClick={() => {
                                const cacheBuster = new Date().getTime();
                                setVoiceChangedAudioPath(`${voice.url_path}?t=${cacheBuster}`);
                              }}
                              startIcon={<PlayArrowIcon />}
                            >
                              Use This Voice
                            </Button>
                            
                            <Button 
                              size="small" 
                              variant="outlined" 
                              color="primary"
                              onClick={() => { /* handleCompareAudio(index) was here, ensure comparison logic is handled */}}
                              startIcon={<CompareIcon />}
                            >
                              Compare
                            </Button>
                          </Box>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </>
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
    // Debug logging
    console.log("Rendering final video creator, availableAudioFiles:", availableAudioFiles);
    console.log("Selected audio ID:", selectedAudioId);
    console.log("Available subtitle files:", availableSubtitleFiles);
    console.log("Selected subtitle ID:", selectedSubtitleId);
    
    // Fetch data if needed
    if (activeStep === 5 && availableAudioFiles.length === 0) {
      console.log("No audio files available in renderFinalVideoCreator, fetching now...");
      fetchAvailableAudio();
    }
    
    if (activeStep === 5 && availableSubtitleFiles.length === 0) {
      console.log("No subtitle files available in renderFinalVideoCreator, fetching now...");
      fetchAvailableSubtitles();
    }
    
    return (
      // ******** FIXED: Added <Box> as single root wrapper for the return statement ********
      <Box> 
        <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
           {/* Title updated to reflect the current conceptual step being configured */}
          <Typography variant="h6" gutterBottom>Create Final Video</Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Create the final video with selected audio and subtitles.
          </Typography>
          
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              mb: 3,
              backgroundColor: 'rgba(0, 0, 0, 0.02)',
              borderColor: 'primary.light'
            }}
          >
            <Typography variant="h6" color="primary" gutterBottom>
              Select Audio and Subtitles
            </Typography>
            
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                  Select Audio Track:
                </Typography>
                <FormControl fullWidth>
                  <Select
                    value={selectedAudioId || ''}
                    onChange={(e) => setSelectedAudioId(e.target.value)}
                    disabled={loading || activeStep > 5} 
                    sx={{ mb: 1 }}
                  >
                    {availableAudioFiles && availableAudioFiles.length > 0 ? (
                      availableAudioFiles.map((audio) => (
                        <MenuItem key={audio.id} value={audio.id}>
                          {audio.name} {audio.type === 'voice_changed' ? '(Voice Changed)' : 
                            audio.type === 'cleaned' ? '(Cleaned)' : '(Original)'}
                        </MenuItem>
                      ))
                    ) : (
                      <MenuItem value="" disabled>No audio files available</MenuItem>
                    )}
                  </Select>
                  <FormHelperText>Select the audio track to use in the final video</FormHelperText>
                  
                  <Button 
                    size="small" 
                    variant="outlined" 
                    onClick={fetchAvailableAudio}
                    sx={{ mt: 1 }}
                  >
                    Refresh Audio Options
                  </Button>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                  Select Subtitles:
                </Typography>
                <FormControl fullWidth>
                  <Select
                    value={selectedSubtitleId || ''}
                    onChange={(e) => setSelectedSubtitleId(e.target.value)}
                    disabled={loading || activeStep > 5}
                    sx={{ mb: 1 }}
                  >
                    <MenuItem value="">No Subtitles</MenuItem>
                    {availableSubtitleFiles && availableSubtitleFiles.length > 0 ? (
                      availableSubtitleFiles.map((subtitle) => (
                        <MenuItem key={subtitle.id} value={subtitle.id}>
                          {subtitle.name} 
                          {subtitle.language !== 'en' ? ` (${subtitle.language === 'mr' ? 'Marathi' : 
                            subtitle.language === 'hi' ? 'Hindi' : subtitle.language})` : ''}
                        </MenuItem>
                      ))
                    ) : (
                      <MenuItem value="" disabled>No subtitle files available</MenuItem>
                    )}
                  </Select>
                  <FormHelperText>Select the subtitles to use in the final video</FormHelperText>
                  
                  <Button 
                    size="small" 
                    variant="outlined" 
                    onClick={fetchAvailableSubtitles}
                    sx={{ mt: 1 }}
                  >
                    Refresh Subtitle Options
                  </Button>
                </FormControl>
              </Grid>
            </Grid>
          </Paper>
          
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              mb: 3,
              backgroundColor: 'rgba(0, 0, 0, 0.02)',
              borderColor: 'secondary.light'
            }}
          >
            <Typography variant="h6" color="secondary" gutterBottom>
              Subtitle Appearance
            </Typography>
            
            <Grid container spacing={2}>
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
                  disabled={loading || activeStep > 5 || !selectedSubtitleId}
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
                    disabled={loading || activeStep > 5 || !selectedSubtitleId}
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
                  disabled={loading || activeStep > 5 || !selectedSubtitleId}
                />
              </Grid>
            </Grid>
          </Paper>
          
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
                disabled={loading || !selectedAudioId}
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
        
        {/* Completion section with downloads */}
        {activeStep === 6 && (
          <Paper elevation={3} sx={{ p: 2, mb: 3, mt: 3 }}>
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
                  <CardContent><Typography variant="h6">Audio</Typography></CardContent>
                  <CardActions>
                    <Button size="small" color="primary" href={getDownloadUrl(jobId, 'audio')} target="_blank">
                      Download
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
              
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined">
                  <CardContent><Typography variant="h6">Subtitles</Typography></CardContent>
                  <CardActions>
                    <Button size="small" color="primary" href={getDownloadUrl(jobId, 'subtitles')} target="_blank">
                      Download
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
              
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined">
                  <CardContent><Typography variant="h6">Cleaned Audio</Typography></CardContent>
                  <CardActions>
                    <Button size="small" color="primary" href={getDownloadUrl(jobId, 'cleaned_audio')} target="_blank">
                      Download
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
              
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined">
                  <CardContent><Typography variant="h6">Final Video</Typography></CardContent>
                  <CardActions>
                    <Button size="small" color="primary" href={getDownloadUrl(jobId, 'final_video')} target="_blank">
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
        )} {/* ******** FIXED: Removed the stray '}' that was here ******** */}
        
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
      </Box> // This Box was the existing closing tag for renderFinalVideoCreator's return
    );
  };

  // Main component render
  return (
    <Box sx={{ display: 'flex' }}>
      <Drawer
        variant="persistent"
        anchor="left"
        open={sidebarOpen}
        sx={{
          width: 240,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 240,
            boxSizing: 'border-box',
          },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', p: 1, justifyContent: 'flex-end' }}>
          <IconButton onClick={toggleSidebar}>
            <ChevronLeftIcon />
          </IconButton>
        </Box>
        <Divider />
        <List>
          <ListItem button onClick={() => setActiveStep(1)} selected={activeStep === 1}>
            <ListItemIcon><BarChartIcon /></ListItemIcon>
            <ListItemText primary="Extract Audio" />
          </ListItem>
          <ListItem button onClick={() => setActiveStep(2)} selected={activeStep === 2} disabled={!audioPath}>
            <ListItemIcon><SettingsIcon /></ListItemIcon>
            <ListItemText primary="Generate Subtitles" />
          </ListItem>
          <ListItem button onClick={() => setActiveStep(3)} selected={activeStep === 3} disabled={!subtitlePath}>
            <ListItemIcon><RecordVoiceOverIcon /></ListItemIcon>
            <ListItemText primary="Voice Changer" />
          </ListItem>
           <ListItem button onClick={() => setActiveStep(4)} selected={activeStep === 4} disabled={!(voiceChangedAudioPath || job?.steps?.change_voice?.status === "skipped")}>
            <ListItemIcon><AddIcon />
            </ListItemIcon>
            <ListItemText primary="Clean Audio" />
          </ListItem>
          <ListItem button onClick={() => setActiveStep(5)} selected={activeStep === 5} disabled={!cleanedAudioPath && !(voiceChangedAudioPath && !job?.steps?.clean_audio?.path && job?.steps?.change_voice?.status === "skipped")}>
            <ListItemIcon><PlayArrowIcon /></ListItemIcon>
            <ListItemText primary="Create Final Video" />
          </ListItem>
        </List>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          transition: (theme) => theme.transitions.create('margin', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
          marginLeft: sidebarOpen ? `0px` : `-${240}px`, // Adjust based on drawer behavior
          mt: '64px' // Assuming a standard AppBar height
        }}
      >
        {!sidebarOpen && (
          <IconButton
            color="inherit"
            aria-label="open drawer"
            onClick={toggleSidebar}
            edge="start"
            sx={{ mr: 2, position: 'fixed', top: '15px', left: '15px', zIndex: 1300 }}
          >
            <MenuIcon />
          </IconButton>
        )}
        <Typography variant="h4" gutterBottom>
          Video Processing: Job {jobId}
        </Typography>

        <Stepper activeStep={activeStep -1} alternativeLabel sx={{ mb: 4 }}>
          {steps.map((label, index) => (
            <Step key={label} completed={activeStep > index + 1}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {loading && activeStep < 6 && <LinearProgress sx={{ my: 2 }} />}
        {error && <Alert severity="error" sx={{ my: 2 }}>{error}</Alert>}


        {activeStep === 1 && renderAudioExtractor()}
        {activeStep === 2 && renderSubtitleGenerator()}
        
        {/* Subtitle Editor and Translator: shown primarily in step 3 (Voice Changer) */}
        {activeStep === 3 && subtitlePath && (
          <Paper elevation={2} sx={{ p:2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>Edit & Translate Subtitles</Typography>
             <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Original Subtitles:</Typography>
                <Box id="original-subtitles">
                  <TextField
                    multiline
                    fullWidth
                    minRows={10}
                    maxRows={10}
                    value={subtitleContent}
                    InputProps={{ readOnly: true, sx: { fontFamily: 'monospace' } }}
                  />
                </Box>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Editable Subtitles:</Typography>
                <Box id="edited-subtitles">
                <TextField
                  multiline
                  fullWidth
                  minRows={10}
                  maxRows={10}
                  value={editedSubtitleContent}
                  onChange={(e) => setEditedSubtitleContent(e.target.value)}
                  InputProps={{ sx: { fontFamily: 'monospace' } }}
                />
                </Box>
              </Grid>
            </Grid>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2, mb:3 }}>
              <Button
                variant="contained"
                color="primary"
                onClick={handleSaveEditedSubtitles}
                disabled={loading || subtitleContent === editedSubtitleContent}
              >
                Save Edited Subtitles
              </Button>
            </Box>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" gutterBottom>Translate Subtitles:</Typography>
             <Grid container spacing={2} alignItems="flex-end">
              <Grid item xs={12} sm={4}>
                <FormControl fullWidth>
                  <Select value={translationLanguage} onChange={(e) => setTranslationLanguage(e.target.value)} disabled={translationLoading}>
                    <MenuItem value="mr">Marathi</MenuItem>
                    <MenuItem value="hi">Hindi</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={8}>
                <Button variant="contained" onClick={handleTranslateSubtitles} disabled={translationLoading || !editedSubtitleContent} startIcon={translationLoading ? <CircularProgress size={20}/> : null}>
                  {translationLoading ? 'Translating...' : 'Translate Edited Subtitles'}
                </Button>
              </Grid>
            </Grid>
            {translationError && <Alert severity={translationLoading && !translationError.toLowerCase().includes('failed') ? "info" : "error"} sx={{ mt: 2 }}>{translationError}</Alert>}
            {translatedSubtitleContent && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>Translated ({translationLanguage === 'mr' ? 'Marathi' : 'Hindi'}) Subtitles:</Typography>
                <TextField multiline fullWidth minRows={10} value={translatedSubtitleContent} onChange={(e) => setTranslatedSubtitleContent(e.target.value)} InputProps={{ sx: { fontFamily: 'monospace' } }}/>
                <Box sx={{display: 'flex', justifyContent: 'flex-end', gap: 1, mt:1}}>
                  <Button variant="outlined" size="small" onClick={handleDownloadTranslatedSubtitles} disabled={saveTranslationLoading}>Download Translated</Button>
                  <Button variant="contained" size="small" onClick={handleSaveTranslatedSubtitles} disabled={saveTranslationLoading}>
                    {saveTranslationLoading ? <CircularProgress size={20}/> : "Save Translated on Server"}
                  </Button>
                </Box>
              </Box>
            )}
          </Paper>
        )}
        {activeStep === 3 && renderVoiceChanger()}

        {activeStep === 4 && renderAudioCleaner()}
        {activeStep === 5 && renderFinalVideoCreator()}
         {/* Download results for activeStep === 6 are now part of renderFinalVideoCreator */}
        
        {showAudioComparison && comparisonData && (
            <WaveformComparison
                originalAudio={comparisonData.original_audio}
                generatedAudio={comparisonData.generated_audio}
                subtitleTimings={comparisonData.subtitle_timing}
                open={showAudioComparison}
                onClose={() => setShowAudioComparison(false)}
            />
        )}

      </Box>
    </Box>
  );
};

export default ProcessingPage;
