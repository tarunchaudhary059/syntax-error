# Python Face Detection Microservice for Shinobi Jutsu

This folder contains the Python face detection module that connects to the **Shinobi Jutsu Battle Mode** in your web browser.

---

## ⚡ How It Works

1. **Client Web Video**: The browser captures camera frames from the local webcam.
2. **WebSocket Bridge**: The browser sends video frames to `ws://localhost:8765`.
3. **Python MediaPipe Detection**: Python receives the image, executes MediaPipe's `FaceDetection` model (or OpenCV Haar Cascades if MediaPipe is not installed), and computes the face bounding box `{ x, y, w, h }`.
4. **Thin Dotted Red Line Highlight**: The browser receives the coordinates and instantly renders the **thin dotted red line** around the player's face.

---

## 🚀 Setup & Usage Instructions

### Step 1: Install Dependencies
In a terminal, navigate to this folder and install dependencies:

```bash
cd "Naruto game 3/python_face_detection"
pip install -r requirements.txt
```

### Step 2: Start the Python Service
```bash
python3 face_detector_service.py
```
You will see:
```
🔥 SHINOBI JUTSU - PYTHON FACE DETECTION SERVICE ONLINE 🔥
📡 WebSocket Server listening on: ws://localhost:8765
```

### Step 3: Enable Python Detection in Battle Mode
1. Open the game in your browser (`https://localhost:3000`).
2. Go to **Battle Mode**.
3. Open your browser Developer Console (`F12` or `Cmd + Option + I` on Mac).
4. Type:
   ```javascript
   window.USE_PYTHON_DETECTOR = true;
   ```
5. You will see in console: `🐍 Connected to Python Face Detection Service`. Your face will now be tracked by your Python module!

*(By default, if this is set to `false`, the game uses browser-native WebAssembly MediaPipe which requires no Python process and runs at 60 FPS directly on the GPU).*

