/**
 * The theatre's sound: synthesised in the browser (no audio files), quiet by default.
 *
 * - voice blips while a line types (pitch per character, so voices are recognisable)
 * - a soft page-turn when a chapter's curtain falls
 * - weather ambience: rain hiss or wind, cross-faded as scenes change
 *
 * Browsers only allow sound after the reader interacts, so ``unlock()`` is called from a click/keypress.
 */

let ctx: AudioContext | null = null;
let master: GainNode | null = null;
let volume = 0.5;
let noise: AudioBuffer | null = null;
let amb: { kind: string; gain: GainNode; stop: () => void } | null = null;
let lastBlip = 0;

export function unlock() {
  try {
    if (!ctx) {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AC) return;
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = volume;
      master.connect(ctx.destination);
    }
    if (ctx.state === "suspended") void ctx.resume();
  } catch {
    ctx = null;
  }
}

export function setVolume(v: number) {
  volume = Math.max(0, Math.min(1, v));
  if (ctx && master) master.gain.setTargetAtTime(volume, ctx.currentTime, 0.05);
}

const ready = () => !!ctx && !!master && ctx.state === "running" && volume > 0;

/** A short soft voice blip; ``seed`` picks the voice (pitch), ``tone`` nudges it. */
export function blip(seed: number, tone?: string | null) {
  if (!ready()) return;
  const now = ctx!.currentTime;
  if (now - lastBlip < 0.045) return;
  lastBlip = now;
  const base = 190 + ((seed * 53) % 9) * 22;
  const f = base * (tone === "shout" ? 1.15 : tone === "whisper" ? 0.85 : 1) * (0.97 + Math.random() * 0.06);
  const o = ctx!.createOscillator();
  const g = ctx!.createGain();
  const lp = ctx!.createBiquadFilter();
  o.type = "triangle";
  o.frequency.value = f;
  lp.type = "lowpass";
  lp.frequency.value = 1400;
  const peak = tone === "whisper" ? 0.035 : 0.06;
  g.gain.setValueAtTime(0, now);
  g.gain.linearRampToValueAtTime(peak, now + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0001, now + 0.07);
  o.connect(lp).connect(g).connect(master!);
  o.start(now);
  o.stop(now + 0.08);
}

function noiseBuffer() {
  if (noise) return noise;
  const len = ctx!.sampleRate * 2;
  noise = ctx!.createBuffer(1, len, ctx!.sampleRate);
  const d = noise.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  return noise;
}

/** Paper: a filtered noise swish. */
export function pageTurn() {
  if (!ready()) return;
  const now = ctx!.currentTime;
  const src = ctx!.createBufferSource();
  src.buffer = noiseBuffer();
  const bp = ctx!.createBiquadFilter();
  bp.type = "bandpass";
  bp.Q.value = 0.8;
  bp.frequency.setValueAtTime(900, now);
  bp.frequency.exponentialRampToValueAtTime(3200, now + 0.35);
  const g = ctx!.createGain();
  g.gain.setValueAtTime(0, now);
  g.gain.linearRampToValueAtTime(0.12, now + 0.06);
  g.gain.exponentialRampToValueAtTime(0.0001, now + 0.5);
  src.connect(bp).connect(g).connect(master!);
  src.start(now);
  src.stop(now + 0.55);
}

/** A low, warm swell for the chapter card. */
export function swell() {
  if (!ready()) return;
  const now = ctx!.currentTime;
  [110, 164.8, 220].forEach((f, i) => {
    const o = ctx!.createOscillator();
    const g = ctx!.createGain();
    o.type = "sine";
    o.frequency.value = f;
    g.gain.setValueAtTime(0, now);
    g.gain.linearRampToValueAtTime(0.045 / (i + 1), now + 0.6);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 2.6);
    o.connect(g).connect(master!);
    o.start(now);
    o.stop(now + 2.7);
  });
}

/** Weather ambience for the current scene: "rain", "wind" or null; cross-fades over ~1.5 s. */
export function ambience(kind: "rain" | "wind" | null) {
  if (!ctx || !master) return;
  if ((amb?.kind ?? null) === kind) return;
  const now = ctx.currentTime;
  if (amb) {
    const old = amb;
    old.gain.gain.setTargetAtTime(0, now, 0.5);
    setTimeout(old.stop, 2500);
    amb = null;
  }
  if (!kind) return;
  const src = ctx.createBufferSource();
  src.buffer = noiseBuffer();
  src.loop = true;
  const g = ctx.createGain();
  g.gain.value = 0;
  const nodes: AudioNode[] = [];
  if (kind === "rain") {
    const hp = ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 500;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 5200;
    nodes.push(hp, lp);
    g.gain.setTargetAtTime(0.07, now, 0.6);
  } else {
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 420;
    lp.Q.value = 3;
    // slow gusts
    const lfo = ctx.createOscillator();
    const depth = ctx.createGain();
    lfo.frequency.value = 0.13;
    depth.gain.value = 180;
    lfo.connect(depth).connect(lp.frequency);
    lfo.start();
    nodes.push(lp);
    g.gain.setTargetAtTime(0.09, now, 0.8);
  }
  let chain: AudioNode = src;
  for (const n of nodes) chain = chain.connect(n);
  chain.connect(g).connect(master);
  src.start();
  amb = {
    kind,
    gain: g,
    stop: () => {
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
    },
  };
}

export function silence() {
  ambience(null);
}
