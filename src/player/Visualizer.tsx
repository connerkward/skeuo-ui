import { useEffect, useRef } from "react";
import type { Pt } from "../template/schema";
import { buildSpline, splineAt, splineTangent } from "./spline";

// Spectrum analyzer. When a live AnalyserNode is supplied (audio engine running)
// it draws the REAL FFT — so volume/EQ/balance visibly reshape the bars. Falls
// back to an animated random-walk when there's no audio yet. Colors come from
// CSS vars (--vis-lo / --vis-hi / --vis-peak) so each skin paints its own bars.
export function Visualizer({ playing, analyser, bars = 19, variant = "linear", path }: {
  playing: boolean;
  analyser?: React.RefObject<AnalyserNode | null> | null;
  bars?: number;
  // "radial" fills a circular dial; "teeth" draws a red grinning equalizer;
  // "ribbon" stands reactive bars perpendicular to an arbitrary freeform spline
  // (the `path`) so each skin's EQ is its own shape, not the same rectangle.
  variant?: "linear" | "radial" | "teeth" | "ribbon" | "blob";
  path?: Pt[];
}) {
  const radial = variant === "radial";
  const teeth = variant === "teeth";
  const ribbon = variant === "ribbon";
  const nBars = radial ? 48 : teeth ? 13 : ribbon ? 28 : bars;
  const ref = useRef<HTMLCanvasElement>(null);
  const heights = useRef<number[]>(Array.from({ length: nBars }, () => 0.12));
  const peaks = useRef<number[]>(Array.from({ length: nBars }, () => 0.12));
  const raf = useRef(0);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d")!;
    let freq: Uint8Array<ArrayBuffer> | null = null;
    // freeform ribbon baseline (normalized in the canvas), built once per path
    const sp = ribbon ? buildSpline(path ?? []) : null;

    const sample = (n: number): number[] | null => {
      const an = analyser?.current;
      if (!an || !playing) return null;
      if (!freq || freq.length !== an.frequencyBinCount) freq = new Uint8Array(an.frequencyBinCount);
      an.getByteFrequencyData(freq);
      // The analyser can exist but read pure SILENCE — a suspended/not-yet-resumed
      // AudioContext (common in headless capture and before a user gesture), or a
      // muted graph. With all-zero bins the bars would collapse to nothing, so fall
      // back to the lively animated walk instead of drawing a dead-flat spectrum.
      let total = 0; for (let j = 0; j < freq.length; j++) total += freq[j];
      if (total === 0) return null;
      return Array.from({ length: n }, (_, i) => {
        const lo2 = Math.floor((i / n) * freq!.length);
        const hi2 = Math.max(lo2 + 1, Math.floor(((i + 1) / n) * freq!.length));
        let m = 0; for (let j = lo2; j < hi2; j++) m = Math.max(m, freq![j]);
        return m / 255;
      });
    };

    const draw = () => {
      const cs = getComputedStyle(cv);
      const lo = cs.getPropertyValue("--vis-lo").trim() || "#1faf4a";
      const hi = cs.getPropertyValue("--vis-hi").trim() || "#ffe23d";
      const peakC = cs.getPropertyValue("--vis-peak").trim() || "#fff";
      const dpr = window.devicePixelRatio || 1;
      const W = cv.clientWidth, H = cv.clientHeight;
      if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);

      const live = sample(nBars);
      // MOCK spectrum (no live audio): make it read like a real song rather than
      // independent per-bar noise — a beat-synced bass punch + a spectral envelope
      // (energy concentrated in the lows, tapering to highs) + smooth per-bar
      // shimmer. Deterministic motion (no per-frame random) so bars move together
      // like music, not TV static.
      const now = performance.now() / 1000;
      const beatPhase = (now * (112 / 60)) % 1;          // ~112 BPM
      const kick = Math.pow(1 - beatPhase, 2.6);         // sharp attack, decays across the beat
      const target = (i: number, n: number): number => {
        if (live) return Math.min(1, live[i] * 1.1);
        if (playing) {
          // Each bar swells/fades on its own via two offset LFOs (adjacent bars
          // differ → reads as real frequency content), plus a beat-synced punch.
          // Big dynamic range (valleys near zero, peaks near full) so it looks
          // like a song's spectrum dancing, not a uniform ring.
          const a = 0.5 + 0.5 * Math.sin(now * 2.4 + i * 0.85);
          const b = 0.5 + 0.5 * Math.sin(now * 4.1 + i * 2.3);
          // gamma > 1 deepens the valleys → clear peaks & troughs, not a flat ring
          const swell = Math.pow(a * 0.55 + b * 0.45, 1.9);
          // persistent per-bar loudness (some bands louder than others) so the
          // spectrum keeps a real shape even under the peak-hold smoothing
          const band = 0.35 + 0.65 * Math.abs(Math.sin(i * 1.7 + 0.6));
          if (radial) {
            // dancing bars all around the ring + a whole-ring pulse on the beat
            return Math.min(1, (0.06 + 0.95 * swell) * band + kick * 0.28);
          }
          // linear: bass-heavy spectral slope; lows punch hardest on the beat
          const t = 1 - i / n;                              // 1 = bass
          const env = 0.2 + 0.8 * Math.pow(t, 0.85);
          return Math.min(1, (0.1 + 0.9 * swell) * env + kick * (0.35 + 0.55 * t));
        }
        return radial ? 0.12 + 0.06 * Math.sin(i * 0.6) : 0.05 + 0.03 * Math.sin(i);
      };

      if (radial) {
        const cx = W / 2, cy = H / 2;
        const rIn = Math.min(W, H) * 0.30;          // center hole for the clock
        const rMax = Math.min(W, H) * 0.49;
        const seg = (Math.PI * 2) / nBars;
        ctx.lineCap = "round";
        for (let i = 0; i < nBars; i++) {
          const tg = target(i, nBars);
          const h = heights.current[i];
          heights.current[i] = tg > h ? tg : h + (tg - h) * 0.25;
          const v = heights.current[i];
          peaks.current[i] = Math.max(v, peaks.current[i] - (playing ? 0.012 : 0.02));
          const ang = -Math.PI / 2 + i * seg;        // start at 12 o'clock
          const co = Math.cos(ang), si = Math.sin(ang);
          const r1 = rIn, r2 = rIn + (rMax - rIn) * v;
          const grad = ctx.createLinearGradient(cx + co * r1, cy + si * r1, cx + co * r2, cy + si * r2);
          grad.addColorStop(0, lo); grad.addColorStop(1, hi);
          ctx.strokeStyle = grad;
          ctx.lineWidth = Math.max(2, seg * rIn * 0.62);
          ctx.beginPath();
          ctx.moveTo(cx + co * r1, cy + si * r1);
          ctx.lineTo(cx + co * r2, cy + si * r2);
          ctx.stroke();
          const rp = rIn + (rMax - rIn) * peaks.current[i];
          ctx.strokeStyle = peakC; ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(cx + co * rp, cy + si * rp);
          ctx.lineTo(cx + co * (rp + 2), cy + si * (rp + 2));
          ctx.stroke();
        }
      } else if (teeth) {
        // red grinning equalizer: spectrum bars are teeth standing on a smile
        // curve (corners up, center down), red root → bright tip, framed by a lip.
        const n = nBars;
        const padX = W * 0.05;
        const usable = W - padX * 2;
        const slot = usable / n;
        const bw = slot * 0.64;
        const centerY = H * 0.9, cornerY = H * 0.5;     // smile baseline endpoints
        const baseAt = (cx: number) => {
          const u = (cx - W / 2) / (usable / 2);        // -1..1
          return centerY - (centerY - cornerY) * u * u; // smile: corners up
        };
        for (let i = 0; i < n; i++) {
          const tg = target(i, n);
          const h = heights.current[i];
          heights.current[i] = tg > h ? tg : h + (tg - h) * 0.25;
          const v = heights.current[i];
          const cx = padX + slot * (i + 0.5);
          const base = baseAt(cx);
          const toothH = (H * 0.6) * (0.22 + 0.78 * v); // min stub so teeth always show
          const top = Math.max(2, base - toothH);
          const r = bw / 2;
          const grad = ctx.createLinearGradient(0, base, 0, top);
          grad.addColorStop(0, "#7d0f0f"); grad.addColorStop(1, "#ff5a4c");
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.moveTo(cx - r, base);
          ctx.lineTo(cx - r, top + r);
          ctx.arc(cx, top + r, r, Math.PI, 0);
          ctx.lineTo(cx + r, base);
          ctx.closePath();
          ctx.fill();
        }
        // red lip arc framing the grin
        ctx.strokeStyle = "#c91f1f"; ctx.lineCap = "round";
        ctx.lineWidth = Math.max(3, H * 0.05);
        ctx.beginPath();
        for (let x = padX; x <= W - padX; x += 3) {
          const y = baseAt(x) + H * 0.045;
          if (x === padX) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
      } else if (ribbon && sp) {
        // FREEFORM ribbon: bars stand PERPENDICULAR to an arbitrary spline, so the
        // equalizer takes the shape authored in the template (a curve that follows
        // the body) instead of a rectangle. Height reacts to the spectrum.
        const n = nBars;
        const barLen = Math.min(W, H) * 0.5;
        ctx.lineCap = "round";
        // soft baseline glow along the curve
        ctx.strokeStyle = lo; ctx.globalAlpha = 0.5; ctx.lineWidth = Math.max(2, H * 0.03);
        ctx.beginPath();
        sp.pts.forEach((p, i) => (i ? ctx.lineTo(p.x * W, p.y * H) : ctx.moveTo(p.x * W, p.y * H)));
        ctx.stroke(); ctx.globalAlpha = 1;
        for (let i = 0; i < n; i++) {
          const tg = target(i, n);
          const h = heights.current[i];
          heights.current[i] = tg > h ? tg : h + (tg - h) * 0.25;
          const v = heights.current[i];
          const t = n === 1 ? 0.5 : i / (n - 1);
          const b = splineAt(sp, t), tan = splineTangent(sp, t);
          const nx = tan.y, ny = -tan.x;                 // unit normal, rises UP off the curve
          const bx = b.x * W, by = b.y * H;
          const len = barLen * (0.12 + 0.88 * v);
          const grad = ctx.createLinearGradient(bx, by, bx + nx * len, by + ny * len);
          grad.addColorStop(0, lo); grad.addColorStop(1, hi);
          ctx.strokeStyle = grad; ctx.lineWidth = Math.max(2, (W / n) * 0.5);
          ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx + nx * len, by + ny * len); ctx.stroke();
          // peak dot at the tip
          peaks.current[i] = Math.max(v, peaks.current[i] - (playing ? 0.012 : 0.02));
          const pl = barLen * (0.12 + 0.88 * peaks.current[i]);
          ctx.fillStyle = peakC;
          ctx.beginPath(); ctx.arc(bx + nx * pl, by + ny * pl, Math.max(1.5, (W / n) * 0.2), 0, Math.PI * 2); ctx.fill();
        }
      } else {
        const gap = Math.max(1, W * 0.012);
        const bw = (W - gap * (nBars - 1)) / nBars;
        for (let i = 0; i < nBars; i++) {
          const tg = target(i, nBars);
          const h = heights.current[i];
          heights.current[i] = tg > h ? tg : h + (tg - h) * 0.25;
          const v = heights.current[i];
          peaks.current[i] = Math.max(v, peaks.current[i] - (playing ? 0.012 : 0.02));
          const x = i * (bw + gap);
          const barH = v * H;
          const grad = ctx.createLinearGradient(0, H, 0, 0);
          grad.addColorStop(0, lo); grad.addColorStop(1, hi);
          ctx.fillStyle = grad;
          ctx.fillRect(x, H - barH, bw, barH);
          const py = H - peaks.current[i] * H;
          ctx.fillStyle = peakC;
          ctx.fillRect(x, Math.max(0, py - 1.5), bw, 1.5);
        }
      }
      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, nBars, radial, teeth, ribbon, analyser, JSON.stringify(path)]);

  return <canvas ref={ref} className="vis-canvas" />;
}
