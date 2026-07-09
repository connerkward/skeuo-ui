import { useEffect, useRef } from "react";
import type { Region } from "../template/schema";
import "./agentObserver.css";

// ─────────────────────────────────────────────────────────────────────────────
// AgentObserver — an "agent-observation" overlay for the wizard's template
// canvas: a glowing reticle cursor that autonomously travels to each control,
// scans it, draws its detection box on arrival, and then STAGES the two real
// gen12 placement algorithms as agent motion:
//   · knob     → candidate circles converging (the extract12 circle_fit mini-
//                Hough dy/dx/r sweep) + the fit-centre → matte-hole-centroid snap
//   · slider-h → a scanline walking outward from the slot centre over the
//                luminance profile (dark recess / bright bezel rim), then the
//                coverage-span travel bar extending + a thumb dot sliding it
// Pure decoration over the REAL LayoutStage — pointer-events: none, labelled as
// studio overlay, Escape dismisses. Companion to PipelineVisualizer (that panel
// shows the real pipeline's stage events; this shows WHERE on the canvas the
// equivalent detection work happens).
// ─────────────────────────────────────────────────────────────────────────────

// per-kind colors — mirrors LayoutStage's KIND_COLOR so overlay boxes read as
// the same identity system as the stage's own region boxes
const KIND_COLOR: Record<string, string> = {
  button: "#5aff82", toggle: "#ff8a3d", "slider-h": "#ff5a6e", "slider-v": "#ffd246",
  knob: "#5ab4ff", "slider-arc": "#ff5a6e", "slider-path": "#ff5a6e", segmented: "#c0a0ff",
  xy: "#46d6ff", display: "#b496ff", flourish: "#c8a0ff",
};
const colorFor = (k: string) => KIND_COLOR[k] ?? "#c8c8c8";
const ACCENT = "#4a8aff";                        // app accent (pipelineViz blue)
const easeIO = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

type Seg = {
  kind: "travel" | "scan" | "box" | "knob" | "snap" | "walk" | "span" | "slide" | "check" | "done";
  ri: number;            // region index (-1 for done)
  dur: number;           // ms
  from?: { x: number; y: number };   // travel start (normalized)
};

function buildScript(regions: Region[]): { segs: Seg[]; order: number[] } {
  // reading order: top-to-bottom then left-to-right, like a methodical pass
  const order = regions.map((_, i) => i).sort((a, b) => {
    const ra = regions[a].rect, rb = regions[b].rect;
    return (ra.y + ra.h / 2) - (rb.y + rb.h / 2) || (ra.x - rb.x);
  });
  const segs: Seg[] = [];
  let prev = { x: 0.5, y: 0.96 };                // enter from the bottom edge
  for (const ri of order) {
    const r = regions[ri];
    const c = { x: r.rect.x + r.rect.w / 2, y: r.rect.y + r.rect.h / 2 };
    const dist = Math.hypot(c.x - prev.x, c.y - prev.y);
    segs.push({ kind: "travel", ri, dur: Math.min(950, Math.max(420, dist * 1600)), from: prev });
    segs.push({ kind: "scan", ri, dur: 620 });
    segs.push({ kind: "box", ri, dur: 320 });
    if (r.kind === "knob") {
      segs.push({ kind: "knob", ri, dur: 1500 });     // circle candidates converge
      segs.push({ kind: "snap", ri, dur: 480 });      // centre → centroid snap
    } else if (r.kind === "slider-h" || r.kind === "slider-v") {
      segs.push({ kind: "walk", ri, dur: 1200 });     // scanline walks outward
      segs.push({ kind: "span", ri, dur: 380 });      // travel bar snaps in
      segs.push({ kind: "slide", ri, dur: 950 });     // thumb covers the span
    } else {
      segs.push({ kind: "check", ri, dur: 260 });
    }
    prev = c;
  }
  segs.push({ kind: "done", ri: -1, dur: 1700 });
  return { segs, order };
}

const SEG_LABEL: Record<Seg["kind"], (name: string) => string> = {
  travel: (n) => `→ moving to ${n}`,
  scan: (n) => `scanning ${n}`,
  box: (n) => `detected ${n} — boxing`,
  knob: () => "circle-fit: sweeping candidate rings (dy·dx·r) for max edge score",
  snap: () => "seat: fit centre → matte-hole centroid snap",
  walk: () => "travel: walking luminance profile — recess + bezel rim",
  span: () => "travel span locked (walk extent ± margin)",
  slide: () => "coverage check: thumb slides the travel span",
  check: (n) => `${n} ok ✓`,
  done: () => "AGENT PASS COMPLETE — looping",
};

export function AgentObserver({ regions, active, onClose }: {
  regions: Region[];
  active: boolean;
  onClose: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose); onCloseRef.current = onClose;

  // Escape dismisses (never while typing in a field)
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if (e.key === "Escape") { e.preventDefault(); onCloseRef.current(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    const host = canvas?.parentElement;                       // .agob
    const stage = host?.parentElement?.querySelector(".ls-stage") as HTMLElement | null;
    if (!canvas || !host || !stage) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { segs } = buildScript(regions);
    const total = segs.reduce((s, x) => s + x.dur, 0);
    const t0 = performance.now();
    const trail: { x: number; y: number }[] = [];
    let raf = 0;

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const hostBox = host.getBoundingClientRect();
      const stBox = stage.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(hostBox.width * dpr) || canvas.height !== Math.round(hostBox.height * dpr)) {
        canvas.width = Math.round(hostBox.width * dpr); canvas.height = Math.round(hostBox.height * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, hostBox.width, hostBox.height);
      // stage box in host-local px; all region coords are normalized to it
      const sx = stBox.left - hostBox.left, sy = stBox.top - hostBox.top;
      const X = (nx: number) => sx + nx * stBox.width;
      const Y = (ny: number) => sy + ny * stBox.height;

      // locate the active segment
      let t = (now - t0) % total;
      let si = 0; while (si < segs.length - 1 && t >= segs[si].dur) { t -= segs[si].dur; si++; }
      const seg = segs[si], u = Math.min(1, t / seg.dur);
      const looped = Math.floor((now - t0) / total);

      const rectOf = (ri: number) => regions[ri].rect;
      const centre = (ri: number) => ({ x: rectOf(ri).x + rectOf(ri).w / 2, y: rectOf(ri).y + rectOf(ri).h / 2 });

      // ── persistent artifacts: everything COMPLETED before the active segment ──
      const doneKinds = new Map<number, Set<Seg["kind"]>>();
      for (let i = 0; i < si; i++) {
        const s = segs[i]; if (s.ri < 0) continue;
        if (!doneKinds.has(s.ri)) doneKinds.set(s.ri, new Set());
        doneKinds.get(s.ri)!.add(s.kind);
      }
      for (const [ri, kinds] of doneKinds) {
        const r = regions[ri], c = colorFor(r.kind);
        const x = X(r.rect.x), y = Y(r.rect.y), w = r.rect.w * stBox.width, h = r.rect.h * stBox.height;
        if (kinds.has("box")) {
          ctx.strokeStyle = c; ctx.lineWidth = 1.6;
          ctx.setLineDash([]); ctx.strokeRect(x, y, w, h);
          ctx.font = "600 10px ui-monospace,monospace";
          const name = r.label || r.bind || r.dynamicType || r.kind;
          const tw = ctx.measureText(name).width;
          ctx.fillStyle = "#000000b8"; ctx.fillRect(x, y - 13, tw + 8, 12);
          ctx.fillStyle = c; ctx.fillText(name, x + 4, y - 4);
        }
        if (kinds.has("snap")) {                       // seated knob: ring + centre
          const cc = centre(ri), rr = Math.min(w, h) / 2;
          ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.beginPath();
          ctx.arc(X(cc.x), Y(cc.y), rr, 0, 7); ctx.stroke();
          ctx.fillStyle = c; ctx.beginPath(); ctx.arc(X(cc.x), Y(cc.y), 2.5, 0, 7); ctx.fill();
        }
        if (kinds.has("span")) {                       // travel bar (kept)
          const cy2 = Y(centre(ri).y);
          ctx.strokeStyle = "#5f7"; ctx.lineWidth = 3; ctx.beginPath();
          ctx.moveTo(x - w * 0.02, cy2); ctx.lineTo(x + w * 1.02, cy2); ctx.stroke();
        }
        if (kinds.has("check") || kinds.has("slide") || kinds.has("snap")) {
          ctx.fillStyle = "#3ad07a"; ctx.font = "700 11px ui-monospace,monospace";
          ctx.fillText("✓", x + w - 11, y + 12);
        }
      }

      // ── cursor position for this instant ─────────────────────────────────────
      let cur: { x: number; y: number };
      if (seg.kind === "travel") {
        const c = centre(seg.ri), e = easeIO(u);
        cur = { x: seg.from!.x + (c.x - seg.from!.x) * e, y: seg.from!.y + (c.y - seg.from!.y) * e };
      } else if (seg.ri >= 0) {
        const c = centre(seg.ri);
        cur = { x: c.x + 0.003 * Math.sin(now / 230), y: c.y + 0.003 * Math.cos(now / 190) };
      } else {
        cur = { x: 0.5, y: 0.96 };
      }
      trail.push({ x: X(cur.x), y: Y(cur.y) });
      if (trail.length > 26) trail.shift();

      // ── the ACTIVE segment's animation ────────────────────────────────────────
      if (seg.ri >= 0) {
        const r = regions[seg.ri], c = colorFor(r.kind);
        const x = X(r.rect.x), y = Y(r.rect.y), w = r.rect.w * stBox.width, h = r.rect.h * stBox.height;
        const cc = centre(seg.ri), ccx = X(cc.x), ccy = Y(cc.y);
        if (seg.kind === "scan") {
          // pulsing ring + sweeping radar arc
          const pr = Math.max(w, h) * (0.55 + 0.1 * Math.sin(now / 120));
          ctx.strokeStyle = ACCENT; ctx.lineWidth = 1.2; ctx.globalAlpha = 0.8;
          ctx.beginPath(); ctx.arc(ccx, ccy, pr, 0, 7); ctx.stroke();
          const a0 = (now / 260) % (2 * Math.PI);
          ctx.strokeStyle = ACCENT; ctx.lineWidth = 3; ctx.globalAlpha = 0.9;
          ctx.beginPath(); ctx.arc(ccx, ccy, pr * 0.8, a0, a0 + 1.1); ctx.stroke();
          ctx.globalAlpha = 1;
        } else if (seg.kind === "box") {
          // box draws on: perimeter stroke progress
          const per = 2 * (w + h), p = per * easeIO(u);
          ctx.strokeStyle = c; ctx.lineWidth = 1.8; ctx.beginPath();
          let rem = p; ctx.moveTo(x, y);
          const edges: [number, number][] = [[x + w, y], [x + w, y + h], [x, y + h], [x, y]];
          let px = x, py = y;
          for (const [ex, ey] of edges) {
            const len = Math.hypot(ex - px, ey - py);
            if (rem <= 0) break;
            const f = Math.min(1, rem / len);
            ctx.lineTo(px + (ex - px) * f, py + (ey - py) * f);
            rem -= len; px = ex; py = ey;
          }
          ctx.stroke();
        } else if (seg.kind === "knob") {
          // candidate circles converging — the dy/dx/r sweep staged as motion
          const R = Math.min(w, h) / 2;
          for (let i = 0; i < 3; i++) {
            const ph = now / (260 + i * 90) + i * 2.1;
            const jit = R * 0.45 * (1 - u);                        // jitter decays → converges
            const jr = R * (1 + 0.35 * (1 - u) * Math.sin(ph * 1.7));
            ctx.strokeStyle = i === 0 ? "#f55" : "#f5555588"; ctx.lineWidth = 1.3;
            ctx.setLineDash([5, 4]); ctx.beginPath();
            ctx.arc(ccx + jit * Math.cos(ph), ccy + jit * Math.sin(ph), Math.max(3, jr), 0, 7);
            ctx.stroke(); ctx.setLineDash([]);
          }
          ctx.strokeStyle = "#5f7"; ctx.lineWidth = 2; ctx.globalAlpha = 0.35 + 0.65 * u;
          ctx.beginPath(); ctx.arc(ccx, ccy, R, 0, 7); ctx.stroke(); ctx.globalAlpha = 1;
          // mini edge-score meter rising with convergence
          ctx.fillStyle = "#161a22"; ctx.fillRect(x, y + h + 6, w, 5);
          ctx.fillStyle = "#5f7"; ctx.fillRect(x, y + h + 6, w * u, 5);
        } else if (seg.kind === "snap") {
          const R = Math.min(w, h) / 2, e = easeIO(u);
          const fx = ccx - R * 0.32, fy = ccy - R * 0.22;          // glare-biased fit centre
          const ix2 = fx + (ccx - fx) * e, iy2 = fy + (ccy - fy) * e;
          ctx.strokeStyle = "#5f7"; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(ix2, iy2, R, 0, 7); ctx.stroke();
          ctx.setLineDash([3, 3]); ctx.strokeStyle = "#ffd246"; ctx.beginPath();
          ctx.moveTo(fx, fy); ctx.lineTo(ccx, ccy); ctx.stroke(); ctx.setLineDash([]);
          ctx.fillStyle = "#f55"; ctx.beginPath(); ctx.arc(fx, fy, 2.5, 0, 7); ctx.fill();
          ctx.fillStyle = "#ffd246"; ctx.beginPath(); ctx.arc(ccx, ccy, 3, 0, 7); ctx.fill();
          ctx.fillStyle = "#5f7"; ctx.beginPath(); ctx.arc(ix2, iy2, 3, 0, 7); ctx.fill();
        } else if (seg.kind === "walk") {
          // scanline pair walking outward from slot centre, colour-coded
          const e = easeIO(u), half = (w / 2) * e;
          for (const dir of [-1, 1]) {
            const wx = ccx + dir * half;
            const frac = half / (w / 2);
            ctx.strokeStyle = frac < 0.72 ? "#5ab4ff" : "#ffd246";   // recess → bezel rim
            ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(wx, y - 4); ctx.lineTo(wx, y + h + 4); ctx.stroke();
          }
          // visited span tint
          ctx.fillStyle = "#5ab4ff18"; ctx.fillRect(ccx - half, y, half * 2, h);
          if (u > 0.97) {                                            // stop markers
            ctx.fillStyle = "#f55";
            ctx.fillRect(x - 2, y - 4, 2, h + 8); ctx.fillRect(x + w, y - 4, 2, h + 8);
          }
        } else if (seg.kind === "span") {
          const e = easeIO(u), cy2 = ccy;
          ctx.strokeStyle = "#5f7"; ctx.lineWidth = 3; ctx.beginPath();
          ctx.moveTo(ccx - (w / 2 + w * 0.02) * e, cy2); ctx.lineTo(ccx + (w / 2 + w * 0.02) * e, cy2); ctx.stroke();
        } else if (seg.kind === "slide") {
          const cy2 = ccy, e = easeIO(u < 0.5 ? u * 2 : 2 - u * 2);  // there and back
          const tx = (x - w * 0.02) + (w * 1.04 - h * 0.9) * e;
          ctx.strokeStyle = "#5f7"; ctx.lineWidth = 3; ctx.beginPath();
          ctx.moveTo(x - w * 0.02, cy2); ctx.lineTo(x + w * 1.02, cy2); ctx.stroke();
          ctx.fillStyle = c; ctx.strokeStyle = "#fff"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(tx + h * 0.45, cy2, Math.max(4, h * 0.45), 0, 7); ctx.fill(); ctx.stroke();
        } else if (seg.kind === "check") {
          ctx.fillStyle = "#3ad07a"; ctx.font = `700 ${11 + 6 * easeIO(u)}px ui-monospace,monospace`;
          ctx.fillText("✓", x + w - 12, y + 13);
        }
      } else if (seg.kind === "done") {
        ctx.fillStyle = "#3ad07a"; ctx.font = "700 12px ui-monospace,monospace";
        const msg = "AGENT PASS COMPLETE";
        ctx.fillText(msg, sx + stBox.width / 2 - ctx.measureText(msg).width / 2, sy + stBox.height / 2);
      }

      // ── cursor: trailing path + glowing reticle ───────────────────────────────
      if (trail.length > 1) {
        for (let i = 1; i < trail.length; i++) {
          ctx.strokeStyle = ACCENT; ctx.globalAlpha = (i / trail.length) * 0.5;
          ctx.lineWidth = 1 + (i / trail.length) * 1.4;
          ctx.beginPath(); ctx.moveTo(trail[i - 1].x, trail[i - 1].y); ctx.lineTo(trail[i].x, trail[i].y); ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }
      const hx = trail[trail.length - 1].x, hy = trail[trail.length - 1].y;
      const g = ctx.createRadialGradient(hx, hy, 0, hx, hy, 16);
      g.addColorStop(0, "#4a8affaa"); g.addColorStop(1, "#4a8aff00");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(hx, hy, 16, 0, 7); ctx.fill();
      ctx.strokeStyle = "#cfe1ff"; ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.arc(hx, hy, 6, 0, 7); ctx.stroke();
      for (const [dx2, dy2] of [[-1, 0], [1, 0], [0, -1], [0, 1]] as const) {
        ctx.beginPath(); ctx.moveTo(hx + dx2 * 8, hy + dy2 * 8); ctx.lineTo(hx + dx2 * 13, hy + dy2 * 13); ctx.stroke();
      }

      // HUD label
      if (labelRef.current) {
        const name = seg.ri >= 0
          ? (regions[seg.ri].label || regions[seg.ri].bind || regions[seg.ri].dynamicType || regions[seg.ri].kind)
          : "";
        labelRef.current.textContent = `${SEG_LABEL[seg.kind](name ?? "")}${looped > 0 ? `  ·  pass ${looped + 1}` : ""}`;
      }
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [active, regions]);

  if (!active) return null;
  return (
    <div className="agob" aria-hidden="true">
      <canvas ref={canvasRef} className="agob-canvas" />
      <div className="agob-badge">AGENT · studio overlay — not part of the skin · Esc dismisses</div>
      <div ref={labelRef} className="agob-label" />
    </div>
  );
}
