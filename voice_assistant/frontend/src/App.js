import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Mic, MicOff, Volume2, VolumeX, Trash2, Command, Activity, Cpu, Wifi,
  AlertCircle, CheckCircle, RefreshCw, Send, Square, Zap, Globe, Volume1
} from 'lucide-react';
import './App.css';

const MANAGED_WEB_APPS = {
  youtube: 'https://youtube.com',
  gmail: 'https://mail.google.com',
  google: 'https://google.com',
  github: 'https://github.com',
  chatgpt: 'https://chat.openai.com'
};

const REUSABLE_WINDOW_KEY = '__assistant_reusable_window__';

const App = () => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [commandHistory, setCommandHistory] = useState([]);
  const [systemStatus, setSystemStatus] = useState({
    listening: false,
    processing: false,
    speaking: false,
    connected: false
  });
  const [confirmationDialog, setConfirmationDialog] = useState(null);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [backendConnected, setBackendConnected] = useState(false);
  const [transcriptConfidence, setTranscriptConfidence] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [showTranscriptVerification, setShowTranscriptVerification] = useState(false);
  const [commandAlternatives] = useState([]);
  const [recognitionError, setRecognitionError] = useState(null);
  const [backgroundMode, setBackgroundMode] = useState(true);
  const [currentLang, setCurrentLang] = useState('en-IN');
  const [typedCommand, setTypedCommand] = useState('');

  const MIN_CONFIDENCE_THRESHOLD = 0.7;
  const quickCommands = [
    // Basic Commands
    'open youtube',
    'open notepad',
    'open chrome',
    'open word',
    'open excel',
    'open file explorer',
    'open calculator',
    
    // Search & Web
    'search for python tutorials',
    'open gmail',
    'open google',
    'open github',
    'open chatgpt',
    'open linkedin',
    'open wikipedia',
    
    // System Commands
    'shutdown',
    'restart',
    'sleep',
    'lock',
    
    // Volume & Brightness
    'increase volume',
    'decrease volume',
    'mute volume',
    'increase brightness',
    'decrease brightness',
    
    // Media Control
    'play music',
    'pause music',
    
    // Window Management
    'minimize window',
    'maximize window',
    'show desktop',
    
    // Keyboard Shortcuts
    'copy',
    'paste',
    'cut',
    'undo',
    'redo',
    'save',
    'refresh',
    'find',
    'new tab',
    'close tab',
    
    // Folder Navigation
    'open documents',
    'open downloads',
    'open desktop',
    
    // Screenshot & Media
    'take screenshot',
    'take photo',
    'start recording',
    'stop recording',
    
    // Browser Navigation
    'go back',
    'go forward',
    
    // System Information
    'system information',
    'network status',
    'disk space',
    'memory usage',
    'battery status',
    
    // Productivity - Time Management
    'pomodoro timer',
    'focus mode',
    'start timer for 25 minutes',
    'stop timer',
    
    // Productivity - Task Management
    'create todo finish report',
    'show todos',
    
    // Productivity - Notes
    'quick note meeting at 3pm',
    'show notes',
    
    // Conversational Queries
    'what can you do',
    'what time is it',
    'tell me a joke',
    
    // Professional Conversations (essential only)
    'productivity tips',
    'email etiquette',
    
    // Pop Culture
    'hello there',
  ];

  const recognitionRef = useRef(null);
  const abortControllerRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const microphoneRef = useRef(null);
  const animationFrameRef = useRef(null);
  const apiClient = useRef(axios.create({ baseURL: '/api', timeout: 5000 }));
  const speakTextRef = useRef(null);
  const handleCommandRef = useRef(null);

  const manualStopRef = useRef(false);
  const silenceTimerRef = useRef(null);
  const isProcessingRef = useRef(false);
  const restartListeningTimeoutRef = useRef(null);
  const backgroundModeRef = useRef(backgroundMode);
  const recognitionErrorRef = useRef(recognitionError);
  const appWindowsRef = useRef({});
  const isListeningRef = useRef(isListening);
  const recognitionActiveRef = useRef(false);
  const currentLangRef = useRef(currentLang);
  const speakingRef = useRef(false);
  const lastProcessedCommandRef = useRef('');
  const lastProcessedTimeRef = useRef(0);
  const isProcessingCommandRef = useRef(false);

  const keepListeningRef = useRef(false);
  const recognitionStartingRef = useRef(false);

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, []);

  const clearRestartListeningTimeout = useCallback(() => {
    if (restartListeningTimeoutRef.current) {
      clearTimeout(restartListeningTimeoutRef.current);
      restartListeningTimeoutRef.current = null;
    }
  }, []);

  const clearRestartTimer = useCallback(() => {
    clearRestartListeningTimeout();
  }, [clearRestartListeningTimeout]);

  useEffect(() => {
    backgroundModeRef.current = backgroundMode;
  }, [backgroundMode]);

  useEffect(() => {
    recognitionErrorRef.current = recognitionError;
  }, [recognitionError]);

  useEffect(() => {
    isListeningRef.current = isListening;
  }, [isListening]);

  useEffect(() => {
    currentLangRef.current = currentLang;
  }, [currentLang]);

  const normalizeCommandText = useCallback((value) => {
    return (value || '')
      .toLowerCase()
      .trim()
      .replace(/[.!?,:;]+$/g, '')
      .replace(/\s+/g, ' ');
  }, []);

  const logClientEvent = useCallback(async (level, event, message, details = {}) => {
    try {
      await apiClient.current.post('/client-log', {
        level,
        event,
        message,
        details
      });
    } catch (error) {
      console.error('Failed to write client log:', error);
    }
  }, []);

  const buildHistoryEntry = useCallback((command, response, intent) => ({
    id: Date.now(),
    command,
    response,
    intent,
    timestamp: new Date().toLocaleTimeString()
  }), []);

  const appendCommandHistory = useCallback((command, response, intent) => {
    setCommandHistory((prev) => [
      buildHistoryEntry(command, response, intent),
      ...prev.slice(0, 19)
    ]);
  }, [buildHistoryEntry]);

  const getManagedWindow = useCallback((name) => {
    const existingWindow = appWindowsRef.current[name];
    if (existingWindow && existingWindow.closed) {
      appWindowsRef.current[name] = null;
      return null;
    }
    return existingWindow || null;
  }, []);

  const clearManagedWindowAliases = useCallback((windowRef, nextName) => {
    Object.keys(appWindowsRef.current).forEach((key) => {
      if (key !== nextName && appWindowsRef.current[key] === windowRef) {
        appWindowsRef.current[key] = null;
      }
    });
  }, []);

  const primeReusableAssistantWindow = useCallback(() => {
    const existingReusableWindow = getManagedWindow(REUSABLE_WINDOW_KEY);
    if (existingReusableWindow) return existingReusableWindow;

    const reusableWindow = window.open('', 'assistant-controlled-window');
    if (reusableWindow) {
      reusableWindow.document.title = 'Assistant Controlled Window';
      reusableWindow.document.body.innerHTML =
        '<p style="font-family: Arial, sans-serif; padding: 16px;">Assistant window is ready for voice-open commands.</p>';
      appWindowsRef.current[REUSABLE_WINDOW_KEY] = reusableWindow;
      console.log('[assistant] primed reusable window');
      return reusableWindow;
    }

    console.log('[assistant] failed to prime reusable window');
    return null;
  }, [getManagedWindow]);

  const openManagedApp = useCallback((name, url) => {
    const existingWindow = getManagedWindow(name);
    console.log('[assistant] open request', { name, url, existing: Boolean(existingWindow) });

    if (existingWindow) {
      existingWindow.focus();
      console.log('[assistant] focus existing window', { name });
      return { success: true, message: `${name} is already open. Focusing it now.` };
    }

    const openedWindow = window.open(url, '_blank');
    if (openedWindow) {
      appWindowsRef.current[name] = openedWindow;
      clearManagedWindowAliases(openedWindow, name);
      console.log('[assistant] opened new window', { name, url });
      return { success: true, message: `Opened ${name}.` };
    }

    const reusableWindow = primeReusableAssistantWindow();
    if (reusableWindow && !reusableWindow.closed) {
      reusableWindow.location.replace(url);
      reusableWindow.focus();
      appWindowsRef.current[name] = reusableWindow;
      clearManagedWindowAliases(reusableWindow, name);
      console.log('[assistant] reused primed window', { name, url });
      return { success: true, message: `Opened ${name}.` };
    }

    console.log('[assistant] failed to open window', { name, url });
    return {
      success: false,
      message: `Popup blocked while opening ${name}. Click Start Mic once again or allow popups for this site.`
    };
  }, [clearManagedWindowAliases, getManagedWindow, primeReusableAssistantWindow]);

  const closeManagedApp = useCallback((name) => {
    const existingWindow = getManagedWindow(name);
    console.log('[assistant] close request', { name, existing: Boolean(existingWindow) });

    if (!existingWindow) {
      return { success: false, message: `${name} is not open or was not opened by this assistant.` };
    }

    try {
      existingWindow.close();
      appWindowsRef.current[name] = null;
      console.log('[assistant] closed managed window', { name });
      return { success: true, message: `Closed ${name}.` };
    } catch (error) {
      console.log('[assistant] failed to close managed window', { name, error: error.message });
      return { success: false, message: `Could not close ${name}.` };
    }
  }, [getManagedWindow]);

  const normalizeVoiceCommand = useCallback((command) => {
    if (
      command.includes('open youtube') ||
      command.includes('youtube kholo') ||
      command.includes('यूट्यूब खोलो') ||
      command.includes('યુટ્યુબ ખોલો')
    ) {
      return 'open_youtube';
    }

    if (
      command.includes('close youtube') ||
      command.includes('exit youtube') ||
      command.includes('shutdown youtube') ||
      command.includes('youtube band karo') ||
      command.includes('यूट्यूब बंद करो') ||
      command.includes('યુટ્યુબ બંધ કરો')
    ) {
      return 'close_youtube';
    }

    if (
      command === 'stop' ||
      command.includes('stop listening') ||
      command.includes('stop assistant') ||
      command.includes('exit assistant') ||
      command.includes('रुको') ||
      command.includes('बंद करो') ||
      command.includes('બંધ કરો')
    ) {
      return 'stop';
    }

    return 'unknown';
  }, []);

  // ✅ SAFE START (no dependency issue)
const safeStartRecognitionRef = useRef();

safeStartRecognitionRef.current = (delay = 0) => {
  clearRestartTimer();

  restartListeningTimeoutRef.current = setTimeout(() => {
    const rec = recognitionRef.current;
    if (!rec) return;
    if (!keepListeningRef.current) return;
    if (recognitionStartingRef.current) return;
    if (recognitionActiveRef.current) return;

    try {
      recognitionStartingRef.current = true;
      rec.start();
    } catch (error) {
      recognitionStartingRef.current = false;
      clearRestartTimer();

      restartListeningTimeoutRef.current = setTimeout(() => {
        if (!keepListeningRef.current) return;
        try {
          recognitionStartingRef.current = true;
          recognitionRef.current?.start();
        } catch (e) {
          recognitionStartingRef.current = false;
          console.log('Recognition retry failed:', e.message);
        }
      }, 100);
    }
  }, delay);
};



// ✅ LANGUAGE SETTER (NO useCallback issues)
const setRecognitionLanguageRef = useRef();

setRecognitionLanguageRef.current = (lang) => {
  currentLangRef.current = lang;
  setCurrentLang(lang);

  if (recognitionRef.current) {
    recognitionRef.current.lang = lang;

    if (keepListeningRef.current) {
      try {
        recognitionRef.current.abort();
      } catch (error) {
        console.log('Language abort error:', error.message);
      }

      safeStartRecognitionRef.current(150); // ✅ safe call
    }
  }

  console.log('[assistant] language set', lang);
};



// ✅ LANGUAGE DETECTOR (NO dependencies at all)
const detectLanguageSwitch = useCallback((command) => {
  if (command.includes('hindi') || command.includes('हिंदी')) {
    setRecognitionLanguageRef.current('hi-IN');
    return true;
  }

  if (command.includes('gujarati') || command.includes('ગુજરાતી')) {
    setRecognitionLanguageRef.current('gu-IN');
    return true;
  }

  if (command.includes('english')) {
    setRecognitionLanguageRef.current('en-IN');
    return true;
  }

  return false;
}, []);

  const speakText = useCallback((text) => {
    if (!ttsEnabled || !text) return;

    // Stop recognition when speaking to prevent picking up system voice
    if (recognitionRef.current && recognitionActiveRef.current) {
      try {
        recognitionRef.current.stop();
        console.log('Stopped recognition while speaking');
      } catch (e) {
        console.log('Error stopping recognition:', e);
      }
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.12;
    utterance.pitch = 1;
    utterance.volume = 1;

    utterance.onstart = () => {
      speakingRef.current = true;
      setSystemStatus(prev => ({ ...prev, speaking: true }));
    };

    utterance.onend = () => {
      speakingRef.current = false;
      setSystemStatus(prev => ({ ...prev, speaking: false }));
      console.log('Finished speaking, resuming recognition');
      // Resume recognition after speaking
      if (keepListeningRef.current && !manualStopRef.current) {
        setTimeout(() => {
          if (recognitionRef.current && !recognitionActiveRef.current) {
            // Directly call recognition start to avoid circular dependency
            if (recognitionRef.current) {
              try {
                recognitionRef.current.start();
              } catch (e) {
                console.log('Error starting recognition:', e);
              }
            }
          }
        }, 500);
      }
    };

    window.speechSynthesis.speak(utterance);
  }, [ttsEnabled]);

  const stopAudioVisualization = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (microphoneRef.current) {
      microphoneRef.current.getTracks().forEach(track => track.stop());
      microphoneRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setAudioLevel(0);
  }, []);

  const startAudioVisualization = useCallback(() => {
    // Don't block - run in background
    (async () => {
      try {
        // Don't start if already running
        if (microphoneRef.current && audioContextRef.current && analyserRef.current) {
          return;
        }

        // Clean up any existing audio resources
        if (audioContextRef.current) {
          try {
            await audioContextRef.current.close();
          } catch (e) {
            console.log('Error closing existing audio context:', e);
          }
          audioContextRef.current = null;
        }

        if (microphoneRef.current) {
          microphoneRef.current.getTracks().forEach(track => track.stop());
          microphoneRef.current = null;
        }

        // Request microphone access with optimized settings to filter system sounds
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: { ideal: true },
            noiseSuppression: { ideal: true },
            autoGainControl: { ideal: false },
            sampleRate: { ideal: 44100 },
            channelCount: { ideal: 1 }
          }
        });
        microphoneRef.current = stream;

        // Create audio context
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: 44100
        });
        analyserRef.current = audioContextRef.current.createAnalyser();
        analyserRef.current.fftSize = 256;
        analyserRef.current.smoothingTimeConstant = 0.8;

        const source = audioContextRef.current.createMediaStreamSource(stream);
        source.connect(analyserRef.current);

        const updateAudioLevel = () => {
          if (!analyserRef.current) return;
          const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
          analyserRef.current.getByteFrequencyData(dataArray);
          const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
          setAudioLevel(average);
          animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
        };

        updateAudioLevel();
        console.log('Audio visualization started successfully');
      } catch (err) {
        console.error('Audio visualization failed:', err);
        setRecognitionError('Microphone access denied or not available');
      }
    })();
  }, []);

  const safeStartRecognition = useCallback((delay = 0) => {
    clearRestartTimer();

    const startNow = () => {
      const rec = recognitionRef.current;
      if (!rec) {
        console.error('Recognition ref is null');
        return;
      }
      if (!keepListeningRef.current) {
        console.log('keepListening is false, not starting recognition');
        return;
      }
      if (recognitionStartingRef.current) {
        console.log('Recognition already starting, skipping');
        return;
      }
      if (recognitionActiveRef.current) {
        console.log('Recognition already active, skipping');
        return;
      }

      try {
        console.log('Starting recognition...');
        recognitionStartingRef.current = true;
        rec.start();
      } catch (error) {
        recognitionStartingRef.current = false;
        console.error('Recognition start error:', error);
        clearRestartTimer();

        // Stop recognition if it's already running and restart
        try {
          rec.stop();
        } catch (e) {
          console.log('Stop error (expected if not running):', e.message);
        }

        // Immediate retry without delay
        if (!keepListeningRef.current) return;
        try {
          recognitionStartingRef.current = true;
          recognitionRef.current?.start();
        } catch (e) {
          recognitionStartingRef.current = false;
          console.error('Recognition start retry failed:', e.message);
        }
      }
    };

    if (delay > 0) {
      restartListeningTimeoutRef.current = setTimeout(startNow, delay);
    } else {
      startNow();
    }
  }, [clearRestartTimer]);

  const startListeningSession = useCallback(() => {
    if (!recognitionRef.current) {
      console.error('Recognition not initialized');
      return;
    }

    // Start immediately, check permissions in background
    navigator.permissions.query({ name: 'microphone' })
      .then(permissions => {
        if (permissions.state === 'denied') {
          setRecognitionError('Microphone permission denied. Please allow microphone access in browser settings.');
          setAiResponse('Microphone permission denied. Please allow microphone access in browser settings.');
        }
      })
      .catch(e => console.log('Could not check microphone permissions:', e));

    keepListeningRef.current = true;
    manualStopRef.current = false;
    isListeningRef.current = true;

    clearSilenceTimer();
    clearRestartTimer();
    setRecognitionError(null);
    setIsListening(true);
    setSystemStatus(prev => ({ ...prev, listening: true }));

    console.log('[assistant] mic start');
    safeStartRecognition(0);
  }, [clearRestartTimer, clearSilenceTimer, safeStartRecognition]);

  const stopListeningSession = useCallback((disableBackground = false) => {
    keepListeningRef.current = false;
    manualStopRef.current = true;

    clearSilenceTimer();
    clearRestartTimer();

    if (disableBackground) {
      setBackgroundMode(false);
    }

    isListeningRef.current = false;
    recognitionStartingRef.current = false;
    recognitionActiveRef.current = false;

    try {
      recognitionRef.current?.stop();
    } catch (error) {
      console.log('Stop ignored:', error.message);
    }

    setIsListening(false);
    setSystemStatus(prev => ({ ...prev, listening: false }));
  }, [clearRestartTimer, clearSilenceTimer]);

  const stopAssistant = useCallback(() => {
    console.log('[assistant] mic stop');
    stopListeningSession(true);
    stopAudioVisualization();
  }, [stopAudioVisualization, stopListeningSession]);

  const checkBackendConnection = async () => {
    try {
      const response = await apiClient.current.get('/health', { timeout: 5000 });
      setBackendConnected(response.data.status === 'healthy');
    } catch (error) {
      setBackendConnected(false);
    }
  };

  const executeCommand = useCallback(async (intent, parameters, confirmed = false) => {
    try {
      await logClientEvent('info', 'execute_command_request', 'Sending execute command request', {
        intent,
        parameters,
        confirmed
      });

      const response = await apiClient.current.post('/execute', {
        intent,
        parameters,
        confirmed
      }, {
        timeout: 30000
      });

      const result = response.data;
      await logClientEvent(
        result.success ? 'info' : 'error',
        'execute_command_response',
        result.message || 'Execute command response received',
        { intent, parameters, confirmed, result }
      );

      if (result.needs_confirmation && !confirmed) {
        setConfirmationDialog({
          message: result.message,
          intent,
          parameters
        });
        speakText(result.message);
      } else {
        const responseMessage =
          result.message || (result.success ? 'Action completed successfully.' : 'Action failed.');
        setAiResponse(responseMessage);
        speakText(responseMessage);
      }
    } catch (error) {
      console.error('Error executing command:', error);
      const backendMessage = error.response?.data?.message;
      const errorMsg = backendMessage || (error.code === 'ECONNABORTED'
        ? 'Command timed out while waiting for Windows to respond.'
        : 'Failed to execute the command.');
      await logClientEvent('error', 'execute_command_error', 'Error executing command', {
        intent,
        parameters,
        confirmed,
        error: error.message,
        backendMessage
      });
      setAiResponse(errorMsg);
      speakText(errorMsg);
    }
  }, [logClientEvent, speakText]);

  const executeLocalAction = useCallback(async (action, originalCommand) => {
    switch (action) {
      case 'open_youtube': {
        const result = openManagedApp('youtube', MANAGED_WEB_APPS.youtube);
        console.log('[assistant] action taken', { action, result });
        appendCommandHistory(originalCommand, result.message, 'open_app');
        setAiResponse(result.message);
        speakText(result.message);
        await logClientEvent(result.success ? 'info' : 'error', 'managed_open', result.message, {
          text: originalCommand,
          app: 'youtube',
          success: result.success
        });
        return true;
      }
      case 'close_youtube': {
        const result = closeManagedApp('youtube');
        console.log('[assistant] action taken', { action, result });
        appendCommandHistory(originalCommand, result.message, 'close_app');
        setAiResponse(result.message);
        speakText(result.message);
        await logClientEvent(result.success ? 'info' : 'error', 'managed_close', result.message, {
          text: originalCommand,
          app: 'youtube',
          success: result.success
        });
        return true;
      }
      case 'stop': {
        const stopMessage = 'Stopping assistant and microphone.';
        appendCommandHistory(originalCommand, stopMessage, 'stop_mic');
        setAiResponse(stopMessage);
        speakText(stopMessage);
        stopAssistant();
        await logClientEvent('info', 'stop_command', stopMessage, { text: originalCommand });
        return true;
      }
      default:
        return false;
    }
  }, [appendCommandHistory, closeManagedApp, logClientEvent, openManagedApp, speakText, stopAssistant]);

  const processSingleCommand = useCallback(async (text) => {
    if (!text.trim()) return;

    isProcessingRef.current = true;
    clearSilenceTimer();
    setSystemStatus(prev => ({ ...prev, processing: true }));

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      await logClientEvent('info', 'process_command_request', 'Sending process command request', {
        text: text.trim()
      });

      const response = await apiClient.current.post(
        '/process-command',
        { text: text.trim() },
        { signal: abortControllerRef.current.signal }
      );

      const result = response.data;
      await logClientEvent('info', 'process_command_response', result.response || 'Process command response received', {
        text,
        result
      });

      appendCommandHistory(text, result.response, result.intent);

      if (result.requires_confirmation && result.intent !== 'clarification_needed') {
        setAiResponse(result.response);
        setConfirmationDialog({
          message: result.response,
          intent: result.intent,
          parameters: result.parameters
        });
        speakText(result.response);
      } else {
        if (result.intent !== 'clarification_needed' && result.intent !== 'general_query') {
          await executeCommand(result.intent, result.parameters, false);
        } else {
          setAiResponse(result.response);
          speakText(result.response);
        }
      }
    } catch (error) {
      if (error.name === 'AbortError' || error.code === 'ERR_CANCELED') {
        return;
      }
      console.error('Error processing command:', error);
      await logClientEvent('error', 'process_command_error', 'Error processing command', {
        text,
        error: error.message
      });
      const errorMsg = 'Sorry, I encountered an error. Please try again.';
      setAiResponse(errorMsg);
      speakText(errorMsg);
    } finally {
      isProcessingRef.current = false;
      setSystemStatus(prev => ({ ...prev, processing: false }));
    }
  }, [appendCommandHistory, clearSilenceTimer, executeCommand, logClientEvent, speakText]);

  const handleCommand = useCallback(async (text) => {
    if (!text.trim()) return;

    // Check for "open [app] and search [query]" pattern - don't split this
    const openSearchPattern = /^(?:open|launch|start)\s+(\w+)\s+(?:and\s+)?search\s+(?:for\s+)?(.+)$/i;
    const openSearchMatch = text.match(openSearchPattern);

    if (openSearchMatch) {
      // Send as single command to backend
      await processSingleCommand(text);
      return;
    }

    // Split multiple commands by common separators (excluding the open-search pattern)
    const commandSeparators = /\s+(?:and|then|after that|next|also)\s+/i;
    const commands = text.split(commandSeparators).map(cmd => cmd.trim()).filter(cmd => cmd);

    if (commands.length > 1) {
      // Process multiple commands sequentially
      for (let i = 0; i < commands.length; i++) {
        await processSingleCommand(commands[i]);
        // Small delay between commands
        if (i < commands.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      }
      return;
    }

    // Single command
    await processSingleCommand(text);
  }, [processSingleCommand]);

  const handleCommandFast = useCallback(async (rawCommand) => {
    const command = normalizeCommandText(rawCommand);
    if (!command) return;

    // Prevent concurrent command execution
    if (isProcessingCommandRef.current) {
      console.log('[assistant] Command already processing, skipping:', command);
      return;
    }

    const now = Date.now();
    const timeSinceLast = now - lastProcessedTimeRef.current;

    // Skip duplicate commands within 3 seconds
    if (command === lastProcessedCommandRef.current && timeSinceLast < 3000) {
      console.log('[assistant] Skipping duplicate command:', command, `(${timeSinceLast}ms ago)`);
      return;
    }

    isProcessingCommandRef.current = true;
    lastProcessedCommandRef.current = command;
    lastProcessedTimeRef.current = now;

    console.log('[assistant] detected transcript', command);

    try {
      // Check for "open [app] and search [query]" pattern - send to backend, don't handle locally
      const openSearchPattern = /^(?:open|launch|start)\s+(\w+)\s+(?:and\s+)?search\s+(?:for\s+)?(.+)$/i;
      const openSearchMatch = command.match(openSearchPattern);

      if (openSearchMatch) {
        await handleCommand(command);
        return;
      }

      const languageSwitched = detectLanguageSwitch(command);
      const action = normalizeVoiceCommand(command);
      console.log('[assistant] parsed intent', action);

      if (action !== 'unknown') {
        const handledLocally = await executeLocalAction(action, command);
        if (handledLocally) return;
      }

      if (languageSwitched && action === 'unknown') {
        return;
      }

      await handleCommand(command);
    } finally {
      isProcessingCommandRef.current = false;
    }
  }, [detectLanguageSwitch, executeLocalAction, handleCommand, normalizeCommandText, normalizeVoiceCommand]);

  const scheduleRecognitionRestart = useCallback(() => {
    if (!keepListeningRef.current || !backgroundModeRef.current) return;

    clearRestartTimer();
    // Restart immediately without delay
    if (!keepListeningRef.current || recognitionStartingRef.current || recognitionActiveRef.current) {
      return;
    }

    console.log('[assistant] mic restart');
    safeStartRecognition(0);
  }, [clearRestartTimer, safeStartRecognition]);

  const startRecognitionEngine = useCallback(() => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      console.error('Speech recognition not supported in this browser');
      setRecognitionError('Speech recognition not supported in this browser. Please use Chrome.');
      return undefined;
    }

    if (!recognitionRef.current) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
    }

    const rec = recognitionRef.current;
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = currentLangRef.current;
    rec.maxAlternatives = 3;

    rec.onstart = () => {
      recognitionStartingRef.current = false;
      recognitionActiveRef.current = true;
      setIsListening(true);
      setSystemStatus(prev => ({ ...prev, listening: true }));
      setRecognitionError(null);
      console.log('🎤 Mic started successfully');
      // Start audio visualization in background without blocking
      startAudioVisualization();
    };

    rec.onend = () => {
      recognitionStartingRef.current = false;
      recognitionActiveRef.current = false;
      setSystemStatus(prev => ({ ...prev, listening: false }));
      console.log('🔁 Recognition ended');

      if (keepListeningRef.current && backgroundModeRef.current && !manualStopRef.current) {
        console.log('🔄 Scheduling recognition restart');
        scheduleRecognitionRestart();
      }
    };

    rec.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcriptText = normalizeCommandText(result[0].transcript);
      const confidence = result[0].confidence || 0.8;

      setTranscript(transcriptText);
      setTranscriptConfidence(confidence);
      setInterimTranscript(result.isFinal ? '' : transcriptText);
      console.log('🗣 Live:', transcriptText, 'Conf:', confidence.toFixed(2), 'Final:', result.isFinal);

      // Don't process if assistant is speaking to avoid picking up system voice
      if (speakingRef.current || isProcessingRef.current) {
        console.log('Ignoring speech - assistant is speaking or processing');
        return;
      }

      // Only process final results to avoid duplicates
      if (result.isFinal && transcriptText.length > 0) {
        console.log('Processing final result:', transcriptText);
        handleCommandFast(transcriptText);
      }
    };

    rec.onerror = (event) => {
      recognitionStartingRef.current = false;
      recognitionActiveRef.current = false;

      console.error('❌ Speech recognition error:', event.error);
      logClientEvent('error', 'speech_recognition_error', 'Speech recognition error', {
        error: event.error
      });

      setRecognitionError(event.error);
      setSystemStatus(prev => ({ ...prev, listening: false }));

      if (event.error === 'not-allowed') {
        const errorMsg = 'Microphone access denied. Please allow microphone permissions in your browser settings.';
        setAiResponse(errorMsg);
        setRecognitionError(errorMsg);
        keepListeningRef.current = false;
        isListeningRef.current = false;
        setIsListening(false);
        return;
      }

      if (event.error === 'no-speech') {
        console.log('No speech detected, will restart if in background mode...');
        if (keepListeningRef.current && backgroundModeRef.current && !manualStopRef.current) {
          scheduleRecognitionRestart();
        }
        return;
      }

      if (event.error === 'network') {
        console.log('Network error, speech recognition requires internet connection');
        setRecognitionError('Network error. Please check your internet connection.');
        if (keepListeningRef.current && backgroundModeRef.current && !manualStopRef.current) {
          scheduleRecognitionRestart();
        }
        return;
      }

      if (event.error === 'audio-capture') {
        console.log('Audio capture error, microphone may be in use');
        setRecognitionError('Audio capture error. Microphone may be in use by another application.');
        if (keepListeningRef.current && backgroundModeRef.current && !manualStopRef.current) {
          scheduleRecognitionRestart();
        }
        return;
      }

      // For other errors, try to restart if in background mode
      console.log('Unknown error, attempting restart if in background mode');
      if (keepListeningRef.current && backgroundModeRef.current && !manualStopRef.current) {
        scheduleRecognitionRestart();
      }
    };

    return rec;
  }, [handleCommandFast, logClientEvent, normalizeCommandText, scheduleRecognitionRestart, startAudioVisualization]);

  useEffect(() => {
    speakTextRef.current = speakText;
    handleCommandRef.current = handleCommandFast;
  }, [handleCommandFast, speakText]);

  useEffect(() => {
    checkBackendConnection();
    const interval = setInterval(checkBackendConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const rec = startRecognitionEngine();

    return () => {
      if (rec) {
        try {
          rec.onend = null;
          rec.onerror = null;
          rec.onresult = null;
          rec.onstart = null;
          rec.stop();
        } catch (e) {}
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearSilenceTimer();
      clearRestartTimer();
      recognitionActiveRef.current = false;
      keepListeningRef.current = false;
      manualStopRef.current = true;
      stopAudioVisualization();
    };
  }, [clearRestartTimer, clearSilenceTimer, startRecognitionEngine, stopAudioVisualization]);

  useEffect(() => {
    // Auto-start recognition if not already started
    if (recognitionRef.current && !recognitionActiveRef.current && !recognitionStartingRef.current) {
      console.log('[assistant] Auto-starting recognition on mount');
      safeStartRecognition(0);
    }
  }, [safeStartRecognition]);

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert('Speech recognition is not supported in your browser. Please use Chrome.');
      return;
    }

    if (isListening) {
      stopListeningSession(true);
      stopAudioVisualization();
    } else {
      manualStopRef.current = false;
      keepListeningRef.current = true;
      isListeningRef.current = true;
      setIsListening(true);
      setSystemStatus(prev => ({ ...prev, listening: true }));
      startListeningSession();
    }
  };

  const toggleBackgroundMode = () => {
    setBackgroundMode((prev) => {
      const next = !prev;
      if (!next) {
        manualStopRef.current = true;
        clearRestartListeningTimeout();
      } else if (isListeningRef.current && !recognitionActiveRef.current) {
        keepListeningRef.current = true;
        safeStartRecognition(0);
      }
      return next;
    });
  };

  const stopListening = () => {
    stopAssistant();
  };

  const handleTranscriptCorrection = (correctedText) => {
    setTranscript(correctedText);
    setShowTranscriptVerification(false);
    handleCommandFast(correctedText);
  };

  const retryListening = () => {
    setShowTranscriptVerification(false);
    setTranscript('');
    setTranscriptConfidence(0);
    manualStopRef.current = false;
    keepListeningRef.current = true;
    isListeningRef.current = true;
    setIsListening(true);
    startListeningSession();
  };

  const handleConfirmation = async (confirmed) => {
    if (confirmationDialog) {
      if (confirmed) {
        await executeCommand(confirmationDialog.intent, confirmationDialog.parameters, true);
      } else {
        const cancelMsg = 'Action cancelled.';
        setAiResponse(cancelMsg);
        speakText(cancelMsg);
      }
      setConfirmationDialog(null);
    }
  };

  const clearHistory = () => {
    setCommandHistory([]);
    setTranscript('');
    setInterimTranscript('');
    setAiResponse('');
    setTranscriptConfidence(0);
    setShowTranscriptVerification(false);
  };

  const stopSpeaking = () => {
    window.speechSynthesis.cancel();
    setSystemStatus(prev => ({ ...prev, speaking: false }));
  };

  const submitTypedCommand = async () => {
    const nextCommand = typedCommand.trim();
    if (!nextCommand) return;
    setTypedCommand('');
    await handleCommandFast(nextCommand);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <Command size={32} />
          <h1>Voice Assistant</h1>
        </div>
        <div className="header-controls">
          <div className={`mode-indicator ${backgroundMode ? 'enabled' : 'disabled'}`}>
            <Activity size={16} />
            <span>{backgroundMode ? 'Continuous Mode: ON' : 'Continuous Mode: OFF'}</span>
          </div>
          <div className="mode-indicator language">
            <Globe size={16} />
            <span>{currentLang}</span>
          </div>
          <button
            className="icon-btn"
            onClick={() => setTtsEnabled(!ttsEnabled)}
            title={ttsEnabled ? 'Disable voice responses' : 'Enable voice responses'}
          >
            {ttsEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
          </button>
          <button
            className="icon-btn"
            onClick={clearHistory}
            title="Clear history"
          >
            <Trash2 size={20} />
          </button>
          <button
            className="icon-btn"
            onClick={toggleBackgroundMode}
            title={backgroundMode ? 'Disable background listening' : 'Enable background listening'}
          >
            {backgroundMode ? 'BG On' : 'BG Off'}
          </button>
          <div className={`status-indicator ${backendConnected ? 'connected' : 'disconnected'}`}>
            <Wifi size={16} />
            <span>{backendConnected ? 'Connected' : 'Offline'}</span>
          </div>
        </div>
      </header>

      <main className="app-main">
        <div className="main-interface">
          <section className="hero-strip">
            <div className="hero-copy">
              <span className="eyebrow">Local Voice Assistant</span>
              <h2>Fast voice control with background-ready listening while this app stays open.</h2>
              <p>
                Keep this browser tab open for continuous mic listening. Use the stop button anytime to mute the microphone instantly.
              </p>
              <div className={`continuous-banner ${backgroundMode ? 'enabled' : 'disabled'}`}>
                <Activity size={18} />
                <span>
                  {backgroundMode
                    ? 'Continuous background listening is active. The assistant keeps waiting for the next command.'
                    : 'Continuous background listening is off. Turn it on to keep the assistant always listening.'}
                </span>
              </div>
            </div>
            <div className="hero-stats">
              <div className="stat-card">
                <Zap size={18} />
                <span>Fast local parsing</span>
              </div>
              <div className="stat-card">
                <Globe size={18} />
                <span>App and web commands</span>
              </div>
              <div className="stat-card">
                <Volume1 size={18} />
                <span>Voice and typed input</span>
              </div>
            </div>
          </section>

          <div className="voice-section">
            <div className={`mic-container ${isListening ? 'listening' : ''}`}>
              <button
                type="button"
                className={`mic-btn ${isListening ? 'active' : ''}`}
                onClick={toggleListening}
              >
                {isListening ? <Mic size={48} /> : <MicOff size={48} />}
              </button>
              {isListening && <div className="mic-ripple"></div>}
            </div>

            <div className="mic-actions">
              <button type="button" className="action-btn primary" onClick={toggleListening}>
                {isListening ? <Mic size={16} /> : <MicOff size={16} />}
                <span>{isListening ? 'Listening' : 'Start Mic'}</span>
              </button>
              <button type="button" className="action-btn danger" onClick={stopListening}>
                <Square size={16} />
                <span>Stop Mic</span>
              </button>
              <button type="button" className={`action-btn ${backgroundMode ? 'active-mode' : ''}`} onClick={toggleBackgroundMode}>
                <Activity size={16} />
                <span>{backgroundMode ? 'Background On' : 'Background Off'}</span>
              </button>
            </div>

            <div className="assistant-grid">
              <div className="assistant-panel">
                <h3>Background Listening</h3>
                <p>
                  {backgroundMode
                    ? 'Enabled. The assistant will try to resume listening after each command while this app stays open.'
                    : 'Disabled. The microphone will stop after each listening session.'}
                </p>
              </div>
              <div className="assistant-panel">
                <h3>Mic Control</h3>
                <p>{isListening ? 'Microphone is active now. Use Stop Mic anytime for immediate silence.' : 'Microphone is idle. Start it when you want voice capture.'}</p>
              </div>
            </div>

            {isListening && (
              <div className="audio-visualizer">
                <div className="audio-label">Audio Level</div>
                <div className="audio-bar-container">
                  <div
                    className={`audio-bar ${audioLevel < 20 ? 'low' : audioLevel < 60 ? 'medium' : 'good'}`}
                    style={{ width: `${Math.min(audioLevel * 1.5, 100)}%` }}
                  />
                </div>
                <div className="audio-hint">
                  {audioLevel < 20 ? 'Speak louder or closer to mic' : audioLevel > 100 ? 'Reduce background noise' : 'Good audio level'}
                </div>
              </div>
            )}

            <div className="transcript-display">
              {interimTranscript && (
                <p className="interim-text">{interimTranscript}</p>
              )}
              {transcript && (
                <>
                  <p className="final-text">{transcript}</p>
                  {transcriptConfidence > 0 && (
                    <div className={`confidence-indicator ${transcriptConfidence >= MIN_CONFIDENCE_THRESHOLD ? 'good' : 'low'}`}>
                      {transcriptConfidence >= MIN_CONFIDENCE_THRESHOLD ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                      <span>Confidence: {Math.round(transcriptConfidence * 100)}%</span>
                    </div>
                  )}
                </>
              )}
              {!transcript && !interimTranscript && (
                <p className="placeholder-text">
                  {isListening
                    ? 'Listening... Speak clearly for best results'
                    : backgroundMode
                      ? 'Background mode is ready. Click the microphone to start listening.'
                      : 'Click the microphone to start'}
                </p>
              )}
            </div>

            <div className="typed-command-box">
              <div className="typed-command-header">
                <h3>Send A Command</h3>
                <span>Use text for fast control when you do not want to speak.</span>
              </div>
              <div className="typed-command-row">
                <input
                  type="text"
                  value={typedCommand}
                  onChange={(event) => setTypedCommand(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      submitTypedCommand();
                    }
                  }}
                  placeholder="Type a command like: open youtube"
                />
                <button className="send-btn" onClick={submitTypedCommand}>
                  <Send size={16} />
                  <span>Send</span>
                </button>
              </div>
            </div>

            <div className="quick-commands">
              <div className="quick-commands-header">
                <h3>Quick Commands</h3>
                <span>Tap once to test assistant actions quickly.</span>
              </div>
              <div className="quick-command-list">
                {quickCommands.map((command) => (
                  <button
                    key={command}
                    className="quick-command-btn"
                    onClick={() => handleCommandFast(command)}
                  >
                    {command}
                  </button>
                ))}
              </div>
            </div>

            <div className="system-status">
              <div className={`status-item ${systemStatus.listening ? 'active' : ''}`}>
                <Mic size={16} />
                <span>Listening</span>
              </div>
              <div className={`status-item ${systemStatus.processing ? 'active' : ''}`}>
                <Cpu size={16} />
                <span>Processing</span>
              </div>
              <div className={`status-item ${systemStatus.speaking ? 'active' : ''}`}>
                <Activity size={16} />
                <span>Speaking</span>
              </div>
            </div>
          </div>

          <div className="response-section">
            <h2>Assistant Response</h2>
            <div className="response-box">
              {aiResponse ? (
                <p>{aiResponse}</p>
              ) : (
                <p className="placeholder">Your assistant response will appear here...</p>
              )}
            </div>
            {systemStatus.speaking && (
              <button className="stop-btn" onClick={stopSpeaking}>
                Stop Speaking
              </button>
            )}
            <div className="response-meta">
              <div className="response-note">
                <strong>Tip:</strong> keep this page open if you want the microphone to keep restarting in background mode.
              </div>
              {recognitionError && (
                <div className="response-warning">
                  <AlertCircle size={16} />
                  <span>Mic issue: {recognitionError}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="history-section">
          <h2>Command History</h2>
          <div className="history-list">
            {commandHistory.length === 0 ? (
              <p className="empty-history">No commands yet. Start speaking!</p>
            ) : (
              commandHistory.map((item) => (
                <div key={item.id} className="history-item">
                  <div className="history-header">
                    <span className="intent-badge">{item.intent}</span>
                    <span className="timestamp">{item.timestamp}</span>
                  </div>
                  <p className="command-text">{item.command}</p>
                  <p className="response-text">{item.response}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </main>

      {showTranscriptVerification && (
        <div className="confirmation-overlay">
          <div className="confirmation-dialog verification-dialog">
            <h3>Did you say this correctly?</h3>
            <p className="recognized-text">"{transcript}"</p>
            <p className="confidence-warning">
              Confidence: {Math.round(transcriptConfidence * 100)}% (below optimal)
            </p>

            {commandAlternatives.length > 0 && (
              <div className="alternatives-section">
                <p>Or did you mean:</p>
                <div className="alternatives-list">
                  {commandAlternatives.map((alt, index) => (
                    <button
                      key={index}
                      className="alternative-btn"
                      onClick={() => handleTranscriptCorrection(alt.text)}
                    >
                      "{alt.text}"
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="verification-buttons">
              <button
                className="confirm-btn confirm"
                onClick={() => handleTranscriptCorrection(transcript)}
              >
                <CheckCircle size={16} /> Yes, proceed
              </button>
              <button
                className="confirm-btn retry"
                onClick={retryListening}
              >
                <RefreshCw size={16} /> Try again
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmationDialog && (
        <div className="confirmation-overlay">
          <div className="confirmation-dialog">
            <h3>Confirmation Required</h3>
            <p>{confirmationDialog.message}</p>
            <div className="confirmation-buttons">
              <button
                className="confirm-btn confirm"
                onClick={() => handleConfirmation(true)}
              >
                Confirm
              </button>
              <button
                className="confirm-btn cancel"
                onClick={() => handleConfirmation(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="app-footer">
        <p>Voice-Controlled Laptop Assistant - Local voice mode</p>
      </footer>
    </div>
  );
};

export default App;