// DEV-ONLY Template Studio (?studio). A human-facing interface to SEED / GENERATE a data
// template and see it PACKED live — all on the REAL shipping heuristics:
//   • cheap heuristic randomizer  → layoutRandomP / layoutArch (the 10 archetypes)
//   • LLM data-template generator → deriveLayout via POST /api/derive (heuristic-guided prompt)
//   • packer                      → repackTemplate (canon-size + resolveOverlaps), live
// Each component has a CENTROID (draggable), an ARBITRARY SHAPE connected to it, and a modular
// DIFFUSENESS (soft-guide spread). Left = raw seeded template, right = packed result.
//
// APPROACH B — the EDITABLE stage is a react-konva Stage/Layer scene graph. Every control is a
// Konva node (rounded Rect / Arc-path / slider Line) with a Konva Transformer providing the
// 8 bbox resize anchors (opposite-anchor-fixed, rotation off), a custom draggable corner handle
// morphing Rect cornerRadius (→ region.corner), and two draggable angle handles shaping a
// slider-arc's sweep directly on canvas (→ region.arc). Marquee multi-select via a Konva
// selection Rect + haveIntersection. The COMBINED blueprint + PaintedSheet panels stay SVG/img.
import { useMemo, useState, useCallback, useEffect, useRef, Fragment } from "react";
import { Stage, Layer, Rect, Line, Circle, Text, Path, Transformer } from "react-konva";
import Konva from "konva";
import {
  layoutRandomP, layoutArch, bakeButtons, resolveOverlaps, ARCHETYPES, DEFAULT_PARAMS, SPOTIFY_BINDS,
  GEN_W, GEN_H, type Params,
} from "../generate/layouts";
import { combinedBlueprint, componentColors } from "../generate/blueprint";
import { PAINT_PROMPT } from "../generate/pipeline";
import PaintedSheet from "./PaintedSheet";
import type { Region, Kind } from "../template/schema";

type SR = Region & { shapeKind?: string; diff?: number };
const KINDS: Kind[] = ["button", "knob", "toggle", "slider-h", "slider-v", "slider-arc", "display"];
const DEF_ARC = { start: 200, end: 340 };   // default partial-circle sweep for a slider-arc
const REPACK_ENABLED = false;   // feature flag: repack/packing is OFF — packed == raw, so the PACKED panel is hidden
const MIN_N = 0.03;             // minimum normalized control size
const clamp01 = (v: number, size = 0) => Math.max(0, Math.min(1 - size, v));
// SVG arc 'd' matching blueprint.ts arcPath (same large-arc/sweep rules) so a slider-arc reads
// IDENTICALLY in the studio panels and the combined blueprint. Used by BOTH the SVG projection
// (Canvas/packed panel) and the Konva Path (editable stage), so the arc look is one source.
const arcD = (cx: number, cy: number, r: number, a0: number, a1: number): string => {
  const p = (a: number): [number, number] => [cx + r * Math.cos((a * Math.PI) / 180), cy + r * Math.sin((a * Math.PI) / 180)];
  const [sx, sy] = p(a0), [ex, ey] = p(a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`;
};
const norm360 = (d: number) => ((d % 360) + 360) % 360;


export default function TemplateStudio() {
  const [P, setP] = useState<Params>({ ...DEFAULT_PARAMS });
  const [regions, setRegions] = useState<SR[]>(() => layoutArch("console", DEFAULT_PARAMS) as SR[]);
  // SELECTION — a set (marquee multi-select). `sel` is the PRIMARY (last-added) selection the
  // inspector/keyboard operate on; `selIds` drives the Konva Transformer's node set.
  const [selIds, setSelIds] = useState<string[]>([]);
  const sel = selIds.length ? selIds[selIds.length - 1] : null;
  const [showOverlays, setShowOverlays] = useState(false);  // studio annotations on the blueprint — OFF by default (see the exact image sent to FAL); toggle on to label cells
  const globalDiff = 0;   // diffuseness disabled for now — anchors are crisp
  const [prompt, setPrompt] = useState("a wild organic Y2K Winamp media player");
  const [llmMsg, setLlmMsg] = useState("");
  const [, setAuthored] = useState(false);   // human-edit flag (setter kept; value unused while repack is off)

  // ── Konva stage plumbing ─────────────────────────────────────────────────────
  const stageWrapRef = useRef<HTMLDivElement>(null);
  const [stagePx, setStagePx] = useState({ w: 1, h: 1 });   // live pixel size of the editable stage
  const nodeRefs = useRef<Map<string, Konva.Rect>>(new Map());   // per-region invisible transform target
  const trRef = useRef<Konva.Transformer>(null);
  const layerRef = useRef<Konva.Layer>(null);
  const [marquee, setMarquee] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const marqueeStart = useRef<{ x: number; y: number } | null>(null);
  const marqueeBox = useRef<{ x: number; y: number; w: number; h: number } | null>(null);   // synced ref so pointerup reads the live box even in a same-frame drag (state closure would be stale)
  // captured normalized rects at gesture start (drag/transform) → group move + delta math
  const gestureOrigin = useRef<Map<string, { x: number; y: number; w: number; h: number }>>(new Map());

  // HARD CONSTRAINT: components at 0 diffuseness (crisp, must-follow guides) may NEVER overlap.
  // Enforced with the SHIPPING resolveOverlaps, scoped to only the zero-diff subset.
  const enforceZeroDiff = useCallback((rs: SR[]): SR[] => {
    const isZero = (r: SR) => (r.diff ?? globalDiff) <= 0.001;
    const zero = rs.filter(isZero);
    if (zero.length < 2) return rs;
    const solved = resolveOverlaps(zero.map((r) => ({ ...r })) as Region[]) as SR[];
    const byId = new Map(solved.map((r) => [r.id, r]));
    return rs.map((r) => byId.get(r.id) ?? r);
  }, [globalDiff]);

  // undo/redo history — normal expected editor UX (⌘Z / ⇧⌘Z). Snapshots on every discrete
  // mutation (and at gesture START, so a whole drag/resize undoes as one step).
  const past = useRef<SR[][]>([]); const future = useRef<SR[][]>([]);
  const mutate = useCallback((updater: (rs: SR[]) => SR[]) => setRegions((rs) => {
    past.current.push(rs); if (past.current.length > 60) past.current.shift();
    future.current = []; return updater(rs);
  }), []);
  const snapshot = useCallback(() => setRegions((rs) => { past.current.push(rs); future.current = []; return rs; }), []);
  const undo = useCallback(() => setRegions((cur) => { const p = past.current.pop(); if (!p) return cur; future.current.push(cur); return p; }), []);
  const redo = useCallback(() => setRegions((cur) => { const f = future.current.pop(); if (!f) return cur; past.current.push(cur); return f; }), []);

  // REPACK DISABLED ("for now"): packed mirrors the raw regions 1:1.
  const packed = useMemo(() => regions as SR[], [regions]);
  const bakedRegs = useMemo(() => {
    try { return bakeButtons(packed.map((r) => ({ ...r, diff: 0 })) as Region[]); }
    catch { return packed as Region[]; }
  }, [packed]);
  const combined = useMemo(() => {
    try { return combinedBlueprint(bakedRegs, "rgb(128,128,130)"); }
    catch { return null; }
  }, [bakedRegs]);
  const colorMap = useMemo(() => componentColors(bakedRegs), [bakedRegs]);
  const colorOf = useCallback((r: SR) => colorMap.get(r.id)?.hex ?? "#888888", [colorMap]);

  const promptPreview = useMemo(() => {
    if (!combined) return "";
    const nButtons = packed.filter((r) => r.kind === "button").length;
    return PAINT_PROMPT
      .replace(/\{brief\}/g, prompt)
      .replace("{material}", prompt)
      .replace("{strip}", combined.stripDesc)
      .replace("{bakeLegend}", combined.bakeLegend || "(no baked buttons)")
      .replace(/\{NBUTTONS\}/g, String(nButtons))
      .replace(/\{BG\}/g, "«BG key-colour · derived from material server-side»");
  }, [combined, prompt, packed]);

  const randomize = () => { mutate(() => layoutRandomP(P) as SR[]); setSelIds([]); setAuthored(false); };
  const archGen = (a: string) => { mutate(() => layoutArch(a, P) as SR[]); setSelIds([]); setAuthored(false); };
  const llmGen = async () => {
    setLlmMsg("generating…");
    try {
      const r = await fetch("/api/derive", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
      const d = await r.json();
      if (d.regions?.length) { mutate(() => d.regions as SR[]); setSelIds([]); setAuthored(false); setLlmMsg(`LLM: ${d.regions.length} regions`); }
      else setLlmMsg(d.hasKey ? "LLM returned no usable layout (fell back)" : "no OpenAI key on server");
    } catch (e) { setLlmMsg("error: " + (e instanceof Error ? e.message : String(e))); }
  };

  const patchSel = (patch: Partial<SR>) => { setAuthored(true); mutate((rs) => enforceZeroDiff(rs.map((r) => r.id === sel ? { ...r, ...patch } : r))); };
  const delSel = useCallback(() => {
    setSelIds((ids) => { if (ids.length) { setAuthored(true); mutate((rs) => rs.filter((r) => !ids.includes(r.id))); } return []; });
  }, [mutate]);
  const addComp = () => {
    const id = "c" + Math.random().toString(36).slice(2, 6);
    setAuthored(true);
    mutate((rs) => enforceZeroDiff([...rs, { id, kind: "button", content: "sprite", layer: "components", bind: id, rect: { x: 0.44, y: 0.44, w: 0.12, h: 0.08 }, shapeKind: "auto", diff: globalDiff } as SR]));
    setSelIds([id]);
  };

  // normal expected keyboard shortcuts (guarded: never intercept while typing in a field)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
      if (e.key === "Escape") { setSelIds([]); return; }
      if (!selIds.length) return;
      if (e.key === "Backspace" || e.key === "Delete") { e.preventDefault(); delSel(); return; }
      const step = e.shiftKey ? 0.02 : 0.005;
      const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
      const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
      if (dx || dy) {
        e.preventDefault(); setAuthored(true);
        mutate((rs) => enforceZeroDiff(rs.map((r) => selIds.includes(r.id) ? { ...r, rect: { ...r.rect, x: clamp01(r.rect.x + dx, r.rect.w), y: clamp01(r.rect.y + dy, r.rect.h) } } : r)));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selIds, mutate, undo, redo, delSel, enforceZeroDiff]);

  // DEV verification hook (studio is debug-only): expose the Konva stage so headless Playwright
  // can read real node geometry + dispatch real pointer events at exact positions.
  useEffect(() => { if (import.meta.env.DEV) (window as unknown as { __ts?: unknown }).__ts = { stage: layerRef.current?.getStage() ?? null, regions, selIds }; });
  // Track the editable stage's live pixel box (Konva needs explicit px width/height).
  useEffect(() => {
    const el = stageWrapRef.current;
    if (!el) return;
    const measure = () => { const b = el.getBoundingClientRect(); if (b.width && b.height) setStagePx({ w: b.width, h: b.height }); };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Sync the Transformer's node set from the current selection (skip sliders? no — bbox resize is
  // valid for every kind). Runs after refs commit; also refreshes the box after inspector/keyboard
  // edits move a node from outside a gesture.
  useEffect(() => {
    const tr = trRef.current; if (!tr) return;
    const nodes = selIds.map((id) => nodeRefs.current.get(id)).filter(Boolean) as Konva.Node[];
    tr.nodes(nodes);
    tr.getLayer()?.batchDraw();
  }, [selIds, regions, stagePx]);

  // ── px ↔ normalized helpers (stage px space) ─────────────────────────────────
  const toPx = useCallback((r: SR) => ({ x: r.rect.x * stagePx.w, y: r.rect.y * stagePx.h, w: r.rect.w * stagePx.w, h: r.rect.h * stagePx.h }), [stagePx]);
  const setField = (id: string, patch: Partial<SR>) => setRegions((rs) => rs.map((r) => r.id === id ? { ...r, ...patch } : r));

  // begin a drag/transform gesture: snapshot for undo + capture every region's start rect.
  const beginGesture = useCallback(() => {
    snapshot(); setAuthored(true);
    const m = new Map<string, { x: number; y: number; w: number; h: number }>();
    regions.forEach((r) => m.set(r.id, { ...r.rect }));
    gestureOrigin.current = m;
  }, [snapshot, regions]);
  const endGesture = useCallback(() => {
    setRegions(enforceZeroDiff);
    requestAnimationFrame(() => { trRef.current?.forceUpdate(); trRef.current?.getLayer()?.batchDraw(); });
  }, [enforceZeroDiff]);

  // MOVE — dragging one selected node moves the WHOLE selection by the same normalized delta
  // (other selected nodes follow via their state-driven position props).
  const onRegionDragStart = (id: string) => { if (!selIds.includes(id)) setSelIds([id]); beginGesture(); };
  const onRegionDragMove = (id: string, node: Konva.Rect) => {
    const o = gestureOrigin.current.get(id); if (!o) return;
    const ndx = node.x() / stagePx.w - o.x, ndy = node.y() / stagePx.h - o.y;
    const set = new Set(selIds.includes(id) ? selIds : [id]);
    setRegions((rs) => rs.map((r) => {
      if (!set.has(r.id)) return r;
      const or = gestureOrigin.current.get(r.id) ?? r.rect;
      return { ...r, rect: { ...r.rect, x: clamp01(or.x + ndx, r.rect.w), y: clamp01(or.y + ndy, r.rect.h) } };
    }));
  };

  // RESIZE — read every Transformer node's live box, normalize scale→width, write model. Called
  // live (onTransform) so the visual projection tracks the drag, and on end to settle overlaps.
  const syncTransform = () => {
    const tr = trRef.current; if (!tr) return;
    const active = new Set(tr.nodes());
    setRegions((rs) => rs.map((r) => {
      const node = nodeRefs.current.get(r.id);
      if (!node || !active.has(node)) return r;
      const w = Math.max(MIN_N * stagePx.w, node.width() * node.scaleX());
      const h = Math.max(MIN_N * stagePx.h, node.height() * node.scaleY());
      node.scaleX(1); node.scaleY(1); node.width(w); node.height(h);
      let nx = clamp01(node.x() / stagePx.w), ny = clamp01(node.y() / stagePx.h);
      let nw = Math.max(MIN_N, w / stagePx.w), nh = Math.max(MIN_N, h / stagePx.h);
      nw = Math.min(nw, 1 - nx); nh = Math.min(nh, 1 - ny);
      return { ...r, rect: { x: nx, y: ny, w: nw, h: nh } };
    }));
  };

  // CORNER-RADIUS morph — a handle riding the selected anchor's top edge. Dragging it toward the
  // corner ⇒ corner 0 (sharp), toward centre ⇒ corner 1 (oval). Writes region.corner.
  const onCornerDrag = (id: string, node: Konva.Circle) => {
    const r = regions.find((x) => x.id === id); if (!r) return;
    const b = toPx(r); const maxR = Math.min(b.w, b.h) / 2;
    const inset = Math.max(0, Math.min(maxR, b.x + b.w - node.x()));
    node.y(b.y); node.x(b.x + b.w - inset);   // lock to the top edge
    setField(id, { corner: +(maxR ? inset / maxR : 0).toFixed(3) });
  };

  // ARC sweep — two handles at the partial-circle's start/end angles. Dragging one sets
  // region.arc.start/end from the handle's angle about the arc centre (y-down, matching blueprint).
  const arcGeom = (r: SR) => { const b = toPx(r); const cx = b.x + b.w / 2, cy = b.y + b.h / 2; const rad = (Math.min(b.w, b.h) / 2) * 0.86; return { cx, cy, rad }; };
  const onArcDrag = (id: string, which: "start" | "end", node: Konva.Circle) => {
    const r = regions.find((x) => x.id === id); if (!r) return;
    const { cx, cy, rad } = arcGeom(r);
    const ang = norm360(Math.atan2(node.y() - cy, node.x() - cx) * 180 / Math.PI);
    node.x(cx + rad * Math.cos(ang * Math.PI / 180)); node.y(cy + rad * Math.sin(ang * Math.PI / 180));  // snap to radius
    const cur = r.arc ?? DEF_ARC;
    setField(id, { arc: { ...cur, [which]: Math.round(ang) } });
  };

  const isSliderK = (k?: Kind) => k === "slider-h" || k === "slider-v" || k === "slider-arc";

  // ── MARQUEE multi-select (empty-canvas drag) ─────────────────────────────────
  const onStageMouseDown = (e: Konva.KonvaEventObject<MouseEvent>) => {
    if (e.target !== e.target.getStage()) return;   // started on a node → not a marquee
    const pos = e.target.getStage()!.getPointerPosition(); if (!pos) return;
    marqueeStart.current = pos; marqueeBox.current = { x: pos.x, y: pos.y, w: 0, h: 0 }; setMarquee(marqueeBox.current);
    if (!e.evt.shiftKey) setSelIds([]);   // empty click = deselect
  };
  const onStageMouseMove = (e: Konva.KonvaEventObject<MouseEvent>) => {
    const s = marqueeStart.current; if (!s) return;
    const pos = e.target.getStage()!.getPointerPosition(); if (!pos) return;
    const box = { x: Math.min(s.x, pos.x), y: Math.min(s.y, pos.y), w: Math.abs(pos.x - s.x), h: Math.abs(pos.y - s.y) };
    marqueeBox.current = box; setMarquee(box);
  };
  const onStageMouseUp = () => {
    const m = marqueeBox.current; marqueeStart.current = null; marqueeBox.current = null; setMarquee(null);
    if (!m || m.w < 4 || m.h < 4) return;   // a click, not a drag → selection already cleared
    const box = { x: m.x, y: m.y, width: m.w, height: m.h };
    const hit = regions.filter((r) => { const b = toPx(r); return Konva.Util.haveIntersection(box, { x: b.x, y: b.y, width: b.w, height: b.h }); }).map((r) => r.id);
    setSelIds(hit);
  };

  // ── Konva visual for one region — reproduces the SVG renderShape look (diffuse rounded-rect via
  // corner→radius + shadow, crosshair, slider line/arc track, centroid, bind label) in px space.
  const renderKonvaShape = (r: SR) => {
    const b = toPx(r);
    const cx = b.x + b.w / 2, cy = b.y + b.h / 2;
    const col = colorOf(r);
    const s = Math.min(b.w, b.h);
    const selected = selIds.includes(r.id);
    const corner = Math.max(0, Math.min(1, r.corner ?? 0.5));
    const lw = Math.max(1, s * 0.03), dot = Math.max(2, s * 0.05), tw = Math.max(2, s * 0.08), arm = s * 0.27;
    const fontSize = Math.max(8, s * 0.3);
    const nodes: React.ReactNode[] = [];

    if (r.kind === "slider-h") {
      nodes.push(<Line key="t" points={[b.x + b.w * 0.1, cy, b.x + b.w * 0.9, cy]} stroke={col} strokeWidth={tw} lineCap="round" listening={false} />);
    } else if (r.kind === "slider-v") {
      nodes.push(<Line key="t" points={[cx, b.y + b.h * 0.1, cx, b.y + b.h * 0.9]} stroke={col} strokeWidth={tw} lineCap="round" listening={false} />);
    } else if (r.kind === "slider-arc") {
      const a = r.arc ?? DEF_ARC;
      nodes.push(<Path key="t" data={arcD(cx, cy, (s / 2) * 0.86, a.start, a.end)} stroke={col} strokeWidth={tw} lineCap="round" listening={false} />);
    } else {
      const rw = b.w * 0.88, rh = b.h * 0.88;
      const rr = (Math.min(rw, rh) / 2) * corner;
      nodes.push(
        <Rect key="body" x={cx - rw / 2} y={cy - rh / 2} width={rw} height={rh} cornerRadius={rr}
          fill={col} opacity={0.42} stroke={col} strokeWidth={Math.max(1.5, s * 0.022)}
          shadowColor={col} shadowBlur={s * 0.18} shadowOpacity={0.55} shadowForStrokeEnabled={false}
          perfectDrawEnabled={false} listening={false} />,
        <Line key="ch" points={[cx - arm, cy, cx + arm, cy]} stroke={col} strokeWidth={lw} lineCap="round" opacity={0.9} listening={false} />,
        <Line key="cv" points={[cx, cy - arm, cx, cy + arm]} stroke={col} strokeWidth={lw} lineCap="round" opacity={0.9} listening={false} />,
      );
    }
    nodes.push(<Circle key="dot" x={cx} y={cy} radius={dot} fill={selected ? "#fff" : col} stroke="#000" strokeWidth={2} listening={false} />);
    nodes.push(<Text key="lbl" x={b.x} y={b.y - fontSize * 1.15} width={b.w} align="center" text={(r.bind || r.id).slice(0, 10)} fill={col} fontSize={fontSize} fontStyle="bold" listening={false} />);
    return nodes;
  };

  // SVG renderShape — kept for the READ-ONLY packed Canvas (flagged off) + parity with blueprint.
  const renderShape = (r: SR) => {
    const W = GEN_W, H = GEN_H;
    const x = r.rect.x * W, y = r.rect.y * H, w = r.rect.w * W, h = r.rect.h * H;
    const cx = x + w / 2, cy = y + h / 2;
    const col = colorOf(r);
    const s = Math.min(w, h);
    const isSlider = isSliderK(r.kind);
    const corner = Math.max(0, Math.min(1, r.corner ?? 0.5));
    const fid = `f_${r.id}`;
    const arm = s * 0.27, lw = Math.max(2.5, s * 0.03), dot = Math.max(3, s * 0.05), tw = Math.max(3, s * 0.08);
    const rw = w * 0.88, rh = h * 0.88, rrx = cx - rw / 2, rry = cy - rh / 2;
    const rr = (Math.min(rw, rh) / 2) * corner;
    const shape = r.kind === "slider-h"
      ? <line x1={x + w * 0.1} y1={cy} x2={x + w * 0.9} y2={cy} stroke={col} strokeWidth={tw} strokeLinecap="round" />
      : r.kind === "slider-v"
        ? <line x1={cx} y1={y + h * 0.1} x2={cx} y2={y + h * 0.9} stroke={col} strokeWidth={tw} strokeLinecap="round" />
        : r.kind === "slider-arc"
          ? <path d={arcD(cx, cy, (s / 2) * 0.86, (r.arc ?? DEF_ARC).start, (r.arc ?? DEF_ARC).end)} fill="none" stroke={col} strokeWidth={tw} strokeLinecap="round" />
          : <rect x={rrx} y={rry} width={rw} height={rh} rx={rr} ry={rr} fill={col} fillOpacity={0.38} stroke={col} strokeWidth={Math.max(1.5, s * 0.022)} filter={`url(#${fid})`} />;
    return (
      <g key={r.id}>
        {!isSlider && <filter id={fid} x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation={s * 0.09} /></filter>}
        {shape}
        {!isSlider && <g stroke={col} strokeWidth={lw} strokeLinecap="round" opacity={0.9}>
          <line x1={cx - arm} y1={cy} x2={cx + arm} y2={cy} />
          <line x1={cx} y1={cy - arm} x2={cx} y2={cy + arm} />
        </g>}
        <circle cx={cx} cy={cy} r={dot} fill={col} stroke="#000" strokeWidth={2} />
        <text x={cx} y={y - 6} fill={col} fontSize={26} textAnchor="middle" style={{ pointerEvents: "none", fontWeight: 700 }}>{(r.bind || r.id).slice(0, 10)}</text>
      </g>
    );
  };

  // read-only projection panel (SVG) — used for the packed Canvas.
  const Canvas = ({ regs, title }: { regs: SR[]; title: string }) => (
    <div className="tsCanvas dev">
      <div className="tsCap">{title} <span>({regs.length} regions)</span></div>
      <div className="tsFit">
        <svg className="tsStage" viewBox={`0 0 ${GEN_W} ${GEN_H}`} style={{ pointerEvents: "none" }}>
          {regs.map((r) => renderShape(r))}
        </svg>
      </div>
    </div>
  );

  const selRegion = regions.find((r) => r.id === sel);
  const showCorner = selIds.length === 1 && !!selRegion && !isSliderK(selRegion.kind);
  const showArc = selIds.length === 1 && !!selRegion && selRegion.kind === "slider-arc";

  // EDITABLE stage — a react-konva scene graph. Visual nodes (listening:false) draw the look; an
  // invisible per-region Rect is the interactive drag/transform target; a Transformer supplies the
  // resize anchors; custom handles drive corner-radius + arc sweep; a marquee Rect does box-select.
  const cornerHandle = (() => {
    if (!showCorner || !selRegion) return null;
    const b = toPx(selRegion); const maxR = Math.min(b.w, b.h) / 2;
    const inset = Math.max(0, Math.min(1, selRegion.corner ?? 0.5)) * maxR;
    return (
      <Circle x={b.x + b.w - inset} y={b.y} radius={7} fill="#7fe0a0" stroke="#0c0c10" strokeWidth={2} draggable
        dragBoundFunc={(pos) => ({ x: Math.max(b.x + b.w - maxR, Math.min(b.x + b.w, pos.x)), y: b.y })}
        onMouseEnter={(e) => (e.target.getStage()!.container().style.cursor = "ew-resize")}
        onMouseLeave={(e) => (e.target.getStage()!.container().style.cursor = "default")}
        onDragStart={snapshot}
        onDragMove={(e) => onCornerDrag(selRegion.id, e.target as Konva.Circle)}
        onDragEnd={() => setAuthored(true)} />
    );
  })();
  const arcHandles = (() => {
    if (!showArc || !selRegion) return null;
    const { cx, cy, rad } = arcGeom(selRegion); const a = selRegion.arc ?? DEF_ARC;
    const pt = (deg: number) => ({ x: cx + rad * Math.cos(deg * Math.PI / 180), y: cy + rad * Math.sin(deg * Math.PI / 180) });
    const mk = (which: "start" | "end", deg: number) => {
      const p = pt(deg);
      return (
        <Circle key={which} x={p.x} y={p.y} radius={8} fill={which === "start" ? "#7fe0a0" : "#e0a07f"} stroke="#0c0c10" strokeWidth={2} draggable
          onMouseEnter={(e) => (e.target.getStage()!.container().style.cursor = "grab")}
          onMouseLeave={(e) => (e.target.getStage()!.container().style.cursor = "default")}
          onDragStart={snapshot}
          onDragMove={(e) => onArcDrag(selRegion.id, which, e.target as Konva.Circle)}
          onDragEnd={() => setAuthored(true)} />
      );
    };
    return <>{mk("start", a.start)}{mk("end", a.end)}</>;
  })();

  const editableStage = (
    <div className="tsCanvas dev">
      <div className="tsCap">RAW template (seed / edit) <span>({regions.length} regions · react-konva)</span></div>
      <div className="tsFit">
        <div className="tsStageWrap" ref={stageWrapRef}>
          {stagePx.w > 1 && (
            <Stage width={stagePx.w} height={stagePx.h}
              onMouseDown={onStageMouseDown} onMouseMove={onStageMouseMove} onMouseUp={onStageMouseUp}
              onTouchStart={onStageMouseDown as unknown as (e: Konva.KonvaEventObject<TouchEvent>) => void}
              style={{ borderRadius: 10 }}>
              <Layer ref={layerRef}>
                {/* visual projection of the model */}
                {regions.map((r) => <Fragment key={r.id}>{renderKonvaShape(r)}</Fragment>)}
                {/* invisible interactive targets (opacity 0 but hit-testable) */}
                {regions.map((r) => {
                  const b = toPx(r);
                  return (
                    <Rect key={r.id} ref={(n) => { if (n) nodeRefs.current.set(r.id, n); else nodeRefs.current.delete(r.id); }}
                      x={b.x} y={b.y} width={b.w} height={b.h} fill="#fff" opacity={0} draggable
                      onMouseEnter={(e) => (e.target.getStage()!.container().style.cursor = "grab")}
                      onMouseLeave={(e) => (e.target.getStage()!.container().style.cursor = "default")}
                      onClick={(e) => { const add = e.evt.shiftKey; setSelIds((p) => add ? (p.includes(r.id) ? p.filter((x) => x !== r.id) : [...p, r.id]) : [r.id]); e.cancelBubble = true; }}
                      onTap={() => setSelIds([r.id])}
                      onDragStart={() => onRegionDragStart(r.id)}
                      onDragMove={(e) => onRegionDragMove(r.id, e.target as Konva.Rect)}
                      onDragEnd={endGesture} />
                  );
                })}
                <Transformer ref={trRef} rotateEnabled={false} keepRatio={false} ignoreStroke flipEnabled={false}
                  borderStroke="#fff" borderDash={[7, 5]} anchorStroke="#7fe0a0" anchorFill="#0c0c10" anchorSize={9} borderStrokeWidth={1.5}
                  boundBoxFunc={(oldB, newB) => (newB.width < MIN_N * stagePx.w || newB.height < MIN_N * stagePx.h ? oldB : newB)}
                  onTransformStart={beginGesture} onTransform={syncTransform} onTransformEnd={() => { syncTransform(); endGesture(); }} />
                {cornerHandle}
                {arcHandles}
                {marquee && <Rect x={marquee.x} y={marquee.y} width={marquee.w} height={marquee.h} fill="rgba(127,224,160,0.12)" stroke="#7fe0a0" strokeWidth={1} dash={[4, 4]} listening={false} />}
              </Layer>
            </Stage>
          )}
        </div>
      </div>
    </div>
  );

  const selR = regions.find((r) => r.id === sel);
  const sl = (label: string, key: keyof Params, min: number, max: number, step = 0.05) => (
    <label style={{ display: "flex", flexDirection: "column", fontSize: 12, color: "#b8b8c4", gap: 2 }}>
      {label} <b style={{ color: "#7fe0a0" }}>{(P[key] as number).toFixed(2)}</b>
      <input type="range" min={min} max={max} step={step} value={P[key] as number} onChange={(e) => setP({ ...P, [key]: +e.target.value })} />
    </label>
  );
  const btn: React.CSSProperties = { background: "#1c1c26", color: "#e8e8ee", border: "1px solid #33333f", borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontSize: 13 };

  return (
    <div className="tsRoot">
      <style>{`
        .tsRoot{position:fixed;inset:0;display:grid;grid-template-columns:218px minmax(0,1fr) 236px;grid-template-rows:auto minmax(0,1fr) auto;background:#0c0c10;color:#e8e8ee;font:14px system-ui,sans-serif}
        .tsHead{grid-column:1/-1;display:flex;align-items:baseline;gap:12px;padding:7px 14px;border-bottom:1px solid #1e1e26;flex-wrap:wrap}
        .tsHead h1{font-size:16px;margin:0}
        .tsHead span{color:#8a8a96;font-size:11.5px}
        .tsLeft{overflow-y:auto;min-height:0;padding:10px;border-right:1px solid #1e1e26;display:flex;flex-direction:column;gap:10px}
        .tsMain{display:flex;gap:12px;padding:8px 12px;min-width:0;min-height:0;justify-content:center;align-items:stretch;overflow-x:auto;overflow-y:hidden}
        .tsRight{overflow-y:auto;min-height:0;padding:10px;border-left:1px solid #1e1e26;display:flex;flex-direction:column;gap:8px}
        .tsFoot{grid-column:1/-1;display:flex;flex-direction:column;gap:6px;padding:6px 14px;border-top:1px solid #1e1e26}
        .tsCmd{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
        .tsPrompt{max-height:118px;overflow:auto;background:#0b0b11;border:1px solid #26262f;border-radius:8px;padding:4px 10px}
        .tsCanvas{display:flex;flex-direction:column;min-width:0;min-height:0;gap:4px;flex:0 0 auto}
        .tsCanvas.dev{width:min(94vw,calc((100vh - 240px) * ${(GEN_W / GEN_H).toFixed(4)}))}
        .tsCanvas.bp{width:min(94vw,calc((100vh - 240px) * ${(GEN_W / 1820).toFixed(4)}))}
        .tsFit{flex:1;min-height:0;display:grid;place-items:center;overflow:hidden}
        .tsCap{color:#cfcfe0;font-weight:600;font-size:12.5px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .tsCap span{color:#8a8a96;font-weight:400;font-size:11px}
        .tsStage{width:100%;aspect-ratio:${GEN_W}/${GEN_H};background:#15151c;border:1px solid #2a2a34;border-radius:10px;touch-action:none}
        /* editable stage: the Konva Stage fills this box; aspect-ratio holds the 1024/1536 shape */
        .tsStageWrap{position:relative;width:100%;aspect-ratio:${GEN_W}/${GEN_H};background:#15151c;border:1px solid #2a2a34;border-radius:10px;touch-action:none;overflow:hidden}
        .tsBP{width:100%;aspect-ratio:${GEN_W}/1820;position:relative;border-radius:10px;overflow:hidden;border:1px solid #2a2a34}
        .tsBP svg{display:block;width:100%;height:100%}
        @media (max-width:1020px){
          .tsRoot{position:static;height:auto;grid-template-columns:1fr;grid-template-rows:auto}
          .tsMain{flex-wrap:wrap;overflow:visible}
          .tsCanvas.dev,.tsCanvas.bp{width:min(96vw,440px)}
          .tsLeft,.tsRight{border:0}
        }
      `}</style>

      <header className="tsHead">
        <h1>Template Studio</h1>
        <span>seed / generate a DATA template → live pack → combined blueprint · real shipping heuristics (layoutRandomP · repackTemplate · combinedBlueprint · deriveLayout) · editable stage = react-konva</span>
      </header>

      {/* LEFT — generators + heuristic params */}
      <aside className="tsLeft">
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button style={btn} onClick={randomize}>🎲 Randomize</button>
          <button style={btn} onClick={addComp}>＋ Component</button>
        </div>
        <div style={{ fontSize: 12, color: "#8a8a96" }}>Archetype (heuristic):</div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {ARCHETYPES.map((a) => <button key={a} style={{ ...btn, padding: "3px 7px", fontSize: 11 }} onClick={() => archGen(a)}>{a}</button>)}
        </div>
        <div style={{ borderTop: "1px solid #26262f", paddingTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          {sl("density", "density", 0, 1)}{sl("symmetry", "symmetry", 0, 1)}{sl("hierarchy", "hierarchy", 0, 1)}{sl("gapScale", "gapScale", 0.5, 3, 0.1)}{sl("spacing", "spacing", 0, 0.08, 0.005)}
        </div>
        <div style={{ marginTop: "auto", fontSize: 11, color: "#66666f", borderTop: "1px solid #26262f", paddingTop: 8 }}>
          Drag to move · corner/edge anchors resize · green handle morphs corner · arc handles sweep a slider-arc · marquee to multi-select.
        </div>
      </aside>

      {/* CENTER — everything at once: raw (editable konva), packed, combined blueprint */}
      <main className="tsMain">
        {editableStage}
        {REPACK_ENABLED && <Canvas regs={packed} title="PACKED (repack)" />}
        {combined && (
          <div className="tsCanvas bp">
            <div className="tsCap" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>COMBINED blueprint <span>(device + {combined.layout.cells.length} sprite cells)</span></span>
              <button onClick={() => setShowOverlays((v) => !v)} title="toggle studio overlays — the bind labels + divider are annotations, NOT part of the image sent to FAL"
                style={{ marginLeft: "auto", flex: "0 0 auto", background: showOverlays ? "#243524" : "#15151c", color: showOverlays ? "#7fe0a0" : "#8a8a96", border: "1px solid #2a2a34", borderRadius: 5, padding: "1px 7px", cursor: "pointer", fontSize: 10, fontWeight: 600, whiteSpace: "nowrap" }}>
                {showOverlays ? "◉" : "◯"} overlays
              </button>
            </div>
            <div className="tsFit"><div className="tsBP">
              <div style={{ position: "absolute", inset: 0, lineHeight: 0 }} dangerouslySetInnerHTML={{ __html: combined.svg.replace(/width="\d+" height="\d+"/, 'width="100%" height="100%"') }} />
              {showOverlays && (
                <>
                  <div style={{ position: "absolute", top: 4, left: 4, zIndex: 2, background: "rgba(10,10,16,.72)", color: "#7fe0a0", fontSize: 8.5, fontWeight: 700, padding: "1px 5px", borderRadius: 4, pointerEvents: "none" }}>◉ studio overlay · not in image → FAL</div>
                  {combined.layout.cells.map((c) => (
                    <div key={c.bind} style={{ position: "absolute", left: `${c.cellRect[0] * 100}%`, top: `${c.cellRect[1] * 100}%`, width: `${c.cellRect[2] * 100}%`, height: `${c.cellRect[3] * 100}%`, display: "flex", alignItems: "flex-end", justifyContent: "center", pointerEvents: "none", color: "#0a8f4d", font: "700 10px ui-monospace,monospace", textShadow: "0 1px 0 rgba(255,255,255,.5)" }}>{c.bind}</div>
                  ))}
                  <div style={{ position: "absolute", left: 0, right: 0, top: `${combined.layout.devFrac * 100}%`, borderTop: "2px dashed rgba(0,0,0,.45)", color: "rgba(0,0,0,.55)", fontSize: 10, paddingLeft: 4, pointerEvents: "none" }}>sprite strip ↓</div>
                </>
              )}
            </div></div>
          </div>
        )}
        {/* 4th section — click to paint the current template via the FAL API */}
        <PaintedSheet regions={packed as Region[]} prompt={prompt} />
      </main>

      {/* RIGHT — components list + inspector */}
      <aside className="tsRight">
        <div style={{ color: "#cfcfe0", fontWeight: 600 }}>Components <span style={{ color: "#8a8a96", fontWeight: 400, fontSize: 12 }}>({regions.length})</span></div>
        <div style={{ flex: "1 1 120px", minHeight: 90, overflowY: "auto", border: "1px solid #26262f", borderRadius: 8 }}>
          {regions.map((r) => (
            <div key={r.id} onClick={() => setSelIds([r.id])}
              style={{ display: "flex", gap: 6, alignItems: "center", padding: "4px 8px", fontSize: 12, cursor: "pointer", background: sel === r.id ? "#242432" : "transparent", color: "#c8c8d2" }}>
              <span style={{ width: 9, height: 9, borderRadius: "50%", background: colorOf(r), flex: "0 0 auto" }} />
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.bind || r.id}</span>
            </div>
          ))}
        </div>
        <div style={{ color: "#cfcfe0", fontWeight: 600 }}>Inspector</div>
        {selR ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12, color: "#b8b8c4" }}>
            <div>id <b style={{ color: "#e8e8ee" }}>{selR.id}</b></div>
            <label>kind<select value={selR.kind} onChange={(e) => patchSel({ kind: e.target.value as Kind })} style={{ width: "100%", background: "#15151c", color: "#fff", border: "1px solid #2a2a34", borderRadius: 6, padding: 4 }}>{KINDS.map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
            <label>bind <span style={{ color: "#66666f", fontSize: 10 }}>(Spotify-drivable only)</span>
              <select value={selR.bind || ""} onChange={(e) => patchSel({ bind: e.target.value })} style={{ width: "100%", background: "#15151c", color: "#fff", border: "1px solid #2a2a34", borderRadius: 6, padding: 4 }}>
                {(SPOTIFY_BINDS.includes(selR.bind || "") ? SPOTIFY_BINDS : [selR.bind || "", ...SPOTIFY_BINDS]).map((b) => <option key={b} value={b}>{b || "—"}</option>)}
              </select></label>
            <label>size <input type="range" min={0.03} max={0.4} step={0.01} value={selR.rect.w} onChange={(e) => { const w = +e.target.value; patchSel({ rect: { ...selR.rect, w, h: w * 0.7 } }); }} style={{ width: "100%" }} /></label>
            {!isSliderK(selR.kind) && (
              <label>corner (rect ↔ oval) <b style={{ color: "#7fe0a0" }}>{(selR.corner ?? 0.5).toFixed(2)}</b>
                <input type="range" min={0} max={1} step={0.02} value={selR.corner ?? 0.5} onChange={(e) => patchSel({ corner: +e.target.value })} style={{ width: "100%" }} /></label>
            )}
            {selR.kind === "slider-arc" && (() => {
              const arc = selR.arc ?? DEF_ARC;
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 6, borderTop: "1px solid #26262f", paddingTop: 6 }}>
                  <div style={{ fontSize: 11, color: "#8a8a96" }}>partial-circle arc — drag the on-canvas handles or sweep here</div>
                  <label>start <b style={{ color: "#7fe0a0" }}>{arc.start}°</b>
                    <input type="range" min={0} max={360} step={1} value={arc.start} onChange={(e) => patchSel({ arc: { ...arc, start: +e.target.value } })} style={{ width: "100%" }} /></label>
                  <label>end <b style={{ color: "#e0a07f" }}>{arc.end}°</b>
                    <input type="range" min={0} max={360} step={1} value={arc.end} onChange={(e) => patchSel({ arc: { ...arc, end: +e.target.value } })} style={{ width: "100%" }} /></label>
                </div>
              );
            })()}
            <button style={{ ...btn, background: "#3a1c1c", borderColor: "#5a2a2a" }} onClick={delSel}>🗑 Delete</button>
          </div>
        ) : <div style={{ color: "#8a8a96", fontSize: 12 }}>Click a component (in the list or on canvas) to edit kind, bind, or size. Marquee-drag on empty canvas to multi-select.</div>}
      </aside>

      {/* BOTTOM — LLM command bar + shortcuts */}
      <footer className="tsFoot">
        <div className="tsCmd">
          <span style={{ fontSize: 13 }}>🧠</span>
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="LLM theme — e.g. a wild organic Y2K Winamp media player"
            onKeyDown={(e) => { if (e.key === "Enter") void llmGen(); }}
            style={{ flex: "1 1 260px", maxWidth: 560, background: "#15151c", color: "#e8e8ee", border: "1px solid #2a2a34", borderRadius: 6, padding: "5px 9px", fontSize: 12 }} />
          <button style={btn} onClick={llmGen}>Generate (deriveLayout)</button>
          <span style={{ fontSize: 11, color: "#8a8a96" }}>{llmMsg}</span>
          <span style={{ marginLeft: "auto", fontSize: 11, color: "#66666f" }}>⌫ delete · arrows nudge (⇧ coarse) · esc deselect · ⌘Z undo · ⇧⌘Z redo</span>
        </div>
        {combined && (
          <div className="tsPrompt">
            <div style={{ fontSize: 10, color: "#8a8a96", fontWeight: 600, marginBottom: 2 }}>text prompt → FAL <span style={{ color: "#66666f", fontWeight: 400 }}>(sent with the blueprint image · {promptPreview.length.toLocaleString()} chars)</span></div>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 10, lineHeight: 1.4, color: "#c2c2ce", fontFamily: "ui-monospace,SFMono-Regular,monospace" }}>{promptPreview}</pre>
          </div>
        )}
      </footer>
    </div>
  );
}
