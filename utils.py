import os
import sys
import time
import math
import warnings
import platform
import importlib
from pathlib import Path
import numpy as np
import cv2

# --- Project Structure ---
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Logging Suppression ---
def suppress_library_logs():
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    os.environ["GLOG_minloglevel"] = "3"
    os.environ["ABSL_LOGLEVEL"] = "3"
    warnings.filterwarnings("ignore")

def suppress_c_stderr():
    try:
        devnull = os.open(os.devnull, os.O_RDWR)
        saved = os.dup(2)
        os.dup2(devnull, 2)
        os.close(devnull)
        return saved
    except Exception:
        return None

def restore_c_stderr(saved_fd):
    if saved_fd is None: return
    try:
        os.dup2(saved_fd, 2)
        os.close(saved_fd)
    except Exception:
        pass

# --- Resource Management ---
def get_resource_path(relative_path):
    """Returns absolute path to a resource relative to project root."""
    return str(BASE_DIR / relative_path)

def get_results_path(filename):
    """Returns absolute path for a result file."""
    return str(RESULTS_DIR / filename)

# --- Camera Management ---
def get_camera(index=0, width=1280, height=720):
    """
    Initializes camera with fallbacks and CAP_DSHOW on Windows.
    """
    flag = cv2.CAP_DSHOW if platform.system().lower() == "windows" else 0
    cap = cv2.VideoCapture(index, flag)
    
    if not cap.isOpened():
        # Try without CAP_DSHOW
        cap = cv2.VideoCapture(index)
        
    if cap.isOpened():
        if width: cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    return cap

# --- UI & Drawing ---
def draw_overlay_box(frame, lines, pos='top', alpha=0.55):
    """Draws a semi-transparent box with descriptive text."""
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.45, h / 720 * 0.6)
    thickness = max(1, int(font_scale * 2))
    pad_x, pad_y = 12, 8
    line_h = int(18 * font_scale) + pad_y
    total_h = line_h * len(lines) + pad_y
    
    if pos == 'top':
        x1, y1 = 10, 10
    else:
        x1, y1 = 10, h - total_h - 10
    
    x2 = w - 10
    y2 = y1 + total_h
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 0), -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    
    y = y1 + pad_y + int(14 * font_scale)
    for txt in lines:
        cv2.putText(frame, txt, (x1 + pad_x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        y += line_h

def draw_status_text(frame, text, pos=(10, 30), color=(0, 255, 0)):
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

# --- Math Utilities ---
def dist(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

def angle_between(a, b, c):
    v1 = (a.x - b.x, a.y - b.y)
    v2 = (c.x - b.x, c.y - b.y)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    n1 = math.hypot(v1[0], v1[1])
    n2 = math.hypot(v2[0], v2[1])
    if n1 * n2 == 0:
        return 180.0
    cosang = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cosang))
