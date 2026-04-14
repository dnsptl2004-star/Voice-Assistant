import os, sys, warnings, importlib, time
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

mp_solutions = None
if hasattr(mp, "solutions"):
    mp_solutions = mp.solutions
else:
    try:
        mp_solutions = importlib.import_module("mediapipe.python.solutions")
    except Exception:
        try:
            mp_solutions = importlib.import_module("mediapipe.solutions")
        except Exception:
            mp_solutions = None

if mp_solutions is None:
    raise RuntimeError("Cannot locate mediapipe.solutions. Ensure mediapipe is correctly installed and try again.")

mp_hands = mp_solutions.hands
mp_draw = mp_solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=4,
    model_complexity=0,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

try:
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
except Exception:
    cap = cv2.VideoCapture(0)

TIPS = [4, 8, 12, 16, 20]
PIPS = [3, 6, 10, 14, 18]

prev_fingers = {}
prev_hand_state = {}

print("ESC to exit")

import winsound

try:
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            time.sleep(0.01)
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        try:
            res = hands.process(rgb)
        except Exception:
            continue

        current_keys = set()
        display_idx = 0

        if res and getattr(res, "multi_hand_landmarks", None) and getattr(res, "multi_handedness", None):
            for lm, hd in zip(res.multi_hand_landmarks, res.multi_handedness):
                if not getattr(hd, "classification", None):
                    continue
                score = hd.classification[0].score
                if score < 0.7:
                    continue

                label = hd.classification[0].label
                wrist = lm.landmark[0]
                hand_key = f"{label}_{round(wrist.x, 2)}_{round(wrist.y, 2)}"
                current_keys.add(hand_key)

                mp_draw.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)

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

                prev = prev_fingers.get(hand_key)
                if prev:
                    for i in range(5):
                        if fingers[i] != prev[i]:
                            winsound.Beep(1200 if fingers[i] else 600, 80)

                prev_fingers[hand_key] = fingers.copy()

                open_count = sum(1 for f in fingers if f)
                hand_state = "OPEN" if open_count >= 4 else "CLOSED"

                if prev_hand_state.get(hand_key) != hand_state:
                    winsound.Beep(1500 if hand_state == "OPEN" else 500, 150)
                    prev_hand_state[hand_key] = hand_state

                start_x = 10
                start_y = 30 + display_idx * 120
                line_height = 28

                font = cv2.FONT_HERSHEY_SIMPLEX
                title_scale = 0.8
                title_thickness = 2
                line_scale = 0.7
                line_thickness = 2

                title_text = f"HAND {display_idx+1} ({label}) : {hand_state} [{open_count}/5]"
                finger_texts = [f"Finger {i+1}: {'OPEN' if state else 'CLOSED'}" for i, state in enumerate(fingers)]

                padding = 8
                max_w = 0

                (tw, th), _ = cv2.getTextSize(title_text, font, title_scale, title_thickness)
                max_w = max(max_w, tw)
                title_h = th

                for t in finger_texts:
                    (tw2, th2), _ = cv2.getTextSize(t, font, line_scale, line_thickness)
                    max_w = max(max_w, tw2)

                rect_tl = (int(start_x - padding), int(start_y - title_h - padding))
                rect_br = (int(start_x + max_w + padding), int(start_y + len(finger_texts) * line_height + padding // 2))

                cv2.rectangle(frame, rect_tl, rect_br, (255, 255, 255), -1)

                cv2.putText(frame, title_text, (start_x, start_y),
                            font, title_scale, (0, 0, 0), title_thickness)

                for i, t in enumerate(finger_texts):
                    line_y = start_y + (i + 1) * line_height
                    cv2.putText(frame, t, (start_x, line_y),
                                font, line_scale, (0, 0, 0), line_thickness)

                display_idx += 1

        stale = set(prev_fingers.keys()) - current_keys
        for k in list(stale):
            prev_fingers.pop(k, None)
            prev_hand_state.pop(k, None)

        cv2.imshow("Hand & Finger Open Close", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

except KeyboardInterrupt:
    pass

finally:
    cap.release()
    cv2.destroyAllWindows()
    hands.close()
