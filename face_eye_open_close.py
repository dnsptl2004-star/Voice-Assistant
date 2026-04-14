import os, sys, time, math, platform, importlib, warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["ABSL_LOGLEVEL"] = "3"
warnings.filterwarnings("ignore")
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
_saved_fd = _suppress_c_stderr()
cv2 = None
mp = None
try:
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
finally:
    _restore_c_stderr(_saved_fd)
if cv2 is None:
    raise RuntimeError("opencv-python not available. Install with: pip install opencv-python")
if mp is None:
    raise RuntimeError("mediapipe not available. Install with: pip install mediapipe")
try:
    import pygame
except Exception:
    raise RuntimeError("pygame not available. Install with: pip install pygame")
mp_solutions = getattr(mp, "solutions", None) or importlib.import_module("mediapipe.solutions")
mp_face = getattr(mp_solutions, "face_mesh", None) or importlib.import_module("mediapipe.solutions.face_mesh")
mp_draw = getattr(mp_solutions, "drawing_utils", None) or importlib.import_module("mediapipe.python.solutions.drawing_utils")
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [263, 387, 385, 362, 380, 373]
EAR_THRESHOLD = 0.20
ALERT_COOLDOWN = 0.9
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
device = 0
if platform.system().lower().startswith("win"):
    try:
        cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(device)
    except Exception:
        cap = cv2.VideoCapture(device)
else:
    cap = cv2.VideoCapture(device)
face = mp_face.FaceMesh(refine_landmarks=True, max_num_faces=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)
landmark_spec = mp_draw.DrawingSpec(color=(0, 255, 0), thickness=0, circle_radius=0)
connection_spec = mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2)
ALARM_PATH = r"C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT\alarm1.mp3"
pygame.mixer.init()
alarm_loaded = False
if os.path.isfile(ALARM_PATH):
    try:
        pygame.mixer.music.load(ALARM_PATH)
        alarm_loaded = True
    except Exception as e:
        print("Failed to load alarm:", e)
else:
    print("Alarm file not found:", ALARM_PATH)
print("ESC to exit")
last_alert = 0.0
alarm_playing = False
try:
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            time.sleep(0.01)
            continue
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = face.process(rgb)
        faces_count = 0
        blink_left = 1.0
        blink_right = 1.0
        face_present = False
        if res and getattr(res, "multi_face_landmarks", None):
            faces_count = len(res.multi_face_landmarks)
            face_present = faces_count > 0
            for fl in res.multi_face_landmarks:
                mp_draw.draw_landmarks(frame, fl, mp_face.FACEMESH_CONTOURS, landmark_spec, connection_spec)
                blink_left = ear(fl.landmark, LEFT_EYE_IDX, w, h)
                blink_right = ear(fl.landmark, RIGHT_EYE_IDX, w, h)
                now = time.time()
                if blink_left < EAR_THRESHOLD and blink_right < EAR_THRESHOLD and (now - last_alert) > ALERT_COOLDOWN:
                    last_alert = now
        should_play = face_present and blink_left < EAR_THRESHOLD and blink_right < EAR_THRESHOLD
        if alarm_loaded and should_play and not alarm_playing:
            try:
                pygame.mixer.music.play(-1)
                alarm_playing = True
            except Exception as e:
                print("Unable to play alarm:", e)
                alarm_playing = False
        if alarm_loaded and not should_play and alarm_playing:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            alarm_playing = False
        status_text = f"Detector: FaceMesh  Faces: {faces_count}  EAR L:{blink_left:.2f} R:{blink_right:.2f}"
        cv2.putText(frame, status_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow("Face Eye Open / Close", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
except KeyboardInterrupt:
    pass
finally:
    try:
        if alarm_playing:
            pygame.mixer.music.stop()
    except Exception:
        pass
    try:
        pygame.mixer.quit()
    except Exception:
        pass
    try:
        cap.release()
    except Exception:
        pass
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
    try:
        face.close()
    except Exception:
        pass
