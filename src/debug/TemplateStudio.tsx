// DEV-ONLY Template Studio (?studio). A human-facing interface to SEED / GENERATE a data
// template and see it PACKED live — all on the REAL shipping heuristics:
//   • cheap heuristic randomizer  → layoutRandomP / layoutArch (the 10 archetypes)
//   • LLM data-template generator → deriveLayout via POST /api/derive (heuristic-guided prompt)
//   • packer                      → repackTemplate (canon-size + resolveOverlaps), live
// Each component has a CENTROID (draggable), an ARBITRARY SHAPE connected to it, and a modular
// DIFFUSENESS (soft-guide spread). Left = raw seeded template, right = packed result.
//
// INTERACTION LAYER — pure SVG + @use-gesture/react (Approach C, bake-off).
//   The OLD hand-roll was flaky because it split the pointer lifecycle: setPointerCapture on a
//   CHILD handle while onPointerMove sat on the SVG ROOT (capture retargeted pointermove to the
//   captured child so the root handler never fired), and a selection onClick raced the drag-start
//   onPointerDown. The (interim) fix was a react-moveable + react-selecto HTML overlay.
//   This version REMOVES both libraries and instead binds a `useDrag` PRIMITIVE to each SVG
//   handle/body directly — use-gesture owns the whole pointerdown→move→up lifecycle on that exact
//   element, so there is no root/child split, no capture retarget, and no click/drag race
//   (filterTaps distinguishes a click from a drag). Handles are bespoke SVG tailored to our
//   controls (esp. the on-canvas arc start/end/radius handles — no library models that need).
import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { useDrag } from "@use-gesture/react";
import {
  layoutRandomP, layoutArch, bakeButtons, ARCHETYPES, DEFAULT_PARAMS, SPOTIFY_BINDS,
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
const SNAP_PX = 7;              // pixel threshold for edge/center snapping to sibling controls
// SVG arc 'd' matching blueprint.ts arcPath (same large-arc/sweep rules) so a slider-arc reads
// IDENTICALLY in the studio panels and the combined blueprint.
const arcD = (cx: number, cy: number, r: number, a0: number, a1: number): string => {
  const p = (a: number): [number, number] => [cx + r * Math.cos((a * Math.PI) / 180), cy + r * Math.sin((a * Math.PI) / 180)];
  const [sx, sy] = p(a0), [ex, ey] = p(a1);
  const large = ((a1 - a0) % 360 + 360) % 360 > 180 ? 1 : 0;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`;
};
const clampPos = (v: number, size: number) => Math.max(0, Math.min(1 - size, v));
const rectsIntersect = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) =>
  a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
type Rect = { x: number; y: number; w: number; h: number };


export default function TemplateStudio() {
  const [P, setP] = useState<Params>({ ...DEFAULT_PARAMS });
  const [regions, setRegions] = useState<SR[]>(() => layoutArch("console", DEFAULT_PARAMS) as SR[]);
  // SELECTION — a set (click + marquee multi-select). `sel` is the PRIMARY (last-added) selection
  // the inspector/keyboard/handles operate on.
  const [selIds, setSelIds] = useState<string[]>([]);
  const sel = selIds.length ? selIds[selIds.length - 1] : null;
  const [showOverlays, setShowOverlays] = useState(false);  // studio annotations on the blueprint — OFF by default (see the exact image sent to FAL); toggle on to label cells
  const globalDiff = 0;   // diffuseness disabled for now — anchors are crisp
  const [prompt, setPrompt] = useState("a wild organic Y2K Winamp media player");
  const [llmMsg, setLlmMsg] = useState("");
  // Live displayed pixel box of the editable SVG stage — for px(movement)→normalized conversion.
  const svgRef = useRef<SVGSVGElement>(null);
  const [stagePx, setStagePx] = useState({ w: 1, h: 1 });
  // Transient marquee rect (SVG user units) while a background drag is in progress.
  const [marquee, setMarquee] = useState<Rect | null>(null);
  // Snap guide lines (SVG user units) surfaced while dragging — [orientation, coordinate].
  const [guides, setGuides] = useState<{ v: number[]; h: number[] }>({ v: [], h: [] });
  // human-authored flag: once the human edits (drag/add/patch/nudge), the packer becomes a
  // PASS-THROUGH — packing must not rearrange a human-authored template. Generators reset it.
  const [, setAuthored] = useState(false);   // human-edit flag (setter kept; value unused while repack is off)

  // undo/redo history — normal expected editor UX (⌘Z / ⇧⌘Z). Snapshots on every discrete
  // mutation (and at the FIRST MOVE of a drag, so a whole drag undoes as one step and a bare
  // click never consumes an undo step).
  const past = useRef<SR[][]>([]); const future = useRef<SR[][]>([]);
  const mutate = useCallback((updater: (rs: SR[]) => SR[]) => setRegions((rs) => {
    past.current.push(rs); if (past.current.length > 60) past.current.shift();
    future.current = []; return updater(rs);
  }), []);
  const snapshot = useCallback(() => setRegions((rs) => { past.current.push(rs); if (past.current.length > 60) past.current.shift(); future.current = []; return rs; }), []);
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

  const patchSel = (patch: Partial<SR>) => { setAuthored(true); mutate((rs) => rs.map((r) => r.id === sel ? { ...r, ...patch } : r)); };
  const delSel = useCallback(() => {
    setSelIds((ids) => { if (ids.length) { setAuthored(true); mutate((rs) => rs.filter((r) => !ids.includes(r.id))); } return []; });
  }, [mutate]);
  const addComp = () => {
    const id = "c" + Math.random().toString(36).slice(2, 6);
    setAuthored(true);
    mutate((rs) => [...rs, { id, kind: "button", content: "sprite", layer: "components", bind: id, rect: { x: 0.44, y: 0.44, w: 0.12, h: 0.08 }, shapeKind: "auto", diff: globalDiff } as SR]);
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
        mutate((rs) => rs.map((r) => selIds.includes(r.id) ? { ...r, rect: { ...r.rect, x: Math.max(0, Math.min(1 - r.rect.w, r.rect.x + dx)), y: Math.max(0, Math.min(1 - r.rect.h, r.rect.y + dy)) } } : r));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selIds, mutate, undo, redo, delSel]);

  // Track the editable SVG stage's live displayed pixel box (movement→normalized conversion).
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const measure = () => { const b = el.getBoundingClientRect(); if (b.width && b.height) setStagePx({ w: b.width, h: b.height }); };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Convert a client (screen) point to SVG user coordinates (0..GEN_W × 0..GEN_H). The viewBox
  // aspect matches the CSS aspect-ratio exactly, so there is no letterboxing to correct.
  const clientToSvg = useCallback((cx: number, cy: number) => {
    const svg = svgRef.current; if (!svg) return { x: 0, y: 0 };
    const m = svg.getScreenCTM(); if (!m) return { x: 0, y: 0 };
    const p = svg.createSVGPoint(); p.x = cx; p.y = cy;
    const r = p.matrixTransform(m.inverse());
    return { x: r.x, y: r.y };
  }, []);
  const commitEdit = useCallback(() => { setAuthored(true); setGuides({ v: [], h: [] }); }, []);
  const isSliderK = (k?: Kind) => k === "slider-h" || k === "slider-v" || k === "slider-arc";

  // ── SNAP: nudge a moving rect's edges/centers onto sibling controls' edges/centers. Operates
  // in NORMALIZED space; the threshold is expressed in px and converted. Returns the snapped
  // top-left + the guide lines (SVG units) to draw. Move-only (resize keeps its own clamp). ──
  const snapMove = useCallback((movingIds: string[], nx: number, ny: number, w: number, h: number): { x: number; y: number; gv: number[]; gh: number[] } => {
    const tx = SNAP_PX / stagePx.w, ty = SNAP_PX / stagePx.h;
    const others = regions.filter((r) => !movingIds.includes(r.id));
    const gv: number[] = [], gh: number[] = [];
    // candidate X anchors on the moving rect: left, center, right
    const xCands = [{ v: nx, off: 0 }, { v: nx + w / 2, off: w / 2 }, { v: nx + w, off: w }];
    const yCands = [{ v: ny, off: 0 }, { v: ny + h / 2, off: h / 2 }, { v: ny + h, off: h }];
    let bestX: { d: number; x: number; line: number } | null = null;
    let bestY: { d: number; y: number; line: number } | null = null;
    for (const o of others) {
      const oxs = [o.rect.x, o.rect.x + o.rect.w / 2, o.rect.x + o.rect.w];
      const oys = [o.rect.y, o.rect.y + o.rect.h / 2, o.rect.y + o.rect.h];
      for (const c of xCands) for (const ox of oxs) { const d = Math.abs(c.v - ox); if (d < tx && (!bestX || d < bestX.d)) bestX = { d, x: ox - c.off, line: ox }; }
      for (const c of yCands) for (const oy of oys) { const d = Math.abs(c.v - oy); if (d < ty && (!bestY || d < bestY.d)) bestY = { d, y: oy - c.off, line: oy }; }
    }
    if (bestX) { nx = bestX.x; gv.push(bestX.line * GEN_W); }
    if (bestY) { ny = bestY.y; gh.push(bestY.line * GEN_H); }
    return { x: nx, y: ny, gv, gh };
  }, [regions, stagePx]);

  // ── MOVE: bind per region body. One drag = one undo step (snapshot on first real move).
  //    A bare click (no movement past filterTaps' 3px) just (re)selects. ──
  type MoveMemo = { ids: string[]; starts: Map<string, Rect>; snapped: boolean };
  const bindBody = useDrag(({ args, first, last, movement: [mx, my], memo, event, shiftKey }) => {
    const id = args[0] as string;
    let m = memo as MoveMemo | undefined;
    if (first) {
      const prev = selIds;
      let ids: string[];
      if (shiftKey) ids = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      else ids = prev.includes(id) ? prev : [id];
      setSelIds(ids);
      const starts = new Map<string, Rect>();
      regions.forEach((r) => { if (ids.includes(r.id)) starts.set(r.id, { ...r.rect }); });
      m = { ids, starts, snapped: false };
    }
    if (!m) return m;
    (event as PointerEvent)?.stopPropagation?.();
    const moved = Math.hypot(mx, my) > 3;
    if (moved && !m.snapped) { snapshot(); m.snapped = true; }
    if (moved) {
      const dnx = mx / stagePx.w, dny = my / stagePx.h;
      // snap using the PRIMARY moving rect; apply the same corrective delta to the whole group.
      const prim = m.starts.get(m.ids[m.ids.length - 1])!;
      const rawX = clampPos(prim.x + dnx, prim.w), rawY = clampPos(prim.y + dny, prim.h);
      const s = m.ids.length === 1 ? snapMove(m.ids, rawX, rawY, prim.w, prim.h) : { x: rawX, y: rawY, gv: [], gh: [] };
      const adjX = s.x - prim.x, adjY = s.y - prim.y;
      setGuides({ v: s.gv, h: s.gh });
      setRegions((rs) => rs.map((r) => {
        const st = m!.starts.get(r.id); if (!st) return r;
        return { ...r, rect: { ...r.rect, x: clampPos(st.x + adjX, st.w), y: clampPos(st.y + adjY, st.h) } };
      }));
    }
    if (last && m.snapped) commitEdit();
    return m;
  }, { filterTaps: false });

  // ── RESIZE: 8 bbox handles (corners + edges) for a SINGLE selection; opposite side stays put,
  //    clamped to [0,1] with a min size. ──
  type RszMemo = Rect;
  const bindHandle = useDrag(({ args, first, last, movement: [mx, my], memo, event }) => {
    const hd = args[0] as string;
    const id = sel; if (!id) return memo;
    (event as PointerEvent)?.stopPropagation?.();
    let m = memo as RszMemo | undefined;
    if (first) { snapshot(); const r = regions.find((x) => x.id === id); if (!r) return memo; m = { ...r.rect }; }
    if (!m) return m;
    const dnx = mx / stagePx.w, dny = my / stagePx.h;
    let x = m.x, y = m.y, w = m.w, h = m.h;
    if (hd.includes("w")) { const right = m.x + m.w; x = Math.min(m.x + dnx, right - MIN_N); x = Math.max(0, x); w = right - x; }
    if (hd.includes("e")) { w = Math.max(MIN_N, m.w + dnx); w = Math.min(w, 1 - x); }
    if (hd.includes("n")) { const bottom = m.y + m.h; y = Math.min(m.y + dny, bottom - MIN_N); y = Math.max(0, y); h = bottom - y; }
    if (hd.includes("s")) { h = Math.max(MIN_N, m.h + dny); h = Math.min(h, 1 - y); }
    setRegions((rs) => rs.map((r) => r.id === id ? ({ ...r, rect: { x, y, w, h } }) as SR : r));
    if (last) commitEdit();
    return m;
  }, { filterTaps: false });

  // ── CORNER-RADIUS (Illustrator live-corner): a handle sitting at the tangent point on the top
  //    edge where the rounding begins. Drag it toward center-x → bigger radius → oval; back to
  //    the corner → sharp rect. Maps the handle's inset (px) to region.corner 0..1. ──
  type CornMemo = { c: number; maxRpx: number };
  const bindCorner = useDrag(({ first, last, movement: [mx], memo, event }) => {
    const id = sel; if (!id) return memo;
    (event as PointerEvent)?.stopPropagation?.();
    let m = memo as CornMemo | undefined;
    if (first) {
      snapshot();
      const r = regions.find((x) => x.id === id); if (!r) return memo;
      const maxRpx = Math.min(r.rect.w * 0.88 * stagePx.w, r.rect.h * 0.88 * stagePx.h) / 2;
      m = { c: r.corner ?? 0.5, maxRpx: Math.max(1, maxRpx) };
    }
    if (!m) return m;
    const c = Math.max(0, Math.min(1, m.c + mx / m.maxRpx));
    setRegions((rs) => rs.map((r) => r.id === id ? ({ ...r, corner: +c.toFixed(3) }) as SR : r));
    if (last) setAuthored(true);
    return m;
  }, { filterTaps: false });

  // ── ARC (slider-arc): draggable start-angle, end-angle, and radius handles on-canvas — the
  //    tactile partial-circle authoring this approach makes the best-of-three. Angle from
  //    atan2 about the arc center (SVG coords, y-down); radius scales the region rect. ──
  type ArcMemo = Rect;
  const bindArc = useDrag(({ args, first, last, xy: [px, py], memo, event }) => {
    const which = args[0] as "start" | "end" | "radius";
    const id = sel; if (!id) return memo;
    (event as PointerEvent)?.stopPropagation?.();
    let m = memo as ArcMemo | undefined;
    const r = regions.find((x) => x.id === id); if (!r) return memo;
    if (first) { snapshot(); m = { ...r.rect }; }
    if (!m) return m;
    const pt = clientToSvg(px, py);
    const cx = (m.x + m.w / 2) * GEN_W, cy = (m.y + m.h / 2) * GEN_H;
    if (which === "radius") {
      const R = Math.hypot(pt.x - cx, pt.y - cy);
      const oldR = (Math.min(m.w * GEN_W, m.h * GEN_H) / 2) * 0.86;
      const f = Math.max(0.25, R / Math.max(1, oldR));
      let nw = Math.min(0.9, m.w * f), nh = Math.min(0.9, m.h * f);
      const nx = clampPos((m.x + m.w / 2) - nw / 2, nw), ny = clampPos((m.y + m.h / 2) - nh / 2, nh);
      setRegions((rs) => rs.map((rr) => rr.id === id ? ({ ...rr, rect: { x: nx, y: ny, w: nw, h: nh } }) as SR : rr));
    } else {
      let deg = Math.atan2(pt.y - cy, pt.x - cx) * 180 / Math.PI;
      if (deg < 0) deg += 360;
      setRegions((rs) => rs.map((rr) => rr.id === id ? ({ ...rr, arc: { ...(rr.arc ?? DEF_ARC), [which]: Math.round(deg) } }) as SR : rr));
    }
    if (last) setAuthored(true);
    return m;
  }, { filterTaps: false });

  // ── MARQUEE: drag on the empty background → selection rect → all intersecting regions. A bare
  //    click (no drag) on the background clears the selection. ──
  const bindMarquee = useDrag(({ first, last, initial: [ix, iy], xy: [px, py], memo, shiftKey }) => {
    let m = memo as { x: number; y: number } | undefined;
    if (first) { m = clientToSvg(ix, iy); if (!shiftKey) setSelIds([]); }
    if (!m) return m;
    const p1 = clientToSvg(px, py);
    const rx = Math.min(m.x, p1.x), ry = Math.min(m.y, p1.y), rw = Math.abs(p1.x - m.x), rh = Math.abs(p1.y - m.y);
    setMarquee({ x: rx, y: ry, w: rw, h: rh });
    if (last) {
      setMarquee(null);
      if (rw > 5 || rh > 5) {
        const box = { x: rx / GEN_W, y: ry / GEN_H, w: rw / GEN_W, h: rh / GEN_H };
        const hit = regions.filter((r) => rectsIntersect(r.rect, box)).map((r) => r.id);
        setSelIds((prev) => shiftKey ? Array.from(new Set([...prev, ...hit])) : hit);
      } else if (!shiftKey) setSelIds([]);
    }
    return m;
  }, { filterTaps: false });

  // Visual shape for a region (bodies drawn here; interaction handles drawn separately on top).
  const renderShape = (r: SR) => {
    const W = GEN_W, H = GEN_H;
    const x = r.rect.x * W, y = r.rect.y * H, w = r.rect.w * W, h = r.rect.h * H;
    const cx = x + w / 2, cy = y + h / 2;
    const col = colorOf(r);
    const s = Math.min(w, h);
    const selected = selIds.includes(r.id);
    const isSlider = r.kind === "slider-h" || r.kind === "slider-v" || r.kind === "slider-arc";
    const corner = Math.max(0, Math.min(1, r.corner ?? 0.5));   // 0 = rect · 1 = oval
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
      <>
        {!isSlider && <filter id={fid} x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation={s * 0.09} /></filter>}
        {shape}
        {!isSlider && <g stroke={col} strokeWidth={lw} strokeLinecap="round" opacity={0.9} style={{ pointerEvents: "none" }}>
          <line x1={cx - arm} y1={cy} x2={cx + arm} y2={cy} />
          <line x1={cx} y1={cy - arm} x2={cx} y2={cy + arm} />
        </g>}
        {selected && <rect x={x} y={y} width={w} height={h} fill="none" stroke="#fff" strokeWidth={2} strokeDasharray="7 5" opacity={0.55} style={{ pointerEvents: "none" }} />}
        <circle cx={cx} cy={cy} r={dot} fill={selected ? "#fff" : col} stroke="#000" strokeWidth={2} style={{ pointerEvents: "none" }} />
        <text x={cx} y={y - 6} fill={col} fontSize={26} textAnchor="middle" style={{ pointerEvents: "none", fontWeight: 700 }}>{(r.bind || r.id).slice(0, 10)}</text>
      </>
    );
  };

  // Read-only projection panel (packed / other views) — pure visual, no interaction.
  const Canvas = ({ regs, title }: { regs: SR[]; title: string }) => (
    <div className="tsCanvas dev">
      <div className="tsCap">{title} <span>({regs.length} regions)</span></div>
      <div className="tsFit">
        <svg className="tsStage" viewBox={`0 0 ${GEN_W} ${GEN_H}`} style={{ pointerEvents: "none" }}>
          {regs.map((r) => <g key={r.id}>{renderShape(r)}</g>)}
        </svg>
      </div>
    </div>
  );

  const selRegion = regions.find((r) => r.id === sel);
  const single = selIds.length === 1 && !!selRegion;
  const showResize = single;
  const showCorner = single && !isSliderK(selRegion!.kind);
  const showArc = single && selRegion!.kind === "slider-arc";

  // Handle geometry (SVG user units) for the single selected region.
  const HS = 20;   // handle visual radius, svg units
  const selBox = selRegion ? { x: selRegion.rect.x * GEN_W, y: selRegion.rect.y * GEN_H, w: selRegion.rect.w * GEN_W, h: selRegion.rect.h * GEN_H } : null;
  const resizeHandles = selBox ? ([
    ["nw", selBox.x, selBox.y], ["n", selBox.x + selBox.w / 2, selBox.y], ["ne", selBox.x + selBox.w, selBox.y],
    ["e", selBox.x + selBox.w, selBox.y + selBox.h / 2], ["se", selBox.x + selBox.w, selBox.y + selBox.h],
    ["s", selBox.x + selBox.w / 2, selBox.y + selBox.h], ["sw", selBox.x, selBox.y + selBox.h], ["w", selBox.x, selBox.y + selBox.h / 2],
  ] as [string, number, number][]) : [];
  const cursorFor: Record<string, string> = { nw: "nwse-resize", se: "nwse-resize", ne: "nesw-resize", sw: "nesw-resize", n: "ns-resize", s: "ns-resize", e: "ew-resize", w: "ew-resize" };
  // corner-radius handle position: tangent point on the top edge of the 0.88-scaled body.
  let cornerHandle: { x: number; y: number } | null = null;
  if (showCorner && selBox) {
    const bw = selBox.w * 0.88, bh = selBox.h * 0.88;
    const bx = selBox.x + selBox.w / 2 - bw / 2, by = selBox.y + selBox.h / 2 - bh / 2;
    const maxR = Math.min(bw, bh) / 2;
    const c = Math.max(0, Math.min(1, selRegion!.corner ?? 0.5));
    cornerHandle = { x: bx + maxR * c, y: by };
  }
  // arc handles: start / end at their angle on the arc, radius at the mid-angle.
  let arcHandles: { start: { x: number; y: number }; end: { x: number; y: number }; radius: { x: number; y: number }; cx: number; cy: number; R: number } | null = null;
  if (showArc && selBox) {
    const cx = selBox.x + selBox.w / 2, cy = selBox.y + selBox.h / 2;
    const R = (Math.min(selBox.w, selBox.h) / 2) * 0.86;
    const arc = selRegion!.arc ?? DEF_ARC;
    const at = (deg: number, rad = R) => ({ x: cx + rad * Math.cos(deg * Math.PI / 180), y: cy + rad * Math.sin(deg * Math.PI / 180) });
    const mid = arc.start + (((arc.end - arc.start) % 360 + 360) % 360) / 2;
    arcHandles = { start: at(arc.start), end: at(arc.end), radius: at(mid, R), cx, cy, R };
  }

  // EDITABLE stage — a single SVG. Background rect owns the marquee; each region <g> owns its
  // MOVE gesture; selection handles (resize / corner / arc) own their own gestures. use-gesture's
  // useDrag binds the whole pointer lifecycle to each element, so no root/child capture split.
  const editableStage = (
    <div className="tsCanvas dev">
      <div className="tsCap">RAW template (seed / edit) <span>({regions.length} regions)</span></div>
      <div className="tsFit">
        <svg ref={svgRef} className="tsStage editable" viewBox={`0 0 ${GEN_W} ${GEN_H}`} style={{ touchAction: "none" }}>
          {/* marquee / deselect background */}
          <rect {...bindMarquee()} x={0} y={0} width={GEN_W} height={GEN_H} fill="transparent" style={{ cursor: "default" }} />
          {regions.map((r) => (
            <g key={r.id} {...bindBody(r.id)} style={{ cursor: "grab", touchAction: "none" }}>
              {/* full-bbox transparent hit area so thin sliders/lines are still grabbable */}
              <rect x={r.rect.x * GEN_W} y={r.rect.y * GEN_H} width={r.rect.w * GEN_W} height={r.rect.h * GEN_H} fill="transparent" />
              {renderShape(r)}
            </g>
          ))}
          {/* snap guides */}
          {guides.v.map((gx, i) => <line key={`gv${i}`} x1={gx} y1={0} x2={gx} y2={GEN_H} stroke="#ff4fa3" strokeWidth={1.5} strokeDasharray="8 6" style={{ pointerEvents: "none" }} />)}
          {guides.h.map((gy, i) => <line key={`gh${i}`} x1={0} y1={gy} x2={GEN_W} y2={gy} stroke="#ff4fa3" strokeWidth={1.5} strokeDasharray="8 6" style={{ pointerEvents: "none" }} />)}
          {/* marquee rect */}
          {marquee && <rect x={marquee.x} y={marquee.y} width={marquee.w} height={marquee.h} fill="rgba(127,224,160,0.12)" stroke="#7fe0a0" strokeWidth={1.5} strokeDasharray="6 4" style={{ pointerEvents: "none" }} />}
          {/* RESIZE handles */}
          {showResize && resizeHandles.map(([hd, hx, hy]) => (
            <rect key={hd} {...bindHandle(hd)} x={hx - HS / 2} y={hy - HS / 2} width={HS} height={HS} rx={3}
              fill="#0c0c10" stroke="#7fe0a0" strokeWidth={2.5} style={{ cursor: cursorFor[hd], touchAction: "none" }} />
          ))}
          {/* CORNER-RADIUS handle (live-corner) */}
          {showCorner && cornerHandle && (
            <g {...bindCorner()} style={{ cursor: "ew-resize", touchAction: "none" }}>
              <circle cx={cornerHandle.x} cy={cornerHandle.y} r={HS * 1.4} fill="transparent" />
              <circle cx={cornerHandle.x} cy={cornerHandle.y} r={HS * 0.75} fill="#ffcf4f" stroke="#0c0c10" strokeWidth={2.5} />
            </g>
          )}
          {/* ARC handles: start (green) · end (amber) · radius (cyan) */}
          {showArc && arcHandles && (
            <>
              <path d={arcD(arcHandles.cx, arcHandles.cy, arcHandles.R, (selRegion!.arc ?? DEF_ARC).start, (selRegion!.arc ?? DEF_ARC).end)} fill="none" stroke="#7fe0a0" strokeWidth={2} strokeDasharray="4 4" opacity={0.6} style={{ pointerEvents: "none" }} />
              {(["start", "end", "radius"] as const).map((k) => {
                const hp = arcHandles![k]; const col = k === "start" ? "#7fe0a0" : k === "end" ? "#ffcf4f" : "#4fd4ff";
                return (
                  <g key={k} {...bindArc(k)} style={{ cursor: "grab", touchAction: "none" }}>
                    <circle cx={hp.x} cy={hp.y} r={HS * 1.5} fill="transparent" />
                    <circle cx={hp.x} cy={hp.y} r={HS * 0.8} fill={col} stroke="#0c0c10" strokeWidth={2.5} />
                  </g>
                );
              })}
            </>
          )}
        </svg>
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
        /* 'safe center' (not plain center): centered when panels fit, but flush-start + SCROLLABLE
           when they overflow — plain center pushes the first panel's left edge UNDER the aside,
           making that slice of the editable canvas unclickable (SVG hit-testing hits the aside). */
        .tsMain{display:flex;gap:12px;padding:8px 12px;min-width:0;min-height:0;justify-content:safe center;align-items:stretch;overflow-x:auto;overflow-y:hidden}
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
        .tsStage.editable{touch-action:none}
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
        <span>seed / generate a DATA template → live pack → combined blueprint · real shipping heuristics (layoutRandomP · repackTemplate · combinedBlueprint · deriveLayout) · pure-SVG + use-gesture handles</span>
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
          Repack is OFF — packed mirrors raw 1:1. Edit raw → packed + blueprint update live. Drag body = move · corner/edge handles = resize · yellow handle = corner-radius · arc dots = start/end/radius.
        </div>
      </aside>

      {/* CENTER — everything at once: raw, packed, combined blueprint (height-fit) */}
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
            {selR.kind !== "slider-h" && selR.kind !== "slider-v" && selR.kind !== "slider-arc" && (
              <label>corner (rect ↔ oval) <b style={{ color: "#7fe0a0" }}>{(selR.corner ?? 0.5).toFixed(2)}</b>
                <input type="range" min={0} max={1} step={0.02} value={selR.corner ?? 0.5} onChange={(e) => patchSel({ corner: +e.target.value })} style={{ width: "100%" }} /></label>
            )}
            {selR.kind === "slider-arc" && (() => {
              const arc = selR.arc ?? DEF_ARC;
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 6, borderTop: "1px solid #26262f", paddingTop: 6 }}>
                  <div style={{ fontSize: 11, color: "#8a8a96" }}>partial-circle arc — drag the on-canvas dots, or sweep here</div>
                  <label>start <b style={{ color: "#7fe0a0" }}>{arc.start}°</b>
                    <input type="range" min={0} max={360} step={1} value={arc.start} onChange={(e) => patchSel({ arc: { ...arc, start: +e.target.value } })} style={{ width: "100%" }} /></label>
                  <label>end <b style={{ color: "#7fe0a0" }}>{arc.end}°</b>
                    <input type="range" min={0} max={360} step={1} value={arc.end} onChange={(e) => patchSel({ arc: { ...arc, end: +e.target.value } })} style={{ width: "100%" }} /></label>
                </div>
              );
            })()}
            <button style={{ ...btn, background: "#3a1c1c", borderColor: "#5a2a2a" }} onClick={delSel}>🗑 Delete</button>
          </div>
        ) : <div style={{ color: "#8a8a96", fontSize: 12 }}>Click a component (in the list or on canvas) to edit. Drag to move · handles to resize · yellow dot = corner-radius · arc dots = start/end/radius.</div>}
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
