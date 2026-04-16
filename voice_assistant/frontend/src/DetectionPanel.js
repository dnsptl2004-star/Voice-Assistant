import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { Camera, CameraOff, Eye, Hand, Activity, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import './DetectionPanel.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const DetectionPanel = () => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [detectionMode, setDetectionMode] = useState('combined'); // 'face-eye', 'hand', 'combined'
  const [detectionResults, setDetectionResults] = useState(null);
  const [error, setError] = useState(null);
  const [serviceStatus, setServiceStatus] = useState(null);
  const [fps, setFps] = useState(0);
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const animationFrameRef = useRef(null);
  const lastFrameTimeRef = useRef(0);
  const frameCountRef = useRef(0);

  // Check detection service health
  const checkServiceHealth = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/detection/health`);
      setServiceStatus(response.data);
      return response.data;
    } catch (err) {
      console.error('Detection service health check failed:', err);
      setServiceStatus({ error: 'Service unavailable' });
      return null;
    }
  }, []);

  useEffect(() => {
    checkServiceHealth();
  }, [checkServiceHealth]);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: 'user' }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
        setIsStreaming(true);
        setError(null);
      }
    } catch (err) {
      setError('Camera access denied or not available');
      console.error('Camera error:', err);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    setIsStreaming(false);
    setDetectionResults(null);
  };

  const captureAndDetect = useCallback(async () => {
    if (!videoRef.current || !isStreaming) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw video frame to canvas
    ctx.drawImage(video, 0, 0);
    
    // Convert to base64
    const imageData = canvas.toDataURL('image/jpeg', 0.8);
    const base64Data = imageData.split(',')[1];

    try {
      let endpoint;
      switch (detectionMode) {
        case 'face-eye':
          endpoint = '/api/detection/face-eye';
          break;
        case 'hand':
          endpoint = '/api/detection/hand';
          break;
        case 'combined':
        default:
          endpoint = '/api/detection/combined';
          break;
      }

      const response = await axios.post(`${API_BASE_URL}${endpoint}`, {
        image: base64Data
      });

      setDetectionResults(response.data);

      // Draw annotated image if available
      if (response.data.annotated_image) {
        const img = new Image();
        img.onload = () => {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0);
        };
        img.src = `data:image/jpeg;base64,${response.data.annotated_image}`;
      }

      // Calculate FPS
      frameCountRef.current++;
      const now = performance.now();
      if (now - lastFrameTimeRef.current >= 1000) {
        setFps(frameCountRef.current);
        frameCountRef.current = 0;
        lastFrameTimeRef.current = now;
      }
    } catch (err) {
      console.error('Detection error:', err);
      setError('Detection service error');
    }
  }, [isStreaming, detectionMode]);

  useEffect(() => {
    let animationId;
    
    const processFrame = () => {
      if (isStreaming) {
        captureAndDetect();
        animationId = requestAnimationFrame(processFrame);
      }
    };

    if (isStreaming) {
      lastFrameTimeRef.current = performance.now();
      frameCountRef.current = 0;
      animationId = requestAnimationFrame(processFrame);
    }

    return () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
  }, [isStreaming, captureAndDetect]);

  const handleStart = () => {
    startCamera();
  };

  const handleStop = () => {
    stopCamera();
  };

  const handleModeChange = (mode) => {
    setDetectionMode(mode);
  };

  return (
    <div className="detection-panel">
      <div className="detection-header">
        <h2>
          <Activity className="icon" />
          Live Detection
        </h2>
        <div className="detection-controls">
          <button
            className={`mode-btn ${detectionMode === 'face-eye' ? 'active' : ''}`}
            onClick={() => handleModeChange('face-eye')}
          >
            <Eye className="icon" />
            Face & Eye
          </button>
          <button
            className={`mode-btn ${detectionMode === 'hand' ? 'active' : ''}`}
            onClick={() => handleModeChange('hand')}
          >
            <Hand className="icon" />
            Hand
          </button>
          <button
            className={`mode-btn ${detectionMode === 'combined' ? 'active' : ''}`}
            onClick={() => handleModeChange('combined')}
          >
            <Activity className="icon" />
            Combined
          </button>
        </div>
      </div>

      <div className="detection-content">
        <div className="video-container">
          <div className="video-wrapper">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`video-feed ${isStreaming ? 'active' : ''}`}
            />
            <canvas
              ref={canvasRef}
              className="detection-canvas"
            />
            {!isStreaming && (
              <div className="video-placeholder">
                <Camera className="placeholder-icon" />
                <p>Camera is off</p>
                <button className="start-btn" onClick={handleStart}>
                  <Camera className="icon" />
                  Start Camera
                </button>
              </div>
            )}
          </div>
          
          {isStreaming && (
            <div className="stream-controls">
              <button className="stop-btn" onClick={handleStop}>
                <CameraOff className="icon" />
                Stop Camera
              </button>
              <div className="fps-counter">
                <Activity className="icon" />
                {fps} FPS
              </div>
            </div>
          )}
        </div>

        <div className="results-panel">
          <div className="results-header">
            <h3>Detection Results</h3>
            <button className="refresh-btn" onClick={checkServiceHealth}>
              <RefreshCw className="icon" />
            </button>
          </div>

          {serviceStatus && (
            <div className="service-status">
              <h4>Service Status</h4>
              <div className="status-item">
                <CheckCircle className={`icon ${serviceStatus.opencv_available ? 'success' : 'error'}`} />
                OpenCV: {serviceStatus.opencv_available ? 'Available' : 'Not Available'}
              </div>
              <div className="status-item">
                <CheckCircle className={`icon ${serviceStatus.mediapipe_available ? 'success' : 'error'}`} />
                MediaPipe: {serviceStatus.mediapipe_available ? 'Available' : 'Not Available'}
              </div>
              <div className="status-item">
                <CheckCircle className={`icon ${serviceStatus.face_detection_available ? 'success' : 'error'}`} />
                Face Detection: {serviceStatus.face_detection_available ? 'Available' : 'Not Available'}
              </div>
              <div className="status-item">
                <CheckCircle className={`icon ${serviceStatus.hand_detection_available ? 'success' : 'error'}`} />
                Hand Detection: {serviceStatus.hand_detection_available ? 'Available' : 'Not Available'}
              </div>
            </div>
          )}

          {error && (
            <div className="error-message">
              <AlertCircle className="icon" />
              {error}
            </div>
          )}

          {detectionResults && (
            <div className="detection-data">
              {detectionMode === 'face-eye' || detectionMode === 'combined' ? (
                <div className="result-section">
                  <h4>
                    <Eye className="icon" />
                    Face & Eye Detection
                  </h4>
                  <div className="data-row">
                    <span className="label">Faces Detected:</span>
                    <span className="value">{detectionResults.faces_detected}</span>
                  </div>
                  <div className="data-row">
                    <span className="label">Left Eye EAR:</span>
                    <span className="value">{detectionResults.left_eye_ear?.toFixed(3)}</span>
                  </div>
                  <div className="data-row">
                    <span className="label">Right Eye EAR:</span>
                    <span className="value">{detectionResults.right_eye_ear?.toFixed(3)}</span>
                  </div>
                  <div className="data-row">
                    <span className="label">Eye Status:</span>
                    <span className={`value ${detectionResults.eyes_closed ? 'closed' : 'open'}`}>
                      {detectionResults.eyes_closed ? 'CLOSED' : 'OPEN'}
                    </span>
                  </div>
                </div>
              ) : null}

              {detectionMode === 'hand' || detectionMode === 'combined' ? (
                <div className="result-section">
                  <h4>
                    <Hand className="icon" />
                    Hand Detection
                  </h4>
                  <div className="data-row">
                    <span className="label">Hands Detected:</span>
                    <span className="value">{detectionResults.hands_detected}</span>
                  </div>
                  {detectionResults.hands && detectionResults.hands.map((hand, index) => (
                    <div key={index} className="hand-info">
                      <div className="data-row">
                        <span className="label">Hand {index + 1} ({hand.label}):</span>
                        <span className={`value ${hand.state === 'OPEN' ? 'open' : 'closed'}`}>
                          {hand.state}
                        </span>
                      </div>
                      <div className="data-row">
                        <span className="label">Fingers Open:</span>
                        <span className="value">{hand.fingers_open}/5</span>
                      </div>
                      {hand.finger_states && (
                        <div className="finger-states">
                          {hand.finger_states.map((state, i) => (
                            <span key={i} className={`finger ${state ? 'open' : 'closed'}`}>
                              {i + 1}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          {!detectionResults && !error && isStreaming && (
            <div className="placeholder-message">
              <Activity className="icon" />
              <p>Waiting for detection results...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DetectionPanel;
