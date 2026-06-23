import { useEffect, useRef, useState } from "react";
import type { Region, Rect, Kind } from "./schema";
import "./layoutstage.css";

// ─────────────────────────────────────────────────────────────────────────────
// LayoutStage — the ONE draggable/resizable region stage shared by the create
// wizard (Step 2 · Layout, on a blank grid) and the template editor (✎ Edit, on
// the rendered frame.png). Previously these were two drifted copies of the same
// engine; this is the merged, stronger one:
//   · 8 resize handles (n/s/e/w + corners), not just corners
//   · screen-space snap threshold (constant px on screen at any stage size)
//   · alignment snapping to other regions' edges/centers + canvas 0/.5/1
//   · NEW symmetry snapping — mirror a control across the canvas centerline
//   · NEW hold-Alt to suspend snapping for free placement
//   · rubber-band multi-select, group move, shift-click toggle, arrow-nudge,
//     Delete/Backspace
//
// Selection can be CONTROLLED (pass `selected` + `onSelectedChange`, as the
// editor does so its side list/inspector stay in sync) or left uncontrolled
// (the wizard, which has no side panel). All geometry is normalized 0..1.
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  regions: Region[];
  onChange: (regions: Region[]) => void;
  editable?: boolean;                 // default true; wizard passes step===1
  frameUrl?: string;                  // background art (editor); absent → grid
  aspectRatio?: string;               // CSS aspect-ratio, e.g. "1024 / 1536"; default "2 / 3"
  showGrid?: boolean;                 // overlay the alignment grid (default true)
  tall?: boolean;                     // height-driven sizing (editor modal) vs width-driven (wizard)
  selected?: Set<string>;             // controlled selection
  onSelectedChange?: (s: Set<string>) => void;
  nameFor?: (r: Region) => string;    // label drawn on each box (default: label/bind/dyn/kind)
  className?: string;
}

type HandleDir = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

// snap "grab" distance, measured in SCREEN pixels (converted to normalized units
// per-axis each move). Constant on screen regardless of how big the stage renders.
const SNAP_PX = 6;

interface Guide { axis: "x" | "y"; at: number; sym: boolean; }
interface Ref1 { at: number; sym: boolean; }

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

// per-kind box color — legible identity at a glance (label-overlays-rule)
const KIND_COLOR: Record<string, string> = {
  button: "#5aff82", toggle: "#ff8a3d", "slider-h": "#ff5a6e", "slider-v": "#ffd246",
  knob: "#5ab4ff", "slider-arc": "#ff5a6e", "slider-path": "#ff5a6e", segmented: "#c0a0ff",
  xy: "#46d6ff", display: "#b496ff", flourish: "#c8a0ff",
};
const colorFor = (k: Kind) => KIND_COLOR[k] ?? "#c8c8c8";
const defaultName = (r: Region) => r.label || r.bind || r.dynamicType || r.kind;

export function LayoutStage({
  regions, onChange, editable = true, frameUrl, aspectRatio = "2 / 3",
  showGrid = true, tall = false, selected, onSelectedChange, nameFor, className = "",
}: Props) {
  const stageRef = useRef<HTMLDivElement>(null);

  // selection: controlled if `selected` provided, else internal.
  const [selInternal, setSelInternal] = useState<Set<string>>(new Set());
  const sel = selected ?? selInternal;
  const setSel = (next: Set<string>) => { if (onSelectedChange) onSelectedChange(next); else setSelInternal(next); };

  const [guides, setGuides] = useState<Guide[]>([]);
  const [band, setBand] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  // drag carries the START rect of EVERY moving region (group move), keyed by id.
  const drag = useRef<{ primary: string; dir: HandleDir; px: number; py: number; starts: Map<string, Rect>; moved: boolean } | null>(null);
  const bandDrag = useRef<{ x0: number; y0: number; additive: boolean } | null>(null);

  // live refs so the window-level pointer handlers (bound once) read current
  // state without re-binding. Synced in an effect — NOT during render — so the
  // ref-safety lint stays happy; the handlers only fire after a commit anyway.
  const regionsRef = useRef(regions);
  const selRef = useRef(sel);
  const onChangeRef = useRef(onChange);
  const setSelRef = useRef(setSel);
  const editableRef = useRef(editable);
  useEffect(() => {
    regionsRef.current = regions; selRef.current = sel; onChangeRef.current = onChange;
    setSelRef.current = setSel; editableRef.current = editable;
  });

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const st = stageRef.current; if (!st) return;
      const box = st.getBoundingClientRect();

      // ── rubber-band selection ──
      const bd = bandDrag.current;
      if (bd) {
        const x = clamp((e.clientX - box.left) / box.width, 0, 1);
        const y = clamp((e.clientY - box.top) / box.height, 0, 1);
        setBand({ x: Math.min(bd.x0, x), y: Math.min(bd.y0, y), w: Math.abs(x - bd.x0), h: Math.abs(y - bd.y0) });
        return;
      }

      const d = drag.current; if (!d) return;
      d.moved = true;
      const suspend = e.altKey;                 // hold Alt → free placement, no snap
      const tx = SNAP_PX / box.width;
      const ty = SNAP_PX / box.height;
      const dx = (e.clientX - d.px) / box.width;
      const dy = (e.clientY - d.py) / box.height;

      // reference lines: canvas edges/center + every NON-moving region's
      // edges/centers, PLUS each of those mirrored across the canvas centerline
      // (symmetry snapping). Mirrored refs are flagged sym:true for the guide color.
      const movingIds = new Set(d.starts.keys());
      const xs: Ref1[] = [{ at: 0, sym: false }, { at: 0.5, sym: false }, { at: 1, sym: false }];
      const ys: Ref1[] = [{ at: 0, sym: false }, { at: 0.5, sym: false }, { at: 1, sym: false }];
      for (const r of regionsRef.current) {
        if (movingIds.has(r.id)) continue;
        const xl = r.rect.x, xr = r.rect.x + r.rect.w, xc = r.rect.x + r.rect.w / 2;
        const yt = r.rect.y, yb = r.rect.y + r.rect.h, yc = r.rect.y + r.rect.h / 2;
        xs.push({ at: xl, sym: false }, { at: xr, sym: false }, { at: xc, sym: false });
        ys.push({ at: yt, sym: false }, { at: yb, sym: false }, { at: yc, sym: false });
        xs.push({ at: 1 - xl, sym: true }, { at: 1 - xr, sym: true }, { at: 1 - xc, sym: true });
        ys.push({ at: 1 - yt, sym: true }, { at: 1 - yb, sym: true }, { at: 1 - yc, sym: true });
      }
      const snap = (v: number, refs: Ref1[], thr: number): { best: number; guide: Ref1 | null } => {
        if (suspend) return { best: v, guide: null };
        let best = v, guide: Ref1 | null = null, bd2 = thr;
        for (const c of refs) { const dd = Math.abs(v - c.at); if (dd < bd2) { bd2 = dd; best = c.at; guide = c; } }
        return { best, guide };
      };

      const newGuides: Guide[] = [];

      if (d.dir === "move") {
        const base = d.starts.get(d.primary)!;
        let nx = clamp(base.x + dx, 0, 1 - base.w);
        let ny = clamp(base.y + dy, 0, 1 - base.h);
        // snap whichever of left/center/right edge is closest to a ref
        const xCands: Array<[number, number]> = [[nx, 0], [nx + base.w / 2, base.w / 2], [nx + base.w, base.w]];
        let bestDx = tx, chosenX: number | null = null, chosenOff = 0, symX = false;
        for (const [edge, off] of xCands) {
          const { guide } = snap(edge, xs, tx);
          if (guide) { const dd = Math.abs(edge - guide.at); if (dd < bestDx) { bestDx = dd; chosenX = guide.at; chosenOff = off; symX = guide.sym; } }
        }
        if (chosenX != null) { nx = clamp(chosenX - chosenOff, 0, 1 - base.w); newGuides.push({ axis: "x", at: chosenX, sym: symX }); }

        const yCands: Array<[number, number]> = [[ny, 0], [ny + base.h / 2, base.h / 2], [ny + base.h, base.h]];
        let bestDy = ty, chosenY: number | null = null, chosenOffY = 0, symY = false;
        for (const [edge, off] of yCands) {
          const { guide } = snap(edge, ys, ty);
          if (guide) { const dd = Math.abs(edge - guide.at); if (dd < bestDy) { bestDy = dd; chosenY = guide.at; chosenOffY = off; symY = guide.sym; } }
        }
        if (chosenY != null) { ny = clamp(chosenY - chosenOffY, 0, 1 - base.h); newGuides.push({ axis: "y", at: chosenY, sym: symY }); }

        const appliedDx = nx - base.x, appliedDy = ny - base.y;
        onChangeRef.current(regionsRef.current.map((r) => {
          const start = d.starts.get(r.id); if (!start) return r;
          return { ...r, rect: {
            x: clamp(start.x + appliedDx, 0, 1 - start.w),
            y: clamp(start.y + appliedDy, 0, 1 - start.h),
            w: start.w, h: start.h,
          } };
        }));
      } else {
        // resize the single primary region; snap only the dragged edge(s)
        const base = d.starts.get(d.primary)!;
        const min = 0.01;
        let { x, y, w, h } = base;
        if (d.dir.includes("e")) {
          let right = base.x + clamp(base.w + dx, min, 1 - base.x);
          const { best, guide } = snap(right, xs, tx); if (guide) { right = best; newGuides.push({ axis: "x", at: best, sym: guide.sym }); }
          w = clamp(right - base.x, min, 1 - base.x);
        }
        if (d.dir.includes("s")) {
          let bottom = base.y + clamp(base.h + dy, min, 1 - base.y);
          const { best, guide } = snap(bottom, ys, ty); if (guide) { bottom = best; newGuides.push({ axis: "y", at: best, sym: guide.sym }); }
          h = clamp(bottom - base.y, min, 1 - base.y);
        }
        if (d.dir.includes("w")) {
          let nx = clamp(base.x + dx, 0, base.x + base.w - min);
          const { best, guide } = snap(nx, xs, tx); if (guide) { nx = clamp(best, 0, base.x + base.w - min); newGuides.push({ axis: "x", at: nx, sym: guide.sym }); }
          w = base.w + (base.x - nx); x = nx;
        }
        if (d.dir.includes("n")) {
          let ny = clamp(base.y + dy, 0, base.y + base.h - min);
          const { best, guide } = snap(ny, ys, ty); if (guide) { ny = clamp(best, 0, base.y + base.h - min); newGuides.push({ axis: "y", at: ny, sym: guide.sym }); }
          h = base.h + (base.y - ny); y = ny;
        }
        onChangeRef.current(regionsRef.current.map((r) => (r.id === d.primary ? { ...r, rect: { x, y, w, h } } : r)));
      }
      setGuides(newGuides);
    };

    const up = (e: PointerEvent) => {
      const st = stageRef.current;
      const bd = bandDrag.current;
      if (bd && st) {
        const box = st.getBoundingClientRect();
        const x = clamp((e.clientX - box.left) / box.width, 0, 1);
        const y = clamp((e.clientY - box.top) / box.height, 0, 1);
        const rx = Math.min(bd.x0, x), ry = Math.min(bd.y0, y);
        const rw = Math.abs(x - bd.x0), rh = Math.abs(y - bd.y0);
        const dragged = rw > 0.005 || rh > 0.005;
        if (dragged) {
          const hit = regionsRef.current.filter((r) =>
            r.rect.x < rx + rw && r.rect.x + r.rect.w > rx &&
            r.rect.y < ry + rh && r.rect.y + r.rect.h > ry).map((r) => r.id);
          const next = bd.additive ? new Set(selRef.current) : new Set<string>();
          for (const id of hit) next.add(id);
          setSelRef.current(next);
        } else if (!bd.additive) {
          setSelRef.current(new Set());   // click on empty space, no drag → clear
        }
        bandDrag.current = null; setBand(null);
      }
      drag.current = null;
      setGuides([]);
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, []);

  // Delete/Backspace removes selection; arrows nudge — never while typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!editableRef.current) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      const cur = selRef.current; if (!cur.size) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        onChangeRef.current(regionsRef.current.filter((r) => !cur.has(r.id)));
        setSelRef.current(new Set());
        return;
      }
      const step = e.shiftKey ? 0.02 : 0.005;
      let dx = 0, dy = 0;
      if (e.key === "ArrowLeft") dx = -step; else if (e.key === "ArrowRight") dx = step;
      else if (e.key === "ArrowUp") dy = -step; else if (e.key === "ArrowDown") dy = step; else return;
      e.preventDefault();
      onChangeRef.current(regionsRef.current.map((r) => cur.has(r.id)
        ? { ...r, rect: { ...r.rect, x: clamp(r.rect.x + dx, 0, 1 - r.rect.w), y: clamp(r.rect.y + dy, 0, 1 - r.rect.h) } }
        : r));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const startDrag = (e: React.PointerEvent, id: string, dir: HandleDir) => {
    if (!editable) return;
    e.stopPropagation();
    const box = stageRef.current?.getBoundingClientRect(); if (!box) return;

    if (dir === "move") {
      if (e.shiftKey) {  // shift+click toggles membership; no drag
        const n = new Set(sel); if (n.has(id)) n.delete(id); else n.add(id); setSel(n);
        return;
      }
      let moving: Set<string>;
      if (sel.has(id) && sel.size > 1) { moving = new Set(sel); }
      else { moving = new Set([id]); setSel(moving); }
      const starts = new Map<string, Rect>();
      for (const r of regionsRef.current) if (moving.has(r.id)) starts.set(r.id, { ...r.rect });
      drag.current = { primary: id, dir, px: e.clientX, py: e.clientY, starts, moved: false };
    } else {
      const r = regionsRef.current.find((x) => x.id === id); if (!r) return;
      setSel(new Set([id]));
      drag.current = { primary: id, dir, px: e.clientX, py: e.clientY, starts: new Map([[id, { ...r.rect }]]), moved: false };
    }
  };

  // pointerdown on empty stage → begin rubber-band (and tentatively clear on no-drag)
  const startBand = (e: React.PointerEvent) => {
    if (!editable) return;
    const tgt = e.target as HTMLElement;
    if (e.target !== stageRef.current && !tgt.classList.contains("ls-grid") && !tgt.classList.contains("ls-frame")) return;
    const box = stageRef.current?.getBoundingClientRect(); if (!box) return;
    const x0 = clamp((e.clientX - box.left) / box.width, 0, 1);
    const y0 = clamp((e.clientY - box.top) / box.height, 0, 1);
    bandDrag.current = { x0, y0, additive: e.shiftKey };
    setBand({ x: x0, y: y0, w: 0, h: 0 });
  };

  const delRegion = (id: string) => {
    onChange(regionsRef.current.filter((r) => r.id !== id));
    const n = new Set(sel); n.delete(id); setSel(n);
  };

  const name = nameFor ?? defaultName;
  const single = sel.size === 1 ? [...sel][0] : null;

  return (
    <div
      ref={stageRef}
      className={`ls-stage ${tall ? "tall" : ""} ${editable ? "edit" : ""} ${className}`}
      style={{ aspectRatio }}
      onPointerDown={startBand}
    >
      {frameUrl && <img className="ls-frame" src={frameUrl} alt="" draggable={false} />}
      {showGrid && <div className="ls-grid" />}

      {regions.map((r) => {
        const c = colorFor(r.kind);
        const ell = r.shape === "ellipse" || r.kind === "knob";
        const arc = r.kind === "slider-arc" || r.kind === "slider-path";
        const on = sel.has(r.id);
        const isSingle = single === r.id;
        return (
          <div key={r.id}
            className={`ls-region ${on ? "sel" : ""} ${on && sel.size > 1 ? "multi" : ""}`}
            style={{
              left: `${r.rect.x * 100}%`, top: `${r.rect.y * 100}%`,
              width: `${r.rect.w * 100}%`, height: `${r.rect.h * 100}%`,
              borderColor: c, background: arc ? "transparent" : `${c}22`,
              borderStyle: arc ? "dashed" : "solid", opacity: arc ? 0.6 : 1,
              borderRadius: ell || arc ? "50%" : "4px",
              cursor: editable ? "move" : "default",
            }}
            onPointerDown={(e) => startDrag(e, r.id, "move")}>
            <span className="ls-tag" style={{ color: c }}>{name(r)}</span>
            {isSingle && editable && (["n", "s", "e", "w", "ne", "nw", "se", "sw"] as HandleDir[]).map((d) => (
              <span key={d} className={`ls-handle h-${d}`} style={{ borderColor: c }}
                onPointerDown={(e) => startDrag(e, r.id, d)} />
            ))}
            {isSingle && editable && (
              <button className="ls-del" onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => { e.stopPropagation(); delRegion(r.id); }} title="Delete (or ⌫)">×</button>
            )}
          </div>
        );
      })}

      {editable && guides.map((g, i) => (
        <div key={i} className={`ls-guide ${g.axis === "x" ? "v" : "h"} ${g.sym ? "sym" : ""}`}
          style={g.axis === "x" ? { left: `${g.at * 100}%` } : { top: `${g.at * 100}%` }} />
      ))}

      {editable && band && (
        <div className="ls-band" style={{ left: `${band.x * 100}%`, top: `${band.y * 100}%`, width: `${band.w * 100}%`, height: `${band.h * 100}%` }} />
      )}
    </div>
  );
}
