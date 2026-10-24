/* =====================================================
   Training Ground Hand Signs & Jutsu Sequences
   ===================================================== */
const SIGNS = [
  { id: "peace",       name: "Peace",         desc: "Index & middle fingers", emoji: "✌🏼" },
  { id: "fist",        name: "Fist",          desc: "All fingers closed",     emoji: "✊🏼" },
  { id: "open",        name: "Open Palm",     desc: "All fingers extended",   emoji: "✋🏼" },
  { id: "dog",         name: "Dog",           desc: "Index finger extended",  emoji: "☝🏼" },
  { id: "horse",       name: "Horse",         desc: "Middle, ring & pinky",   emoji: "👌🏼" },
  { id: "rat",         name: "Rat",           desc: "Index finger & thumb",   emoji: '<span style="display:inline-block;transform:rotate(-90deg);line-height:1;">👉🏼</span>' },
  { id: "tiger",       name: "Tiger",         desc: "Pinky finger extended",  emoji: '<span style="display:inline-block;transform:rotate(-90deg);line-height:1;">🤙🏼</span>' },
  { id: "purpleStart", name: "Index + Pinky", desc: "Index & pinky extended", emoji: "🤘🏼" }
];

const JUTSU = [
  { name: "Rasenshuriken", seq: ["peace", "fist", "open"] },
  { name: "Chidori",       seq: ["fist", "dog", "open"] },
  { name: "Fireball Jutsu", seq: ["horse", "rat", "tiger"] },
  { name: "Hollow Purple",  seq: ["purpleStart", "fist", "peace"] }
];

/* ---------- Build guide content ---------- */
const signOf = id => SIGNS.find(s => s.id === id) || { name: id, emoji: "" };

document.getElementById("signGrid").innerHTML = SIGNS.map(s => `
  <div class="sign">
    <div class="k" aria-hidden="true">${s.emoji}</div>
    <div class="info">
      <div class="n">${s.name}</div>
      <div class="j">${s.desc}</div>
    </div>
  </div>`).join("");

document.getElementById("jutsuList").innerHTML = JUTSU.map(j => `
  <article>
    <h3>${j.name}</h3>
    <div class="seq">${j.seq.map(id => {
      const s = signOf(id);
      return `<span class="chip"><span class="chip-emoji">${s.emoji}</span> ${s.name}</span>`;
    }).join('<span class="arrow" aria-hidden="true">›</span>')}</div>
  </article>`).join("");

/* ---------- Dialog + tabs ---------- */
const dlg = document.getElementById("howDialog");
document.getElementById("howBtn").addEventListener("click", () => dlg.showModal());
document.getElementById("closeBtn").addEventListener("click", () => dlg.close());
dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });

const tabs = [...document.querySelectorAll('[role="tab"]')];
tabs.forEach(tab => tab.addEventListener("click", () => {
  tabs.forEach(t => {
    const on = t === tab;
    t.setAttribute("aria-selected", on);
    document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
  });
}));


/* ---------- Video: hide if the file is missing; sound toggle ---------- */
const video = document.getElementById("bgVideo");
video.querySelector("source").addEventListener("error", () => video.remove());
const soundBtn = document.getElementById("soundBtn");
soundBtn.addEventListener("click", () => {
  const on = video.muted;               // currently muted -> turn sound on
  video.muted = !on;
  soundBtn.setAttribute("aria-pressed", on);
  soundBtn.textContent = on ? "Sound on" : "Sound off";
  if (on) video.play().catch(() => {});
});
if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) video.pause();

/* ---------- Drifting embers / chakra sparks ---------- */
(() => {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.getElementById("embers"), ctx = c.getContext("2d");
  let w, h, parts = [];
  const resize = () => { w = c.width = innerWidth; h = c.height = innerHeight; };
  addEventListener("resize", resize); resize();
  const make = () => ({
    x: Math.random() * w, y: h + 10,
    r: Math.random() * 2.2 + .6,
    vy: -(Math.random() * .9 + .35),
    vx: (Math.random() - .5) * .4,
    hue: Math.random() < .75 ? "255,140,40" : "94,200,255",
    a: Math.random() * .6 + .3
  });
  for (let i = 0; i < 70; i++) { const p = make(); p.y = Math.random() * h; parts.push(p); }
  (function tick() {
    ctx.clearRect(0, 0, w, h);
    for (const p of parts) {
      p.x += p.vx + Math.sin(p.y / 60) * .25; p.y += p.vy;
      if (p.y < -10) Object.assign(p, make());
      ctx.beginPath();
      ctx.fillStyle = `rgba(${p.hue},${p.a})`;
      ctx.shadowColor = `rgba(${p.hue},.9)`; ctx.shadowBlur = 8;
      ctx.arc(p.x, p.y, p.r, 0, 6.283); ctx.fill();
    }
    requestAnimationFrame(tick);
  })();
})();