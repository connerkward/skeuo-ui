import { useEffect, useRef } from "react";

// A tiny generative WebAudio engine so EVERY audio control has a real effect.
// A detuned saw-chord pad (rich harmonics → the EQ visibly reshapes it) runs
// through: master/preamp gain → 10 peaking EQ bands → stereo panner (balance)
// → volume gain → AnalyserNode → speakers. The visualizer reads the analyser,
// so volume/EQ/balance changes are both AUDIBLE and VISIBLE in the spectrum.
//
// Browsers block audio until a user gesture, so the context is created/resumed
// on the first play. Returns the AnalyserNode for the visualizer.

const BAND_HZ = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000];
// a major-ish chord (Hz), transposed per track for a little variety
const CHORD = [130.81, 164.81, 196.0, 246.94];

export interface AudioState {
  playing: boolean;
  volume: number;     // 0..1
  balance: number;    // 0..1 (0.5 = center)
  eqBands: number[];   // [preamp, b60..b16k] 0..1
  eqOn: boolean;
  muted: boolean;
  trackIdx: number;
  tone: { x: number; y: number };  // xy pad → pan offset (x) + bass/treble tilt (y)
}

export function useAudio(s: AudioState) {
  const ctxRef = useRef<AudioContext | null>(null);
  const nodes = useRef<{
    master: GainNode; vol: GainNode; pan: StereoPannerNode;
    bands: BiquadFilterNode[]; oscs: OscillatorNode[]; analyser: AnalyserNode;
    lowShelf: BiquadFilterNode; highShelf: BiquadFilterNode;
  } | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  // build the graph lazily on first play
  const ensure = () => {
    if (ctxRef.current) return ctxRef.current;
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const master = ctx.createGain(); master.gain.value = 0.5;
    const bands = BAND_HZ.map((hz) => {
      const f = ctx.createBiquadFilter(); f.type = "peaking"; f.frequency.value = hz; f.Q.value = 1.1; f.gain.value = 0;
      return f;
    });
    const lowShelf = ctx.createBiquadFilter(); lowShelf.type = "lowshelf"; lowShelf.frequency.value = 320; lowShelf.gain.value = 0;
    const highShelf = ctx.createBiquadFilter(); highShelf.type = "highshelf"; highShelf.frequency.value = 3200; highShelf.gain.value = 0;
    const pan = ctx.createStereoPanner();
    const vol = ctx.createGain(); vol.gain.value = 0;
    const analyser = ctx.createAnalyser(); analyser.fftSize = 128; analyser.smoothingTimeConstant = 0.8;
    // chain: master → bands... → lowShelf → highShelf → pan → vol → analyser → destination
    let prev: AudioNode = master;
    bands.forEach((b) => { prev.connect(b); prev = b; });
    prev.connect(lowShelf); lowShelf.connect(highShelf); highShelf.connect(pan);
    pan.connect(vol); vol.connect(analyser); analyser.connect(ctx.destination);
    // a soft detuned saw pad
    const oscs: OscillatorNode[] = [];
    CHORD.forEach((hz) => {
      [0, 6].forEach((detune) => {
        const o = ctx.createOscillator(); o.type = "sawtooth"; o.frequency.value = hz; o.detune.value = detune;
        const g = ctx.createGain(); g.gain.value = 0.12;
        o.connect(g); g.connect(master); o.start(); oscs.push(o);
      });
    });
    ctxRef.current = ctx; analyserRef.current = analyser;
    nodes.current = { master, vol, pan, bands, oscs, analyser, lowShelf, highShelf };
    return ctx;
  };

  // play/pause: ramp the output gain; resume the suspended context on first play
  useEffect(() => {
    if (s.playing) {
      try {
        const ctx = ensure();
        if (ctx.state === "suspended") ctx.resume().catch(() => {});
      } catch { /* audio unavailable / no user gesture yet */ }
    }
    const n = nodes.current, ctx = ctxRef.current;
    if (!n || !ctx) return;
    const target = s.playing && !s.muted ? s.volume : 0;
    n.vol.gain.cancelScheduledValues(ctx.currentTime);
    n.vol.gain.setTargetAtTime(target, ctx.currentTime, 0.05);
  }, [s.playing, s.volume, s.muted]);

  // balance + xy.x → pan;  xy.y → bass/treble tilt
  useEffect(() => {
    const n = nodes.current, ctx = ctxRef.current; if (!n || !ctx) return;
    const pan = Math.max(-1, Math.min(1, (s.balance * 2 - 1) + (s.tone.x - 0.5) * 0.6));
    n.pan.pan.setTargetAtTime(pan, ctx.currentTime, 0.05);
    const tilt = (s.tone.y - 0.5) * 24; // y up = brighter
    n.highShelf.gain.setTargetAtTime(tilt, ctx.currentTime, 0.05);
    n.lowShelf.gain.setTargetAtTime(-tilt, ctx.currentTime, 0.05);
  }, [s.balance, s.tone.x, s.tone.y]);

  // EQ bands + preamp
  useEffect(() => {
    const n = nodes.current, ctx = ctxRef.current; if (!n || !ctx) return;
    n.master.gain.setTargetAtTime(0.5 * (0.4 + s.eqBands[0]), ctx.currentTime, 0.05);
    n.bands.forEach((b, i) => {
      const v = s.eqOn ? (s.eqBands[i + 1] - 0.5) * 28 : 0; // ±14 dB
      b.gain.setTargetAtTime(v, ctx.currentTime, 0.05);
    });
  }, [s.eqBands, s.eqOn]);

  // re-tune the chord per track
  useEffect(() => {
    const n = nodes.current, ctx = ctxRef.current; if (!n || !ctx) return;
    const semis = [(s.trackIdx * 5) % 12 - 6];
    const ratio = Math.pow(2, semis[0] / 12);
    n.oscs.forEach((o, i) => {
      const base = CHORD[(i >> 1) % CHORD.length];
      o.frequency.setTargetAtTime(base * ratio, ctx.currentTime, 0.08);
    });
  }, [s.trackIdx]);

  useEffect(() => () => {
    // guard: closing an already-closed context throws (noisy on rapid
    // mount/unmount, e.g. mobile swipe swapping composites)
    const c = ctxRef.current;
    if (c && c.state !== "closed") c.close().catch(() => {});
  }, []);

  return analyserRef;
}
