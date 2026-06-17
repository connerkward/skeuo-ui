import { useEffect, useMemo, useRef, useState } from "react";
import type { Region, Template, Kind, Rect, DynamicType, Content } from "../template/schema";
import "./editor.css";

// Draggable + resizable template editor. Overlays every Region of `template`
// as a box on the frame image (same normalized rects the runtime compositor
// uses), lets you move/resize/add/delete regions and edit kind+bind, and
// exports the edited template.json (download + copy). Coords are normalized
// 0..1; the readout shows them and a "snap to px" pass rounds to the canvas grid.
//
// Supports: alignment snapping (move + resize) with cyan guide lines,
// rubber-band multi-select + group move, shift-click toggle.
//
// UX layer: the list and inspector speak in *roles* (Play button, Seek bar,
// Visualizer screen) — friendly names derived from bind / dynamicType / kind —
// and the raw numeric coords + content/layer live under a collapsed Advanced
// disclosure. The geometry/snapping/multi-select engine below is unchanged.
interface Props {
  template: Template;
  frameUrl?: string;          // background frame.png (optional; grid shown if absent)
  onApply: (t: Template) => void;  // live-update the preview
  onClose: () => void;
}

const KINDS: Kind[] = ["button", "toggle", "slider-h", "slider-v", "knob", "slider-arc", "segmented", "xy", "display", "flourish"];
const BINDS = ["", "play", "pause", "stop", "prev", "next", "eject", "seek", "volume", "balance", "shuffle", "eqOn", "eqAuto", "mute", "eqBand", "repeatMode", "eqPreset"];
const DYN_TYPES: DynamicType[] = ["visualizer", "marquee", "playlist", "time", "meta", "eq-curve", "title"];

type HandleDir = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

// Snap threshold in pixels (converted to normalized units per-axis).
const SNAP_PX = 6;

interface Guide { axis: "x" | "y"; at: number; }

/* ---------- friendly naming / roles ------------------------------------ */

// Human title-case a token: "eqBand" -> "Eq Band", "slider-h" -> "Slider H",
// "screen-2" -> "Screen 2".
const humanize = (s: string): string =>
  s.replace(/[-_]+/g, " ")
   .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
   .trim()
   .replace(/\b\w/g, (c) => c.toUpperCase());

// Friendly display names for known binds / dynamic types.
const BIND_LABEL: Record<string, string> = {
  play: "Play", pause: "Pause", stop: "Stop", prev: "Prev", next: "Next",
  eject: "Eject", seek: "Seek", volume: "Volume", balance: "Balance",
  shuffle: "Shuffle", eqOn: "EQ On", eqAuto: "EQ Auto", mute: "Mute",
  eqBand: "EQ Band", repeatMode: "Repeat", eqPreset: "EQ Preset",
};
const DYN_LABEL: Record<string, string> = {
  visualizer: "Visualizer", marquee: "Marquee", playlist: "Playlist",
  time: "Clock", meta: "Track Info", "eq-curve": "EQ Curve", title: "Title",
};
// Kind nouns used to compose a role name when there's no bind/dyn ("Knob", "Switch").
const KIND_NOUN: Record<Kind, string> = {
  button: "Button", toggle: "Switch", "slider-h": "Slider", "slider-v": "Slider",
  knob: "Knob", "slider-arc": "Ring", "slider-path": "Path", segmented: "Segments",
  xy: "Pad", display: "Screen", flourish: "Ornament",
};

// The single human-readable name shown in the list / on the box / as the Name field.
const regionName = (r: Region): string => {
  if (r.bind && BIND_LABEL[r.bind]) return BIND_LABEL[r.bind];
  if (r.dynamicType && DYN_LABEL[r.dynamicType]) return DYN_LABEL[r.dynamicType];
  if (r.label) return r.label;
  if (r.bind) return humanize(r.bind);
  if (r.dynamicType) return humanize(r.dynamicType);
  return humanize(r.id);
};

// Short, muted kind chip text ("Button", "Screen", "Knob").
const kindChip = (r: Region): string => KIND_NOUN[r.kind] ?? humanize(r.kind);

// The full role line for the inspector subhead ("Play button", "Visualizer screen").
const roleLabel = (r: Region): string => {
  const noun = KIND_NOUN[r.kind] ?? humanize(r.kind);
  if (r.bind && BIND_LABEL[r.bind]) return `${BIND_LABEL[r.bind]} ${noun.toLowerCase()}`;
  if (r.dynamicType && DYN_LABEL[r.dynamicType]) return `${DYN_LABEL[r.dynamicType]} ${noun.toLowerCase()}`;
  return noun;
};

// A small glyph hint per kind for the list chip.
const kindGlyph = (k: Kind): string => ({
  button: "▢", toggle: "◉", "slider-h": "▭", "slider-v": "▯", knob: "◍",
  "slider-arc": "◜", "slider-path": "〜", segmented: "▤", xy: "✛",
  display: "▥", flourish: "✦",
} as Record<Kind, string>)[k] ?? "▢";

// ----- The Role picker: a flat menu of meaningful presets (kind + bind/dyn). ---
interface RolePreset { id: string; label: string; kind: Kind; bind?: string; dynamicType?: DynamicType; content: Content; }
const ROLE_PRESETS: RolePreset[] = [
  { id: "play", label: "Play button", kind: "button", bind: "play", content: "sprite" },
  { id: "pause", label: "Pause button", kind: "button", bind: "pause", content: "sprite" },
  { id: "stop", label: "Stop button", kind: "button", bind: "stop", content: "sprite" },
  { id: "prev", label: "Prev button", kind: "button", bind: "prev", content: "sprite" },
  { id: "next", label: "Next button", kind: "button", bind: "next", content: "sprite" },
  { id: "eject", label: "Eject button", kind: "button", bind: "eject", content: "sprite" },
  { id: "seek", label: "Seek bar", kind: "slider-h", bind: "seek", content: "sprite" },
  { id: "volume", label: "Volume knob", kind: "knob", bind: "volume", content: "sprite" },
  { id: "balance", label: "Balance knob", kind: "knob", bind: "balance", content: "sprite" },
  { id: "eqBand", label: "EQ band fader", kind: "slider-v", bind: "eqBand", content: "sprite" },
  { id: "shuffle", label: "Shuffle switch", kind: "toggle", bind: "shuffle", content: "sprite" },
  { id: "eqOn", label: "EQ-on switch", kind: "toggle", bind: "eqOn", content: "sprite" },
  { id: "mute", label: "Mute switch", kind: "toggle", bind: "mute", content: "sprite" },
  { id: "repeatMode", label: "Repeat switch", kind: "toggle", bind: "repeatMode", content: "sprite" },
  { id: "visualizer", label: "Visualizer screen", kind: "display", dynamicType: "visualizer", content: "dynamic" },
  { id: "marquee", label: "Marquee / scroller", kind: "display", dynamicType: "marquee", content: "dynamic" },
  { id: "playlist", label: "Playlist screen", kind: "display", dynamicType: "playlist", content: "dynamic" },
  { id: "time", label: "Clock display", kind: "display", dynamicType: "time", content: "dynamic" },
  { id: "title", label: "Title display", kind: "display", dynamicType: "title", content: "dynamic" },
  { id: "flourish", label: "Ornament (decoration)", kind: "flourish", content: "decoration" },
];
// Match a region to a preset id (for the picker's current value); "" = custom.
const presetIdFor = (r: Region): string => {
  const m = ROLE_PRESETS.find((p) =>
    p.kind === r.kind &&
    (p.bind ?? undefined) === (r.bind ?? undefined) &&
    (p.dynamicType ?? undefined) === (r.dynamicType ?? undefined));
  return m?.id ?? "";
};

export function TemplateEditor({ template, frameUrl, onApply, onClose }: Props) {
  const [regions, setRegions] = useState<Region[]>(() => template.regions.map((r) => ({ ...r, rect: { ...r.rect } })));
  const [sel, setSel] = useState<Set<string>>(() => new Set(regions[0]?.id ? [regions[0].id] : []));
  const [copied, setCopied] = useState(false);
  const [advanced, setAdvanced] = useState(false);
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

  // Make a clean, unique id from a friendly base ("seek", "screen", "volume").
  const uniqueId = (base: string): string => {
    const taken = new Set(regionsRef.current.map((r) => r.id));
    const slug = base.replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase() || "region";
    if (!taken.has(slug)) return slug;
    for (let i = 2; i < 999; i++) { const c = `${slug}-${i}`; if (!taken.has(c)) return c; }
    return `${slug}-${Date.now().toString(36).slice(-3)}`;
  };

  const addRegion = () => {
    // friendly default: a button bound to the first unused transport role, else a knob.
    const used = new Set(regionsRef.current.map((r) => r.bind).filter(Boolean));
    const order = ["play", "pause", "stop", "prev", "next", "seek", "volume"];
    const free = order.find((b) => !used.has(b)) ?? "play";
    const preset = ROLE_PRESETS.find((p) => p.bind === free)!;
    const id = uniqueId(preset.bind || preset.kind);
    const r: Region = {
      id, kind: preset.kind, content: preset.content, layer: "components",
      rect: { x: 0.4, y: 0.45, w: 0.12, h: 0.08 }, bind: preset.bind, label: undefined,
    };
    setRegions((rs) => [...rs, r]); setSel(new Set([id]));
  };

  // Add a screen: default to the first unused dynamicType (visualizer→marquee→…).
  const addScreen = () => {
    const used = new Set(regionsRef.current.map((r) => r.dynamicType).filter(Boolean));
    const free = (DYN_TYPES.find((d) => !used.has(d)) ?? "visualizer") as DynamicType;
    const id = uniqueId(free);
    const r: Region = {
      id, kind: "display", content: "dynamic", layer: "screen",
      rect: { x: 0.3, y: 0.18, w: 0.4, h: 0.16 }, dynamicType: free,
    };
    setRegions((rs) => [...rs, r]); setSel(new Set([id]));
  };

  const delRegion = (id: string) => {
    setRegions((rs) => rs.filter((r) => r.id !== id));
    setSel((s) => { const n = new Set(s); n.delete(id); return n; });
  };

  // Apply a role preset to the selected region (kind + bind/dyn + content).
  const applyRole = (id: string, presetId: string) => {
    const p = ROLE_PRESETS.find((x) => x.id === presetId);
    if (!p) return;
    patch(id, { kind: p.kind, bind: p.bind, dynamicType: p.dynamicType, content: p.content });
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
        <div className="te-tb-group">
          <button onClick={addRegion} title="Add a control">+ Control</button>
          <button onClick={addScreen} title="Add a dynamic screen">+ Screen</button>
        </div>
        <div className="te-tb-group">
          <button onClick={snapToPixels} title="Round every rect to the pixel grid">Snap to px</button>
        </div>
        <div className="te-tb-group">
          <button onClick={download}>Download</button>
          <button onClick={copy}>{copied ? "Copied ✓" : "Copy JSON"}</button>
        </div>
        <span className="te-count">{regions.length} regions{sel.size > 1 ? ` · ${sel.size} selected` : ""}</span>
        <button className="te-close" onClick={onClose}>Done</button>
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
          <div className="te-list-head">Regions</div>
          <div className="te-list">
            {regions.map((r) => (
              <button key={r.id} className={`te-item ${sel.has(r.id) ? "sel" : ""}`} onClick={(e) => onListClick(e, r.id)}>
                <span className="te-item-glyph" aria-hidden>{kindGlyph(r.kind)}</span>
                <span className="te-item-name">{regionName(r)}</span>
                <span className="te-item-chip">{kindChip(r)}</span>
              </button>
            ))}
          </div>
          {selR && (
            <div className="te-inspector" key={selR.id}>
              <div className="te-insp-head">
                <div className="te-insp-name">{regionName(selR)}</div>
                <div className="te-insp-role">{roleLabel(selR)}</div>
              </div>

              <label className="te-field">Name
                <input value={selR.label ?? ""} placeholder={regionName(selR)}
                  onChange={(e) => patch(selR.id, { label: e.target.value || undefined })} />
              </label>

              <label className="te-field">Type / Role
                <select value={presetIdFor(selR)} onChange={(e) => applyRole(selR.id, e.target.value)}>
                  {presetIdFor(selR) === "" && <option value="">Custom ({roleLabel(selR)})</option>}
                  {ROLE_PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
              </label>

              <button className="te-disclose" onClick={() => setAdvanced((v) => !v)}>
                <span className={`te-chevron ${advanced ? "open" : ""}`}>▸</span> Advanced
              </button>

              {advanced && (
                <div className="te-advanced">
                  <label className="te-field">id
                    <input value={selR.id} onChange={(e) => patch(selR.id, { id: e.target.value })} />
                  </label>
                  <div className="te-field-row">
                    <label className="te-field">kind
                      <select value={selR.kind} onChange={(e) => patch(selR.id, { kind: e.target.value as Kind })}>
                        {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                      </select>
                    </label>
                    <label className="te-field">bind
                      <select value={selR.bind ?? ""} onChange={(e) => patch(selR.id, { bind: e.target.value || undefined })}>
                        {BINDS.map((b) => <option key={b} value={b}>{b || "(none)"}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="te-field-row">
                    <label className="te-field">content
                      <select value={selR.content} onChange={(e) => patch(selR.id, { content: e.target.value as Content })}>
                        <option value="sprite">sprite</option><option value="dynamic">dynamic</option><option value="decoration">decoration</option>
                      </select>
                    </label>
                    <label className="te-field">dynamicType
                      <select value={selR.dynamicType ?? ""} onChange={(e) => patch(selR.id, { dynamicType: (e.target.value || undefined) as DynamicType | undefined })}>
                        <option value="">(none)</option>
                        {DYN_TYPES.map((d) => <option key={d} value={d}>{d}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="te-coords">
                    {(["x", "y", "w", "h"] as (keyof Rect)[]).map((k) => (
                      <label key={k} className="te-field">{k}
                        <input type="number" step="0.001" min="0" max="1" value={round(selR.rect[k])}
                          onChange={(e) => update(selR.id, { ...selR.rect, [k]: clamp(parseFloat(e.target.value) || 0, 0, 1) })} />
                      </label>
                    ))}
                  </div>
                  <div className="te-px">px: {Math.round(selR.rect.x * template.canvas.w)},{Math.round(selR.rect.y * template.canvas.h)} · {Math.round(selR.rect.w * template.canvas.w)}×{Math.round(selR.rect.h * template.canvas.h)}</div>
                </div>
              )}

              <button className="te-del" onClick={() => delRegion(selR.id)}>Delete region</button>
            </div>
          )}
          {sel.size > 1 && (
            <div className="te-inspector te-multi-note">{sel.size} regions selected — drag any one to move the group. Select a single region to edit it.</div>
          )}
          {sel.size === 0 && (
            <div className="te-inspector te-multi-note">No region selected — click one in the list or on the canvas, or rubber-band a group.</div>
          )}
        </div>
      </div>
    </div>
  );
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const round = (v: number) => Math.round(v * 1000) / 1000;
