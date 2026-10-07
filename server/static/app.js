/**
 * ROYAL ARENA ESPORTS // CLASH ROYALE CLIENT ENGINE
 * Features:
 * - Hardware-accelerated Canvas Particle & Projectile FX Engine
 * - Floating Combat Text & Dynamic Damage Numbers
 * - High-Fidelity Procedural Web Audio Synthesis (zero external asset latency)
 * - Screen Shake, Death Poofs, and Dynamic Attack Animations
 * - Real-time WebSocket Match Sync, Knockout Tournament Tree & Multi-Laptop JSON Sync
 */

// Global Match & Application State
let currentMatchState = null;
let currentTourneyState = null;
let ws = null;
let soundEnabled = true;
let masterVolume = 0.75;
let audioCtx = null;
let masterGain = null;
let lastLogCount = 0;
let victoryModalDismissed = false;
let lastMatchStatus = null;
let processedEventCount = 0;
let lastProcessedRound = -1;

let toastTimer = null;
function showToast(message, type = 'info') {
  let toast = document.getElementById('clashToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'clashToast';
    toast.className = 'clash-toast';
    document.body.appendChild(toast);
  }
  let icon = 'ℹ️';
  if (type === 'success') icon = '✓';
  else if (type === 'warning') icon = '⚠️';
  else if (type === 'error') icon = '✕';

  toast.innerHTML = `<span class="toast-icon">${icon}</span> <span>${message}</span>`;
  toast.className = `clash-toast show ${type}`;

  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove('show');
  }, 2200);
}

// Card Catalog Definition for Client
const CARD_PROTOS = {
  knight: { name: 'Knight', elixir: 3, icon: '🗡️', type: 'Melee Brawler', rarity: 'common', category: 'troop', hp: 850, dmg: 95, speedStr: 'Medium (8.0 tiles/s)', targetStr: 'Ground & Air (Nearest)', desc: 'Tough frontline melee fighter. Solid damage and excellent counter-push potential.', synergies: 'Archers, Musketeer', counters: 'Giant, Hog Rider' },
  archers: { name: 'Archers', elixir: 3, icon: '🏹', type: 'Sharpshooter Pair', rarity: 'common', category: 'swarm', hp: 280, dmg: 55, speedStr: 'Medium (8.0 tiles/s)', targetStr: 'Ground & Air (Nearest)', desc: 'Pair of sharpshooters. Snipes ground and air threats from safe distance.', synergies: 'Knight, Giant', counters: 'P.E.K.K.A, Baby Dragon' },
  giant: { name: 'Giant', elixir: 5, icon: '🗿', type: 'Siege Tank', rarity: 'rare', category: 'tank', hp: 2200, dmg: 110, speedStr: 'Slow (5.0 tiles/s)', targetStr: 'Buildings Only', desc: 'Colossal siege tank that marches straight for enemy towers, ignoring distractions.', synergies: 'Musketeer, Baby Dragon', counters: 'Princess Towers' },
  musketeer: { name: 'Musketeer', elixir: 4, icon: '🔫', type: 'Precision Sniper', rarity: 'rare', category: 'troop', hp: 420, dmg: 120, speedStr: 'Medium (7.5 tiles/s)', targetStr: 'Ground & Air (Nearest)', desc: 'Long-range boomstick specialist. Shreds incoming tanks from behind friendly lines.', synergies: 'Giant, Pekka', counters: 'Baby Dragon, Hog Rider' },
  hog_rider: { name: 'Hog Rider', elixir: 4, icon: '🐗', type: 'Tower Rusher', rarity: 'rare', category: 'troop', hp: 750, dmg: 120, speedStr: 'Very Fast (13.0 tiles/s)', targetStr: 'Buildings Only', desc: 'Fast hammer-wielding tower rusher. Charges the bridge and chips the crown tower!', synergies: 'Goblin Barrel, Fireball', counters: 'Crown Towers' },
  skeletons: { name: 'Skeleton Army', elixir: 2, icon: '💀', type: 'Distraction Swarm', rarity: 'epic', category: 'swarm', hp: 65, dmg: 50, speedStr: 'Fast (11.0 tiles/s)', targetStr: 'Ground & Air (Nearest)', desc: 'Bony distraction swarm. Overwhelms single-target tanks like the Giant and Knight.', synergies: 'Hog Rider, Pekka', counters: 'P.E.K.K.A, Giant, Hog Rider' },
  baby_dragon: { name: 'Baby Dragon', elixir: 4, icon: '🐲', type: 'Air Splash', rarity: 'epic', category: 'air', hp: 800, dmg: 85, speedStr: 'Fast (9.5 tiles/s)', targetStr: 'Ground & Air (Splash)', desc: 'Flying splash-damage dragon. Spits fireballs that vaporize swarms.', synergies: 'P.E.K.K.A, Giant', counters: 'Skeleton Army, Archers' },
  pekka: { name: 'P.E.K.K.A', elixir: 7, icon: '🤖', type: 'Heavy Armor Titan', rarity: 'legendary', category: 'tank', hp: 2600, dmg: 420, speedStr: 'Slow (4.5 tiles/s)', targetStr: 'Ground & Air (Nearest)', desc: 'Heavily armored mechanical beast. Obliterates tanks with catastrophic sword strikes.', synergies: 'Baby Dragon, Musketeer', counters: 'Giant, Hog Rider, Knight' },
  fireball: { name: 'Fireball', elixir: 4, icon: '🔥', type: 'Direct Spell', rarity: 'rare', category: 'spell', hp: '-', dmg: 360, speedStr: 'Instant Spell', targetStr: 'Area Splash Radius 15', desc: 'Direct spell blast. Incinerates enemy troop clusters or finishes off damaged towers.', synergies: 'Hog Rider, Goblin Barrel', counters: 'Clustered Swarms & Support' },
  goblin_barrel: { name: 'Goblin Barrel', elixir: 3, icon: '🪵', type: 'Tower Flank Spell', rarity: 'epic', category: 'spell', hp: 100, dmg: 60, speedStr: 'Fast Flying (11.0 tiles/s)', targetStr: 'Ground & Air (Nearest)', desc: 'Direct tower assault. Launches 3 dagger goblins right onto the enemy Princess Tower!', synergies: 'Hog Rider, Skeleton Army', counters: 'Crown Towers' }
};

// ==============================================================
// 1. PROCEDURAL WEB AUDIO SYNTHESIS ENGINE
// ==============================================================
function initAudio() {
  if (!audioCtx) {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    if (AudioCtxClass) {
      audioCtx = new AudioCtxClass();
      masterGain = audioCtx.createGain();
      masterGain.gain.setValueAtTime(masterVolume, audioCtx.currentTime);
      masterGain.connect(audioCtx.destination);
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
}

function setMasterVolume(val) {
  masterVolume = Math.max(0, Math.min(1, parseFloat(val)));
  if (masterGain && audioCtx) {
    masterGain.gain.setValueAtTime(masterVolume, audioCtx.currentTime);
  }
}

function playClashSound(type, panX = 50) {
  if (!soundEnabled) return;
  try {
    initAudio();
    if (!audioCtx || !masterGain) return;

    const now = audioCtx.currentTime;
    let targetBus = masterGain;

    if (audioCtx.createStereoPanner) {
      const panner = audioCtx.createStereoPanner();
      const panVal = Math.max(-1.0, Math.min(1.0, (panX - 50.0) / 50.0));
      panner.pan.setValueAtTime(panVal, now);
      panner.connect(masterGain);
      targetBus = panner;
    }

    // 1. Sword Melee Clash
    if (type === 'sword') {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(1400, now);
      osc.frequency.exponentialRampToValueAtTime(120, now + 0.12);

      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

      osc.connect(gain);
      gain.connect(targetBus);
      osc.start(now);
      osc.stop(now + 0.12);

      // Noise burst for steel impact
      createNoiseBurst(now, 0.08, 0.12, 1800);
    }
    // 2. Cannon Detonation / Explosion
    else if (type === 'cannon' || type === 'explosion') {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(110, now);
      osc.frequency.exponentialRampToValueAtTime(35, now + 0.38);

      gain.gain.setValueAtTime(0.35, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.38);

      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(now);
      osc.stop(now + 0.38);

      createNoiseBurst(now, 0.28, 0.22, 450);
    }
    // 3. Fireball Whistle & Blast
    else if (type === 'fireball') {
      createNoiseBurst(now, 0.24, 0.25, 600);
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(600, now);
      osc.frequency.exponentialRampToValueAtTime(80, now + 0.3);

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);

      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(now);
      osc.stop(now + 0.3);
    }
    // 4. Arrow Shot
    else if (type === 'arrow') {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(1800, now);
      osc.frequency.exponentialRampToValueAtTime(400, now + 0.09);

      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.09);

      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(now);
      osc.stop(now + 0.09);
    }
    // 5. Troop Deploy Chime
    else if (type === 'deploy') {
      const notes = [392.00, 523.25]; // G4, C5
      notes.forEach((freq, idx) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now + idx * 0.07);

        gain.gain.setValueAtTime(0.15, now + idx * 0.07);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.07 + 0.18);

        osc.connect(gain);
        gain.connect(masterGain);
        osc.start(now + idx * 0.07);
        osc.stop(now + idx * 0.07 + 0.18);
      });
    }
    // 6. Crown Horn / Royal Fanfare
    else if (type === 'crown' || type === 'horn') {
      const chord = [293.66, 369.99, 440.00, 587.33]; // D, F#, A, D
      chord.forEach((freq, idx) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now + idx * 0.09);

        gain.gain.setValueAtTime(0.2, now + idx * 0.09);
        gain.gain.linearRampToValueAtTime(0.001, now + idx * 0.09 + 0.55);

        osc.connect(gain);
        gain.connect(masterGain);
        osc.start(now + idx * 0.09);
        osc.stop(now + idx * 0.09 + 0.55);
      });
    }
    // 7. Double Elixir Charge
    else if (type === 'double_elixir') {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.45);

      gain.gain.setValueAtTime(0.2, now);
      gain.gain.linearRampToValueAtTime(0.01, now + 0.45);

      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(now);
      osc.stop(now + 0.45);
    }
  } catch (e) {
    // Autoplay policy or context error
  }
}

function createNoiseBurst(startTime, duration, volume, filterFreq) {
  if (!audioCtx || !masterGain) return;
  const bufferSize = audioCtx.sampleRate * duration;
  const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
  const output = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) {
    output[i] = Math.random() * 2 - 1;
  }

  const whiteNoise = audioCtx.createBufferSource();
  whiteNoise.buffer = buffer;

  const filter = audioCtx.createBiquadFilter();
  filter.type = 'lowpass';
  filter.frequency.setValueAtTime(filterFreq, startTime);

  const gain = audioCtx.createGain();
  gain.gain.setValueAtTime(volume, startTime);
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

  whiteNoise.connect(filter);
  filter.connect(gain);
  gain.connect(masterGain);

  whiteNoise.start(startTime);
  whiteNoise.stop(startTime + duration);
}

// ==============================================================
// 2. HARDWARE-ACCELERATED FX CANVAS & PARTICLE ENGINE
// ==============================================================
class ArenaFxEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas ? canvas.getContext('2d') : null;
    this.damageNumbers = [];
    this.projectiles = [];
    this.particles = [];
    this.animFrameId = null;
    this.lastTime = performance.now();

    if (this.canvas) {
      this.resize();
      window.addEventListener('resize', () => this.resize());
      this.startLoop();
    }
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    this.width = rect.width;
    this.height = rect.height;
    this.canvas.width = rect.width * (window.devicePixelRatio || 1);
    this.canvas.height = rect.height * (window.devicePixelRatio || 1);
    if (this.ctx) {
      this.ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    }
  }

  startLoop() {
    const loop = (timestamp) => {
      const dt = (timestamp - this.lastTime) / 1000.0;
      this.lastTime = timestamp;
      this.update(dt);
      this.render();
      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  // Spawn Floating Damage Text
  addDamageText(xPct, yPct, amount, isCrit = false) {
    const px = (xPct / 100.0) * this.width;
    const py = (yPct / 100.0) * this.height;
    this.damageNumbers.push({
      x: px,
      y: py,
      text: `-${amount}`,
      color: isCrit ? '#f59e0b' : '#ef4444',
      size: isCrit ? 18 : 13,
      alpha: 1.0,
      life: 0.9,
      maxLife: 0.9,
      vy: -35 - Math.random() * 15,
      vx: (Math.random() - 0.5) * 10
    });
  }

  // Spawn Flying Projectile
  addProjectile(kind, fromXPct, fromYPct, toXPct, toYPct, damage) {
    const startX = (fromXPct / 100.0) * this.width;
    const startY = (fromYPct / 100.0) * this.height;
    const endX = (toXPct / 100.0) * this.width;
    const endY = (toYPct / 100.0) * this.height;

    this.projectiles.push({
      kind,
      startX, startY,
      endX, endY,
      x: startX, y: startY,
      progress: 0.0,
      speed: kind === 'fireball' ? 1.4 : (kind === 'barrel' ? 1.1 : 2.5),
      damage,
      trail: []
    });
  }

  // Spawn Particle Cloud (Death Poofs / Explosions)
  addExplosion(x, y, color = '#f59e0b', count = 18) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 30 + Math.random() * 80;
      this.particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        color,
        radius: 2 + Math.random() * 4,
        alpha: 1.0,
        life: 0.5 + Math.random() * 0.3,
        maxLife: 0.8
      });
    }
  }

  addElixirPoof(xPct, yPct) {
    const px = (xPct / 100.0) * this.width;
    const py = (yPct / 100.0) * this.height;
    for (let i = 0; i < 10; i++) {
      this.particles.push({
        x: px + (Math.random() - 0.5) * 16,
        y: py + (Math.random() - 0.5) * 16,
        vx: (Math.random() - 0.5) * 20,
        vy: -25 - Math.random() * 25,
        color: '#d946ef',
        radius: 3 + Math.random() * 3,
        alpha: 0.85,
        life: 0.6,
        maxLife: 0.6
      });
    }
  }

  update(dt) {
    // 1. Damage Numbers
    for (let i = this.damageNumbers.length - 1; i >= 0; i--) {
      const d = this.damageNumbers[i];
      d.life -= dt;
      d.x += d.vx * dt;
      d.y += d.vy * dt;
      d.alpha = Math.max(0, d.life / d.maxLife);
      if (d.life <= 0) this.damageNumbers.splice(i, 1);
    }

    // 2. Projectiles
    for (let i = this.projectiles.length - 1; i >= 0; i--) {
      const p = this.projectiles[i];
      p.progress += p.speed * dt;
      const t = Math.min(1.0, p.progress);

      p.x = p.startX + (p.endX - p.startX) * t;
      // Arc height
      const arcHeight = p.kind === 'barrel' ? 80 : (p.kind === 'fireball' ? 35 : 0);
      p.y = p.startY + (p.endY - p.startY) * t - Math.sin(t * Math.PI) * arcHeight;

      // Add trail point
      p.trail.push({ x: p.x, y: p.y, alpha: 1.0 });
      if (p.trail.length > 8) p.trail.shift();

      if (p.progress >= 1.0) {
        // Projectile reached target!
        if (p.kind === 'fireball') {
          this.addExplosion(p.endX, p.endY, '#f97316', 24);
          triggerScreenShake(7);
          playClashSound('fireball');
        } else if (p.kind === 'barrel') {
          this.addExplosion(p.endX, p.endY, '#854d0e', 14);
          playClashSound('cannon');
        } else if (p.kind === 'cannon') {
          this.addExplosion(p.endX, p.endY, '#f59e0b', 16);
          triggerScreenShake(5);
        }
        this.projectiles.splice(i, 1);
      }
    }

    // 3. Particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const part = this.particles[i];
      part.life -= dt;
      part.x += part.vx * dt;
      part.y += part.vy * dt;
      part.alpha = Math.max(0, part.life / part.maxLife);
      if (part.life <= 0) this.particles.splice(i, 1);
    }
  }

  render() {
    if (!this.ctx) return;
    this.ctx.clearRect(0, 0, this.width, this.height);

    // 1. Render Projectiles
    this.projectiles.forEach(p => {
      // Trail
      this.ctx.save();
      for (let i = 0; i < p.trail.length; i++) {
        const tr = p.trail[i];
        this.ctx.beginPath();
        this.ctx.arc(tr.x, tr.y, (i + 1) * 0.8, 0, Math.PI * 2);
        this.ctx.fillStyle = p.kind === 'fireball' ? `rgba(249, 115, 22, ${i / p.trail.length * 0.6})` : `rgba(255, 255, 255, ${i / p.trail.length * 0.4})`;
        this.ctx.fill();
      }

      // Projectile Core
      this.ctx.beginPath();
      if (p.kind === 'fireball') {
        this.ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
        this.ctx.fillStyle = '#ea580c';
        this.ctx.shadowColor = '#f97316';
        this.ctx.shadowBlur = 12;
        this.ctx.fill();
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        this.ctx.fillStyle = '#fef08a';
        this.ctx.fill();
      } else if (p.kind === 'barrel') {
        this.ctx.arc(p.x, p.y, 7, 0, Math.PI * 2);
        this.ctx.fillStyle = '#854d0e';
        this.ctx.fill();
      } else if (p.kind === 'cannon') {
        this.ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
        this.ctx.fillStyle = '#1e293b';
        this.ctx.fill();
      } else {
        // Arrow
        this.ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        this.ctx.fillStyle = '#f8fafc';
        this.ctx.fill();
      }
      this.ctx.restore();
    });

    // 2. Render Particles
    this.particles.forEach(part => {
      this.ctx.save();
      this.ctx.globalAlpha = part.alpha;
      this.ctx.beginPath();
      this.ctx.arc(part.x, part.y, part.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = part.color;
      this.ctx.fill();
      this.ctx.restore();
    });

    // 3. Render Damage Numbers
    this.damageNumbers.forEach(d => {
      this.ctx.save();
      this.ctx.globalAlpha = d.alpha;
      this.ctx.font = `800 ${d.size}px 'JetBrains Mono', sans-serif`;
      this.ctx.textAlign = 'center';
      // Shadow / Outline
      this.ctx.strokeStyle = 'rgba(0, 0, 0, 0.9)';
      this.ctx.lineWidth = 3;
      this.ctx.strokeText(d.text, d.x, d.y);
      this.ctx.fillStyle = d.color;
      this.ctx.fillText(d.text, d.x, d.y);
      this.ctx.restore();
    });
  }
}

let fxEngine = null;

function triggerScreenShake(intensity = 6) {
  const pitch = document.getElementById('clashPitch');
  if (!pitch) return;
  const originalTransform = pitch.style.transform || '';
  const subtleAmount = Math.min(2.5, intensity * 0.25);
  const xOffset = (Math.random() - 0.5) * subtleAmount;
  const yOffset = (Math.random() - 0.5) * subtleAmount;
  pitch.style.transform = `translate(${xOffset}px, ${yOffset}px)`;
  setTimeout(() => {
    pitch.style.transform = originalTransform;
  }, 100);
}

// ==============================================================
// 3. WEBSOCKET SYNC & ARENA STATE MANAGEMENT
// ==============================================================
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/arena`;
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('[Royal Arena] WebSocket connected to match orchestrator.');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.status) {
        renderState(data);
      }
      if (data.tournament) {
        currentTourneyState = data.tournament;
        renderBracket(data.tournament);
      }
    } catch (e) {
      console.error('[Royal Arena] State parse error:', e);
    }
  };

  ws.onclose = () => {
    setTimeout(connectWebSocket, 2000);
  };
}

function renderElixirPips(containerId, elixirVal) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const pipsCount = Math.min(10, Math.max(0, Math.floor(elixirVal || 0)));
  let html = '';
  for (let i = 1; i <= 10; i++) {
    html += `<span class="pip ${i <= pipsCount ? 'active' : ''}"></span>`;
  }
  container.innerHTML = html;
}

function updateDebugPanel(state) {
  const panel = document.getElementById('debugPanel');
  if (!panel || panel.style.display === 'none') return;

  setElText('debugTickRound', state.round_number || 0);
  setElText('debugElapsedTime', `${(state.elapsed_seconds || 0).toFixed(1)}s`);
  const troops = state.troops || state.units || [];
  setElText('debugUnitCount', troops.length);
  setElText('debugEngineStatus', (state.status || 'STANDBY').toUpperCase());

  const tbody = document.getElementById('debugTroopsTbody');
  if (tbody) {
    if (troops.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-muted">No active units deployed.</td></tr>';
    } else {
      tbody.innerHTML = troops.map(t => `
        <tr class="${t.team === 'red' ? 'red-troop' : 'blue-troop'}">
          <td><strong>${(t.team || '').toUpperCase()}</strong></td>
          <td>${t.name || t.card_id}</td>
          <td>${t.lane || 'mid'}</td>
          <td>${Number(t.x || 0).toFixed(1)}</td>
          <td>${Number(t.y || 0).toFixed(1)}</td>
          <td>${t.hp}/${t.max_hp}</td>
        </tr>
      `).join('');
    }
  }

  const dump = document.getElementById('debugJsonDump');
  if (dump) {
    dump.textContent = JSON.stringify(state, null, 2);
  }
}

function renderState(state) {
  currentMatchState = state;

  const red = state.players ? state.players.red : (state.kingdoms ? state.kingdoms.red : {});
  const blue = state.players ? state.players.blue : (state.kingdoms ? state.kingdoms.blue : {});

  // 1. Status & Timer Display
  const elStatus = document.getElementById('matchStatusBadge');
  if (elStatus) {
    let statusText = state.status.toUpperCase();
    if (state.is_overtime) statusText = 'OVERTIME';
    else if (state.is_double_elixir) statusText = '2X ELIXIR';
    elStatus.textContent = statusText;
    elStatus.className = `match-status-badge ${state.status}`;
  }

  // Esports Top HUD Matchup Names
  setElText('hudRedName', (red.name || 'RED STRATEGY').toUpperCase());
  setElText('hudBlueName', (blue.name || 'BLUE STRATEGY').toUpperCase());

  // Esports Live Status Badge
  const elLiveBadge = document.getElementById('hudLiveBadge');
  const elLiveText = document.getElementById('hudLiveText');
  if (elLiveText) {
    if (state.status === 'running') {
      elLiveText.textContent = state.is_overtime ? 'OVERTIME' : (state.is_double_elixir ? '2X ELIXIR' : 'LIVE MATCH');
      if (elLiveBadge) elLiveBadge.className = 'hud-live-badge live';
    } else if (state.status === 'paused') {
      elLiveText.textContent = 'MATCH PAUSED';
      if (elLiveBadge) elLiveBadge.className = 'hud-live-badge paused';
    } else if (state.status === 'finished') {
      elLiveText.textContent = 'MATCH CONCLUDED';
      if (elLiveBadge) elLiveBadge.className = 'hud-live-badge finished';
    } else {
      elLiveText.textContent = 'STANDBY';
      if (elLiveBadge) elLiveBadge.className = 'hud-live-badge standby';
    }
  }

  const elTimer = document.getElementById('matchTimer');
  const remainingSeconds = Math.max(0, state.max_duration_seconds - state.elapsed_seconds);
  const mins = Math.floor(remainingSeconds / 60).toString();
  const secs = Math.floor(remainingSeconds % 60).toString().padStart(2, '0');
  const timerStr = `${mins}:${secs}`;

  if (elTimer) {
    elTimer.textContent = `${mins.padStart(2, '0')}:${secs}`;
    if (remainingSeconds <= 30 && state.status === 'running') {
      elTimer.style.color = '#ef4444';
    } else {
      elTimer.style.color = '#fff';
    }
  }

  // Pitch Overlay Timer & Trainer Meta (Matching Reference Image)
  setElText('pitchTimerText', timerStr);
  setElText('pitchRedName', (red.name || 'TRAINER EARL').toUpperCase());
  setElText('pitchRedSub', red.author || 'Royal Trainers');

  // 2. Crown Scoreboard & Side Crowns
  const elCrownScoreBadge = document.getElementById('crownScoreBadge');
  setElText('scoreRedCrowns', red.crowns || 0);
  setElText('scoreBlueCrowns', blue.crowns || 0);
  setElText('sideCrownRedNum', red.crowns || 0);
  setElText('sideCrownBlueNum', blue.crowns || 0);

  const elRedCrown = document.getElementById('redCrownDisplay');
  if (elRedCrown) {
    elRedCrown.innerHTML = `<i data-lucide="crown"></i> ${red.crowns || 0}`;
  }
  const elBlueCrown = document.getElementById('blueCrownDisplay');
  if (elBlueCrown) {
    elBlueCrown.innerHTML = `<i data-lucide="crown"></i> ${blue.crowns || 0}`;
  }
  if (window.lucide) {
    lucide.createIcons();
  }

  // 3. Dynamic Strategy Standing Pills
  const redCrowns = red.crowns || 0;
  const blueCrowns = blue.crowns || 0;
  let redStatus = '● LIVE';
  let blueStatus = '● LIVE';
  let redStatusClass = 'status-live';
  let blueStatusClass = 'status-live';

  if (state.status === 'finished') {
    if (state.winner === 'red') {
      redStatus = '👑 WINNER'; redStatusClass = 'status-winning';
      blueStatus = '💀 DEFEATED'; blueStatusClass = 'status-losing';
    } else if (state.winner === 'blue') {
      redStatus = '💀 DEFEATED'; redStatusClass = 'status-losing';
      blueStatus = '👑 WINNER'; blueStatusClass = 'status-winning';
    } else {
      redStatus = '⚖️ DRAW'; blueStatus = '⚖️ DRAW';
    }
  } else if (state.status === 'running') {
    if (redCrowns > blueCrowns) {
      redStatus = '▲ ADVANTAGE'; redStatusClass = 'status-winning';
      blueStatus = '▼ DEFENDING'; blueStatusClass = 'status-losing';
    } else if (blueCrowns > redCrowns) {
      redStatus = '▼ DEFENDING'; redStatusClass = 'status-losing';
      blueStatus = '▲ ADVANTAGE'; blueStatusClass = 'status-winning';
    } else {
      const redHp = (red.towers?.king?.hp || 0) + (red.towers?.left_princess?.hp || 0) + (red.towers?.right_princess?.hp || 0);
      const blueHp = (blue.towers?.king?.hp || 0) + (blue.towers?.left_princess?.hp || 0) + (blue.towers?.right_princess?.hp || 0);
      if (redHp > blueHp + 200) {
        redStatus = '▲ PRESSURE'; redStatusClass = 'status-winning';
        blueStatus = '▼ REGROUPING'; blueStatusClass = 'status-losing';
      } else if (blueHp > redHp + 200) {
        redStatus = '▼ REGROUPING'; redStatusClass = 'status-losing';
        blueStatus = '▲ PRESSURE'; blueStatusClass = 'status-winning';
      } else {
        redStatus = '● CONTESTED'; redStatusClass = 'status-live';
        blueStatus = '● CONTESTED'; blueStatusClass = 'status-live';
      }
    }
  }

  const redStatusEl = document.getElementById('redStrategyStatus');
  const redStatusText = document.getElementById('redStatusText');
  if (redStatusEl && redStatusText) {
    redStatusText.textContent = redStatus;
    redStatusEl.className = `strategy-status-pill ${redStatusClass}`;
  }

  const blueStatusEl = document.getElementById('blueStrategyStatus');
  const blueStatusText = document.getElementById('blueStatusText');
  if (blueStatusEl && blueStatusText) {
    blueStatusText.textContent = blueStatus;
    blueStatusEl.className = `strategy-status-pill ${blueStatusClass}`;
  }

  // 4. Double Elixir Banner Pill
  const elDoublePill = document.getElementById('doubleElixirBadge');
  if (elDoublePill) {
    if (state.is_double_elixir) {
      elDoublePill.textContent = '⚡ 2X DOUBLE ELIXIR!';
      elDoublePill.classList.add('active');
    } else {
      elDoublePill.textContent = '1X REGULATION ELIXIR';
      elDoublePill.classList.remove('active');
    }
  }

  // 5. Spectator Control Buttons
  const btnStart = document.getElementById('btnStart');
  const btnPause = document.getElementById('btnPause');
  if (btnStart && btnPause) {
    if (state.status === 'running') {
      btnStart.disabled = true;
      btnPause.disabled = false;
      btnPause.innerHTML = '<i data-lucide="pause"></i> PAUSE';
    } else if (state.status === 'paused') {
      btnStart.disabled = true;
      btnPause.disabled = false;
      btnPause.innerHTML = '<i data-lucide="play"></i> RESUME';
    } else {
      btnStart.disabled = false;
      btnPause.disabled = true;
      btnPause.innerHTML = '<i data-lucide="pause"></i> PAUSE';
    }
    if (window.lucide) window.lucide.createIcons();
  }

  // Sync Speed Multiplier Buttons
  if (state.speed_multiplier !== undefined && state.speed_multiplier !== null) {
    updateSpeedButtons(state.speed_multiplier);
  }

  // 6. Red Player Telemetry
  setElText('redName', red.name || 'Red Kingdom');
  setElText('redAuthor', red.author || 'Commander');
  setElText('redElixirNum', `${Number(red.elixir || 0).toFixed(1)} / 10`);
  const redElixirPct = Math.max(0, Math.min(100, ((red.elixir || 0) / 10.0) * 100));
  const elRedElixirBar = document.getElementById('redElixirBar');
  if (elRedElixirBar) elRedElixirBar.style.width = `${redElixirPct}%`;

  // Render 10 Pips for Red
  renderElixirPips('redElixirPips', red.elixir || 0);

  if (red.towers) {
    renderTowerEntity('red', 'king', red.towers.king);
    renderTowerEntity('red', 'left', red.towers.left_princess);
    renderTowerEntity('red', 'right', red.towers.right_princess);

    setElText('redKingHp', `${red.towers.king.hp} / ${red.towers.king.max_hp}`);
    setElText('redLeftHp', `${red.towers.left_princess.hp} / ${red.towers.left_princess.max_hp}`);
    setElText('redRightHp', `${red.towers.right_princess.hp} / ${red.towers.right_princess.max_hp}`);

    setBarWidth('redKingBar', (red.towers.king.hp / red.towers.king.max_hp) * 100);
    setBarWidth('redLeftBar', (red.towers.left_princess.hp / red.towers.left_princess.max_hp) * 100);
    setBarWidth('redRightBar', (red.towers.right_princess.hp / red.towers.right_princess.max_hp) * 100);
  }

  setElText('redThought', `"${red.last_thought || 'Reading opponent card cadence...'}"`);
  setElText('redTaunt', red.last_taunt ? `"${red.last_taunt}"` : '');
  renderHandCards('red', red.deck || [], red.elixir || 0);

  // 7. Blue Player Telemetry
  setElText('blueName', blue.name || 'Blue Kingdom');
  setElText('blueAuthor', blue.author || 'Commander');
  setElText('blueElixirNum', `${Number(blue.elixir || 0).toFixed(1)} / 10`);
  const blueElixirPct = Math.max(0, Math.min(100, ((blue.elixir || 0) / 10.0) * 100));
  const elBlueElixirBar = document.getElementById('blueElixirBar');
  if (elBlueElixirBar) elBlueElixirBar.style.width = `${blueElixirPct}%`;

  // Render 10 Pips for Blue
  renderElixirPips('blueElixirPips', blue.elixir || 0);

  if (blue.towers) {
    renderTowerEntity('blue', 'king', blue.towers.king);
    renderTowerEntity('blue', 'left', blue.towers.left_princess);
    renderTowerEntity('blue', 'right', blue.towers.right_princess);

    setElText('blueKingHp', `${blue.towers.king.hp} / ${blue.towers.king.max_hp}`);
    setElText('blueLeftHp', `${blue.towers.left_princess.hp} / ${blue.towers.left_princess.max_hp}`);
    setElText('blueRightHp', `${blue.towers.right_princess.hp} / ${blue.towers.right_princess.max_hp}`);

    setBarWidth('blueKingBar', (blue.towers.king.hp / blue.towers.king.max_hp) * 100);
    setBarWidth('blueLeftBar', (blue.towers.left_princess.hp / blue.towers.left_princess.max_hp) * 100);
    setBarWidth('blueRightBar', (blue.towers.right_princess.hp / blue.towers.right_princess.max_hp) * 100);
  }

  setElText('blueThought', `"${blue.last_thought || 'Saving elixir for counter-push...'}"`);
  setElText('blueTaunt', blue.last_taunt ? `"${blue.last_taunt}"` : '');
  renderHandCards('blue', blue.deck || [], blue.elixir || 0);

  // 8. Derive Recent Action Tickers
  const logs = state.combat_log || [];
  let redLastAct = red.last_action || null;
  let blueLastAct = blue.last_action || null;
  if (!redLastAct || !blueLastAct) {
    for (let i = logs.length - 1; i >= 0; i--) {
      const entry = logs[i];
      const text = entry.text || '';
      if (!redLastAct && (text.includes(red.name || 'Red') || text.includes('North Bastion') || text.toLowerCase().includes('red'))) {
        redLastAct = text;
      }
      if (!blueLastAct && (text.includes(blue.name || 'Blue') || text.includes('South Fortress') || text.toLowerCase().includes('blue'))) {
        blueLastAct = text;
      }
      if (redLastAct && blueLastAct) break;
    }
  }
  setElText('redLastActionText', redLastAct || 'Executing tactical doctrine');
  setElText('blueLastActionText', blueLastAct || 'Executing tactical doctrine');

  // 9. Render Active Troops on Pitch
  renderTroops(state.troops || state.units || []);

  // 10. Process Simulation Combat & Particle Events
  if (state.events && state.round_number !== lastProcessedRound) {
    processCombatEvents(state.events);
    lastProcessedRound = state.round_number;
  }

  // 11. Caster Combat Feed
  renderFeed(state.combat_log || []);

  // 12. Update Debug Inspector if active
  updateDebugPanel(state);

  // 13. Match Header
  const activeHeader = document.getElementById('arenaMatchHeader');
  if (activeHeader) {
    if (state.active_match_id) {
      activeHeader.textContent = `TOURNAMENT MATCH: ${state.active_match_id.toUpperCase()}`;
    } else {
      activeHeader.textContent = `${red.name || 'Red'} VS ${blue.name || 'Blue'}`;
    }
  }

  // 14. Victory Modal
  if (lastMatchStatus && lastMatchStatus !== 'finished' && state.status === 'finished' && state.winner && !victoryModalDismissed) {
    showVictoryModal(state);
  }
  lastMatchStatus = state.status;
}

function processCombatEvents(events) {
  if (!events || !Array.isArray(events) || !fxEngine) return;

  events.forEach(ev => {
    const eventX = ev.from_x !== undefined ? ev.from_x : (ev.x !== undefined ? ev.x : 50);
    if (ev.type === 'damage') {
      fxEngine.addDamageText(ev.x, ev.y, ev.amount, ev.is_crit);
    } else if (ev.type === 'projectile') {
      fxEngine.addProjectile(ev.kind, ev.from_x, ev.from_y, ev.to_x, ev.to_y, ev.damage);
      if (ev.kind === 'fireball') playClashSound('fireball', eventX);
      else if (ev.kind === 'cannon') playClashSound('cannon', eventX);
      else playClashSound('arrow', eventX);
    } else if (ev.type === 'tower_attack') {
      fxEngine.addProjectile(ev.kind || 'arrow', ev.from_x, ev.from_y, ev.to_x, ev.to_y, ev.damage);
      if (ev.kind === 'cannon') playClashSound('cannon', eventX);
      else playClashSound('arrow', eventX);
    } else if (ev.type === 'death') {
      fxEngine.addElixirPoof(ev.x, ev.y);
    } else if (ev.type === 'deploy') {
      playClashSound('deploy', eventX);
    } else if (ev.type === 'tower_destroyed') {
      triggerScreenShake(12);
      playClashSound('cannon', eventX);
      playClashSound('crown', eventX);
    } else if (ev.type === 'shake') {
      triggerScreenShake(ev.intensity || 6);
    } else if (ev.type === 'double_elixir') {
      playClashSound('double_elixir');
    } else if (ev.type === 'victory') {
      playClashSound('crown');
    }
  });
}

function setBarWidth(id, pct) {
  const el = document.getElementById(id);
  if (el) el.style.width = `${Math.max(0, Math.min(100, pct))}%`;
}

function renderTowerEntity(team, towerKey, towerData) {
  const el = document.getElementById(`tower_${team}_${towerKey}`);
  const tag = document.getElementById(`tag_${team}_${towerKey}`);
  const fill = document.getElementById(`fill_${team}_${towerKey}`);
  const cannon = document.getElementById(`cannon_${team}_${towerKey}`);
  if (!el || !towerData) return;

  const hpPct = Math.max(0, Math.min(100, (towerData.hp / towerData.max_hp) * 100));
  if (fill) fill.style.width = `${hpPct}%`;

  if (cannon) {
    if (towerData.active || towerData.hp < towerData.max_hp) {
      cannon.classList.add('cannon-active');
    } else {
      cannon.classList.remove('cannon-active');
    }
  }

  if (towerData.destroyed) {
    el.classList.add('destroyed');
    if (tag) tag.textContent = '0';
  } else {
    el.classList.remove('destroyed');
    if (tag) tag.textContent = `${towerData.hp}`;
  }
}

function renderHandCards(team, deckList, currentElixir) {
  const container = document.getElementById(`${team}HandCards`);
  const trayContainer = (team === 'blue') ? document.getElementById('trayHandSlots') : null;

  if (container && deckList) {
    container.innerHTML = '';
    deckList.forEach(cardId => {
      const proto = CARD_PROTOS[cardId] || { name: cardId, elixir: 3, icon: '⚔️', rarity: 'common' };
      const isAffordable = currentElixir >= proto.elixir;
      const cardEl = document.createElement('div');
      cardEl.className = `hand-card-3d rarity-${proto.rarity || 'common'} ${isAffordable ? 'affordable' : 'unaffordable'}`;
      cardEl.title = `${proto.name} (💧 ${proto.elixir} Elixir) - ${proto.type}`;
      cardEl.innerHTML = `
        <div class="hand-card-elixir">💧${proto.elixir}</div>
        <div class="hand-card-icon">${proto.icon}</div>
        <div class="hand-card-name">${proto.name}</div>
        <div class="hand-card-level">Lvl 11</div>
        ${!isAffordable ? `<div class="elixir-lock-overlay"></div>` : ''}
      `;
      container.appendChild(cardEl);
    });
  }
}

function renderTroops(troopsList) {
  const layer = document.getElementById('troopsLayer');
  if (!layer) return;

  layer.innerHTML = '';
  troopsList.forEach(t => {
    const proto = CARD_PROTOS[t.card_id] || { icon: '⚔️', category: 'troop' };
    const hpPct = Math.max(0, Math.min(100, (t.hp / t.max_hp) * 100));
    const isAir = proto.category === 'air';
    const isBoss = t.card_id === 'pekka' || t.card_id === 'giant';

    const avatar = document.createElement('div');
    avatar.className = `troop-avatar-3d ${isAir ? 'air-unit' : ''} ${isBoss ? 'boss-unit' : ''}`;
    avatar.style.left = `${t.x}%`;
    avatar.style.top = `${t.y}%`;

    avatar.innerHTML = `
      <div class="troop-shadow"></div>
      <div class="troop-badge troop-team-${t.team} card-${t.card_id}" title="${t.name} (${t.hp}/${t.max_hp} HP)">
        <span class="troop-icon">${proto.icon}</span>
        <span class="troop-lvl">11</span>
      </div>
      <div class="troop-hp-bar">
        <div class="troop-hp-fill ${t.team === 'red' ? 'fill-red-hp' : 'fill-blue-hp'}" style="width: ${hpPct}%;"></div>
      </div>
    `;
    layer.appendChild(avatar);
  });
}

// Caster Combat Feed Ticker
function renderFeed(logs) {
  const feedEl = document.getElementById('combatFeed');
  const badgeEl = document.getElementById('feedCounterBadge');
  if (badgeEl && logs) {
    badgeEl.textContent = `${logs.length} EVENTS RECORDED`;
  }
  if (!feedEl || !logs) return;

  if (logs.length !== lastLogCount) {
    feedEl.innerHTML = '';
    logs.forEach(entry => {
      const msg = document.createElement('div');
      msg.className = `feed-msg ${entry.category || 'combat'}`;
      msg.textContent = `[${entry.time || 0}s] ${entry.icon || '⚔️'} ${entry.text}`;
      feedEl.appendChild(msg);
    });
    feedEl.scrollTop = feedEl.scrollHeight;
    lastLogCount = logs.length;
  }
}

// Victory Modal Presentation
function showVictoryModal(state) {
  const modal = document.getElementById('victoryModal');
  const crest = document.getElementById('modalWinnerCrest');
  const title = document.getElementById('modalWinnerTitle');
  const reason = document.getElementById('modalWinnerReason');
  const redCrownsEl = document.getElementById('modalRedCrowns');
  const blueCrownsEl = document.getElementById('modalBlueCrowns');

  if (!modal) return;

  const winner = state.winner;
  const isRed = winner === 'red';
  const isDraw = winner === 'draw';

  const red = state.players ? state.players.red : {};
  const blue = state.players ? state.players.blue : {};

  crest.textContent = isDraw ? '⚖️' : '👑';
  title.textContent = isDraw ? 'DRAW // SUDDEN DEATH' : `${(state.players[winner] || {}).name || winner.toUpperCase()} VICTORIOUS!`;
  title.style.color = isDraw ? '#facc15' : (isRed ? '#ef4444' : '#0ea5e9');
  reason.textContent = state.win_reason || 'Match concluded via autonomous strategy execution.';

  setElText('modalRedName', (red.name || 'RED STRATEGY').toUpperCase());
  setElText('modalBlueName', (blue.name || 'BLUE STRATEGY').toUpperCase());

  if (redCrownsEl) redCrownsEl.textContent = `🔴 ${red.crowns || 0} CROWNS`;
  if (blueCrownsEl) blueCrownsEl.textContent = `🔵 ${blue.crowns || 0} CROWNS`;

  // Head-to-Head Battle Statistics Calculation
  const redKingHp = (red.towers && red.towers.king) ? red.towers.king.hp : 0;
  const blueKingHp = (blue.towers && blue.towers.king) ? blue.towers.king.hp : 0;
  const redPrincessHp = ((red.towers?.left_princess?.hp || 0) + (red.towers?.right_princess?.hp || 0));
  const bluePrincessHp = ((blue.towers?.left_princess?.hp || 0) + (blue.towers?.right_princess?.hp || 0));
  
  const totalBaseHp = 2400 + 1400 * 2; // 5200 HP total
  const redDmg = Math.max(0, totalBaseHp - (blueKingHp + bluePrincessHp));
  const blueDmg = Math.max(0, totalBaseHp - (redKingHp + redPrincessHp));

  setElText('statRedDmg', `${redDmg} HP`);
  setElText('statBlueDmg', `${blueDmg} HP`);

  let redCards = 0;
  let blueCards = 0;
  const logs = state.combat_log || [];
  logs.forEach(l => {
    const txt = l.text || '';
    if (txt.includes('deployed') || txt.includes('cast')) {
      if (txt.includes(red.name || 'Red') || txt.toLowerCase().includes('red')) redCards++;
      else if (txt.includes(blue.name || 'Blue') || txt.toLowerCase().includes('blue')) blueCards++;
    }
  });
  setElText('statRedCards', redCards || (red.cards_played || 12));
  setElText('statBlueCards', blueCards || (blue.cards_played || 11));

  const elixirRate = state.is_double_elixir ? 0.7 : 0.35;
  const estElixir = Math.min(100, Math.floor((state.elapsed_seconds || 60) * elixirRate));
  setElText('statRedElixir', `${red.total_elixir_spent || estElixir}💧`);
  setElText('statBlueElixir', `${blue.total_elixir_spent || estElixir}💧`);

  setElText('statRedKingHp', `${redKingHp} HP`);
  setElText('statBlueKingHp', `${blueKingHp} HP`);

  modal.classList.add('active');
  playClashSound('crown');
}

// Knockout Tournament Bracket Rendering
function renderBracket(tourney) {
  const treeEl = document.getElementById('bracketTree');
  if (!treeEl || !tourney || !tourney.matches) return;

  currentTourneyState = tourney;
  treeEl.innerHTML = '';

  const matches = tourney.matches;
  const matchKeys = Object.keys(matches);

  const qfMatches = matchKeys.filter(k => k.startsWith('qf_')).map(k => matches[k]);
  const semiMatches = matchKeys.filter(k => k.startsWith('semi_')).map(k => matches[k]);
  const finalMatches = matchKeys.filter(k => k.startsWith('final_')).map(k => matches[k]);

  if (qfMatches.length > 0) treeEl.appendChild(createRoundColumn('QUARTERFINALS', qfMatches));
  if (semiMatches.length > 0) treeEl.appendChild(createRoundColumn('SEMIFINALS', semiMatches));
  if (finalMatches.length > 0) treeEl.appendChild(createRoundColumn('🏆 GRAND CHAMPIONSHIP', finalMatches));

  if (tourney.champion) {
    const champCol = document.createElement('div');
    champCol.className = 'bracket-round-column champion-col';
    champCol.innerHTML = `
      <div class="round-col-title">👑 TOURNAMENT CHAMPION</div>
      <div class="tournament-match-card champion-card" style="border-color: #f59e0b; text-align: center; padding: 24px; box-shadow: 0 0 24px rgba(245, 158, 11, 0.4);">
        <div style="font-size: 40px; margin-bottom: 8px;">👑</div>
        <h3 style="color: #fbbf24; font-family: var(--font-serif); font-size: 18px; margin-bottom: 6px;">${tourney.champion}</h3>
        <p style="font-size: 11px; color: #10b981; font-family: var(--font-mono);">Knockout Champion Crowned!</p>
      </div>
    `;
    treeEl.appendChild(champCol);
  }
}

function createRoundColumn(title, matchArr) {
  const col = document.createElement('div');
  col.className = 'bracket-round-column';

  const titleEl = document.createElement('div');
  titleEl.className = 'round-col-title';
  titleEl.textContent = title;
  col.appendChild(titleEl);

  matchArr.forEach(m => {
    const card = document.createElement('div');
    card.className = `tournament-match-card ${m.status === 'in_progress' ? 'active' : ''}`;

    const isAWin = m.winner_file && m.winner_file === m.team_a_file;
    const isBWin = m.winner_file && m.winner_file === m.team_b_file;

    const teamAName = m.team_a_file ? m.team_a_file.replace('.md', '') : 'TBD';
    const teamBName = m.team_b_file ? m.team_b_file.replace('.md', '') : 'TBD';

    let actionButton = '';
    if (m.status === 'scheduled' && m.team_a_file && m.team_b_file) {
      actionButton = `<button class="btn-launch-match" onclick="launchBracketMatch('${m.match_id}')">⚔️ LAUNCH MATCH</button>`;
    } else if (m.status === 'in_progress') {
      actionButton = `<div style="font-family: var(--font-mono); font-size: 10px; color: #f59e0b; text-align: center; font-weight: 800;">⚡ IN PROGRESS</div>`;
    } else if (m.status === 'completed') {
      const redC = m.scorecard ? m.scorecard.red_crowns : 0;
      const blueC = m.scorecard ? m.scorecard.blue_crowns : 0;
      actionButton = `<div style="font-family: var(--font-mono); font-size: 12px; color: #34d399; text-align: center; font-weight: 800;">👑 ${redC} - ${blueC} 👑</div>`;
    }

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; font-size: 10px; color: #64748b; font-family: var(--font-mono);">
        <span>${m.round_name}</span>
        <span style="text-transform: uppercase;">${m.status}</span>
      </div>
      <div class="match-slot ${isAWin ? 'winner' : ''}">
        <span>🔴 ${teamAName}</span>
        <span>${isAWin ? '👑 WIN' : ''}</span>
      </div>
      <div class="match-slot ${isBWin ? 'winner' : ''}">
        <span>🔵 ${teamBName}</span>
        <span>${isBWin ? '👑 WIN' : ''}</span>
      </div>
      ${actionButton}
    `;
    col.appendChild(card);
  });

  return col;
}

window.launchBracketMatch = async function(matchId) {
  try {
    const res = await fetch('/api/tournament/launch_match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ match_id: matchId })
    });
    const data = await res.json();
    if (data.status === 'match_loaded') {
      switchToArena();
      playClashSound('crown');
      await fetch('/api/match/start', { method: 'POST' });
    }
  } catch (e) {
    alert('Failed to launch tournament match: ' + e);
  }
};

// Switch Views
function switchView(viewName) {
  const views = {
    lobby: document.getElementById('viewLobby'),
    arena: document.getElementById('viewArena'),
    bracket: document.getElementById('viewBracket'),
    rules: document.getElementById('viewRules')
  };

  const tabs = {
    lobby: document.getElementById('btnViewLobby'),
    arena: document.getElementById('btnViewArena'),
    bracket: document.getElementById('btnViewBracket'),
    rules: document.getElementById('btnViewRules')
  };

  Object.keys(views).forEach(k => {
    if (views[k]) {
      if (k === viewName) {
        views[k].style.display = (k === 'arena') ? 'grid' : 'flex';
        views[k].classList.add('active');
      } else {
        views[k].style.display = 'none';
        views[k].classList.remove('active');
      }
    }
    if (tabs[k]) {
      if (k === viewName) tabs[k].classList.add('active');
      else tabs[k].classList.remove('active');
    }
  });

  if (viewName === 'arena' && fxEngine) {
    setTimeout(() => fxEngine.resize(), 100);
  }
  if (viewName === 'bracket') fetchTournamentState();
  if (viewName === 'rules') renderCardsCatalog();

  if (window.lucide) {
    setTimeout(() => lucide.createIcons(), 20);
  }
}

function switchToArena() { switchView('arena'); }
function switchToBracket() { switchView('bracket'); }
function switchToLobby() { switchView('lobby'); }
function switchToRules() { switchView('rules'); }

// Global 3D State Variables
let card3dRenderer = null, card3dScene = null, card3dCamera = null, card3dControls = null, card3dMeshGroup = null, card3dAnimReq = null;
let currentInspectedCardId = null;
let arena3dRenderer = null, arena3dScene = null, arena3dCamera = null, arena3dControls = null, arena3dAnimReq = null;
let isArena3dAutoRotating = false;
let currentFilterType = 'all', currentFilterElixir = 'all', currentSearchQuery = '';

// Codex Sub-Nav Tab Switching
function setupCodexSubtabs() {
  const btnCompendium = document.getElementById('tabCompendium3D');
  const btnArena = document.getElementById('tabArenaRules3D');
  const panelCompendium = document.getElementById('subpanelCompendium');
  const panelArena = document.getElementById('subpanelArena');

  if (!btnCompendium || !btnArena || !panelCompendium || !panelArena) return;

  btnCompendium.onclick = () => {
    btnCompendium.classList.add('active');
    btnArena.classList.remove('active');
    panelCompendium.style.display = 'block';
    panelArena.style.display = 'none';
    playClashSound('deploy');
  };

  btnArena.onclick = () => {
    btnArena.classList.add('active');
    btnCompendium.classList.remove('active');
    panelArena.style.display = 'block';
    panelCompendium.style.display = 'none';
    playClashSound('horn');
    setTimeout(initArena3dDiorama, 50);
  };
}

// Card Filter Toolbar Setup
function setupCardFilters() {
  const typeBtns = document.querySelectorAll('[data-filter-type]');
  const elixirBtns = document.querySelectorAll('[data-filter-elixir]');
  const searchInput = document.getElementById('cardSearchInput');

  typeBtns.forEach(btn => {
    btn.onclick = () => {
      typeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilterType = btn.dataset.filterType;
      filterCards3DGrid();
      playClashSound('sword');
    };
  });

  elixirBtns.forEach(btn => {
    btn.onclick = () => {
      elixirBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilterElixir = btn.dataset.filterElixir;
      filterCards3DGrid();
      playClashSound('sword');
    };
  });

  if (searchInput) {
    searchInput.oninput = (e) => {
      currentSearchQuery = e.target.value.toLowerCase().trim();
      filterCards3DGrid();
    };
  }
}

function filterCards3DGrid() {
  const cardEls = document.querySelectorAll('.catalog-card-3d');
  cardEls.forEach(el => {
    const cardId = el.dataset.cardId;
    const proto = CARD_PROTOS[cardId];
    if (!proto) return;

    let matchesType = (currentFilterType === 'all') || (proto.category === currentFilterType);
    let matchesElixir = (currentFilterElixir === 'all') || (proto.elixir.toString() === currentFilterElixir);
    let matchesSearch = !currentSearchQuery || 
                        proto.name.toLowerCase().includes(currentSearchQuery) || 
                        cardId.toLowerCase().includes(currentSearchQuery) ||
                        proto.desc.toLowerCase().includes(currentSearchQuery);

    if (matchesType && matchesElixir && matchesSearch) {
      el.style.display = 'block';
    } else {
      el.style.display = 'none';
    }
  });
}

// 3D Cards Catalog Rendering Engine
function renderCardsCatalog() {
  setupCodexSubtabs();
  setupCardFilters();

  const grid = document.getElementById('cardsCatalogGrid');
  const chipContainer = document.getElementById('quickCardChips');

  if (chipContainer) {
    chipContainer.innerHTML = '';
    Object.keys(CARD_PROTOS).forEach(k => {
      const c = CARD_PROTOS[k];
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'card-id-chip';
      chip.title = `Click to copy '${k}'`;
      chip.onclick = () => {
        copyTextToClipboard(k, () => {
          const prev = chip.innerHTML;
          chip.innerHTML = `✓ Copied!`;
          chip.style.borderColor = '#4ade80';
          chip.style.color = '#4ade80';
          setTimeout(() => {
            chip.innerHTML = prev;
            chip.style.borderColor = '';
            chip.style.color = '';
          }, 1200);
          playClashSound('deploy');
        });
      };
      chipContainer.appendChild(chip);
    });
  }

  if (!grid) return;

  grid.innerHTML = '';
  Object.keys(CARD_PROTOS).forEach(k => {
    const c = CARD_PROTOS[k];
    const cardEl = document.createElement('div');
    cardEl.className = `catalog-card-3d rarity-${c.rarity || 'common'}`;
    cardEl.dataset.cardId = k;

    cardEl.innerHTML = `
      <div class="card-3d-inner">
        <div class="card-3d-top">
          <span class="card-rarity-badge">${(c.rarity || 'COMMON').toUpperCase()}</span>
          <span class="card-3d-elixir">💧 ${c.elixir}</span>
        </div>

        <div class="card-3d-avatar-box">
          ${c.icon}
        </div>

        <div class="card-3d-title-block">
          <h3>${c.name}</h3>
          <span class="card-3d-type-sub">${c.type}</span>
        </div>

        <div class="card-3d-stats-mini">
          <span><i data-lucide="heart"></i> ${c.hp} HP</span>
          <span><i data-lucide="zap"></i> ${c.dmg} DMG</span>
        </div>

        <div class="card-3d-actions">
          <button class="btn-card-inspect" onclick="openCard3dInspector('${k}')">
            <i data-lucide="box"></i> INSPECT IN 3D
          </button>
        </div>
      </div>
    `;

    // Interactive 3D Mouse Tilt Parallax
    cardEl.addEventListener('mousemove', (e) => {
      const rect = cardEl.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -12;
      const rotateY = ((x - centerX) / centerX) * 12;
      cardEl.style.setProperty('--rx', `${rotateX}deg`);
      cardEl.style.setProperty('--ry', `${rotateY}deg`);
      cardEl.style.setProperty('--mx', `${(x / rect.width) * 100}%`);
      cardEl.style.setProperty('--my', `${(y / rect.height) * 100}%`);
    });

    cardEl.addEventListener('mouseleave', () => {
      cardEl.style.setProperty('--rx', '0deg');
      cardEl.style.setProperty('--ry', '0deg');
    });

    cardEl.addEventListener('mouseenter', () => {
      playClashSound('sword');
    });

    grid.appendChild(cardEl);
  });

  if (window.lucide) {
    lucide.createIcons();
  }
}

// 3D Card Inspector Modal Engine
window.openCard3dInspector = function(cardId) {
  const proto = CARD_PROTOS[cardId];
  if (!proto) return;

  currentInspectedCardId = cardId;
  const modal = document.getElementById('card3dModal');
  if (!modal) return;

  setElText('modalCard3dRarity', `${(proto.rarity || 'COMMON').toUpperCase()} ${proto.category.toUpperCase()}`);
  setElText('modalCard3dIcon', proto.icon);
  setElText('modalCard3dName', proto.name);
  setElText('modalCard3dType', proto.type);
  setElText('modalCard3dElixir', `💧 ${proto.elixir} ELIXIR`);
  setElText('modalCard3dId', cardId);
  setElText('modalCard3dDesc', proto.desc);
  setElText('modalCard3dTarget', proto.targetStr);
  setElText('modalCard3dSpeed', proto.speedStr);
  setElText('modalCard3dSynergies', proto.synergies || 'Standard Deck Support');
  setElText('modalCard3dCounters', proto.counters || 'Crown Towers');

  const btnCopyModal = document.getElementById('btnCopyModalCardId');
  if (btnCopyModal) {
    btnCopyModal.onclick = () => {
      copyTextToClipboard(cardId, () => {
        btnCopyModal.innerHTML = '<i data-lucide="check"></i> Copied';
        if (window.lucide) window.lucide.createIcons();
        setTimeout(() => {
          btnCopyModal.innerHTML = '<i data-lucide="copy"></i> Copy';
          if (window.lucide) window.lucide.createIcons();
        }, 1200);
      });
    };
  }

  const slider = document.getElementById('cardLevelSlider');
  const levelNum = document.getElementById('cardLevelNum');
  if (slider) {
    slider.value = 11;
    if (levelNum) levelNum.textContent = 'Level 11 (Tournament Standard)';
    updateScaledCardStats(cardId, 11);

    slider.oninput = (e) => {
      const lvl = parseInt(e.target.value, 10);
      if (levelNum) levelNum.textContent = `Level ${lvl} ${lvl === 11 ? '(Tournament Standard)' : ''}`;
      updateScaledCardStats(cardId, lvl);
    };
  }

  const btnTestAttack = document.getElementById('btn3dTestAttack');
  const btnSound = document.getElementById('btn3dPlaySound');
  if (btnTestAttack) btnTestAttack.onclick = () => trigger3dAttackAnimation(cardId);
  if (btnSound) btnSound.onclick = () => playCardSoundEffect(cardId);

  modal.classList.add('active');
  playClashSound('horn');

  setTimeout(() => initCard3dStage(cardId), 50);

  const btnDismiss = document.getElementById('btnCard3dDismiss');
  if (btnDismiss) {
    btnDismiss.onclick = () => {
      modal.classList.remove('active');
      if (card3dAnimReq) cancelAnimationFrame(card3dAnimReq);
    };
  }
};

function updateScaledCardStats(cardId, level) {
  const proto = CARD_PROTOS[cardId];
  if (!proto) return;

  const multiplier = 1 + (level - 1) * 0.10;
  
  if (typeof proto.hp === 'number') {
    const scaledHp = Math.round(proto.hp * multiplier);
    setElText('modalCard3dHp', scaledHp.toLocaleString());
    const barHp = document.getElementById('barModalHp');
    if (barHp) barHp.style.width = `${Math.min(100, Math.max(15, (scaledHp / 3000) * 100))}%`;
  } else {
    setElText('modalCard3dHp', proto.hp);
    const barHp = document.getElementById('barModalHp');
    if (barHp) barHp.style.width = '100%';
  }

  if (typeof proto.dmg === 'number') {
    const scaledDmg = Math.round(proto.dmg * multiplier);
    setElText('modalCard3dDmg', scaledDmg.toLocaleString());
    const barDmg = document.getElementById('barModalDmg');
    if (barDmg) barDmg.style.width = `${Math.min(100, Math.max(15, (scaledDmg / 500) * 100))}%`;
  } else {
    setElText('modalCard3dDmg', proto.dmg);
  }
}

// Three.js 3D Stage for Card Inspector
function initCard3dStage(cardId) {
  const canvas = document.getElementById('card3dCanvas');
  if (!canvas || !window.THREE) return;

  if (card3dAnimReq) cancelAnimationFrame(card3dAnimReq);

  const width = canvas.clientWidth || 360;
  const height = canvas.clientHeight || 380;

  card3dScene = new THREE.Scene();
  card3dScene.background = new THREE.Color(0x0c1322);
  card3dScene.fog = new THREE.FogExp2(0x0c1322, 0.04);

  card3dCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
  card3dCamera.position.set(0, 3.2, 7.5);

  card3dRenderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  card3dRenderer.setSize(width, height);
  card3dRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  if (THREE.OrbitControls) {
    card3dControls = new THREE.OrbitControls(card3dCamera, card3dRenderer.domElement);
    card3dControls.enableDamping = true;
    card3dControls.dampingFactor = 0.05;
    card3dControls.maxPolarAngle = Math.PI / 2 + 0.1;
  }

  // Lighting
  const amb = new THREE.AmbientLight(0xffffff, 0.6);
  card3dScene.add(amb);

  const spot = new THREE.SpotLight(0xffd700, 1.4);
  spot.position.set(5, 10, 5);
  card3dScene.add(spot);

  const rim = new THREE.DirectionalLight(0x3b82f6, 0.9);
  rim.position.set(-5, 4, -5);
  card3dScene.add(rim);

  // Pedestal
  const pedestalGeo = new THREE.CylinderGeometry(2.5, 2.7, 0.4, 32);
  const pedestalMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.3, metalness: 0.7 });
  const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
  pedestal.position.y = -0.2;
  card3dScene.add(pedestal);

  const ringGeo = new THREE.TorusGeometry(2.55, 0.06, 16, 64);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0xffd700 });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.01;
  card3dScene.add(ring);

  // Custom 3D Procedural Mesh
  card3dMeshGroup = build3dElementMesh(cardId);
  card3dScene.add(card3dMeshGroup);

  let clock = new THREE.Clock();
  function animate() {
    card3dAnimReq = requestAnimationFrame(animate);
    const time = clock.getElapsedTime();

    if (card3dControls) card3dControls.update();

    if (card3dMeshGroup) {
      card3dMeshGroup.rotation.y = time * 0.4;
      card3dMeshGroup.position.y = Math.sin(time * 2.0) * 0.08 + 0.1;

      if (cardId === 'baby_dragon' && card3dMeshGroup.userData.wings) {
        card3dMeshGroup.userData.wings.forEach((wing, i) => {
          wing.rotation.z = Math.sin(time * 8.0) * 0.3 * (i === 0 ? 1 : -1);
        });
      } else if (cardId === 'fireball' && card3dMeshGroup.userData.rings) {
        card3dMeshGroup.userData.rings.forEach((r, idx) => {
          r.rotation.x += 0.02 * (idx + 1);
          r.rotation.y += 0.03 * (idx + 1);
        });
      }
    }

    card3dRenderer.render(card3dScene, card3dCamera);
  }

  animate();
}

function build3dElementMesh(cardId) {
  const group = new THREE.Group();

  if (cardId === 'knight') {
    const torsoGeo = new THREE.CylinderGeometry(0.5, 0.4, 1.2, 16);
    const torsoMat = new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.8, roughness: 0.2 });
    const torso = new THREE.Mesh(torsoGeo, torsoMat);
    torso.position.y = 0.6;
    group.add(torso);

    const headGeo = new THREE.SphereGeometry(0.35, 16, 16);
    const headMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9 });
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.y = 1.45;
    group.add(head);

    const visorGeo = new THREE.BoxGeometry(0.4, 0.12, 0.38);
    const visorMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.9 });
    const visor = new THREE.Mesh(visorGeo, visorMat);
    visor.position.set(0, 1.45, 0.1);
    group.add(visor);

    const plumeGeo = new THREE.ConeGeometry(0.15, 0.4, 8);
    const plumeMat = new THREE.MeshStandardMaterial({ color: 0xffd700 });
    const plume = new THREE.Mesh(plumeGeo, plumeMat);
    plume.position.set(0, 1.85, 0);
    group.add(plume);

    const bladeGeo = new THREE.BoxGeometry(0.08, 1.2, 0.04);
    const bladeMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.95 });
    const blade = new THREE.Mesh(bladeGeo, bladeMat);
    blade.position.set(0.7, 0.9, 0.2);
    blade.rotation.z = -Math.PI / 6;
    group.add(blade);

    const shieldGeo = new THREE.BoxGeometry(0.6, 0.8, 0.1);
    const shieldMat = new THREE.MeshStandardMaterial({ color: 0x2563eb });
    const shield = new THREE.Mesh(shieldGeo, shieldMat);
    shield.position.set(-0.6, 0.7, 0.3);
    group.add(shield);
  }
  else if (cardId === 'archers') {
    [-0.5, 0.5].forEach((xPos) => {
      const archer = new THREE.Group();
      const bodyGeo = new THREE.CylinderGeometry(0.3, 0.25, 1.0, 12);
      const bodyMat = new THREE.MeshStandardMaterial({ color: 0x166534 });
      const body = new THREE.Mesh(bodyGeo, bodyMat);
      body.position.y = 0.5;
      archer.add(body);

      const hoodGeo = new THREE.SphereGeometry(0.28, 12, 12);
      const hoodMat = new THREE.MeshStandardMaterial({ color: 0x15803d });
      const hood = new THREE.Mesh(hoodGeo, hoodMat);
      hood.position.y = 1.15;
      archer.add(hood);

      const bowGeo = new THREE.TorusGeometry(0.4, 0.03, 8, 16, Math.PI);
      const bowMat = new THREE.MeshStandardMaterial({ color: 0x78350f });
      const bow = new THREE.Mesh(bowGeo, bowMat);
      bow.position.set(0.3, 0.7, 0.2);
      bow.rotation.y = Math.PI / 2;
      archer.add(bow);

      archer.position.x = xPos;
      group.add(archer);
    });
  }
  else if (cardId === 'giant') {
    const bodyGeo = new THREE.CylinderGeometry(0.9, 0.7, 1.6, 16);
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x92400e, roughness: 0.8 });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 0.8;
    group.add(body);

    const headGeo = new THREE.BoxGeometry(0.7, 0.7, 0.7);
    const headMat = new THREE.MeshStandardMaterial({ color: 0xd97706 });
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.y = 1.95;
    group.add(head);

    [-1.0, 1.0].forEach(x => {
      const fistGeo = new THREE.SphereGeometry(0.4, 12, 12);
      const fistMat = new THREE.MeshStandardMaterial({ color: 0x78350f });
      const fist = new THREE.Mesh(fistGeo, fistMat);
      fist.position.set(x, 0.7, 0.3);
      group.add(fist);
    });
  }
  else if (cardId === 'musketeer') {
    const bodyGeo = new THREE.CylinderGeometry(0.4, 0.35, 1.1, 14);
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x6b21a8 });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 0.55;
    group.add(body);

    const hatDiskGeo = new THREE.CylinderGeometry(0.7, 0.7, 0.06, 16);
    const hatMat = new THREE.MeshStandardMaterial({ color: 0x581c87 });
    const hatDisk = new THREE.Mesh(hatDiskGeo, hatMat);
    hatDisk.position.y = 1.45;
    group.add(hatDisk);

    const hatTopGeo = new THREE.CylinderGeometry(0.4, 0.4, 0.3, 16);
    const hatTop = new THREE.Mesh(hatTopGeo, hatMat);
    hatTop.position.y = 1.6;
    group.add(hatTop);

    const rifleGeo = new THREE.CylinderGeometry(0.06, 0.12, 1.4, 12);
    const rifleMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8 });
    const rifle = new THREE.Mesh(rifleGeo, rifleMat);
    rifle.position.set(0.3, 0.8, 0.4);
    rifle.rotation.x = Math.PI / 3;
    group.add(rifle);
  }
  else if (cardId === 'hog_rider') {
    const hogGeo = new THREE.SphereGeometry(0.7, 16, 16);
    hogGeo.scale(1, 0.7, 1.4);
    const hogMat = new THREE.MeshStandardMaterial({ color: 0x78350f });
    const hog = new THREE.Mesh(hogGeo, hogMat);
    hog.position.y = 0.6;
    group.add(hog);

    const riderGeo = new THREE.CylinderGeometry(0.4, 0.3, 0.9, 12);
    const riderMat = new THREE.MeshStandardMaterial({ color: 0x92400e });
    const rider = new THREE.Mesh(riderGeo, riderMat);
    rider.position.set(0, 1.2, -0.1);
    group.add(rider);

    const hammerShaftGeo = new THREE.CylinderGeometry(0.04, 0.04, 1.3, 8);
    const hammerMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8 });
    const shaft = new THREE.Mesh(hammerShaftGeo, hammerMat);
    shaft.position.set(0.6, 1.6, 0.1);
    shaft.rotation.z = -Math.PI / 4;
    group.add(shaft);

    const headGeo = new THREE.BoxGeometry(0.4, 0.3, 0.3);
    const head = new THREE.Mesh(headGeo, hammerMat);
    head.position.set(0.9, 2.0, 0.1);
    group.add(head);
  }
  else if (cardId === 'skeletons') {
    const offsets = [[-0.4, -0.4], [0.4, -0.4], [-0.4, 0.4], [0.4, 0.4]];
    offsets.forEach(([xPos, zPos]) => {
      const skel = new THREE.Group();
      const headGeo = new THREE.SphereGeometry(0.22, 12, 12);
      const headMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc });
      const head = new THREE.Mesh(headGeo, headMat);
      head.position.y = 0.6;
      skel.add(head);

      const eyeGeo = new THREE.SphereGeometry(0.04, 8, 8);
      const eyeMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
      const eyeL = new THREE.Mesh(eyeGeo, eyeMat);
      const eyeR = new THREE.Mesh(eyeGeo, eyeMat);
      eyeL.position.set(-0.08, 0.63, 0.18);
      eyeR.position.set(0.08, 0.63, 0.18);
      skel.add(eyeL);
      skel.add(eyeR);

      const bodyGeo = new THREE.CylinderGeometry(0.12, 0.1, 0.5, 8);
      const body = new THREE.Mesh(bodyGeo, headMat);
      body.position.y = 0.25;
      skel.add(body);

      skel.position.set(xPos, 0, zPos);
      group.add(skel);
    });
  }
  else if (cardId === 'baby_dragon') {
    const dragonBodyGeo = new THREE.SphereGeometry(0.65, 16, 16);
    dragonBodyGeo.scale(1, 0.8, 1.2);
    const dragonMat = new THREE.MeshStandardMaterial({ color: 0x16a34a });
    const dragon = new THREE.Mesh(dragonBodyGeo, dragonMat);
    dragon.position.y = 1.2;
    group.add(dragon);

    const wings = [];
    [-1, 1].forEach(side => {
      const wingGeo = new THREE.ConeGeometry(0.6, 0.9, 3);
      const wingMat = new THREE.MeshStandardMaterial({ color: 0x15803d, side: THREE.DoubleSide });
      const wing = new THREE.Mesh(wingGeo, wingMat);
      wing.position.set(side * 0.7, 1.3, 0);
      wing.rotation.x = Math.PI / 2;
      wing.rotation.z = side * Math.PI / 3;
      group.add(wing);
      wings.push(wing);
    });
    group.userData.wings = wings;

    const fireGeo = new THREE.SphereGeometry(0.12, 8, 8);
    const fireMat = new THREE.MeshBasicMaterial({ color: 0xf97316 });
    for (let i = 0; i < 5; i++) {
      const f = new THREE.Mesh(fireGeo, fireMat);
      f.position.set(0, 1.1 - i * 0.08, 0.7 + i * 0.18);
      group.add(f);
    }
  }
  else if (cardId === 'pekka') {
    const torsoGeo = new THREE.BoxGeometry(1.1, 1.3, 0.8);
    const torsoMat = new THREE.MeshStandardMaterial({ color: 0x312e81, metalness: 0.9 });
    const torso = new THREE.Mesh(torsoGeo, torsoMat);
    torso.position.y = 0.85;
    group.add(torso);

    const headGeo = new THREE.BoxGeometry(0.6, 0.5, 0.6);
    const headMat = new THREE.MeshStandardMaterial({ color: 0x1e1b4b, metalness: 0.95 });
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.y = 1.65;
    group.add(head);

    [-0.35, 0.35].forEach(x => {
      const hornGeo = new THREE.ConeGeometry(0.12, 0.5, 8);
      const hornMat = new THREE.MeshStandardMaterial({ color: 0xc026d3, metalness: 0.8 });
      const horn = new THREE.Mesh(hornGeo, hornMat);
      horn.position.set(x, 2.0, 0);
      horn.rotation.z = x > 0 ? -Math.PI / 6 : Math.PI / 6;
      group.add(horn);
    });

    const visorGeo = new THREE.BoxGeometry(0.45, 0.08, 0.1);
    const visorMat = new THREE.MeshBasicMaterial({ color: 0xa855f7 });
    const visor = new THREE.Mesh(visorGeo, visorMat);
    visor.position.set(0, 1.65, 0.31);
    group.add(visor);

    [-0.8, 0.8].forEach(x => {
      const swordGeo = new THREE.BoxGeometry(0.12, 1.5, 0.05);
      const swordMat = new THREE.MeshStandardMaterial({ color: 0xa855f7, metalness: 0.9 });
      const sword = new THREE.Mesh(swordGeo, swordMat);
      sword.position.set(x, 1.0, 0.3);
      group.add(sword);
    });
  }
  else if (cardId === 'fireball') {
    const coreGeo = new THREE.SphereGeometry(0.8, 24, 24);
    const coreMat = new THREE.MeshBasicMaterial({ color: 0xf97316 });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.position.y = 1.0;
    group.add(core);

    const rings = [];
    [1.0, 1.2].forEach((radius, idx) => {
      const ringGeo = new THREE.TorusGeometry(radius, 0.08, 12, 32);
      const ringMat = new THREE.MeshBasicMaterial({ color: idx === 0 ? 0xef4444 : 0xeab308 });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.y = 1.0;
      group.add(ring);
      rings.push(ring);
    });
    group.userData.rings = rings;
  }
  else if (cardId === 'goblin_barrel') {
    const barrelGeo = new THREE.CylinderGeometry(0.65, 0.65, 1.2, 16);
    const barrelMat = new THREE.MeshStandardMaterial({ color: 0x78350f });
    const barrel = new THREE.Mesh(barrelGeo, barrelMat);
    barrel.position.y = 0.6;
    group.add(barrel);

    [-0.3, 0.3].forEach(y => {
      const bandGeo = new THREE.TorusGeometry(0.66, 0.04, 8, 24);
      const bandMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8 });
      const band = new THREE.Mesh(bandGeo, bandMat);
      band.rotation.x = Math.PI / 2;
      band.position.y = 0.6 + y;
      group.add(band);
    });

    for (let i = 0; i < 3; i++) {
      const angle = (i / 3) * Math.PI * 2;
      const headGeo = new THREE.SphereGeometry(0.2, 12, 12);
      const headMat = new THREE.MeshStandardMaterial({ color: 0x15803d });
      const head = new THREE.Mesh(headGeo, headMat);
      head.position.set(Math.cos(angle) * 0.35, 1.25, Math.sin(angle) * 0.35);
      group.add(head);
    }
  }

  return group;
}

function trigger3dAttackAnimation(cardId) {
  if (!card3dMeshGroup) return;

  playCardSoundEffect(cardId);

  let startY = card3dMeshGroup.position.y;
  let startTime = Date.now();
  
  function anim() {
    let elapsed = (Date.now() - startTime) / 1000;
    if (elapsed < 0.4) {
      card3dMeshGroup.position.y = startY + Math.sin((elapsed / 0.4) * Math.PI) * 0.4;
      card3dMeshGroup.rotation.x = Math.sin((elapsed / 0.4) * Math.PI * 2) * 0.2;
      requestAnimationFrame(anim);
    } else {
      card3dMeshGroup.position.y = startY;
      card3dMeshGroup.rotation.x = 0;
    }
  }
  anim();
}

function playCardSoundEffect(cardId) {
  if (cardId === 'knight' || cardId === 'pekka') playClashSound('sword');
  else if (cardId === 'giant' || cardId === 'hog_rider') playClashSound('cannon');
  else if (cardId === 'archers' || cardId === 'musketeer') playClashSound('arrow');
  else if (cardId === 'fireball' || cardId === 'baby_dragon') playClashSound('fireball');
  else playClashSound('deploy');
}

// Three.js 3D Arena Holo-Diorama Engine
function initArena3dDiorama() {
  const canvas = document.getElementById('arena3dCanvas');
  if (!canvas || !window.THREE) return;

  if (arena3dAnimReq) cancelAnimationFrame(arena3dAnimReq);

  const width = canvas.clientWidth || 500;
  const height = canvas.clientHeight || 440;

  arena3dScene = new THREE.Scene();
  arena3dScene.background = new THREE.Color(0x0a101d);
  arena3dScene.fog = new THREE.FogExp2(0x0a101d, 0.02);

  arena3dCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
  arena3dCamera.position.set(0, 14, 18);

  arena3dRenderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  arena3dRenderer.setSize(width, height);
  arena3dRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  if (THREE.OrbitControls) {
    arena3dControls = new THREE.OrbitControls(arena3dCamera, arena3dRenderer.domElement);
    arena3dControls.enableDamping = true;
    arena3dControls.dampingFactor = 0.05;
    arena3dControls.target.set(0, 0, 0);
  }

  const ambLight = new THREE.AmbientLight(0xffffff, 0.7);
  arena3dScene.add(ambLight);

  const dirLight = new THREE.DirectionalLight(0xffd700, 1.2);
  dirLight.position.set(10, 20, 10);
  arena3dScene.add(dirLight);

  // Field
  const fieldGeo = new THREE.PlaneGeometry(16, 22);
  const fieldMat = new THREE.MeshStandardMaterial({ color: 0x1e3a1e, roughness: 0.8 });
  const field = new THREE.Mesh(fieldGeo, fieldMat);
  field.rotation.x = -Math.PI / 2;
  arena3dScene.add(field);

  // River
  const riverGeo = new THREE.PlaneGeometry(16, 2.5);
  const riverMat = new THREE.MeshBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.85 });
  const river = new THREE.Mesh(riverGeo, riverMat);
  river.rotation.x = -Math.PI / 2;
  river.position.set(0, 0.02, 0);
  arena3dScene.add(river);

  // Bridges
  [-4.0, 4.0].forEach(x => {
    const bridgeGeo = new THREE.BoxGeometry(1.6, 0.15, 2.8);
    const bridgeMat = new THREE.MeshStandardMaterial({ color: 0x78350f });
    const bridge = new THREE.Mesh(bridgeGeo, bridgeMat);
    bridge.position.set(x, 0.08, 0);
    arena3dScene.add(bridge);
  });

  // Towers
  const createTower3D = (x, z, isKing, colorHex) => {
    const group = new THREE.Group();
    const rad = isKing ? 0.9 : 0.6;
    const h = isKing ? 1.8 : 1.3;
    const bodyGeo = new THREE.CylinderGeometry(rad, rad * 1.1, h, 16);
    const bodyMat = new THREE.MeshStandardMaterial({ color: colorHex, metalness: 0.5 });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = h / 2;
    group.add(body);

    if (isKing) {
      const crownGeo = new THREE.TorusGeometry(0.5, 0.08, 8, 16);
      const crownMat = new THREE.MeshBasicMaterial({ color: 0xffd700 });
      const crown = new THREE.Mesh(crownGeo, crownMat);
      crown.rotation.x = Math.PI / 2;
      crown.position.y = h + 0.3;
      group.add(crown);
      group.userData.crown = crown;
    }

    group.position.set(x, 0, z);
    arena3dScene.add(group);
    return group;
  };

  const redKing = createTower3D(0, -8.5, true, 0xd97706);
  createTower3D(-4.0, -5.5, false, 0xd97706);
  createTower3D(4.0, -5.5, false, 0xd97706);

  const blueKing = createTower3D(0, 8.5, true, 0x2563eb);
  createTower3D(-4.0, 5.5, false, 0x2563eb);
  createTower3D(4.0, 5.5, false, 0x2563eb);

  // Camera Presets
  const camBtns = document.querySelectorAll('.cam-btn[data-cam]');
  camBtns.forEach(btn => {
    btn.onclick = () => {
      camBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.dataset.cam;
      if (mode === 'iso') {
        arena3dCamera.position.set(0, 14, 18);
        if (arena3dControls) arena3dControls.target.set(0, 0, 0);
      } else if (mode === 'top') {
        arena3dCamera.position.set(0, 22, 0.1);
        if (arena3dControls) arena3dControls.target.set(0, 0, 0);
      } else if (mode === 'red') {
        arena3dCamera.position.set(0, 8, -16);
        if (arena3dControls) arena3dControls.target.set(0, 0, 0);
      } else if (mode === 'blue') {
        arena3dCamera.position.set(0, 8, 16);
        if (arena3dControls) arena3dControls.target.set(0, 0, 0);
      }
      playClashSound('sword');
    };
  });

  const btnAutoRotate = document.getElementById('btnToggle3DRotate');
  if (btnAutoRotate) {
    btnAutoRotate.onclick = () => {
      isArena3dAutoRotating = !isArena3dAutoRotating;
      btnAutoRotate.classList.toggle('active', isArena3dAutoRotating);
    };
  }

  let clock = new THREE.Clock();
  function animateArena() {
    arena3dAnimReq = requestAnimationFrame(animateArena);
    const time = clock.getElapsedTime();

    if (arena3dControls) {
      if (isArena3dAutoRotating) {
        arena3dScene.rotation.y = time * 0.2;
      } else {
        arena3dScene.rotation.y = 0;
      }
      arena3dControls.update();
    }

    if (redKing && redKing.userData.crown) redKing.userData.crown.rotation.z = time * 1.5;
    if (blueKing && blueKing.userData.crown) blueKing.userData.crown.rotation.z = time * 1.5;

    arena3dRenderer.render(arena3dScene, arena3dCamera);
  }

  animateArena();
}

// Tournament Bracket Controls
async function fetchTournamentState() {
  try {
    const res = await fetch('/api/tournament/state');
    const tourney = await res.json();
    renderBracket(tourney);
  } catch (e) {
    console.error('Failed to fetch tournament state:', e);
  }
}

async function createTournamentBracket() {
  try {
    const res = await fetch('/api/skills');
    const skills = await res.json();
    const files = skills.map(s => s.filename);

    if (files.length < 2) {
      alert('You need at least 2 deck files in the "skills/" folder to generate a bracket.');
      return;
    }

    const tourneyRes = await fetch('/api/tournament/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ participant_files: files.slice(0, 8) })
    });
    const data = await tourneyRes.json();
    renderBracket(data.tournament);
    playClashSound('crown');
  } catch (e) {
    alert('Error generating tournament: ' + e);
  }
}

async function exportTournamentJson() {
  try {
    const res = await fetch('/api/tournament/export');
    const tourney = await res.json();
    const jsonStr = JSON.stringify(tourney, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `royal_arena_tournament_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('Failed to export tournament: ' + e);
  }
}

function importTournamentJson() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (evt) => {
      try {
        const parsed = JSON.parse(evt.target.result);
        const res = await fetch('/api/tournament/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tournament_data: parsed })
        });
        const data = await res.json();
        renderBracket(data.tournament);
        alert('Championship tournament state successfully imported!');
      } catch (err) {
        alert('Invalid JSON file: ' + err);
      }
    };
    reader.readAsText(file);
  };
  input.click();
}

// API Skills & Deck Management
async function fetchSkills() {
  try {
    const res = await fetch('/api/skills');
    const skills = await res.json();
    populateSkillDropdowns(skills);
  } catch (e) {
    console.error('Failed to fetch skills:', e);
  }
}

function populateSkillDropdowns(skills) {
  const elSelectRed = document.getElementById('selectRedSkill');
  const elSelectBlue = document.getElementById('selectBlueSkill');
  if (!elSelectRed || !elSelectBlue) return;

  const prevRed = elSelectRed.value;
  const prevBlue = elSelectBlue.value;

  elSelectRed.innerHTML = '';
  elSelectBlue.innerHTML = '';

  skills.forEach(s => {
    const optRed = document.createElement('option');
    optRed.value = s.filename;
    optRed.textContent = `${s.name} (${s.author || 'Commander'}) [${s.filename}]`;
    elSelectRed.appendChild(optRed);

    const optBlue = document.createElement('option');
    optBlue.value = s.filename;
    optBlue.textContent = `${s.name} (${s.author || 'Commander'}) [${s.filename}]`;
    elSelectBlue.appendChild(optBlue);
  });

  if (prevRed && Array.from(elSelectRed.options).some(o => o.value === prevRed)) {
    elSelectRed.value = prevRed;
  } else if (skills.length >= 1) {
    elSelectRed.selectedIndex = 0;
  }

  if (prevBlue && Array.from(elSelectBlue.options).some(o => o.value === prevBlue)) {
    elSelectBlue.value = prevBlue;
  } else if (skills.length >= 2) {
    elSelectBlue.selectedIndex = 1;
  }

  refreshSkillPill('Red');
  refreshSkillPill('Blue');
}

// Dropzone & File Upload Handlers
function setupUploadDropzones() {
  ['Red', 'Blue'].forEach(side => {
    const dropzone = document.getElementById(`dropzone${side}`);
    const fileInput = document.getElementById(`fileInput${side}`);
    const selectEl = document.getElementById(`select${side}Skill`);

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => {
      fileInput.value = '';
      fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        handleSkillFileUpload(e.target.files[0], side);
      }
    });

    ['dragenter', 'dragover'].forEach(evtName => {
      dropzone.addEventListener(evtName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'dragend'].forEach(evtName => {
      dropzone.addEventListener(evtName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleSkillFileUpload(e.dataTransfer.files[0], side);
      }
    });

    if (selectEl) {
      selectEl.addEventListener('change', () => {
        refreshSkillPill(side);
      });
    }
  });
}

async function handleSkillFileUpload(file, side) {
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async (evt) => {
    try {
      const content = evt.target.result;
      let filename = file.name.replace(/\s+/g, '_');
      if (!filename.endsWith('.md') && !filename.endsWith('.txt')) {
        filename += '.md';
      } else if (filename.endsWith('.txt')) {
        filename = filename.slice(0, -4) + '.md';
      }

      const res = await fetch('/api/skills/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, content })
      });
      const data = await res.json();
      await fetchSkills();

      const selectEl = document.getElementById(`select${side}Skill`);
      if (selectEl) selectEl.value = data.filename;

      if (data.profile) {
        updateSkillPill(side, data.profile);
      } else {
        await refreshSkillPill(side);
      }
      playClashSound('crown');
    } catch (err) {
      alert(`Error reading deck file: ${err}`);
    }
  };
  reader.readAsText(file);
}

function updateSkillPill(side, profile) {
  const pillName = document.getElementById(`pill${side}Name`);
  const pillSub = document.getElementById(`pill${side}Sub`);
  const preview = document.getElementById(`${side.toLowerCase()}DeckPreview`);

  if (pillName) pillName.textContent = profile.name || 'Custom Battle Deck';
  if (pillSub) {
    const author = profile.author || 'Commander';
    const arch = (profile.archetype || 'Balanced').toUpperCase().replace(/_/g, ' ');
    pillSub.textContent = `${author} • ${arch}`;
  }

  if (preview && profile.deck) {
    preview.innerHTML = '';
    profile.deck.forEach(cardId => {
      const proto = CARD_PROTOS[cardId] || { name: cardId, elixir: 3, icon: '⚔️' };
      const chip = document.createElement('div');
      chip.className = 'card-chip';
      chip.innerHTML = `${proto.icon} ${proto.name} <span class="elixir-cost">${proto.elixir}e</span>`;
      preview.appendChild(chip);
    });
  }
}

async function refreshSkillPill(side) {
  const selectEl = document.getElementById(`select${side}Skill`);
  if (!selectEl || !selectEl.value) return;

  try {
    const res = await fetch(`/api/skills/${selectEl.value}`);
    const data = await res.json();
    if (data.profile) {
      updateSkillPill(side, data.profile);
    }
  } catch (e) {
    console.error(`Failed to refresh pill for ${side}:`, e);
  }
}

// Tactical Deck Forge
// ==============================================================
// 4.1 SCHEMA DEFINITION & STRATEGY STUDIO LOGIC
// ==============================================================
const SCHEMA_4_1_TEMPLATE = `# Deck Name: <Kingdom / Commander Title>
# Player / Author: <Team Name>
# War Cry: "<Short Custom Battle Cry>"

## Archetype & Playstyle
<Brief description of strategic doctrine: cycle, beatdown, spell_bait, pekka_control, or bridge_spam>

## 8-Card Battle Deck
# Select exactly 8 cards from the catalog with percentage weights (must total 100%):
# Available Cards: knight (3e), archers (3e), giant (5e), musketeer (4e), hog_rider (4e),
#                  skeletons (2e), baby_dragon (4e), pekka (7e), fireball (4e), goblin_barrel (3e)
- <card_id_1>: <weight_percentage>%
- <card_id_2>: <weight_percentage>%
- <card_id_3>: <weight_percentage>%
- <card_id_4>: <weight_percentage>%
- <card_id_5>: <weight_percentage>%
- <card_id_6>: <weight_percentage>%
- <card_id_7>: <weight_percentage>%
- <card_id_8>: <weight_percentage>%

## Preferred Lane
<"left", "right", or "balanced">

## Tactical Triggers (If-Then Rules)
# Priority rules evaluated in real-time each simulation tick (top-to-bottom):
1. IF <Condition> -> <Action>!
2. IF <Condition> -> <Action>!
3. IF <Condition> -> <Action>!
4. IF <Condition> -> <Action>!
`;

const SCHEMA_4_1_EXAMPLE = `# Deck Name: Royal Vanguard
# Player / Author: Team Champion
# War Cry: "Victory for the Crown!"

## Archetype & Playstyle
Fast-paced tempo and counter-assault doctrine. Control the bridges with disciplined defense, then launch decisive counter-pushes down the exposed flank.

## 8-Card Battle Deck
- knight: 20%
- archers: 15%
- giant: 20%
- musketeer: 15%
- hog_rider: 15%
- skeletons: 5%
- baby_dragon: 5%
- fireball: 5%

## Preferred Lane
balanced

## Tactical Triggers (If-Then Rules)
1. IF Elixir >= 7 -> Deploy primary tank (Giant or Hog Rider) to begin a push!
2. IF enemy drops a heavy tank -> Deploy Skeletons and Musketeer on that lane to defend!
3. IF enemy Princess Tower HP < 380 -> Cast Fireball directly onto the tower to claim the Crown!
4. IF enemy attacks left lane -> Counter-attack with Hog Rider on the opposite right lane!
`;

async function copyTextToClipboard(text, successCallback) {
  let copied = false;
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch (err) {
      console.warn('navigator.clipboard.writeText failed, attempting in-viewport textarea fallback', err);
    }
  }

  if (!copied) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '0';
      ta.style.left = '0';
      ta.style.width = '2em';
      ta.style.height = '2em';
      ta.style.padding = '0';
      ta.style.border = 'none';
      ta.style.outline = 'none';
      ta.style.boxShadow = 'none';
      ta.style.background = 'transparent';
      ta.style.opacity = '0.01';
      ta.style.zIndex = '99999';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      ta.setSelectionRange(0, text.length);
      copied = document.execCommand('copy');
      document.body.removeChild(ta);
    } catch (fallbackErr) {
      console.error('execCommand fallback copy failed:', fallbackErr);
      copied = false;
    }
  }

  if (copied) {
    if (successCallback) successCallback();
    showToast('Copied to clipboard!', 'success');
  } else {
    window.prompt('Copy to clipboard (Ctrl+C, Enter):', text);
    if (successCallback) successCallback();
    showToast('Copied via text dialog!', 'info');
  }
}

function setupSchemaDefinitionUI() {
  // 1. Copy Buttons
  const btnCopySchema = document.getElementById('btnCopySchema');
  const btnCopyExample = document.getElementById('btnCopyExample');
  const btnCodeWindowCopy = document.getElementById('btnCodeWindowCopy');
  const copyLabel = document.getElementById('copySchemaBtnText');
  const copyExampleLabel = document.getElementById('copyExampleBtnText');

  const onCopySuccess = () => {
    if (copyLabel) copyLabel.textContent = '✓ Copied!';
    if (btnCopySchema) btnCopySchema.style.borderColor = '#10b981';
    if (btnCodeWindowCopy) btnCodeWindowCopy.innerHTML = '<i data-lucide="check"></i>';
    if (window.lucide) window.lucide.createIcons();
    playClashSound('click');
    showToast('4.1 Schema Template copied to clipboard!', 'success');
    setTimeout(() => {
      if (copyLabel) copyLabel.textContent = 'Copy Template';
      if (btnCopySchema) btnCopySchema.style.borderColor = '';
      if (btnCodeWindowCopy) btnCodeWindowCopy.innerHTML = '<i data-lucide="copy"></i>';
      if (window.lucide) window.lucide.createIcons();
    }, 2000);
  };

  const onCopyExampleSuccess = () => {
    if (copyExampleLabel) copyExampleLabel.textContent = '✓ Copied!';
    if (btnCopyExample) btnCopyExample.style.borderColor = '#10b981';
    playClashSound('click');
    showToast('Royal Vanguard reference deck copied to clipboard!', 'success');
    setTimeout(() => {
      if (copyExampleLabel) copyExampleLabel.textContent = 'Copy Example';
      if (btnCopyExample) btnCopyExample.style.borderColor = '';
    }, 2000);
  };

  if (btnCopySchema) {
    btnCopySchema.addEventListener('click', () => {
      copyTextToClipboard(SCHEMA_4_1_TEMPLATE, onCopySuccess);
    });
  }

  if (btnCopyExample) {
    btnCopyExample.addEventListener('click', () => {
      copyTextToClipboard(SCHEMA_4_1_EXAMPLE, onCopyExampleSuccess);
    });
  }

  if (btnCodeWindowCopy) {
    btnCodeWindowCopy.addEventListener('click', () => {
      copyTextToClipboard(SCHEMA_4_1_TEMPLATE, onCopySuccess);
    });
  }

  // 2. Download .md template
  const btnDownload = document.getElementById('btnDownloadSchema');
  if (btnDownload) {
    btnDownload.addEventListener('click', () => {
      const blob = new Blob([SCHEMA_4_1_TEMPLATE], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'skill_schema_template.md';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      playClashSound('click');
      showToast('Downloaded skill_schema_template.md', 'success');
    });
  }

  // 3. Schema Subnav Tabs
  const schemaTabs = document.querySelectorAll('.schema-tab');
  schemaTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      schemaTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.schematab;
      document.querySelectorAll('.schema-panel').forEach(p => p.classList.remove('active'));
      if (target === 'blueprint') {
        document.getElementById('panelSchemaBlueprint')?.classList.add('active');
      } else if (target === 'breakdown') {
        document.getElementById('panelSchemaBreakdown')?.classList.add('active');
      } else if (target === 'cards') {
        document.getElementById('panelSchemaCards')?.classList.add('active');
      }
      if (window.lucide) window.lucide.createIcons();
      playClashSound('click');
    });
  });

  // 4. Load Schema into Forge
  const btnLoadForge = document.getElementById('btnLoadSchemaToForge');
  if (btnLoadForge) {
    btnLoadForge.addEventListener('click', () => {
      const btnModeEditor = document.getElementById('btnModeEditor');
      if (btnModeEditor) btnModeEditor.click();
      const textarea = document.getElementById('forgeCustomMarkdown');
      if (textarea && !textarea.value.trim()) {
        textarea.value = SCHEMA_4_1_TEMPLATE;
      }
      const studio = document.getElementById('deckForgeStudio');
      if (studio) {
        studio.scrollIntoView({ behavior: 'smooth' });
      }
      playClashSound('click');
      showToast('Opened 4.1 Schema Template in Deck Forge Studio', 'info');
    });
  }
}

// Tactical Deck Forge & Studio Logic
function setupNoCodeBuilder() {
  setupSchemaDefinitionUI();

  // Mode Toggling
  const btnModeRapid = document.getElementById('btnModeRapid');
  const btnModeEditor = document.getElementById('btnModeEditor');
  const formRapid = document.getElementById('forgeRapidForm');
  const wrapperEditor = document.getElementById('forgeEditorWrapper');
  const txtEditor = document.getElementById('forgeCustomMarkdown');

  if (btnModeRapid && btnModeEditor && formRapid && wrapperEditor) {
    btnModeRapid.addEventListener('click', () => {
      btnModeRapid.classList.add('active');
      btnModeEditor.classList.remove('active');
      formRapid.style.display = 'grid';
      wrapperEditor.style.display = 'none';
      playClashSound('click');
    });

    btnModeEditor.addEventListener('click', () => {
      btnModeEditor.classList.add('active');
      btnModeRapid.classList.remove('active');
      formRapid.style.display = 'none';
      wrapperEditor.style.display = 'flex';
      if (txtEditor && !txtEditor.value.trim()) {
        txtEditor.value = SCHEMA_4_1_TEMPLATE;
      }
      if (window.lucide) window.lucide.createIcons();
      playClashSound('click');
    });
  }

  // Rapid Builder Button
  const btnBuild = document.getElementById('btnBuildSkill');
  if (btnBuild) {
    btnBuild.addEventListener('click', async () => {
      const deckName = document.getElementById('builderKingdomName')?.value.trim() || 'Royal Vanguard';
      const author = document.getElementById('builderRulerName')?.value.trim() || 'Commander Valerius';
      const arch = document.getElementById('builderStrategy')?.value || 'hog_cycle';
      const lane = document.getElementById('builderLane')?.value || 'balanced';

      const deckTemplates = {
        hog_cycle: ["hog_rider", "musketeer", "knight", "skeletons", "fireball", "archers", "baby_dragon", "goblin_barrel"],
        beatdown: ["giant", "baby_dragon", "musketeer", "knight", "fireball", "archers", "skeletons", "hog_rider"],
        spell_bait: ["goblin_barrel", "knight", "skeletons", "archers", "fireball", "musketeer", "baby_dragon", "hog_rider"],
        pekka_control: ["pekka", "baby_dragon", "musketeer", "knight", "fireball", "skeletons", "archers", "hog_rider"],
        bridge_spam: ["hog_rider", "knight", "goblin_barrel", "baby_dragon", "archers", "skeletons", "fireball", "musketeer"]
      };

      const cards = deckTemplates[arch] || deckTemplates.hog_cycle;
      const content = `# Deck Name: ${deckName}
# Player / Author: ${author}
# War Cry: "Victory for the Crown!"

## Archetype & Playstyle
${arch.replace('_', ' ').toUpperCase()} doctrine configured for the ${lane} lane according to 4.1 Schema.

## 8-Card Battle Deck
${cards.map((c, i) => `- ${c}: ${i < 4 ? '15%' : '10%'}`).join('\n')}

## Preferred Lane
${lane}

## Tactical Triggers (If-Then Rules)
1. IF Elixir >= 6 -> Deploy primary win condition at the bridge!
2. IF enemy drops a tank -> Defend with swarms and ranged support!
3. IF enemy tower < 380 HP -> Cast Fireball to finish the Crown!
`;

      const cleanFilename = deckName.toLowerCase().replace(/[^a-z0-9]/g, '_') + '_deck.md';
      await saveAndEquipSkill(cleanFilename, content, 'Red');
    });
  }

  // Reset to 4.1 Template in Editor
  const btnResetTemplate = document.getElementById('btnEditorLoadTemplate');
  if (btnResetTemplate && txtEditor) {
    btnResetTemplate.addEventListener('click', () => {
      txtEditor.value = SCHEMA_4_1_TEMPLATE;
      const statusBox = document.getElementById('validationFeedbackBox');
      if (statusBox) statusBox.style.display = 'none';
      playClashSound('click');
      showToast('Loaded 4.1 Schema Template into Editor', 'info');
    });
  }

  // Load 4.1 Working Example in Editor
  const btnLoadExample = document.getElementById('btnEditorLoadExample');
  if (btnLoadExample && txtEditor) {
    btnLoadExample.addEventListener('click', () => {
      txtEditor.value = SCHEMA_4_1_EXAMPLE;
      const statusBox = document.getElementById('validationFeedbackBox');
      if (statusBox) statusBox.style.display = 'none';
      playClashSound('click');
      showToast('Loaded Royal Vanguard Reference Deck into Editor', 'info');
    });
  }

  // Validate Schema in Editor
  const btnValidate = document.getElementById('btnEditorValidate');
  if (btnValidate && txtEditor) {
    btnValidate.addEventListener('click', async () => {
      const content = txtEditor.value.trim();
      if (!content) {
        alert('Please enter or paste your skill markdown before validating.');
        return;
      }
      await runSchemaValidation(content);
    });
  }

  // Deploy Buttons
  const btnSaveLib = document.getElementById('btnSaveCustomSkill');
  const btnDeployRed = document.getElementById('btnDeployCustomRed');
  const btnDeployBlue = document.getElementById('btnDeployCustomBlue');
  const inputFilename = document.getElementById('forgeCustomFilename');

  const getDossierData = () => {
    let fn = inputFilename ? inputFilename.value.trim() : 'custom_doctrine.md';
    if (!fn.endsWith('.md')) fn += '.md';
    fn = fn.replace(/[^a-zA-Z0-9_\-\.]/g, '_');
    const content = txtEditor ? txtEditor.value.trim() : '';
    return { filename: fn, content };
  };

  if (btnSaveLib) {
    btnSaveLib.addEventListener('click', async () => {
      const { filename, content } = getDossierData();
      if (!content) return alert('Dossier content cannot be empty.');
      await saveAndEquipSkill(filename, content, null);
    });
  }

  if (btnDeployRed) {
    btnDeployRed.addEventListener('click', async () => {
      const { filename, content } = getDossierData();
      if (!content) return alert('Dossier content cannot be empty.');
      await saveAndEquipSkill(filename, content, 'Red');
    });
  }

  if (btnDeployBlue) {
    btnDeployBlue.addEventListener('click', async () => {
      const { filename, content } = getDossierData();
      if (!content) return alert('Dossier content cannot be empty.');
      await saveAndEquipSkill(filename, content, 'Blue');
    });
  }
}

async function runSchemaValidation(content) {
  const feedbackBox = document.getElementById('validationFeedbackBox');
  const valBadge = document.getElementById('valStatusBadge');
  const valTitle = document.getElementById('valStatusTitle');
  const checklist = document.getElementById('valChecklist');
  if (!feedbackBox || !valBadge || !checklist) return;

  try {
    const res = await fetch('/api/skills/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    const data = await res.json();
    feedbackBox.style.display = 'block';

    const sec = data.sections_status || {};
    const prof = data.profile || {};
    const deckCount = (prof.deck || []).length;
    const trigCount = (prof.triggers || []).length;

    if (data.valid) {
      feedbackBox.className = 'validation-feedback-box valid-schema';
      valBadge.className = 'val-badge';
      valBadge.textContent = '4.1 SCHEMA VALID';
      valTitle.textContent = `✓ "${prof.name || 'Custom Doctrine'}" passed verification. Ready to deploy!`;
    } else {
      feedbackBox.className = 'validation-feedback-box invalid-schema';
      valBadge.className = 'val-badge val-err';
      valBadge.textContent = 'SCHEMA ISSUES';
      valTitle.textContent = data.errors?.join(', ') || 'Validation errors detected';
    }

    checklist.innerHTML = `
      <div class="val-check-item ${sec.header_metadata ? 'ok' : 'fail'}">
        <i data-lucide="${sec.header_metadata ? 'check-circle' : 'alert-circle'}"></i>
        <span>Header: <strong>${prof.name || 'Missing'}</strong> (${prof.author || 'Anonymous'})</span>
      </div>
      <div class="val-check-item ${sec.archetype ? 'ok' : 'fail'}">
        <i data-lucide="${sec.archetype ? 'check-circle' : 'alert-circle'}"></i>
        <span>Archetype: <strong>${(prof.archetype || 'None').toUpperCase()}</strong></span>
      </div>
      <div class="val-check-item ${deckCount >= 8 ? 'ok' : 'fail'}">
        <i data-lucide="${deckCount >= 8 ? 'check-circle' : 'alert-circle'}"></i>
        <span>8-Card Deck: <strong>${deckCount}/8 Cards</strong></span>
      </div>
      <div class="val-check-item ${sec.lane ? 'ok' : 'fail'}">
        <i data-lucide="${sec.lane ? 'check-circle' : 'alert-circle'}"></i>
        <span>Lane Bias: <strong>${prof.preferred_lane || 'balanced'}</strong></span>
      </div>
      <div class="val-check-item ${trigCount >= 1 ? 'ok' : 'fail'}">
        <i data-lucide="${trigCount >= 1 ? 'check-circle' : 'alert-circle'}"></i>
        <span>Triggers: <strong>${trigCount} Rules Active</strong></span>
      </div>
    `;
    if (window.lucide) window.lucide.createIcons();
    playClashSound(data.valid ? 'crown' : 'drop');
  } catch (err) {
    feedbackBox.style.display = 'block';
    feedbackBox.className = 'validation-feedback-box invalid-schema';
    valBadge.className = 'val-badge val-err';
    valBadge.textContent = 'ERROR';
    valTitle.textContent = `Server error validating: ${err}`;
  }
}

async function saveAndEquipSkill(filename, content, equipSide) {
  try {
    const res = await fetch('/api/skills/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, content })
    });
    const data = await res.json();
    await fetchSkills();

    if (equipSide === 'Red') {
      const selectRed = document.getElementById('selectRedSkill');
      if (selectRed) {
        selectRed.value = data.filename;
        refreshSkillPill('Red');
      }
    } else if (equipSide === 'Blue') {
      const selectBlue = document.getElementById('selectBlueSkill');
      if (selectBlue) {
        selectBlue.value = data.filename;
        refreshSkillPill('Blue');
      }
    }

    const statusEl = document.getElementById('builderStatusMsg');
    if (statusEl) {
      if (equipSide) {
        statusEl.textContent = `✓ Saved "${data.filename}" and equipped for ${equipSide} Commander!`;
      } else {
        statusEl.textContent = `✓ Saved "${data.filename}" to Tournament Skill Library!`;
      }
    }
    playClashSound('crown');
  } catch (e) {
    alert(`Error saving skill dossier: ${e}`);
  }
}

async function lockAndStartMatch() {
  const elSelectRed = document.getElementById('selectRedSkill');
  const elSelectBlue = document.getElementById('selectBlueSkill');
  const elSelectTimer = document.getElementById('selectTimer');
  if (!elSelectRed || !elSelectBlue || !elSelectTimer) return;

  const redSkill = elSelectRed.value;
  const blueSkill = elSelectBlue.value;
  const timerSecs = parseInt(elSelectTimer.value, 10);

  try {
    const res = await fetch('/api/match/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        red_skill_file: redSkill,
        blue_skill_file: blueSkill,
        max_duration_seconds: timerSecs
      })
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`Setup error: ${err.detail || 'Could not load match'}`);
      return;
    }
    victoryModalDismissed = false;
    const modal = document.getElementById('victoryModal');
    if (modal) modal.classList.remove('active');
    switchToArena();
    playClashSound('crown');
    await fetch('/api/match/start', { method: 'POST' });
  } catch (e) {
    alert('Error starting match: ' + e);
  }
}

async function startBattle() {
  try {
    initAudio();
    victoryModalDismissed = false;
    const modal = document.getElementById('victoryModal');
    if (modal) modal.classList.remove('active');
    await fetch('/api/match/start', { method: 'POST' });
    playClashSound('crown');
  } catch (e) {
    console.error('Failed to start:', e);
  }
}

async function pauseBattle() {
  try {
    if (currentMatchState && currentMatchState.status === 'paused') {
      await fetch('/api/match/resume', { method: 'POST' });
    } else {
      await fetch('/api/match/pause', { method: 'POST' });
    }
  } catch (e) {
    console.error('Failed to pause/resume:', e);
  }
}

async function stepBattle() {
  try {
    await fetch('/api/match/step', { method: 'POST' });
  } catch (e) {
    console.error('Failed to step:', e);
  }
}

async function resetBattle() {
  if (confirm('Reset the arena and re-initialize the match?')) {
    try {
      victoryModalDismissed = false;
      const modal = document.getElementById('victoryModal');
      if (modal) modal.classList.remove('active');
      await fetch('/api/match/reset', { method: 'POST' });
    } catch (e) {
      console.error('Failed to reset:', e);
    }
  }
}

function updateSpeedButtons(speed) {
  const numSpeed = parseFloat(speed) || 1.0;
  document.querySelectorAll('.speed-btn').forEach(btn => {
    const btnSpeed = parseFloat(btn.dataset.speed) || 1.0;
    btn.classList.toggle('active', Math.abs(btnSpeed - numSpeed) < 0.1);
  });
}

async function setSpeed(speed) {
  const numSpeed = parseFloat(speed) || 1.0;
  updateSpeedButtons(numSpeed);
  playClashSound('click');
  showToast(`Match playback speed: ${numSpeed}x`, 'info');
  try {
    const res = await fetch('/api/match/speed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ speed: numSpeed })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.speed !== undefined) {
        updateSpeedButtons(data.speed);
      }
    }
  } catch (e) {
    console.error('Failed to set speed:', e);
  }
}

function setElText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// Window Initialization
window.addEventListener('DOMContentLoaded', async () => {
  // Initialize Canvas FX Engine
  const canvasEl = document.getElementById('fxCanvas');
  if (canvasEl) {
    fxEngine = new ArenaFxEngine(canvasEl);
  }

  connectWebSocket();

  // Mode View Switchers
  const btnLobby = document.getElementById('btnViewLobby');
  const btnArena = document.getElementById('btnViewArena');
  const btnBracket = document.getElementById('btnViewBracket');
  const btnRules = document.getElementById('btnViewRules');
  if (btnLobby) btnLobby.addEventListener('click', switchToLobby);
  if (btnArena) btnArena.addEventListener('click', switchToArena);
  if (btnBracket) btnBracket.addEventListener('click', switchToBracket);
  if (btnRules) btnRules.addEventListener('click', switchToRules);

  // Match Action Controls
  const btnLockStart = document.getElementById('btnLockAndStart');
  const btnStart = document.getElementById('btnStart');
  const btnPause = document.getElementById('btnPause');
  const btnStep = document.getElementById('btnStep');
  const btnReset = document.getElementById('btnReset');
  const btnSound = document.getElementById('btnSound');
  const volumeSlider = document.getElementById('volumeSlider');

  if (btnLockStart) btnLockStart.addEventListener('click', lockAndStartMatch);
  if (btnStart) btnStart.addEventListener('click', startBattle);
  if (btnPause) btnPause.addEventListener('click', pauseBattle);
  if (btnStep) btnStep.addEventListener('click', stepBattle);
  if (btnReset) btnReset.addEventListener('click', resetBattle);

  // Developer Telemetry Drawer Toggle
  const btnToggleDebug = document.getElementById('btnToggleDebug');
  const btnDebugClose = document.getElementById('btnDebugClose');
  const debugPanel = document.getElementById('debugPanel');

  if (btnToggleDebug && debugPanel) {
    btnToggleDebug.addEventListener('click', () => {
      const isOpen = debugPanel.style.display !== 'none';
      debugPanel.style.display = isOpen ? 'none' : 'flex';
      if (!isOpen && currentMatchState) {
        updateDebugPanel(currentMatchState);
      }
    });
  }

  if (btnDebugClose && debugPanel) {
    btnDebugClose.addEventListener('click', () => {
      debugPanel.style.display = 'none';
    });
  }

  if (btnSound) {
    btnSound.addEventListener('click', () => {
      soundEnabled = !soundEnabled;
      btnSound.innerHTML = `<i data-lucide="${soundEnabled ? 'volume-2' : 'volume-x'}"></i>`;
      if (window.lucide) lucide.createIcons();
    });
  }

  if (volumeSlider) {
    volumeSlider.addEventListener('input', (e) => {
      setMasterVolume(e.target.value);
    });
  }

  // Speed Buttons
  document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => setSpeed(btn.dataset.speed));
  });

  // Tournament Bracket Buttons
  const btnGenBracket = document.getElementById('btnCreateBracket');
  const btnExport = document.getElementById('btnExportTourney');
  const btnImport = document.getElementById('btnImportTourney');

  if (btnGenBracket) btnGenBracket.addEventListener('click', createTournamentBracket);
  if (btnExport) btnExport.addEventListener('click', exportTournamentJson);
  if (btnImport) btnImport.addEventListener('click', importTournamentJson);

  // Victory Modal Close
  const modal = document.getElementById('victoryModal');
  const btnModalClose = document.getElementById('btnModalClose');
  const btnModalDismiss = document.getElementById('btnModalDismiss');
  const btnModalStay = document.getElementById('btnModalStay');

  const closeModal = (proceedToBracket = false) => {
    victoryModalDismissed = true;
    if (modal) modal.classList.remove('active');
    if (proceedToBracket) switchToBracket();
  };

  if (btnModalClose) btnModalClose.addEventListener('click', () => closeModal(true));
  if (btnModalDismiss) btnModalDismiss.addEventListener('click', () => closeModal(false));
  if (btnModalStay) btnModalStay.addEventListener('click', () => closeModal(false));
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal(false);
    });
  }

  setupUploadDropzones();
  setupNoCodeBuilder();
  renderCardsCatalog();
  updateSpeedButtons(1.0);

  await fetchSkills();
  await fetchTournamentState();
  switchToLobby();

  try {
    const res = await fetch('/api/match/state');
    const state = await res.json();
    if (state.status && state.status !== 'not_initialized') {
      renderState(state);
      if (state.status === 'running' || state.status === 'paused') {
        switchToArena();
      }
    }
  } catch (e) {
    console.log('Initial state load: ' + e);
  }

  if (window.lucide) {
    lucide.createIcons();
  }
});
