import { useEffect, useRef } from "react";

// Canvas spectrum analyzer. Skin-agnostic geometry; colors come from CSS vars
// (--vis-lo / --vis-hi / --vis-peak / --vis-bg) read off the canvas element so
// each skin paints its own bars. Animates only while `playing`.
export function Visualizer({ playing, bars = 19 }: { playing: boolean; bars?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const heights = useRef<number[]>(Array.from({ length: bars }, () => 0.15));
  const peaks = useRef<number[]>(Array.from({ length: bars }, () => 0.15));
  const phase = useRef<number[]>(Array.from({ length: bars }, (_, i) => i * 0.7));
  const raf = useRef(0);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d")!;

    const draw = () => {
      const cs = getComputedStyle(cv);
      const lo = cs.getPropertyValue("--vis-lo").trim() || "#1faf4a";
      const hi = cs.getPropertyValue("--vis-hi").trim() || "#ffe23d";
      const peakC = cs.getPropertyValue("--vis-peak").trim() || "#fff";
      const dpr = window.devicePixelRatio || 1;
      const W = cv.clientWidth, H = cv.clientHeight;
      if (cv.width !== W * dpr || cv.height !== H * dpr) {
        cv.width = W * dpr; cv.height = H * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);

      const gap = Math.max(1, W * 0.012);
      const bw = (W - gap * (bars - 1)) / bars;

      for (let i = 0; i < bars; i++) {
        // Bass-weighted profile: left bars taller, animated random-walk.
        const profile = 0.35 + 0.65 * Math.pow(1 - i / bars, 0.6);
        let target;
        if (playing) {
          phase.current[i] += 0.18 + Math.random() * 0.12;
          const wob = 0.5 + 0.5 * Math.sin(phase.current[i]);
          target = Math.min(1, profile * (0.45 + 0.7 * wob * Math.random()));
        } else {
          target = 0.05 + 0.03 * Math.sin(i);
        }
        // Smooth attack, slower decay.
        const h = heights.current[i];
        heights.current[i] = target > h ? target : h + (target - h) * 0.22;
        const v = heights.current[i];

        // Peak cap falls slowly.
        peaks.current[i] = Math.max(v, peaks.current[i] - (playing ? 0.012 : 0.02));

        const x = i * (bw + gap);
        const barH = v * H;
        const grad = ctx.createLinearGradient(0, H, 0, 0);
        grad.addColorStop(0, lo);
        grad.addColorStop(1, hi);
        ctx.fillStyle = grad;
        ctx.fillRect(x, H - barH, bw, barH);

        // Peak marker.
        const py = H - peaks.current[i] * H;
        ctx.fillStyle = peakC;
        ctx.fillRect(x, Math.max(0, py - 1.5), bw, 1.5);
      }
      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, bars]);

  return <canvas ref={ref} className="vis-canvas" />;
}
