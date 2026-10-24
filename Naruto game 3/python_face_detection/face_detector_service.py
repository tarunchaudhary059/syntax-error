#!/usr/bin/env python3
"""
Shinobi Jutsu - Python Face Detection Microservice
=================================================
This Python service listens on WebSocket ws://localhost:8765.
It receives camera frames from the browser, runs face detection using
MediaPipe (with OpenCV fallback), and sends back normalized bounding
box coordinates so the browser highlights both players' faces with
the thin dotted red line.

Setup & Usage:
1. pip install -r requirements.txt
2. python3 face_detector_service.py
3. In browser console or battle.html, set: window.USE_PYTHON_DETECTOR = true;
"""

import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib_cache")
try:
    os.makedirs("/tmp/matplotlib_cache", exist_ok=True)
except Exception:
    pass

import asyncio
import base64
import json
import sys

# Verify dependencies before importing
missing_deps = []

try:
    import numpy as np
except ImportError:
    missing_deps.append("numpy")

try:
    import cv2
except ImportError:
    missing_deps.append("opencv-python")

try:
    import websockets
except ImportError:
    missing_deps.append("websockets")

if missing_deps:
    print("\n" + "=" * 62)
    print("❌ MISSING PYTHON DEPENDENCIES FOR FACE DETECTION SERVICE:")
    for dep in missing_deps:
        print(f"   • {dep}")
    print("\n💡 Easy Fix - run one of these options:")
    print("   1) Run the automatic launcher:")
    print("      bash start_python_service.sh")
    print("      (or 'npm run python-detector' from project root)")
    print("\n   2) Or manually install packages in your terminal:")
    print("      pip3 install -r requirements.txt")
    print("=" * 62 + "\n")
    sys.exit(1)

# Try initializing MediaPipe Face Mesh, with graceful fallback to BlazeFace / Haar Cascades
MEDIAPIPE_AVAILABLE = False
MEDIAPIPE_MESH_AVAILABLE = False
mp_face_mesh_detector = None
mp_face_detector = None

try:
    import mediapipe as mp
    try:
        mp_face_mesh = mp.solutions.face_mesh
        mp_face_mesh_detector = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        MEDIAPIPE_MESH_AVAILABLE = True
        print("✅ MediaPipe Face Mesh initialized (468 facial points detected for rectangular boundary).")
    except Exception as mesh_err:
        print(f"⚠️ FaceMesh unavailable, falling back to BlazeFace detection: {mesh_err}")

    mp_face_detection = mp.solutions.face_detection
    mp_face_detector = mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)
    MEDIAPIPE_AVAILABLE = True
    print("✅ MediaPipe Face Detection initialized successfully.")
except Exception as e:
    print(f"ℹ️ Note on MediaPipe Python: {e}")
    cascade_dir = getattr(cv2.data, 'haarcascades', '')
    cascade_path = os.path.join(cascade_dir, 'haarcascade_frontalface_default.xml') if cascade_dir else ''
    if cascade_path and os.path.exists(cascade_path):
        print("ℹ️ Using OpenCV frontal face cascade detector.")
        face_cascade = cv2.CascadeClassifier(cascade_path)
    else:
        face_cascade = None
        print("ℹ️ Using OpenCV color-based adaptive facial contour detector.")


def detect_face_skin(image_bgr):
    """
    Adaptive skin-color space face segmentation fallback.
    Requires no external model files and runs in ~1ms on CPU.
    """
    h, w = image_bgr.shape[:2]
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8), np.array([255, 173, 127], dtype=np.uint8))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    best_box = None
    max_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < (h * w * 0.02):
            continue
        bx, by, bw, bh = cv2.boundingRect(c)
        aspect = bh / max(1, bw)
        if 0.7 <= aspect <= 2.2 and area > max_area:
            max_area = area
            best_box = {
                "x": float(bx / w),
                "y": float(by / h),
                "w": float(bw / w),
                "h": float(bh / h),
                "engine": "opencv_adaptive"
            }
    return best_box


def detect_face(image_bgr):
    """
    Detects face in BGR image using MediaPipe Face Mesh.
    Captures all 468 facial points (jawline, cheeks, eyes, nose, forehead, chin)
    and computes the tight rectangular boundary enclosing all detected points.
    Returns normalized dict: {'x': x_min, 'y': y_min, 'w': width, 'h': height} in range [0, 1]
    or None if no face is detected.
    """
    h, w, _ = image_bgr.shape
    if h == 0 or w == 0:
        return None

    # 1. Primary: MediaPipe Face Mesh (extracts all 468 facial points)
    if MEDIAPIPE_MESH_AVAILABLE and mp_face_mesh_detector is not None:
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        results = mp_face_mesh_detector.process(image_rgb)
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            all_x = [pt.x for pt in landmarks]
            all_y = [pt.y for pt in landmarks]
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            pad_x = (max_x - min_x) * 0.04
            pad_y = (max_y - min_y) * 0.04
            box_x = float(max(0.0, min_x - pad_x))
            box_y = float(max(0.0, min_y - pad_y))
            box_w = float(min(1.0 - box_x, (max_x - min_x) + pad_x * 2))
            box_h = float(min(1.0 - box_y, (max_y - min_y) + pad_y * 2))
            return {
                "x": box_x,
                "y": box_y,
                "w": box_w,
                "h": box_h,
                "engine": "mediapipe_face_mesh",
                "point_count": len(landmarks)
            }
        return None

    # 2. Secondary fallback: MediaPipe BlazeFace detection
    if MEDIAPIPE_AVAILABLE and mp_face_detector is not None:
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        results = mp_face_detector.process(image_rgb)
        if results.detections:
            first_face = results.detections[0]
            box = first_face.location_data.relative_bounding_box
            return {
                "x": float(max(0.0, min(1.0, box.xmin))),
                "y": float(max(0.0, min(1.0, box.ymin))),
                "w": float(max(0.0, min(1.0, box.width))),
                "h": float(max(0.0, min(1.0, box.height))),
                "engine": "mediapipe_blazeface"
            }
        return None

    # 3. Tertiary fallback: OpenCV Haar Cascades
    if face_cascade is not None:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
        if len(faces) > 0:
            x, y, fw, fh = faces[0]
            return {
                "x": float(x / w),
                "y": float(y / h),
                "w": float(fw / w),
                "h": float(fh / h),
                "engine": "opencv_cascade"
            }

    # 4. Quaternary fallback: Adaptive color-based contour detector
    return detect_face_skin(image_bgr)


async def handler(websocket):
    print(f"🔗 Browser client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            try:
                # Handle base64 data URLs: "data:image/jpeg;base64,..."
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

                box = detect_face(frame)
                if box:
                    response = {"detected": True, "box": box}
                else:
                    response = {"detected": False}

                await websocket.send(json.dumps(response))
            except Exception as frame_err:
                # Keep loop alive even if one frame fails to decode
                continue
    except websockets.exceptions.ConnectionClosed:
        print("🔌 Client disconnected.")
    except Exception as e:
        print(f"⚠️ WebSocket error: {e}")


async def main():
    host = "localhost"
    port = 8765
    print("\n" + "=" * 60)
    print("🔥 SHINOBI JUTSU - PYTHON FACE DETECTION SERVICE ONLINE 🔥")
    print("=" * 60)
    print(f"📡 WebSocket Server listening on: ws://{host}:{port}")
    print("💡 To enable in battle mode:")
    print("   Open https://localhost:3000 in your browser, open console (F12),")
    print("   and type: window.USE_PYTHON_DETECTOR = true;")
    print("=" * 60 + "\n")

    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Python Face Detection Service stopped.")

