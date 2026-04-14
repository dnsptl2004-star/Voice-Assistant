import sys
import subprocess
import os
import time
import cv2
import numpy as np
import argparse

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--image", type=str, help="single image filename (relative to BASE_DIR)")
group.add_argument("--live", action="store_true", help="run live webcam detection")
parser.add_argument("--display", action="store_true", help="display windows (for --image shows image; for --live shows frames)")
parser.add_argument("--conf", type=float, default=0.25, help="confidence threshold")
args = parser.parse_args()

if args.live and not args.display:
    args.display = True

try:
    from ultralytics import YOLO
except Exception:
    subprocess.run([sys.executable, "-m", "pip", "install", "ultralytics", "opencv-python", "numpy"], check=True)
    from ultralytics import YOLO

try:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
except Exception:
    device = "cpu"

MODEL_PATH = "yolov8n.pt"

def load_model(path):
    try:
        return YOLO(path)
    except Exception:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        return YOLO(path)

model = load_model(MODEL_PATH)

def _to_numpy(x):
    if x is None:
        return np.empty((0, 4))
    try:
        return x.cpu().numpy()
    except Exception:
        try:
            return np.array(x)
        except Exception:
            return np.empty((0, 4))

def names_get(names, idx):
    try:
        if isinstance(names, dict):
            return names.get(int(idx), str(idx))
        return names[int(idx)]
    except Exception:
        return str(idx)

def parse_result(result, scale_x=1.0, scale_y=1.0):
    if result is None or getattr(result, "boxes", None) is None:
        return np.empty((0, 4)), np.array([], dtype=int), np.array([])
    try:
        boxes = _to_numpy(result.boxes.xyxy).astype(float)
    except Exception:
        boxes = np.empty((0, 4))
    if boxes.size == 0:
        return boxes, np.array([], dtype=int), np.array([])
    boxes[:, [0, 2]] *= scale_x
    boxes[:, [1, 3]] *= scale_y
    try:
        cls = _to_numpy(result.boxes.cls).astype(int).flatten()
    except Exception:
        cls = np.array([], dtype=int)
    try:
        conf = _to_numpy(result.boxes.conf).flatten()
    except Exception:
        conf = np.array([])
    return boxes, cls, conf

def draw_annotations(img, boxes, cls, conf):
    h, w = img.shape[:2]
    person_idx = 1
    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes[i]
        x1, y1, x2, y2 = int(max(0, x1)), int(max(0, y1)), int(min(w - 1, x2)), int(min(h - 1, y2))
        score = float(conf[i]) if i < len(conf) else 0.0
        cid = int(cls[i]) if i < len(cls) else -1
        name = names_get(model.names, cid)
        if str(name).lower() == "person":
            label = f"person {person_idx} {score:.2f}"
            person_idx += 1
        else:
            label = f"{name} {score:.2f}"
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        ty = max(y1 - 10, th + 10)
        cv2.rectangle(img, (x1, ty - th - 6), (x1 + tw + 6, ty), (0, 255, 255), -1)
        cv2.putText(img, label, (x1 + 3, ty - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)
    return img

BASE_DIR = r"C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT"
OUT_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(OUT_DIR, exist_ok=True)

if args.image:
    image_name = args.image
    image_path = os.path.join(BASE_DIR, image_name)
    if not os.path.exists(image_path):
        raise SystemExit(f"Image not found: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        raise SystemExit(f"Unable to read image: {image_path}")
    h, w = img.shape[:2]
    small_w = 640
    small_h = max(1, int(small_w * h / w))
    small = cv2.resize(img, (small_w, small_h))
    try:
        res = model(small, device=device, imgsz=small_w, conf=args.conf, verbose=False)[0]
    except Exception:
        res = None
    boxes, cls, conf = parse_result(res, scale_x=w / small_w, scale_y=h / small_h)
    ann = draw_annotations(img.copy(), boxes, cls, conf)
    save_path = os.path.join(OUT_DIR, f"annotated_{image_name}")
    cv2.imwrite(save_path, ann)
    print(f"Saved -> {save_path}")
    if args.display:
        cv2.imshow("Detection", ann)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    sys.exit(0)

if args.live:
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit("Camera not accessible")
    prev_time = time.time()
    fps = 0.0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            now = time.time()
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)
            h, w = frame.shape[:2]
            small_w = 640
            small_h = max(1, int(small_w * h / w))
            small = cv2.resize(frame, (small_w, small_h))
            try:
                res = model(small, device=device, imgsz=small_w, conf=args.conf, verbose=False)[0]
            except Exception:
                res = None
            boxes, cls, conf = parse_result(res, scale_x=w / small_w, scale_y=h / small_h)
            out = draw_annotations(frame.copy(), boxes, cls, conf)
            cv2.putText(out, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            if args.display:
                cv2.imshow("Live Object Detection", out)
                k = cv2.waitKey(1) & 0xFF
                if k == 27 or k == ord("q"):
                    break
            else:
                if cv2.waitKey(1) & 0xFF == 27:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()