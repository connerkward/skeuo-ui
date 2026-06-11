import { useEffect, useRef } from "react";

// Spectrum analyzer. When a live AnalyserNode is supplied (audio engine running)
// it draws the REAL FFT — so volume/EQ/balance visibly reshape the bars. Falls
// back to an animated random-walk when there's no audio yet. Colors come from
// CSS vars (--vis-lo / --vis-hi / --vis-peak) so each skin paints its own bars.
export function Visualizer({ playing, analyser, bars = 19 }: {
  playing: boolean;
  analyser?: React.RefObject<AnalyserNode | null> | null;
  bars?: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const heights = useRef<number[]>(Array.from({ length: bars }, () => 0.12));
  const peaks = useRef<number[]>(Array.from({ length: bars }, () => 0.12));
  const phase = useRef<number[]>(Array.from({ length: bars }, (_, i) => i * 0.7));
  const raf = useRef(0);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d")!;
    let freq: Uint8Array<ArrayBuffer> | null = null;

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

      const an = analyser?.current;
      let live: number[] | null = null;
      if (an && playing) {
        if (!freq || freq.length !== an.frequencyBinCount) freq = new Uint8Array(an.frequencyBinCount);
        an.getByteFrequencyData(freq);
        // map FFT bins (log-ish) to our bar count
        live = Array.from({ length: bars }, (_, i) => {
          const lo2 = Math.floor((i / bars) * freq!.length);
          const hi2 = Math.max(lo2 + 1, Math.floor(((i + 1) / bars) * freq!.length));
          let m = 0; for (let j = lo2; j < hi2; j++) m = Math.max(m, freq![j]);
          return m / 255;
        });
      }

      const gap = Math.max(1, W * 0.012);
      const bw = (W - gap * (bars - 1)) / bars;
      for (let i = 0; i < bars; i++) {
        let target: number;
        if (live) {
          target = Math.min(1, live[i] * 1.1);
        } else if (playing) {
          phase.current[i] += 0.18 + Math.random() * 0.12;
          const wob = 0.5 + 0.5 * Math.sin(phase.current[i]);
          const profile = 0.35 + 0.65 * Math.pow(1 - i / bars, 0.6);
          target = Math.min(1, profile * (0.45 + 0.7 * wob * Math.random()));
        } else {
          target = 0.05 + 0.03 * Math.sin(i);
        }
        const h = heights.current[i];
        heights.current[i] = target > h ? target : h + (target - h) * 0.25;
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
      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, bars, analyser]);

  return <canvas ref={ref} className="vis-canvas" />;
}
