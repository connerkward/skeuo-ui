// DEV-ONLY Template Studio (?studio). A human-facing interface to SEED / GENERATE a data
// template and see it PACKED live — all on the REAL shipping heuristics:
//   • cheap heuristic randomizer  → layoutRandomP / layoutArch (the 10 archetypes)
//   • LLM data-template generator → deriveLayout via POST /api/derive (heuristic-guided prompt)
//   • packer                      → repackTemplate (canon-size + resolveOverlaps), live
// Each component has a CENTROID (draggable), an ARBITRARY SHAPE connected to it, and a modular
// DIFFUSENESS (soft-guide spread). Left = raw seeded template, right = packed result.
import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import {
  layoutRandomP, layoutArch, bakeButtons, resolveOverlaps, ARCHETYPES, DEFAULT_PARAMS, SPOTIFY_BINDS,
  GEN_W, GEN_H, type Params,
} from "../generate/layouts";
import { combinedBlueprint, componentColors } from "../generate/blueprint";
import { PAINT_PROMPT } from "../generate/pipeline";
import PaintedSheet from "./PaintedSheet";
import Moveable from "react-moveable";
import Selecto from "react-selecto";
import type { Region, Kind } from "../template/schema";

type SR = Region & { shapeKind?: string; diff?: number };
const KINDS: Kind[] = ["button", "knob", "toggle", "slider-h", "slider-v", "slider-arc", "display"];
const DEF_ARC = { start: 200, end: 340 };   // default partial-circle sweep for a slider-arc
const REPACK_ENABLED = false;   // feature flag: repack/packing is OFF — packed == raw, so the PACKED panel is hidden
// SVG arc 'd' matching blueprint.ts arcPath (same large-arc/sweep rules) so a slider-arc reads
// IDENTICALLY in the studio panels and the combined blueprint.
const arcD = (cx: number, cy: number, r: number, a0: number, a1: number): string => {
  const p = (a: number): [number, number] => [cx + r * Math.cos((a * Math.PI) / 180), cy + r * Math.sin((a * Math.PI) / 180)];
  const [sx, sy] = p(a0), [ex, ey] = p(a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`;
};


export default function TemplateStudio() {
  const [P, setP] = useState<Params>({ ...DEFAULT_PARAMS });
  const [regions, setRegions] = useState<SR[]>(() => layoutArch("console", DEFAULT_PARAMS) as SR[]);
  // SELECTION — a set (marquee multi-select via Selecto). `sel` is the PRIMARY (last-added)
  // selection the inspector/keyboard operate on; `selIds` drives the Moveable target set.
  const [selIds, setSelIds] = useState<string[]>([]);
  const sel = selIds.length ? selIds[selIds.length - 1] : null;
  const [showOverlays, setShowOverlays] = useState(false);  // studio annotations on the blueprint — OFF by default (see the exact image sent to FAL); toggle on to label cells
  const globalDiff = 0;   // diffuseness disabled for now — anchors are crisp
  const [prompt, setPrompt] = useState("a wild organic Y2K Winamp media player");
  const [llmMsg, setLlmMsg] = useState("");
  // Moveable/Selecto interaction refs — the transparent overlay divs (.ctrl) are Moveable's
  // targets; the SVG below is a pure visual projection of the normalized model (pointer-events:none).
  const overlayRef = useRef<HTMLDivElement>(null);
  const moveableRef = useRef<Moveable>(null);
  const selectoRef = useRef<Selecto>(null);
  const ctrlEls = useRef<Map<string, HTMLElement>>(new Map());
  const [targets, setTargets] = useState<HTMLElement[]>([]);
  const [stagePx, setStagePx] = useState({ w: 1, h: 1 });
  // Ids under an ACTIVE Moveable gesture — while set, the transparent target div is frozen at its
  // gesture-start rect so Moveable's gesto sees a STABLE target (moving its own target mid-drag
  // corrupts the pointer baseline). The visible SVG shape still tracks the live model underneath.
  const [gesturing, setGesturing] = useState<Set<string>>(new Set());
  // human-authored flag: once the human edits (drag/add/patch/nudge), the packer becomes a
  // PASS-THROUGH — packing must not rearrange a human-authored template. Generators reset it.
  const [, setAuthored] = useState(false);   // human-edit flag (setter kept; value unused while repack is off)

  // HARD CONSTRAINT: components at 0 diffuseness (crisp, must-follow guides) may NEVER overlap.
  // Enforced with the SHIPPING resolveOverlaps, scoped to only the zero-diff subset — the packer
  // heuristic applied exactly where it makes sense, even on human-authored templates.
  const enforceZeroDiff = useCallback((rs: SR[]): SR[] => {
    const isZero = (r: SR) => (r.diff ?? globalDiff) <= 0.001;
    const zero = rs.filter(isZero);
    if (zero.length < 2) return rs;
    const solved = resolveOverlaps(zero.map((r) => ({ ...r })) as Region[]) as SR[];
    const byId = new Map(solved.map((r) => [r.id, r]));
    return rs.map((r) => byId.get(r.id) ?? r);
  }, [globalDiff]);

  // undo/redo history — normal expected editor UX (⌘Z / ⇧⌘Z). Snapshots on every
  // discrete mutation (and at drag START, so a whole drag undoes as one step).
  const past = useRef<SR[][]>([]); const future = useRef<SR[][]>([]);
  const mutate = useCallback((updater: (rs: SR[]) => SR[]) => setRegions((rs) => {
    past.current.push(rs); if (past.current.length > 60) past.current.shift();
    future.current = []; return updater(rs);
  }), []);
  const snapshot = useCallback(() => setRegions((rs) => { past.current.push(rs); future.current = []; return rs; }), []);
  const undo = useCallback(() => setRegions((cur) => { const p = past.current.pop(); if (!p) return cur; future.current.push(cur); return p; }), []);
  const redo = useCallback(() => setRegions((cur) => { const f = future.current.pop(); if (!f) return cur; past.current.push(cur); return f; }), []);

  // REPACK DISABLED ("for now"): packed mirrors the raw regions 1:1 — no packDiffuse /
  // repackTemplate rearrangement — so the blueprint reflects exactly what you edit.
  // (Zero-diff overlap prevention still runs live on edits via enforceZeroDiff.)
  const packed = useMemo(() => regions as SR[], [regions]);
  // BAKED regions (transport buttons molded into the body) — the EXACT input the blueprint
  // uses. Shared so the studio panels colour controls the SAME way the blueprint does.
  const bakedRegs = useMemo(() => {
    try { return bakeButtons(packed.map((r) => ({ ...r, diff: 0 })) as Region[]); }
    catch { return packed as Region[]; }
  }, [packed, globalDiff]);
  // COMBINED blueprint — real shipping function (bakeButtons → combinedBlueprint).
  const combined = useMemo(() => {
    try { return combinedBlueprint(bakedRegs, "rgb(128,128,130)"); }
    catch { return null; }
  }, [bakedRegs]);
  // SHARED per-component identity colour with the blueprint (same componentColors registry):
  // EVERY control gets its OWN distinct hex, identical in the RAW / PACKED panels, the combined
  // blueprint, the component list, the prompt legend, and the output mask.
  const colorMap = useMemo(() => componentColors(bakedRegs), [bakedRegs]);
  const colorOf = useCallback((r: SR) => colorMap.get(r.id)?.hex ?? "#888888", [colorMap]);

  // The exact TEXT prompt that rides ALONGSIDE the blueprint image to FAL — reconstructed
  // live from the shared PAINT_PROMPT + this template's strip / bake-legend, so you can read
  // what textual data the model actually receives. (material + BG key-colour are Director-
  // derived server-side; shown as placeholders here.)
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
        mutate((rs) => enforceZeroDiff(rs.map((r) => selIds.includes(r.id) ? { ...r, rect: { ...r.rect, x: Math.max(0, Math.min(1 - r.rect.w, r.rect.x + dx)), y: Math.max(0, Math.min(1 - r.rect.h, r.rect.y + dy)) } } : r)));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selIds, mutate, undo, redo, delSel, enforceZeroDiff]);

  // ── Moveable/Selecto plumbing ────────────────────────────────────────────────
  // Track the overlay's live pixel box (for px→normalized conversion + Moveable bounds).
  useEffect(() => {
    const el = overlayRef.current;
    if (!el) return;
    const measure = () => { const b = el.getBoundingClientRect(); if (b.width && b.height) setStagePx({ w: b.width, h: b.height }); };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // Resolve the DOM targets Moveable acts on from the current selection (after render commits refs).
  // Depend on SELECTION only — the .ctrl elements are stable across region edits (stable keys), so
  // rebuilding this array on every drag frame (regions dep) would hand Moveable a new `target` prop
  // mid-gesture and abort the drag. `regions.length` catches add/delete membership changes.
  useEffect(() => {
    setTargets(selIds.map((id) => ctrlEls.current.get(id)).filter(Boolean) as HTMLElement[]);
  }, [selIds, regions.length]);
  // Model changed (inspector edit, nudge, generator) → re-sync Moveable's control box to the divs.
  // Skip WHILE a gesture is active (updateRect mid-drag would reset Moveable's in-progress state).
  useEffect(() => { if (gesturing.size === 0) moveableRef.current?.updateRect(); }, [regions, targets, stagePx, gesturing]);

  const px2n = () => { const b = overlayRef.current?.getBoundingClientRect(); return { w: b?.width || stagePx.w, h: b?.height || stagePx.h }; };
  const clampPos = (v: number, size: number) => Math.max(0, Math.min(1 - size, v));
  const MIN_N = 0.03;
  // Capture each target's START rect so drag/resize are DELTA-based off Moveable's px distance
  // (e.dist), NOT its re-measured absolute e.left/e.top — which drift, because the .ctrl divs are
  // repositioned live from the model every frame and that feeds a runaway back into e.left.
  const gestureStart = useRef<Map<string, { x: number; y: number; w: number; h: number }>>(new Map());
  const beginGesture = useCallback(() => {
    snapshot();
    const m = new Map<string, { x: number; y: number; w: number; h: number }>();
    regions.forEach((r) => m.set(r.id, { ...r.rect }));
    gestureStart.current = m;
    setGesturing(new Set(selIds));   // freeze the active target divs for the gesture's duration
  }, [snapshot, regions, selIds]);
  // MOVE: dist = total px drag from gesture start → normalized delta added to the captured start rect.
  const applyDrag = (t: HTMLElement, distX: number, distY: number) => {
    const id = t.dataset.id, s = id ? gestureStart.current.get(id) : undefined; if (!s) return;
    const { w, h } = px2n();
    const nx = clampPos(s.x + distX / w, s.w), ny = clampPos(s.y + distY / h, s.h);
    setRegions((rs) => rs.map((r) => r.id === id ? { ...r, rect: { ...r.rect, x: nx, y: ny } } : r));
  };
  // RESIZE: absolute e.width/e.height (start-cached in Moveable → safe) for size; the moving corner's
  // position via delta (opposite corner fixed → its drag dist is 0). Clamped to [0,1] + MIN size.
  const applyResize = (t: HTMLElement, width: number, height: number, distX: number, distY: number) => {
    const id = t.dataset.id, s = id ? gestureStart.current.get(id) : undefined; if (!s) return;
    const { w, h } = px2n();
    let nx = Math.max(0, s.x + distX / w), ny = Math.max(0, s.y + distY / h);
    let nw = Math.max(MIN_N, width / w), nh = Math.max(MIN_N, height / h);
    nw = Math.min(nw, 1 - nx); nh = Math.min(nh, 1 - ny);
    setRegions((rs) => rs.map((r) => r.id === id ? { ...r, rect: { x: nx, y: ny, w: nw, h: nh } } as SR : r));
  };
  // CORNER RADIUS: roundable emits a % border-radius (roundRelative) → scalar corner 0..1 (50%=oval→1).
  const applyRound = (t: HTMLElement, borderRadius: string) => {
    const id = t.dataset.id; if (!id) return;
    const first = parseFloat(borderRadius) || 0;
    const corner = Math.max(0, Math.min(1, borderRadius.includes("%") ? first / 50 : first / (Math.min(stagePx.w, stagePx.h) / 2)));
    setRegions((rs) => rs.map((r) => r.id === id ? { ...r, corner: +corner.toFixed(3) } as SR : r));
  };
  const commitZeroDiff = () => { setAuthored(true); setRegions(enforceZeroDiff); setGesturing(new Set()); requestAnimationFrame(() => moveableRef.current?.updateRect()); };
  const isSliderK = (k?: Kind) => k === "slider-h" || k === "slider-v" || k === "slider-arc";

  const renderShape = (r: SR) => {
    const W = GEN_W, H = GEN_H;
    const x = r.rect.x * W, y = r.rect.y * H, w = r.rect.w * W, h = r.rect.h * H;
    const cx = x + w / 2, cy = y + h / 2;
    const col = colorOf(r);
    const s = Math.min(w, h);
    const selected = sel === r.id;
    const isSlider = r.kind === "slider-h" || r.kind === "slider-v" || r.kind === "slider-arc";
    const corner = Math.max(0, Math.min(1, r.corner ?? 0.5));   // 0 = rect · 1 = oval
    const fid = `f_${r.id}`;
    const arm = s * 0.27, lw = Math.max(2.5, s * 0.03), dot = Math.max(3, s * 0.05), tw = Math.max(3, s * 0.08);

    // SLIDERS = their track (straight line / partial-circle arc); every other control = a
    // DIFFUSE rounded-rect ANCHOR whose `corner` morphs it rect↔oval (dragged with live
    // corner handles). Same shape maths as the blueprint's anchorMark.
    const rw = w * 0.88, rh = h * 0.88, rrx = cx - rw / 2, rry = cy - rh / 2;
    const rr = (Math.min(rw, rh) / 2) * corner;
    const shape = r.kind === "slider-h"
      ? <line x1={x + w * 0.1} y1={cy} x2={x + w * 0.9} y2={cy} stroke={col} strokeWidth={tw} strokeLinecap="round" />
      : r.kind === "slider-v"
        ? <line x1={cx} y1={y + h * 0.1} x2={cx} y2={y + h * 0.9} stroke={col} strokeWidth={tw} strokeLinecap="round" />
        : r.kind === "slider-arc"
          ? <path d={arcD(cx, cy, (s / 2) * 0.86, (r.arc ?? DEF_ARC).start, (r.arc ?? DEF_ARC).end)} fill="none" stroke={col} strokeWidth={tw} strokeLinecap="round" />
          : <rect x={rrx} y={rry} width={rw} height={rh} rx={rr} ry={rr} fill={col} fillOpacity={0.38} stroke={col} strokeWidth={Math.max(1.5, s * 0.022)} filter={`url(#${fid})`} />;

    // PURE VISUAL LAYER — no pointer interaction here. Selection/drag/resize/radius are owned by
    // react-moveable + react-selecto on the transparent HTML overlay (.ctrl divs) above this SVG;
    // the shapes below are just a projection of the normalized model, redrawn as it edits.
    return (
      <g key={r.id}>
        {!isSlider && <filter id={fid} x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation={s * 0.09} /></filter>}
        {shape}
        {!isSlider && <g stroke={col} strokeWidth={lw} strokeLinecap="round" opacity={0.9}>
          <line x1={cx - arm} y1={cy} x2={cx + arm} y2={cy} />
          <line x1={cx} y1={cy - arm} x2={cx} y2={cy + arm} />
        </g>}
        {selected && <rect x={x} y={y} width={w} height={h} fill="none" stroke="#fff" strokeWidth={2} strokeDasharray="7 5" opacity={0.55} />}
        <circle cx={cx} cy={cy} r={dot} fill={selected ? "#fff" : col} stroke="#000" strokeWidth={2} />
        <text x={cx} y={y - 6} fill={col} fontSize={26} textAnchor="middle" style={{ pointerEvents: "none", fontWeight: 700 }}>{(r.bind || r.id).slice(0, 10)}</text>
      </g>
    );
  };

  // height-fit canvas (READ-ONLY): the stage derives its width from the viewport height via
  // aspect-ratio. The SVG is pointer-events:none — a pure visual projection of the model.
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
  const roundable = selIds.length === 1 && !!selRegion && !isSliderK(selRegion.kind);
  // EDITABLE stage — SVG visual layer (pointer-events:none) UNDER a transparent HTML overlay of
  // .ctrl divs (Moveable targets), driven by react-moveable (drag/resize/round) + react-selecto
  // (marquee + click select). Inlined (NOT a nested component) so Moveable/Selecto persist across
  // renders instead of remounting.
  const editableStage = (
    <div className="tsCanvas dev">
      <div className="tsCap">RAW template (seed / edit) <span>({regions.length} regions)</span></div>
      <div className="tsFit">
        <div className="tsStageWrap" ref={overlayRef}>
          <svg className="tsStage" viewBox={`0 0 ${GEN_W} ${GEN_H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
            {regions.map((r) => renderShape(r))}
          </svg>
          {/* transparent Moveable targets — projections of the normalized rects, FROZEN at the
              gesture-start rect while under active drag/resize so gesto's baseline stays stable. */}
          {regions.map((r) => {
            const g = gesturing.has(r.id) ? gestureStart.current.get(r.id) : undefined;
            const rc = g ?? r.rect;
            return (
              <div key={r.id} className="ctrl" data-id={r.id}
                ref={(el) => { if (el) ctrlEls.current.set(r.id, el); else ctrlEls.current.delete(r.id); }}
                style={{ position: "absolute", left: `${rc.x * 100}%`, top: `${rc.y * 100}%`, width: `${rc.w * 100}%`, height: `${rc.h * 100}%`, boxSizing: "border-box", background: "transparent" }} />
            );
          })}
          <Moveable
            ref={moveableRef}
            target={targets}
            draggable
            resizable
            roundable={roundable}
            roundRelative
            snappable
            origin={false}
            elementGuidelines={[".ctrl"]}
            bounds={{ left: 0, top: 0, right: stagePx.w, bottom: stagePx.h, position: "css" }}
            throttleDrag={0}
            throttleResize={0}
            keepRatio={false}
            onDragStart={beginGesture}
            onDrag={(e) => applyDrag(e.target as HTMLElement, e.dist[0], e.dist[1])}
            onDragEnd={commitZeroDiff}
            onDragGroupStart={beginGesture}
            onDragGroup={(e) => e.events.forEach((ev) => applyDrag(ev.target as HTMLElement, ev.dist[0], ev.dist[1]))}
            onDragGroupEnd={commitZeroDiff}
            onResizeStart={beginGesture}
            onResize={(e) => applyResize(e.target as HTMLElement, e.width, e.height, e.drag.dist[0], e.drag.dist[1])}
            onResizeEnd={commitZeroDiff}
            onResizeGroupStart={beginGesture}
            onResizeGroup={(e) => e.events.forEach((ev) => applyResize(ev.target as HTMLElement, ev.width, ev.height, ev.drag.dist[0], ev.drag.dist[1]))}
            onResizeGroupEnd={commitZeroDiff}
            onRoundStart={snapshot}
            onRound={(e) => applyRound(e.target as HTMLElement, String(e.borderRadius))}
          />
          <Selecto
            ref={selectoRef}
            dragContainer={".tsStageWrap"}
            selectableTargets={[".ctrl"]}
            hitRate={0}
            selectByClick
            selectFromInside={false}
            toggleContinueSelect={"shift"}
            onDragStart={(e) => {
              const mv = moveableRef.current;
              const t = e.inputEvent.target as HTMLElement;
              if (mv && (mv.isMoveableElement(t) || targets.some((tg) => tg === t || tg.contains(t)))) e.stop();
            }}
            onSelect={(e) => setSelIds((e.selected as HTMLElement[]).map((el) => el.dataset.id!).filter(Boolean))}
            onSelectEnd={(e) => {
              setSelIds((e.selected as HTMLElement[]).map((el) => el.dataset.id!).filter(Boolean));
              if (e.isDragStart) {
                e.inputEvent.preventDefault();
                requestAnimationFrame(() => requestAnimationFrame(() => moveableRef.current?.dragStart(e.inputEvent)));
              }
            }}
          />
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
        /* panels: FULL height, width derived from their aspect (so the svg box stays exact —
           pointer math needs it); centred, horizontal-scroll if the three overflow. */
        .tsCanvas{display:flex;flex-direction:column;min-width:0;min-height:0;gap:4px;flex:0 0 auto}
        .tsCanvas.dev{width:min(94vw,calc((100vh - 240px) * ${(GEN_W / GEN_H).toFixed(4)}))}
        .tsCanvas.bp{width:min(94vw,calc((100vh - 240px) * ${(GEN_W / 1820).toFixed(4)}))}
        .tsFit{flex:1;min-height:0;display:grid;place-items:center;overflow:hidden}
        .tsCap{color:#cfcfe0;font-weight:600;font-size:12.5px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .tsCap span{color:#8a8a96;font-weight:400;font-size:11px}
        .tsStage{width:100%;aspect-ratio:${GEN_W}/${GEN_H};background:#15151c;border:1px solid #2a2a34;border-radius:10px;touch-action:none}
        /* editable stage: relative wrapper holds the visual SVG + the transparent Moveable target divs */
        .tsStageWrap{position:relative;width:100%;aspect-ratio:${GEN_W}/${GEN_H};background:#15151c;border:1px solid #2a2a34;border-radius:10px;touch-action:none}
        .ctrl{cursor:grab}
        .ctrl:active{cursor:grabbing}
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
        <span>seed / generate a DATA template → live pack → combined blueprint · real shipping heuristics (layoutRandomP · repackTemplate · combinedBlueprint · deriveLayout)</span>
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
          Repack is OFF — packed mirrors raw 1:1. Edit raw → packed + blueprint update live.
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
              {/* STUDIO OVERLAYS — annotations drawn ON TOP of the blueprint for the human; NOT part of
                  the rasterized image sent to FAL. Always badge-labelled as such + toggleable, so it's
                  never ambiguous whether an annotation is in the real artifact. */}
              {showOverlays && (
                <>
                  <div style={{ position: "absolute", top: 4, left: 4, zIndex: 2, background: "rgba(10,10,16,.72)", color: "#7fe0a0", fontSize: 8.5, fontWeight: 700, padding: "1px 5px", borderRadius: 4, pointerEvents: "none" }}>◉ studio overlay · not in image → FAL</div>
                  {/* sprite-cell labels — the SPRITE LOCATIONS the cutter will use, keyed by bind */}
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
                  <div style={{ fontSize: 11, color: "#8a8a96" }}>partial-circle arc — sweep the ends</div>
                  <label>start <b style={{ color: "#7fe0a0" }}>{arc.start}°</b>
                    <input type="range" min={0} max={360} step={1} value={arc.start} onChange={(e) => patchSel({ arc: { ...arc, start: +e.target.value } })} style={{ width: "100%" }} /></label>
                  <label>end <b style={{ color: "#7fe0a0" }}>{arc.end}°</b>
                    <input type="range" min={0} max={360} step={1} value={arc.end} onChange={(e) => patchSel({ arc: { ...arc, end: +e.target.value } })} style={{ width: "100%" }} /></label>
                </div>
              );
            })()}
            <button style={{ ...btn, background: "#3a1c1c", borderColor: "#5a2a2a" }} onClick={delSel}>🗑 Delete</button>
          </div>
        ) : <div style={{ color: "#8a8a96", fontSize: 12 }}>Click a component (in the list or its centroid) to edit kind, bind, or size.</div>}
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
