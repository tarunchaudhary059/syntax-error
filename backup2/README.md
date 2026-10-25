# Shinobi Jutsu — Multiplayer Battle Mode

A real-time 2-player webcam jutsu clash designed for two players on the same Wi-Fi network (or two browser windows for local testing).

---

## ⚡ Quick Start: How to Host & Play

### Step 1: Start the Server (Host Laptop)
In your terminal (macOS Terminal or Windows PowerShell) inside this project folder:

```bash
npm start
```
*(or `node server.js`)*

The server will automatically detect your local network IP and display:
```
============================================================
🔥 SHINOBI JUTSU MULTIPLAYER BATTLE SERVER ONLINE 🔥
============================================================
Host Laptop (HTTPS):  https://localhost:3000
Rival Laptop (HTTPS): https://<YOUR_IP>:3000
------------------------------------------------------------
Alternative Plain HTTP (Port 3001):
Host Laptop:          http://localhost:3001
Rival Laptop:         http://<YOUR_IP>:3001
============================================================
```

Keep this terminal window running.

---

### Step 2: Open the Game

#### On Laptop 1 (Host):
1. Open Google Chrome, Brave, or Safari and go to:
   ```
   https://localhost:3000
   ```
2. Click **Battle Mode** → Click **Enable Camera** (allow webcam permission).
3. Click **Create Room**. A 6-character room code will appear (e.g. `ABC123`).

#### On Laptop 2 (Rival):
Both laptops must be connected to the **same Wi-Fi network**.

1. On the rival's laptop, open Chrome and navigate to the address shown in your host terminal:
   ```
   https://<YOUR_HOST_IP>:3000
   ```
   *(e.g. `https://10.70.108.37:3000`)*
2. If Chrome displays a certificate warning, click **Advanced → Proceed to ... (unsafe)**.
3. Click **Battle Mode** → Click **Enable Camera** (allow webcam permission).
4. Enter the 6-character room code in the box and click **Join Room**.

---

### Step 3: Battle Rules & Controls

- **Aim**: Your index fingertip controls your red crosshair.
- **Head Target**: Face detection automatically locks onto your rival's head with a cyan dashed target box.
- **Strike**: Perform the hand sign sequence in order while aiming inside your rival's head zone:
  - **Fireball Jutsu** (`18 DMG`): **Horse** (`👌🏼`) → **Rat** (`👉🏼`) → **Tiger** (`🤙🏼`) (or key `1`)
  - **Chidori** (`25 DMG`): **Fist** (`✊🏼`) → **Dog** (`☝🏼`) → **Open Palm** (`✋🏼`) (or key `2`)
  - **Rasenshuriken** (`22 DMG`): **Peace** (`✌🏼`) → **Fist** (`✊🏼`) → **Open Palm** (`✋🏼`) (or key `3`)
  - **Hollow Purple** (`35 DMG`): **Index+Pinky** (`🤘🏼`) → **Fist** (`✊🏼`) → **Peace** (`✌🏼`) (or key `4`)
- When a hit lands, the anime jutsu animation plays on both screens, damage is registered, and the rival's chakra bar decreases.
- First shinobi to 0 HP loses. Click **Fight Again** to rematch instantly!

---

## 🛠️ Tips for Smooth Camera Access on Rival Laptop

Modern browsers (Chrome/Brave/Edge) require a secure origin for camera access across local IP addresses. Here are the two ways to handle it:

### Option A: Allow Insecure Origin Flag (Fastest & No Cert Setup Required)
If you don't want to install root certificates on the second laptop:
1. On the rival's laptop, open Chrome and type in the address bar:
   `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. Enable the flag and enter the host IP:
   `http://<YOUR_HOST_IP>:3001, https://<YOUR_HOST_IP>:3000`
3. Click **Relaunch** at the bottom.
4. Now the rival's browser will allow full camera and microphone access without warnings!

### Option B: Local SSL Certificates with mkcert
If using the bundled HTTPS certificates:
1. Trust the development root certificate on the rival machine, or generate local certs with `mkcert localhost 127.0.0.1 ::1 <YOUR_HOST_IP>`.
2. Connect to `https://<YOUR_HOST_IP>:3000`.

---

## 📁 Key Project Files
- `index.html` & `index .html`: Main menu featuring Battle Mode, Practice Mode, and How to Play.
- `battle.html`: Multiplayer arena with WebRTC peer video, MediaPipe hand crosshair, face detection hitbox, and jutsu effects.
- `practice.html`: Solo training ground for practicing 8 hand signs and 4 jutsu sequences.
- `server.js`: Dual-port Express & Socket.IO server handling rooms, signaling, and hit verification.
- `assets/`: Optimized anime jutsu videos (`sasuke.mp4`, `naruto.mp4`, `fireball_justsu.mp4`, `Hollow purple.mp4`, `naruto112.mp4`).
