import os
import sys
import time
import math
import platform
import importlib
import warnings
import base64
import io
from flask import Blueprint, request, jsonify

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["ABSL_LOGLEVEL"] = "3"
warnings.filterwarnings("ignore")

detection_bp = Blueprint('detection', __name__)

# Suppress C stderr
def _suppress_c_stderr():
    try:
        devnull = os.open(os.devnull, os.O_RDWR)
        saved = os.dup(2)
        os.dup2(devnull, 2)
        os.close(devnull)
        return saved
    except Exception:
        return None

def _restore_c_stderr(saved_fd):
    if saved_fd is None:
        return
    try:
        os.dup2(saved_fd, 2)
    except Exception:
        pass
    try:
        os.close(saved_fd)
    except Exception:
        pass

# Import libraries
cv2 = None
mp = None
np = None

try:
    _saved_fd = _suppress_c_stderr()
    try:
        import cv2
    except Exception:
        cv2 = None
    try:
        import mediapipe as mp
    except Exception:
        try:
            mp = importlib.import_module("mediapipe")
        except Exception:
            mp = None
    try:
        import numpy as np
    except Exception:
        np = None
finally:
    _restore_c_stderr(_saved_fd)

if cv2 is None:
    print("Warning: opencv-python not available")
if mp is None:
    print("Warning: mediapipe not available")
if np is None:
    print("Warning: numpy not available")

# Initialize MediaPipe solutions
mp_solutions = None
mp_face = None
mp_hands = None
mp_draw = None

if mp is not None:
    try:
        mp_solutions = getattr(mp, "solutions", None) or importlib.import_module("mediapipe.solutions")
        mp_face = getattr(mp_solutions, "face_mesh", None) or importlib.import_module("mediapipe.solutions.face_mesh")
        mp_hands = mp_solutions.hands
        mp_draw = mp_solutions.drawing_utils
    except Exception as e:
        print(f"Warning: Could not initialize MediaPipe solutions: {e}")

# Face mesh indices
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [263, 387, 385, 362, 380, 373]
EAR_THRESHOLD = 0.20

# Hand detection indices
TIPS = [4, 8, 12, 16, 20]
PIPS = [3, 6, 10, 14, 18]

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def ear(landmarks, idx, w, h):
    try:
        pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in idx]
    except Exception:
        return 1.0
    denom = dist(pts[0], pts[3])
    if denom <= 1e-6:
        return 1.0
    return (dist(pts[1], pts[5]) + dist(pts[2], pts[4])) / (2.0 * denom)

def frame_to_base64(frame):
    """Convert OpenCV frame to base64 string"""
    try:
        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode('utf-8')
    except Exception:
        return None

# Initialize detectors
face_detector = None
hand_detector = None

if mp_face is not None:
    try:
        face_detector = mp_face.FaceMesh(
            refine_landmarks=True, 
            max_num_faces=1, 
            min_detection_confidence=0.5, 
            min_tracking_confidence=0.5
        )
    except Exception:
        pass

if mp_hands is not None:
    try:
        hand_detector = mp_hands.Hands(
            max_num_hands=4,
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
    except Exception:
        pass

@detection_bp.route('/api/detection/face-eye', methods=['POST'])
def detect_face_eye():
    """Detect face and eye state from image"""
    try:
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400
        
        if np is None:
            return jsonify({'error': 'NumPy not available'}), 500
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Could not decode image'}), 400
        
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        result = {
            'faces_detected': 0,
            'left_eye_ear': 1.0,
            'right_eye_ear': 1.0,
            'eyes_closed': False,
            'landmarks': []
        }
        
        if face_detector is not None:
            res = face_detector.process(rgb)
            if res and getattr(res, "multi_face_landmarks", None):
                result['faces_detected'] = len(res.multi_face_landmarks)
                for fl in res.multi_face_landmarks:
                    landmarks = []
                    for lm in fl.landmark:
                        landmarks.append({
                            'x': lm.x,
                            'y': lm.y,
                            'z': lm.z
                        })
                    result['landmarks'].append(landmarks)
                    
                    blink_left = ear(fl.landmark, LEFT_EYE_IDX, w, h)
                    blink_right = ear(fl.landmark, RIGHT_EYE_IDX, w, h)
                    result['left_eye_ear'] = blink_left
                    result['right_eye_ear'] = blink_right
                    result['eyes_closed'] = blink_left < EAR_THRESHOLD and blink_right < EAR_THRESHOLD
        
        # Annotate frame
        annotated = frame.copy()
        if result['faces_detected'] > 0:
            # Draw face mesh
            if res and res.multi_face_landmarks:
                for fl in res.multi_face_landmarks:
                    mp_draw.draw_landmarks(
                        annotated, 
                        fl, 
                        mp_face.FACEMESH_CONTOURS,
                        mp_draw.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1),
                        mp_draw.DrawingSpec(color=(0, 255, 0), thickness=1)
                    )
            
            # Draw status
            status = f"Faces: {result['faces_detected']} | L-EAR: {result['left_eye_ear']:.2f} | R-EAR: {result['right_eye_ear']:.2f}"
            color = (0, 255, 0) if not result['eyes_closed'] else (0, 0, 255)
            cv2.putText(annotated, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        result['annotated_image'] = frame_to_base64(annotated)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@detection_bp.route('/api/detection/hand', methods=['POST'])
def detect_hand():
    """Detect hand and finger states from image"""
    try:
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400
        
        if np is None:
            return jsonify({'error': 'NumPy not available'}), 500
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Could not decode image'}), 400
        
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        result = {
            'hands_detected': 0,
            'hands': []
        }
        
        if hand_detector is not None:
            res = hand_detector.process(rgb)
            if res and getattr(res, "multi_hand_landmarks", None) and getattr(res, "multi_handedness", None):
                result['hands_detected'] = len(res.multi_hand_landmarks)
                
                for lm, hd in zip(res.multi_hand_landmarks, res.multi_handedness):
                    if not getattr(hd, "classification", None):
                        continue
                    
                    score = hd.classification[0].score
                    if score < 0.7:
                        continue
                    
                    label = hd.classification[0].label
                    
                    # Detect finger states
                    fingers = []
                    try:
                        if label == "Right":
                            fingers.append(lm.landmark[4].x < lm.landmark[3].x)
                        else:
                            fingers.append(lm.landmark[4].x > lm.landmark[3].x)
                        for i in range(1, 5):
                            fingers.append(lm.landmark[TIPS[i]].y < lm.landmark[PIPS[i]].y)
                    except Exception:
                        continue
                    
                    open_count = sum(1 for f in fingers if f)
                    hand_state = "OPEN" if open_count >= 4 else "CLOSED"
                    
                    hand_info = {
                        'label': label,
                        'confidence': score,
                        'state': hand_state,
                        'fingers_open': open_count,
                        'finger_states': fingers,
                        'landmarks': [{'x': lm.x, 'y': lm.y, 'z': lm.z} for lm in lm.landmark]
                    }
                    result['hands'].append(hand_info)
        
        # Annotate frame
        annotated = frame.copy()
        if result['hands_detected'] > 0 and res:
            for lm in res.multi_hand_landmarks:
                mp_draw.draw_landmarks(annotated, lm, mp_hands.HAND_CONNECTIONS)
            
            # Draw hand info
            y_offset = 30
            for i, hand in enumerate(result['hands']):
                text = f"Hand {i+1} ({hand['label']}): {hand['state']} [{hand['fingers_open']}/5]"
                cv2.putText(annotated, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                y_offset += 30
        
        result['annotated_image'] = frame_to_base64(annotated)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@detection_bp.route('/api/detection/combined', methods=['POST'])
def detect_combined():
    """Combined face, eye, and hand detection"""
    try:
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400
        
        if np is None:
            return jsonify({'error': 'NumPy not available'}), 500
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Could not decode image'}), 400
        
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        result = {
            'faces_detected': 0,
            'eyes_closed': False,
            'left_eye_ear': 1.0,
            'right_eye_ear': 1.0,
            'hands_detected': 0,
            'hands': []
        }
        
        # Face and eye detection
        res_face = None
        if face_detector is not None:
            res_face = face_detector.process(rgb)
            if res_face and getattr(res_face, "multi_face_landmarks", None):
                result['faces_detected'] = len(res_face.multi_face_landmarks)
                for fl in res_face.multi_face_landmarks:
                    blink_left = ear(fl.landmark, LEFT_EYE_IDX, w, h)
                    blink_right = ear(fl.landmark, RIGHT_EYE_IDX, w, h)
                    result['left_eye_ear'] = blink_left
                    result['right_eye_ear'] = blink_right
                    result['eyes_closed'] = blink_left < EAR_THRESHOLD and blink_right < EAR_THRESHOLD
        
        # Hand detection
        res_hand = None
        if hand_detector is not None:
            res_hand = hand_detector.process(rgb)
            if res_hand and getattr(res_hand, "multi_hand_landmarks", None) and getattr(res_hand, "multi_handedness", None):
                result['hands_detected'] = len(res_hand.multi_hand_landmarks)
                
                for lm, hd in zip(res_hand.multi_hand_landmarks, res_hand.multi_handedness):
                    if not getattr(hd, "classification", None):
                        continue
                    
                    score = hd.classification[0].score
                    if score < 0.7:
                        continue
                    
                    label = hd.classification[0].label
                    
                    fingers = []
                    try:
                        if label == "Right":
                            fingers.append(lm.landmark[4].x < lm.landmark[3].x)
                        else:
                            fingers.append(lm.landmark[4].x > lm.landmark[3].x)
                        for i in range(1, 5):
                            fingers.append(lm.landmark[TIPS[i]].y < lm.landmark[PIPS[i]].y)
                    except Exception:
                        continue
                    
                    open_count = sum(1 for f in fingers if f)
                    hand_state = "OPEN" if open_count >= 4 else "CLOSED"
                    
                    hand_info = {
                        'label': label,
                        'state': hand_state,
                        'fingers_open': open_count
                    }
                    result['hands'].append(hand_info)
        
        # Annotate frame
        annotated = frame.copy()
        
        # Draw face mesh
        if res_face and res_face.multi_face_landmarks:
            for fl in res_face.multi_face_landmarks:
                mp_draw.draw_landmarks(
                    annotated, 
                    fl, 
                    mp_face.FACEMESH_CONTOURS,
                    mp_draw.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1),
                    mp_draw.DrawingSpec(color=(0, 255, 0), thickness=1)
                )
        
        # Draw hands
        if res_hand and res_hand.multi_hand_landmarks:
            for lm in res_hand.multi_hand_landmarks:
                mp_draw.draw_landmarks(annotated, lm, mp_hands.HAND_CONNECTIONS)
        
        # Draw status overlay
        y_offset = 30
        face_color = (0, 255, 0) if not result['eyes_closed'] else (0, 0, 255)
        cv2.putText(annotated, f"Faces: {result['faces_detected']} | Eyes: {'CLOSED' if result['eyes_closed'] else 'OPEN'}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, face_color, 2)
        y_offset += 30
        cv2.putText(annotated, f"Hands: {result['hands_detected']}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        for i, hand in enumerate(result['hands']):
            y_offset += 30
            cv2.putText(annotated, f"Hand {i+1} ({hand['label']}): {hand['state']} [{hand['fingers_open']}/5]", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        result['annotated_image'] = frame_to_base64(annotated)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@detection_bp.route('/api/detection/health', methods=['GET'])
def detection_health():
    """Check if detection services are available"""
    return jsonify({
        'opencv_available': cv2 is not None,
        'mediapipe_available': mp is not None,
        'numpy_available': np is not None,
        'face_detection_available': face_detector is not None,
        'hand_detection_available': hand_detector is not None
    })
