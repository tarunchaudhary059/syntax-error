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

import asyncio
import base64
import json
import numpy as np

# Try importing OpenCV
try:
    import cv2
except ImportError:
    print("❌ OpenCV not found. Please install it with: pip install opencv-python")
    raise

# Try importing MediaPipe, with graceful fallback to OpenCV Haar Cascades
MEDIAPIPE_AVAILABLE = False
try:
    import mediapipe as mp
    mp_face_detection = mp.solutions.face_detection
    mp_detector = mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)
    MEDIAPIPE_AVAILABLE = True
    print("✅ MediaPipe Python Face Detector initialized successfully.")
except Exception as e:
    print(f"⚠️ MediaPipe Python import note: {e}")
    print("ℹ️ Falling back to OpenCV frontal face cascade detector.")
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)

# Try importing websockets
try:
    import websockets
except ImportError:
    print("❌ websockets library not found. Please install with: pip install websockets")
    raise


def detect_face(image_bgr):
    """
    Detects face in BGR image.
    Returns normalized dict: {'x': x_min, 'y': y_min, 'w': width, 'h': height} in range [0, 1]
    or None if no face is detected.
    """
    h, w, _ = image_bgr.shape
    if h == 0 or w == 0:
        return None

    if MEDIAPIPE_AVAILABLE:
        # Convert BGR to RGB for MediaPipe
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        results = mp_detector.process(image_rgb)
        if results.detections:
            # Pick first face detection
            first_face = results.detections[0]
            box = first_face.location_data.relative_bounding_box
            return {
                "x": float(max(0.0, min(1.0, box.xmin))),
                "y": float(max(0.0, min(1.0, box.ymin))),
                "w": float(max(0.0, min(1.0, box.width))),
                "h": float(max(0.0, min(1.0, box.height))),
                "engine": "mediapipe"
            }
        return None
    else:
        # OpenCV Haar Cascade fallback
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
        return None


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

