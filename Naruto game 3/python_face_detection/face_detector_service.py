#!/usr/bin/env python3
"""
Shinobi Jutsu - High-Precision Face Detection Microservice
==========================================================
Detects face landmark points using Google MediaPipe Face Landmarker (478 points)
with OpenCV Haar Cascade fallback, and outputs the absolute SMALLEST enclosing
rectangle containing all face points.

WebSocket: ws://localhost:8765
"""

import os
import sys

# Prevent matplotlib from hanging on font cache creation in sandboxed/restricted environments
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
try:
    os.makedirs("/tmp/matplotlib_cache", exist_ok=True)
except Exception:
    pass

import asyncio
import base64
import json
import threading

DETECT_LOCK = threading.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_MODEL_PATH = os.path.join(BASE_DIR, "models", "face_landmarker.task")
CASCADE_PATH = os.path.join(BASE_DIR, "models", "haarcascade_frontalface_default.xml")

# Check required libraries
try:
    import numpy as np
    import cv2
    import websockets
except ImportError as e:
    print(f"❌ Missing required library: {e}")
    sys.exit(1)

# Initialize MediaPipe Face Landmarker (478 3D facial points)
LANDMARKER = None
MEDIAPIPE_AVAILABLE = False

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    if os.path.exists(TASK_MODEL_PATH):
        base_options = python.BaseOptions(model_asset_path=TASK_MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False
        )
        LANDMARKER = vision.FaceLandmarker.create_from_options(options)
        MEDIAPIPE_AVAILABLE = True
        print(f"✅ MediaPipe Face Landmarker initialized (478 face points model: {os.path.basename(TASK_MODEL_PATH)})")
    else:
        print(f"⚠️ MediaPipe model not found at: {TASK_MODEL_PATH}")
except Exception as e:
    print(f"⚠️ Could not initialize MediaPipe Face Landmarker: {e}")

# Initialize OpenCV Haar Cascade Detector as secondary fallback
FACE_CASCADE = None
if os.path.exists(CASCADE_PATH):
    try:
        FACE_CASCADE = cv2.CascadeClassifier(CASCADE_PATH)
        print(f"✅ OpenCV Haar Cascade initialized as fallback ({os.path.basename(CASCADE_PATH)})")
    except Exception as e:
        print(f"⚠️ Could not initialize CascadeClassifier: {e}")


def compute_smallest_enclosing_box(landmarks):
    """
    Given landmark points on the face, computes the mathematically smallest
    axis-aligned rectangle that encloses ALL the points.
    """
    all_x = [pt.x for pt in landmarks]
    all_y = [pt.y for pt in landmarks]

    min_x = max(0.0, float(min(all_x)))
    max_x = min(1.0, float(max(all_x)))
    min_y = max(0.0, float(min(all_y)))
    max_y = min(1.0, float(max(all_y)))

    return {
        "x": round(min_x, 5),
        "y": round(min_y, 5),
        "w": round(max(0.001, max_x - min_x), 5),
        "h": round(max(0.001, max_y - min_y), 5),
        "engine": "mediapipe_landmarker_478",
        "point_count": len(landmarks)
    }


def detect_face(image_bgr):
    """
    Extracts face points and returns the smallest rectangle enclosing all points.
    Uses MediaPipe Face Landmarker (478 points), falling back to OpenCV Cascade.
    """
    if image_bgr is None:
        return None
    h, w = image_bgr.shape[:2]
    if h < 10 or w < 10:
        return None

    # 1. Primary: MediaPipe Face Landmarker (478 landmark points)
    if MEDIAPIPE_AVAILABLE and LANDMARKER is not None:
        try:
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            with DETECT_LOCK:
                result = LANDMARKER.detect(mp_image)
            if result.face_landmarks and len(result.face_landmarks) > 0:
                landmarks = result.face_landmarks[0]
                return compute_smallest_enclosing_box(landmarks)
        except Exception as err:
            pass

    # 2. Secondary: OpenCV Haar Cascade
    if FACE_CASCADE is not None:
        try:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            with DETECT_LOCK:
                faces = FACE_CASCADE.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=(int(w * 0.15), int(h * 0.15))
                )
            if len(faces) > 0:
                # Pick largest detected face
                best = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = best
                return {
                    "x": round(float(fx / w), 5),
                    "y": round(float(fy / h), 5),
                    "w": round(float(fw / w), 5),
                    "h": round(float(fh / h), 5),
                    "engine": "opencv_cascade",
                    "point_count": 4
                }
        except Exception:
            pass

    # 3. Tertiary: Adaptive Skin Color Segmentation
    try:
        ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8), np.array([255, 173, 127], dtype=np.uint8))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(c)
            if area >= (h * w * 0.03):
                bx, by, bw, bh = cv2.boundingRect(c)
                if 0.7 <= (bh / max(1, bw)) <= 2.2:
                    return {
                        "x": round(float(bx / w), 5),
                        "y": round(float(by / h), 5),
                        "w": round(float(bw / w), 5),
                        "h": round(float(bh / h), 5),
                        "engine": "opencv_adaptive",
                        "point_count": 0
                    }
    except Exception:
        pass

    return None


class FaceBoxSmoother:
    """
    Smooths micro-jitter while tracking rapid head movements instantly.
    """
    def __init__(self, alpha=0.85):
        self.alpha = alpha
        self.box = None
        self.lost_count = 0

    def update(self, raw_box):
        if raw_box is None:
            self.lost_count += 1
            if self.lost_count > 6:
                self.box = None
            return self.box

        self.lost_count = 0
        if self.box is None:
            self.box = dict(raw_box)
            return self.box

        # If fast movement, track without lag
        dx = abs(raw_box["x"] - self.box["x"])
        dy = abs(raw_box["y"] - self.box["y"])
        a = 0.95 if (dx > 0.05 or dy > 0.05) else self.alpha

        self.box["x"] = round(a * raw_box["x"] + (1 - a) * self.box["x"], 5)
        self.box["y"] = round(a * raw_box["y"] + (1 - a) * self.box["y"], 5)
        self.box["w"] = round(a * raw_box["w"] + (1 - a) * self.box["w"], 5)
        self.box["h"] = round(a * raw_box["h"] + (1 - a) * self.box["h"], 5)
        self.box["engine"] = raw_box.get("engine", "mediapipe_landmarker_478")
        self.box["point_count"] = raw_box.get("point_count", 478)

        return self.box


async def handler(websocket):
    print(f"🔗 Browser connected: {websocket.remote_address}")
    smoother = FaceBoxSmoother(alpha=0.85)

    try:
        async for message in websocket:
            try:
                # Handle Data URLs ("data:image/jpeg;base64,...")
                if "," in message:
                    _, b64data = message.split(",", 1)
                else:
                    b64data = message

                img_bytes = base64.b64decode(b64data)
                np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is None:
                    await websocket.send(json.dumps({"detected": False}))
                    continue

                # Run detection in thread to keep event loop responsive
                raw_box = await asyncio.to_thread(detect_face, frame)
                box = smoother.update(raw_box)

                if box:
                    resp = {
                        "detected": True,
                        "box": box,
                        "points": box.get("point_count", 478),
                        "engine": box.get("engine", "mediapipe")
                    }
                else:
                    resp = {"detected": False}

                await websocket.send(json.dumps(resp))
            except Exception:
                continue
    except websockets.exceptions.ConnectionClosed:
        print("🔌 Browser disconnected.")
    except Exception as e:
        print(f"⚠️ Connection error: {e}")


async def main():
    host = "0.0.0.0"
    port = 8765
    print("\n" + "=" * 65)
    print("🔥 SHINOBI JUTSU - HIGH PRECISION FACE POINT DETECTOR ONLINE 🔥")
    print("=" * 65)
    print(f"📡 WebSocket Server: ws://{host}:{port}")
    print(f"🧠 Face Points Engine: Google MediaPipe Face Landmarker (478 points)")
    print(f"📐 Boundary: Smallest enclosing rectangle containing all points")
    print("=" * 65 + "\n")

    async with websockets.serve(handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Microservice stopped.")
