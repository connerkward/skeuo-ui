import { useEffect, useMemo, useRef, useState } from "react";
import type { Region, Template, Kind, Rect } from "../template/schema";
import "./editor.css";

// Draggable + resizable template editor. Overlays every Region of `template`
// as a box on the frame image (same normalized rects the runtime compositor
// uses), lets you move/resize/add/delete regions and edit kind+bind, and
// exports the edited template.json (download + copy). Coords are normalized
// 0..1; the readout shows them and a "snap to px" pass rounds to the canvas grid.
interface Props {
  template: Template;
  frameUrl?: string;          // background frame.png (optional; grid shown if absent)
  onApply: (t: Template) => void;  // live-update the preview
  onClose: () => void;
}

const KINDS: Kind[] = ["button", "toggle", "slider-h", "slider-v", "knob", "slider-arc", "segmented", "xy", "display", "flourish"];
const BINDS = ["", "play", "pause", "stop", "prev", "next", "eject", "seek", "volume", "balance", "shuffle", "eqOn", "eqAuto", "mute", "eqBand", "repeatMode", "eqPreset"];

type HandleDir = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

export function TemplateEditor({ template, frameUrl, onApply, onClose }: Props) {
  const [regions, setRegions] = useState<Region[]>(() => template.regions.map((r) => ({ ...r, rect: { ...r.rect } })));
  const [sel, setSel] = useState<string | null>(regions[0]?.id ?? null);
  const [copied, setCopied] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ id: string; dir: HandleDir; px: number; py: number; rect: Rect; w: number; h: number } | null>(null);

  // re-seed when a different template comes in (e.g. switching skins)
  useEffect(() => {
    setRegions(template.regions.map((r) => ({ ...r, rect: { ...r.rect } })));
    setSel(template.regions[0]?.id ?? null);
  }, [template]);

  // push edits to the live preview whenever regions change
  const out = useMemo<Template>(() => ({ ...template, regions }), [template, regions]);
  useEffect(() => { onApply(out); }, [out, onApply]);

  const update = (id: string, rect: Rect) =>
    setRegions((rs) => rs.map((r) => (r.id === id ? { ...r, rect } : r)));
  const patch = (id: string, p: Partial<Region>) =>
    setRegions((rs) => rs.map((r) => (r.id === id ? { ...r, ...p } : r)));

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = drag.current; const st = stageRef.current; if (!d || !st) return;
      const box = st.getBoundingClientRect();
      const dx = (e.clientX - d.px) / box.width;
      const dy = (e.clientY - d.py) / box.height;
      let { x, y, w, h } = d.rect;
      const min = 0.01;
      if (d.dir === "move") { x = clamp(d.rect.x + dx, 0, 1 - w); y = clamp(d.rect.y + dy, 0, 1 - h); }
      else {
        if (d.dir.includes("e")) w = clamp(d.rect.w + dx, min, 1 - d.rect.x);
        if (d.dir.includes("s")) h = clamp(d.rect.h + dy, min, 1 - d.rect.y);
        if (d.dir.includes("w")) { const nx = clamp(d.rect.x + dx, 0, d.rect.x + d.rect.w - min); w = d.rect.w + (d.rect.x - nx); x = nx; }
        if (d.dir.includes("n")) { const ny = clamp(d.rect.y + dy, 0, d.rect.y + d.rect.h - min); h = d.rect.h + (d.rect.y - ny); y = ny; }
      }
      update(d.id, { x, y, w, h });
    };
    const up = () => (drag.current = null);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, []);

  const startDrag = (e: React.PointerEvent, id: string, dir: HandleDir) => {
    e.stopPropagation(); setSel(id);
    const r = regions.find((x) => x.id === id); const box = stageRef.current?.getBoundingClientRect();
    if (!r || !box) return;
    drag.current = { id, dir, px: e.clientX, py: e.clientY, rect: { ...r.rect }, w: box.width, h: box.height };
  };

  const addRegion = () => {
    const id = `region-${Date.now().toString(36).slice(-4)}`;
    const r: Region = { id, kind: "button", content: "sprite", layer: "components", rect: { x: 0.4, y: 0.45, w: 0.12, h: 0.08 }, bind: "play", label: id };
    setRegions((rs) => [...rs, r]); setSel(id);
  };
  const delRegion = (id: string) => {
    setRegions((rs) => rs.filter((r) => r.id !== id));
    setSel((s) => (s === id ? null : s));
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

  const selR = regions.find((r) => r.id === sel) ?? null;
  const ar = `${template.canvas.w} / ${template.canvas.h}`;

  return (
    <div className="tpl-editor">
      <div className="te-toolbar">
        <strong>Template editor</strong>
        <button onClick={addRegion}>+ Region</button>
        <button onClick={snapToPixels}>Snap to px</button>
        <button onClick={download}>Download JSON</button>
        <button onClick={copy}>{copied ? "Copied ✓" : "Copy JSON"}</button>
        <span className="te-count">{regions.length} regions</span>
        <button className="te-close" onClick={onClose}>Close editor</button>
      </div>
      <div className="te-body">
        <div className="te-canvas">
          <div ref={stageRef} className="te-stage" style={{ aspectRatio: ar }}>
            {frameUrl && <img className="te-frame" src={frameUrl} alt="" draggable={false} />}
            <div className="te-grid" />
            {regions.map((r) => (
              <div key={r.id}
                className={`te-region ${r.id === sel ? "sel" : ""} k-${r.kind}`}
                style={{ left: `${r.rect.x * 100}%`, top: `${r.rect.y * 100}%`, width: `${r.rect.w * 100}%`, height: `${r.rect.h * 100}%` }}
                onPointerDown={(e) => startDrag(e, r.id, "move")}>
                <span className="te-tag">{r.id}</span>
                {(["n", "s", "e", "w", "ne", "nw", "se", "sw"] as HandleDir[]).map((d) => (
                  <span key={d} className={`te-handle h-${d}`} onPointerDown={(e) => startDrag(e, r.id, d)} />
                ))}
              </div>
            ))}
          </div>
        </div>
        <div className="te-side">
          <div className="te-list">
            {regions.map((r) => (
              <button key={r.id} className={`te-item ${r.id === sel ? "sel" : ""}`} onClick={() => setSel(r.id)}>
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
        </div>
      </div>
    </div>
  );
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const round = (v: number) => Math.round(v * 1000) / 1000;
