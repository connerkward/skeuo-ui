import { useEffect, useMemo, useRef, useState } from "react";
import type { Region, Template, Kind, Rect } from "../template/schema";
import "./editor.css";

// Draggable + resizable template editor. Overlays every Region of `template`
// as a box on the frame image (same normalized rects the runtime compositor
// uses), lets you move/resize/add/delete regions and edit kind+bind, and
// exports the edited template.json (download + copy). Coords are normalized
// 0..1; the readout shows them and a "snap to px" pass rounds to the canvas grid.
//
// Supports: alignment snapping (move + resize) with cyan guide lines,
// rubber-band multi-select + group move, shift-click toggle.
interface Props {
  template: Template;
  frameUrl?: string;          // background frame.png (optional; grid shown if absent)
  onApply: (t: Template) => void;  // live-update the preview
  onClose: () => void;
}

const KINDS: Kind[] = ["button", "toggle", "slider-h", "slider-v", "knob", "slider-arc", "segmented", "xy", "display", "flourish"];
const BINDS = ["", "play", "pause", "stop", "prev", "next", "eject", "seek", "volume", "balance", "shuffle", "eqOn", "eqAuto", "mute", "eqBand", "repeatMode", "eqPreset"];

type HandleDir = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

// Snap threshold in pixels (converted to normalized units per-axis).
const SNAP_PX = 6;

interface Guide { axis: "x" | "y"; at: number; }

// On-box tag: a meaningful name (bind, else dynamicType, else id).
const regionName = (r: Region): string => r.bind || r.dynamicType || r.id;

export function TemplateEditor({ template, frameUrl, onApply, onClose }: Props) {
  const [regions, setRegions] = useState<Region[]>(() => template.regions.map((r) => ({ ...r, rect: { ...r.rect } })));
  const [sel, setSel] = useState<Set<string>>(() => new Set(regions[0]?.id ? [regions[0].id] : []));
  const [copied, setCopied] = useState(false);
  const [guides, setGuides] = useState<Guide[]>([]);
  const [band, setBand] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  // drag carries the originals of EVERY moving region (group move) keyed by id.
  const drag = useRef<{
    primary: string; dir: HandleDir; px: number; py: number;
    starts: Map<string, Rect>; w: number; h: number; moved: boolean;
  } | null>(null);
  // rubber-band drag state (selection box on empty stage)
  const bandDrag = useRef<{ x0: number; y0: number; px: number; py: number; w: number; h: number; additive: boolean } | null>(null);

  // re-seed when a different template comes in (e.g. switching skins)
  useEffect(() => {
    setRegions(template.regions.map((r) => ({ ...r, rect: { ...r.rect } })));
    setSel(new Set(template.regions[0]?.id ? [template.regions[0].id] : []));
    setGuides([]); setBand(null);
  }, [template]);

  // push edits to the live preview whenever regions change
  const out = useMemo<Template>(() => ({ ...template, regions }), [template, regions]);
  useEffect(() => { onApply(out); }, [out, onApply]);

  const update = (id: string, rect: Rect) =>
    setRegions((rs) => rs.map((r) => (r.id === id ? { ...r, rect } : r)));
  const patch = (id: string, p: Partial<Region>) =>
    setRegions((rs) => rs.map((r) => (r.id === id ? { ...r, ...p } : r)));

  // Refs so the global pointer handlers always read live state without re-binding.
  const regionsRef = useRef(regions); regionsRef.current = regions;
  const selRef = useRef(sel); selRef.current = sel;

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const st = stageRef.current; if (!st) return;
      const box = st.getBoundingClientRect();

      // --- rubber-band selection ---
      const bd = bandDrag.current;
      if (bd) {
        const x = clamp((e.clientX - box.left) / box.width, 0, 1);
        const y = clamp((e.clientY - box.top) / box.height, 0, 1);
        const bx = Math.min(bd.x0, x), by = Math.min(bd.y0, y);
        setBand({ x: bx, y: by, w: Math.abs(x - bd.x0), h: Math.abs(y - bd.y0) });
        return;
      }

      const d = drag.current; if (!d) return;
      d.moved = true;
      const tx = SNAP_PX / box.width;   // snap threshold, x axis
      const ty = SNAP_PX / box.height;  // snap threshold, y axis
      const dx = (e.clientX - d.px) / box.width;
      const dy = (e.clientY - d.py) / box.height;

      // reference lines from every region NOT being moved + canvas edges/centers
      const movingIds = new Set(d.starts.keys());
      const xs: number[] = [0, 0.5, 1];
      const ys: number[] = [0, 0.5, 1];
      for (const r of regionsRef.current) {
        if (movingIds.has(r.id)) continue;
        xs.push(r.rect.x, r.rect.x + r.rect.w, r.rect.x + r.rect.w / 2);
        ys.push(r.rect.y, r.rect.y + r.rect.h, r.rect.y + r.rect.h / 2);
      }
      const snapX = (v: number): [number, number | null] => {
        let best = v, gline: number | null = null, bd2 = tx;
        for (const c of xs) { const dd = Math.abs(v - c); if (dd < bd2) { bd2 = dd; best = c; gline = c; } }
        return [best, gline];
      };
      const snapY = (v: number): [number, number | null] => {
        let best = v, gline: number | null = null, bd2 = ty;
        for (const c of ys) { const dd = Math.abs(v - c); if (dd < bd2) { bd2 = dd; best = c; gline = c; } }
        return [best, gline];
      };

      const newGuides: Guide[] = [];

      if (d.dir === "move") {
        const base = d.starts.get(d.primary)!;
        let nx = clamp(base.x + dx, 0, 1 - base.w);
        let ny = clamp(base.y + dy, 0, 1 - base.h);
        // snap left / center / right -> pick closest within threshold
        const xCands: Array<[number, number]> = [
          [nx, 0],                  // left edge offset 0
          [nx + base.w / 2, base.w / 2],
          [nx + base.w, base.w],
        ];
        let bestDx = tx, chosenX: number | null = null, chosenOff = 0;
        for (const [edge, off] of xCands) {
          const [snapped, gl] = snapX(edge);
          if (gl != null) { const dd = Math.abs(edge - snapped); if (dd < bestDx) { bestDx = dd; chosenX = snapped; chosenOff = off; } }
        }
        if (chosenX != null) { nx = clamp(chosenX - chosenOff, 0, 1 - base.w); newGuides.push({ axis: "x", at: chosenX }); }

        const yCands: Array<[number, number]> = [
          [ny, 0],
          [ny + base.h / 2, base.h / 2],
          [ny + base.h, base.h],
        ];
        let bestDy = ty, chosenY: number | null = null, chosenOffY = 0;
        for (const [edge, off] of yCands) {
          const [snapped, gl] = snapY(edge);
          if (gl != null) { const dd = Math.abs(edge - snapped); if (dd < bestDy) { bestDy = dd; chosenY = snapped; chosenOffY = off; } }
        }
        if (chosenY != null) { ny = clamp(chosenY - chosenOffY, 0, 1 - base.h); newGuides.push({ axis: "y", at: chosenY }); }

        // apply same delta (post-snap) to every moving region, clamped to [0,1]
        const appliedDx = nx - base.x, appliedDy = ny - base.y;
        setRegions((rs) => rs.map((r) => {
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
          const [s, gl] = snapX(right); if (gl != null) { right = s; newGuides.push({ axis: "x", at: s }); }
          w = clamp(right - base.x, min, 1 - base.x);
        }
        if (d.dir.includes("s")) {
          let bottom = base.y + clamp(base.h + dy, min, 1 - base.y);
          const [s, gl] = snapY(bottom); if (gl != null) { bottom = s; newGuides.push({ axis: "y", at: s }); }
          h = clamp(bottom - base.y, min, 1 - base.y);
        }
        if (d.dir.includes("w")) {
          let nx = clamp(base.x + dx, 0, base.x + base.w - min);
          const [s, gl] = snapX(nx); if (gl != null) { nx = clamp(s, 0, base.x + base.w - min); newGuides.push({ axis: "x", at: nx }); }
          w = base.w + (base.x - nx); x = nx;
        }
        if (d.dir.includes("n")) {
          let ny = clamp(base.y + dy, 0, base.y + base.h - min);
          const [s, gl] = snapY(ny); if (gl != null) { ny = clamp(s, 0, base.y + base.h - min); newGuides.push({ axis: "y", at: ny }); }
          h = base.h + (base.y - ny); y = ny;
        }
        update(d.primary, { x, y, w, h });
      }
      setGuides(newGuides);
    };

    const up = (e: PointerEvent) => {
      const st = stageRef.current;
      // finalize rubber-band
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
            r.rect.y < ry + rh && r.rect.y + r.rect.h > ry
          ).map((r) => r.id);
          setSel((prev) => {
            const next = bd.additive ? new Set(prev) : new Set<string>();
            for (const id of hit) next.add(id);
            return next;
          });
        } else if (!bd.additive) {
          setSel(new Set());  // click on empty space with no drag clears
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

  // Delete/Backspace removes all selected (unless typing in an input/select).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (selRef.current.size === 0) return;
      e.preventDefault();
      const ids = selRef.current;
      setRegions((rs) => rs.filter((r) => !ids.has(r.id)));
      setSel(new Set());
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const startDrag = (e: React.PointerEvent, id: string, dir: HandleDir) => {
    e.stopPropagation();
    const box = stageRef.current?.getBoundingClientRect();
    if (!box) return;

    if (dir === "move") {
      if (e.shiftKey) {
        // shift+click toggles membership; don't start a drag.
        setSel((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
        return;
      }
      // plain click on a region: if it's already in a multi-selection, keep the
      // group and group-move; otherwise select just this one.
      let moving: Set<string>;
      if (selRef.current.has(id) && selRef.current.size > 1) {
        moving = new Set(selRef.current);
      } else {
        moving = new Set([id]);
        setSel(moving);
      }
      const starts = new Map<string, Rect>();
      for (const r of regionsRef.current) if (moving.has(r.id)) starts.set(r.id, { ...r.rect });
      drag.current = { primary: id, dir, px: e.clientX, py: e.clientY, starts, w: box.width, h: box.height, moved: false };
    } else {
      // resize handle: only ever on the single selected region
      const r = regionsRef.current.find((x) => x.id === id); if (!r) return;
      setSel(new Set([id]));
      const starts = new Map<string, Rect>([[id, { ...r.rect }]]);
      drag.current = { primary: id, dir, px: e.clientX, py: e.clientY, starts, w: box.width, h: box.height, moved: false };
    }
  };

  // pointerdown on empty stage -> begin rubber-band
  const startBand = (e: React.PointerEvent) => {
    if (e.target !== stageRef.current && !(e.target as HTMLElement).classList.contains("te-grid") && !(e.target as HTMLElement).classList.contains("te-frame")) return;
    const box = stageRef.current?.getBoundingClientRect(); if (!box) return;
    const x0 = clamp((e.clientX - box.left) / box.width, 0, 1);
    const y0 = clamp((e.clientY - box.top) / box.height, 0, 1);
    bandDrag.current = { x0, y0, px: e.clientX, py: e.clientY, w: box.width, h: box.height, additive: e.shiftKey };
    setBand({ x: x0, y: y0, w: 0, h: 0 });
  };

  const addRegion = () => {
    const id = `region-${Date.now().toString(36).slice(-4)}`;
    const r: Region = { id, kind: "button", content: "sprite", layer: "components", rect: { x: 0.4, y: 0.45, w: 0.12, h: 0.08 }, bind: "play", label: id };
    setRegions((rs) => [...rs, r]); setSel(new Set([id]));
  };
  const delRegion = (id: string) => {
    setRegions((rs) => rs.filter((r) => r.id !== id));
    setSel((s) => { const n = new Set(s); n.delete(id); return n; });
  };

  const snapToPixels = () => {
    const { w: cw, h: ch } = template.canvas;
    setRegions((rs) => rs.map((r) => ({
      ...r, rect: {
        x: Math.round(r.rect.x * cw) / cw, y: Math.round(r.rect.y * ch) / ch,
        w: Math.round(r.rect.w * cw) / cw, h: Math.round(r.rect.h * ch) / ch,
      },
    })));
  };

  const json = () => JSON.stringify({ ...template, regions }, null, 2);
  const download = () => {
    const blob = new Blob([json()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${template.id || "template"}.json`;
    a.click(); URL.revokeObjectURL(a.href);
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(json()); setCopied(true); setTimeout(() => setCopied(false), 1500); }
    catch { /* clipboard may be blocked; download still works */ }
  };

  const onListClick = (e: React.MouseEvent, id: string) => {
    if (e.shiftKey) setSel((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
    else setSel(new Set([id]));
  };

  const selR = sel.size === 1 ? regions.find((r) => sel.has(r.id)) ?? null : null;
  const ar = `${template.canvas.w} / ${template.canvas.h}`;

  return (
    <div className="tpl-editor">
      <div className="te-toolbar">
        <strong>Template editor</strong>
        <button onClick={addRegion}>+ Region</button>
        <button onClick={snapToPixels}>Snap to px</button>
        <button onClick={download}>Download JSON</button>
        <button onClick={copy}>{copied ? "Copied ✓" : "Copy JSON"}</button>
        <span className="te-count">{regions.length} regions{sel.size > 1 ? ` · ${sel.size} selected` : ""}</span>
        <button className="te-close" onClick={onClose}>Close editor</button>
      </div>
      <div className="te-body">
        <div className="te-canvas">
          <div ref={stageRef} className="te-stage" style={{ aspectRatio: ar }} onPointerDown={startBand}>
            {frameUrl && <img className="te-frame" src={frameUrl} alt="" draggable={false} />}
            <div className="te-grid" />
            {regions.map((r) => (
              <div key={r.id}
                className={`te-region ${sel.has(r.id) ? "sel" : ""} ${sel.size > 1 && sel.has(r.id) ? "multi" : ""} k-${r.kind}`}
                style={{ left: `${r.rect.x * 100}%`, top: `${r.rect.y * 100}%`, width: `${r.rect.w * 100}%`, height: `${r.rect.h * 100}%` }}
                onPointerDown={(e) => startDrag(e, r.id, "move")}>
                <span className="te-tag">{regionName(r)}</span>
                {sel.size === 1 && sel.has(r.id) && (["n", "s", "e", "w", "ne", "nw", "se", "sw"] as HandleDir[]).map((d) => (
                  <span key={d} className={`te-handle h-${d}`} onPointerDown={(e) => startDrag(e, r.id, d)} />
                ))}
              </div>
            ))}
            {guides.map((g, i) => (
              <div key={i} className={`te-guide ${g.axis === "x" ? "v" : "h"}`}
                style={g.axis === "x" ? { left: `${g.at * 100}%` } : { top: `${g.at * 100}%` }} />
            ))}
            {band && (
              <div className="te-band" style={{ left: `${band.x * 100}%`, top: `${band.y * 100}%`, width: `${band.w * 100}%`, height: `${band.h * 100}%` }} />
            )}
          </div>
        </div>
        <div className="te-side">
          <div className="te-list">
            {regions.map((r) => (
              <button key={r.id} className={`te-item ${sel.has(r.id) ? "sel" : ""}`} onClick={(e) => onListClick(e, r.id)}>
                <span className="te-item-id">{r.id}</span>
                <span className="te-item-kind">{r.kind}</span>
              </button>
            ))}
          </div>
          {selR && (
            <div className="te-inspector">
              <label>id<input value={selR.id} onChange={(e) => patch(selR.id, { id: e.target.value })} /></label>
              <label>kind
                <select value={selR.kind} onChange={(e) => patch(selR.id, { kind: e.target.value as Kind })}>
                  {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
              <label>bind
                <select value={selR.bind ?? ""} onChange={(e) => patch(selR.id, { bind: e.target.value || undefined })}>
                  {BINDS.map((b) => <option key={b} value={b}>{b || "(none)"}</option>)}
                </select>
              </label>
              <label>content
                <select value={selR.content} onChange={(e) => patch(selR.id, { content: e.target.value as Region["content"] })}>
                  <option value="sprite">sprite</option><option value="dynamic">dynamic</option><option value="decoration">decoration</option>
                </select>
              </label>
              <label>label<input value={selR.label ?? ""} onChange={(e) => patch(selR.id, { label: e.target.value || undefined })} /></label>
              <div className="te-coords">
                {(["x", "y", "w", "h"] as (keyof Rect)[]).map((k) => (
                  <label key={k}>{k}
                    <input type="number" step="0.001" min="0" max="1" value={round(selR.rect[k])}
                      onChange={(e) => update(selR.id, { ...selR.rect, [k]: clamp(parseFloat(e.target.value) || 0, 0, 1) })} />
                  </label>
                ))}
              </div>
              <div className="te-px">px: {Math.round(selR.rect.x * template.canvas.w)},{Math.round(selR.rect.y * template.canvas.h)} · {Math.round(selR.rect.w * template.canvas.w)}×{Math.round(selR.rect.h * template.canvas.h)}</div>
              <button className="te-del" onClick={() => delRegion(selR.id)}>Delete region</button>
            </div>
          )}
          {sel.size > 1 && (
            <div className="te-inspector te-multi-note">{sel.size} regions selected — drag any one to move the group. Select a single region to edit it.</div>
          )}
        </div>
      </div>
    </div>
  );
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const round = (v: number) => Math.round(v * 1000) / 1000;
