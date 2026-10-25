const express = require('express');
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const os = require('os');
const { Server } = require('socket.io');

const app = express();
const certDir = path.join(__dirname, 'certs');
const keyPath = path.join(certDir, 'server-key.pem');
const certPath = path.join(certDir, 'server.pem');
const useHttps = fs.existsSync(keyPath) && fs.existsSync(certPath);
const server = useHttps
  ? https.createServer({ key: fs.readFileSync(keyPath), cert: fs.readFileSync(certPath) }, app)
  : http.createServer(app);
const io = new Server(server, { maxHttpBufferSize: 1e5, cors: { origin: false } });
let httpServer = null;
if (useHttps) {
  httpServer = http.createServer(app);
  io.attach(httpServer);
}
const PORT = Number(process.env.PORT || 3000);
const rooms = new Map(); // code -> { players: Set(socketId), health: Map(socketId, health), over: boolean }
const socketRoom = new Map();
const lastGestureAt = new Map();
const lastAimAt = new Map();
const lastAttackAt = new Map();
const lastTypeAttackAt = new Map();
const DAMAGE = { fireball: 18, chidori: 25, rasenshuriken: 22, hollowPurple: 35, narutoRush: 20 };
const COOLDOWNS = { fireball: 5000, rasenshuriken: 6500, chidori: 7500, hollowPurple: 10000, narutoRush: 6000 };
const MAX_HEALTH = 250;

app.get('/', (_req, res) => {
  const indexFile = fs.existsSync(path.join(__dirname, 'index.html'))
    ? path.join(__dirname, 'index.html')
    : path.join(__dirname, 'index .html');
  res.sendFile(indexFile);
});
app.use(express.static(__dirname, { extensions: ['html'] }));
app.get('/health', (_req, res) => res.json({ ok: true, rooms: rooms.size, https: useHttps }));
function makeCode() {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code;
  do { code = Array.from(crypto.randomBytes(6), b => alphabet[b % alphabet.length]).join(''); }
  while (rooms.has(code));
  return code;
}
function snapshot(code) {
  const room = rooms.get(code);
  if (!room) return;
  const health = {};
  for (const id of room.players) health[id] = room.health.get(id) ?? MAX_HEALTH;
  const scores = {};
  for (const id of room.players) scores[id] = (room.scores && room.scores.get(id)) ?? 0;
  io.to(code).emit('battle-state', {
    health,
    maxHealth: MAX_HEALTH,
    scores,
    currentRound: room.currentRound || 1,
    totalRounds: room.totalRounds || 3,
    roundOver: Boolean(room.roundOver),
    over: room.over
  });
}
function leaveRoom(socket) {
  const code = socketRoom.get(socket.id);
  if (!code) return;
  const room = rooms.get(code);
  if (room) {
    room.players.delete(socket.id);
    room.health.delete(socket.id);
    if (room.scores) room.scores.delete(socket.id);
    if (room.roundTimer) clearTimeout(room.roundTimer);

    // If battle was live and opponent is still connected, declare them winner
    if (!room.over && room.players.size > 0) {
      room.over = true;
      const winnerId = [...room.players][0];
      io.to(code).emit('battle-over', {
        winner: winnerId,
        loser: socket.id,
        reason: 'disconnect',
        scores: Object.fromEntries(room.scores || []),
        totalRounds: room.totalRounds || 3
      });
    } else {
      socket.to(code).emit('room-error', { message: 'Your opponent left the room.' });
    }

    if (room.players.size === 0) rooms.delete(code);
    else snapshot(code);
  }
  socketRoom.delete(socket.id);
  socket.leave(code);
}
function joinExisting(socket, code) {
  const room = rooms.get(code);
  if (!room) return socket.emit('room-error', { message: 'Room not found. Check the code or create a new room.' });
  if (room.players.has(socket.id)) return;
  if (room.players.size >= 2) return socket.emit('room-error', { message: 'That room already has two players.' });
  room.players.add(socket.id);
  room.health.set(socket.id, MAX_HEALTH);
  if (!room.scores) room.scores = new Map();
  room.scores.set(socket.id, 0);
  socketRoom.set(socket.id, code);
  socket.join(code);
  socket.emit('room-joined', { roomCode: code, playerNumber: room.players.size, totalRounds: room.totalRounds || 3, maxHealth: MAX_HEALTH });
  socket.to(code).emit('player-joined', { playerNumber: 2 });
  if (room.players.size === 2) snapshot(code);
}

io.on('connection', socket => {
  socket.on('create-room', payload => {
    leaveRoom(socket);
    const code = makeCode();
    const totalRounds = Math.max(1, Math.min(15, parseInt(payload?.totalRounds) || 3));
    rooms.set(code, {
      players: new Set([socket.id]),
      health: new Map([[socket.id, MAX_HEALTH]]),
      scores: new Map([[socket.id, 0]]),
      totalRounds,
      currentRound: 1,
      roundOver: false,
      over: false,
      roundTimer: null
    });
    socketRoom.set(socket.id, code);
    socket.join(code);
    socket.emit('room-created', { roomCode: code, maxHealth: MAX_HEALTH, totalRounds });
  });
  socket.on('join-room', payload => {
    const code = String(payload?.roomCode || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6);
    if (!/^[A-Z0-9]{6}$/.test(code)) return socket.emit('room-error', { message: 'Room code must be six characters.' });
    leaveRoom(socket);
    joinExisting(socket, code);
  });

  // WebRTC media stays peer-to-peer; the server only forwards signaling messages.
  for (const eventName of ['webrtc-offer', 'webrtc-answer', 'webrtc-ice']) {
    socket.on(eventName, payload => {
      const code = socketRoom.get(socket.id);
      if (!code || !rooms.has(code) || !payload || typeof payload !== 'object') return;
      const field = eventName === 'webrtc-ice' ? 'candidate' : 'description';
      if (payload[field] && typeof payload[field] === 'object') socket.to(code).emit(eventName, { [field]: payload[field] });
    });
  }
  socket.on('aim-position', payload => {
    const code = socketRoom.get(socket.id);
    if (!code || !rooms.has(code) || !payload || typeof payload !== 'object') return;
    if (payload.visible !== true) { socket.to(code).emit('opponent-aim-position', { visible: false }); return; }
    const now = Date.now();
    if (now - (lastAimAt.get(socket.id) || 0) < 35) return;
    lastAimAt.set(socket.id, now);
    const x = Number.isFinite(payload.x) ? Math.max(0, Math.min(1, payload.x)) : 0.5;
    const y = Number.isFinite(payload.y) ? Math.max(0, Math.min(1, payload.y)) : 0.5;
    socket.to(code).emit('opponent-aim-position', { x, y, visible: true, charged: payload.charged === true });
  });

  socket.on('player-charged', payload => {
    const code = socketRoom.get(socket.id);
    if (!code || !rooms.has(code)) return;
    socket.to(code).emit('opponent-charged', { charged: Boolean(payload?.charged) });
  });

  socket.on('head-position', payload => {
    const code = socketRoom.get(socket.id);
    if (!code || !rooms.has(code) || !payload || typeof payload !== 'object') return;
    if (payload.visible !== true) { socket.to(code).emit('opponent-head-position', { visible: false }); return; }
    const now = Date.now();
    if (now - (lastAimAt.get(socket.id + '_head') || 0) < 30) return;
    lastAimAt.set(socket.id + '_head', now);
    socket.to(code).emit('opponent-head-position', {
      x: Number(payload.x) || 0,
      y: Number(payload.y) || 0,
      w: Number(payload.w) || 0,
      h: Number(payload.h) || 0,
      visible: true
    });
  });

  socket.on('gesture-state', payload => {
    const code = socketRoom.get(socket.id);
    if (!code) return;
    const now = Date.now();
    if (now - (lastGestureAt.get(socket.id) || 0) < 100) return;
    lastGestureAt.set(socket.id, now);
    const allowed = new Set(['open', 'fist', 'peace', 'dog', 'horse', 'rat', 'tiger', 'purpleStart', 'OPEN', 'PEACE', 'FIST', 'ONE', 'THREE']);
    const g = payload && allowed.has(payload.gesture) ? payload.gesture : 'OTHER';
    socket.to(code).emit('opponent-gesture-state', { gesture: g });
  });
  socket.on('attack', payload => {
    const code = socketRoom.get(socket.id);
    const room = rooms.get(code);
    if (!room || room.over || room.players.size !== 2 || !payload) return;
    const type = String(payload.type || '');
    if (!(type in DAMAGE)) return;
    const now = Date.now();
    const cd = COOLDOWNS[type] || 5000;
    const atkKey = `${socket.id}_${type}`;
    const lastUsed = lastTypeAttackAt.get(atkKey) || 0;
    if (now - lastUsed < (cd - 350)) return;
    if (now - (lastAttackAt.get(socket.id) || 0) < 450) return;
    lastAttackAt.set(socket.id, now);
    lastTypeAttackAt.set(atkKey, now);
    const x = Number.isFinite(payload.x) ? Math.max(0, Math.min(1, payload.x)) : 0.5;
    const y = Number.isFinite(payload.y) ? Math.max(0, Math.min(1, payload.y)) : 0.5;
    // Always show the attack effect to the opponent, but only apply damage on a head hit.
    socket.to(code).emit('opponent-attack', { type, x, y, hit: payload.hit === true, damage: DAMAGE[type] });
    if (payload.hit === true) {
      const targetId = [...room.players].find(id => id !== socket.id);
      if (!targetId) return;
      if (room.roundOver || room.over) return;
      const health = Math.max(0, (room.health.get(targetId) ?? MAX_HEALTH) - DAMAGE[type]);
      room.health.set(targetId, health);
      io.to(code).emit('battle-log', { attacker: socket.id, target: targetId, type, damage: DAMAGE[type], hit: true, health, x, y });
      snapshot(code);
      if (health === 0) {
        room.roundOver = true;
        const currentWinnerScore = ((room.scores && room.scores.get(socket.id)) || 0) + 1;
        if (room.scores) room.scores.set(socket.id, currentWinnerScore);
        const scoresObj = Object.fromEntries(room.scores || new Map());
        const neededWins = Math.ceil(room.totalRounds / 2);

        if (currentWinnerScore >= neededWins || room.currentRound >= room.totalRounds) {
          room.over = true;
          io.to(code).emit('battle-over', {
            winner: socket.id,
            loser: targetId,
            reason: 'knockout',
            scores: scoresObj,
            totalRounds: room.totalRounds
          });
        } else {
          io.to(code).emit('round-over', {
            roundWinner: socket.id,
            scores: scoresObj,
            currentRound: room.currentRound,
            totalRounds: room.totalRounds,
            waitSeconds: 5
          });

          room.roundTimer = setTimeout(() => {
            if (!rooms.has(code) || room.over) return;
            room.currentRound++;
            room.roundOver = false;
            for (const id of room.players) {
              room.health.set(id, MAX_HEALTH);
              for (const k of lastTypeAttackAt.keys()) {
                if (k.startsWith(id + '_')) lastTypeAttackAt.delete(k);
              }
            }
            io.to(code).emit('round-started', {
              currentRound: room.currentRound,
              totalRounds: room.totalRounds,
              scores: Object.fromEntries(room.scores || new Map()),
              maxHealth: MAX_HEALTH
            });
            snapshot(code);
          }, 5000);
        }
      }
    } else {
      socket.emit('battle-log', { attacker: socket.id, type, hit: false, x, y });
    }
  });
  socket.on('forfeit', () => {
    const code = socketRoom.get(socket.id);
    const room = rooms.get(code);
    if (!room || room.over || !room.players.has(socket.id)) return;
    room.over = true;
    if (room.roundTimer) clearTimeout(room.roundTimer);
    const rivalId = [...room.players].find(id => id !== socket.id);
    io.to(code).emit('battle-over', {
      winner: rivalId,
      loser: socket.id,
      reason: 'forfeit',
      scores: Object.fromEntries(room.scores || new Map()),
      totalRounds: room.totalRounds || 3
    });
  });
  socket.on('rematch', () => {
    const code = socketRoom.get(socket.id), room = rooms.get(code);
    if (!room || room.players.size !== 2) return;
    if (room.roundTimer) clearTimeout(room.roundTimer);
    room.over = false;
    room.roundOver = false;
    room.currentRound = 1;
    for (const id of room.players) {
      room.health.set(id, MAX_HEALTH);
      if (room.scores) room.scores.set(id, 0);
      for (const k of lastTypeAttackAt.keys()) {
        if (k.startsWith(id + '_')) lastTypeAttackAt.delete(k);
      }
    }
    io.to(code).emit('rematch-started', {
      currentRound: 1,
      totalRounds: room.totalRounds || 3,
      scores: Object.fromEntries(room.scores || new Map()),
      maxHealth: MAX_HEALTH
    });
    snapshot(code);
  });
  socket.on('disconnect', () => {
    leaveRoom(socket);
    lastGestureAt.delete(socket.id);
    lastAimAt.delete(socket.id);
    lastAttackAt.delete(socket.id);
    for (const k of lastTypeAttackAt.keys()) {
      if (k.startsWith(socket.id + '_')) lastTypeAttackAt.delete(k);
    }
  });
});

function getLocalIpv4() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return null;
}

server.listen(PORT, '0.0.0.0', () => {
  const protocol = useHttps ? 'https' : 'http';
  const localIp = getLocalIpv4();

  if (httpServer) {
    httpServer.listen(PORT + 1, '0.0.0.0', () => {});
  }

  console.log(`\n============================================================`);
  console.log(`🔥 SHINOBI JUTSU MULTIPLAYER BATTLE SERVER ONLINE 🔥`);
  console.log(`============================================================`);
  console.log(`Host MacBook:         ${protocol}://localhost:${PORT}`);
  if (localIp) {
    console.log(`Friend MacBook (LAN): ${protocol}://${localIp}:${PORT}`);
  }
  console.log(`------------------------------------------------------------`);
  console.log(`🌐 CANNOT CONNECT? (Campus/Hostel Wi-Fi AP Isolation):`);
  console.log(`Most university/hostel Wi-Fi networks block direct Mac-to-Mac links.`);
  console.log(`To get a universal HTTPS link that works on ANY network with full`);
  console.log(`webcam access, open a new Terminal window in this folder and run:`);
  console.log(`\n👉 npm run tunnel\n`);
  console.log(`(Or: ssh -p 443 -R0:localhost:${PORT} a.pinggy.io)`);
  console.log(`This will give you a public https://... link to share with your friend.`);
  console.log(`============================================================\n`);
});
