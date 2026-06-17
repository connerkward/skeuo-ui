import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Kind, Pt, Region, Template } from "../template/schema";
import {
  arcPath, layoutButtons, overlapCount, shapePointsInRect, type Disc, type V2,
} from "./geometry";
import "./workshop.css";

/* ============================================================
   WorkshopEditor — the standalone "workshop" authoring surface
   (mounted at /editor.html, isolated from the main App).

   A human places & shapes controls over a body backdrop, then copies a
   valid Template (src/template/schema.ts) the generator/app can consume.

   Authoring affordances, all writing back into the SAME Template:
     • freeform DRAG / RESIZE of any region's normalized rect
     • transport buttons laid out grid OR along-curve (Y2K) with auto-REPACK
     • seek as a CAD arc (slider-arc.arc) OR a spline path (slider-path.path)
     • visualizer as a non-rectangular shape (circle / round-poly / blob)
     • envelope: pick a skin's frame.png OR upload a body silhouette
   ============================================================ */

// skins that ship a frame.png usable as the body backdrop (served from public/).
const SKINS = [
  "pebble", "bondi", "frog", "obelisk", "egypt", "halo", "fallout",
  "biomech", "cupcake", "tomato", "scarab", "vortex", "winamp", "wmp",
];

const KINDS: Kind[] = [
  "button", "toggle", "slider-h", "slider-v", "knob",
  "slider-arc", "slider-path", "segmented", "xy", "display", "flourish",
];

function starterTemplate(): Template {
  return {
    id: "untitled",
    name: "untitled",
    canvas: { w: 1024, h: 1536 },
    regions: [
      mk("visualizer", "display", { x: 0.32, y: 0.12, w: 0.36, h: 0.24 },
        { content: "dynamic", layer: "screen", dynamicType: "visualizer", shape: "ellipse" }),
      mk("seek", "slider-arc", { x: 0.22, y: 0.4, w: 0.56, h: 0.16 },
        { content: "sprite", layer: "components", bind: "seek", label: "Seek", arc: { start: 200, end: 340 } }),
      mk("prev", "button", { x: 0.3, y: 0.62, w: 0.08, h: 0.055 },
        { content: "sprite", layer: "components", bind: "prev", label: "prev", shape: "ellipse" }),
      mk("play", "button", { x: 0.46, y: 0.62, w: 0.08, h: 0.055 },
        { content: "sprite", layer: "components", bind: "play", label: "play", shape: "ellipse" }),
      mk("next", "button", { x: 0.62, y: 0.62, w: 0.08, h: 0.055 },
        { content: "sprite", layer: "components", bind: "next", label: "next", shape: "ellipse" }),
    ],
  };
}

function mk(id: string, kind: Kind, rect: Region["rect"], rest: Partial<Region>): Region {
  return { id, kind, content: "sprite", layer: "components", rect, ...rest };
}

type Handle = "" | "se";

export default function WorkshopEditor() {
  const [tpl, setTpl] = useState<Template>(starterTemplate);
  const [skin, setSkin] = useState("pebble");
  const [uploaded, setUploaded] = useState<string | null>(null);
  const [selId, setSelId] = useState<string | null>("play");
  const stageRef = useRef<HTMLDivElement>(null);

  const regions = tpl.regions;
  const sel = regions.find((r) => r.id === selId) ?? null;

  // ---- mutate helpers -----------------------------------------------------
  const patchRegion = useCallback((id: string, patch: Partial<Region>) => {
    setTpl((t) => ({ ...t, regions: t.regions.map((r) => (r.id === id ? { ...r, ...patch } : r)) }));
  }, []);
  const patchRect = useCallback((id: string, patch: Partial<Region["rect"]>) => {
    setTpl((t) => ({
      ...t,
      regions: t.regions.map((r) => (r.id === id ? { ...r, rect: { ...r.rect, ...patch } } : r)),
    }));
  }, []);

  // ---- freeform drag / resize (normalized stage space) --------------------
  const drag = useRef<{ id: string; handle: Handle; px: number; py: number; rect: Region["rect"] } | null>(null);

  const stageNorm = (clientX: number, clientY: number): V2 => {
    const rc = stageRef.current!.getBoundingClientRect();
    return { x: (clientX - rc.left) / rc.width, y: (clientY - rc.top) / rc.height };
  };

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = drag.current;
      if (!d || !stageRef.current) return;
      const p = stageNorm(e.clientX, e.clientY);
      const dx = p.x - d.px, dy = p.y - d.py;
      if (d.handle === "se") {
        patchRect(d.id, { w: clamp(d.rect.w + dx, 0.02, 1), h: clamp(d.rect.h + dy, 0.02, 1) });
      } else {
        patchRect(d.id, {
          x: clamp(d.rect.x + dx, 0, 1 - d.rect.w),
          y: clamp(d.rect.y + dy, 0, 1 - d.rect.h),
        });
      }
    };
    const up = () => (drag.current = null);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, [patchRect]);

  const startDrag = (e: React.PointerEvent, id: string, handle: Handle) => {
    e.preventDefault();
    e.stopPropagation();
    setSelId(id);
    const r = tpl.regions.find((x) => x.id === id);
    if (!r) return;
    const p = stageNorm(e.clientX, e.clientY);
    drag.current = { id, handle, px: p.x, py: p.y, rect: { ...r.rect } };
  };

  // ---- transport button layout (grid vs along-curve + repack) -------------
  const [btnMode, setBtnMode] = useState<"grid" | "curve">("curve");
  const [btnCurveR, setBtnCurveR] = useState(0.26);
  const [btnA0, setBtnA0] = useState(215);
  const [btnA1, setBtnA1] = useState(325);
  const [btnRepack, setBtnRepack] = useState(true);

  const visRegion = regions.find((r) => r.kind === "display") ?? null;
  const dialCenter: V2 = visRegion
    ? { x: visRegion.rect.x + visRegion.rect.w / 2, y: visRegion.rect.y + visRegion.rect.h / 2 }
    : { x: 0.5, y: 0.3 };

  const buttonRegions = useMemo(() => regions.filter((r) => r.kind === "button"), [regions]);

  const applyButtonLayout = useCallback(() => {
    const btns = buttonRegions;
    if (!btns.length) return;
    const avgSize = btns.reduce((s, r) => s + Math.max(r.rect.w, r.rect.h), 0) / btns.length;
    const discs: Disc[] = layoutButtons({
      mode: btnMode, count: btns.length, size: avgSize, center: dialCenter,
      curveRadius: btnCurveR, startDeg: btnA0, endDeg: btnA1, repack: btnRepack,
    });
    setTpl((t) => ({
      ...t,
      regions: t.regions.map((r) => {
        if (r.kind !== "button") return r;
        const i = btns.findIndex((b) => b.id === r.id);
        const d = discs[i];
        if (!d) return r;
        return {
          ...r,
          rect: {
            ...r.rect,
            x: clamp(d.x - r.rect.w / 2, 0, 1 - r.rect.w),
            y: clamp(d.y - r.rect.h / 2, 0, 1 - r.rect.h),
          },
        };
      }),
    }));
  }, [buttonRegions, btnMode, dialCenter, btnCurveR, btnA0, btnA1, btnRepack]);

  const btnOverlaps = useMemo(() => overlapCount(
    buttonRegions.map((r) => ({
      x: r.rect.x + r.rect.w / 2, y: r.rect.y + r.rect.h / 2, r: Math.max(r.rect.w, r.rect.h) / 2,
    })),
  ), [buttonRegions]);

  // ---- seek curve (slider-arc / slider-path) ------------------------------
  const seekRegion = regions.find((r) => r.id === "seek" || r.kind === "slider-arc" || r.kind === "slider-path") ?? null;
  const seekArc = seekRegion?.arc ?? { start: 200, end: 340 };
  const setSeekArc = (patch: Partial<{ start: number; end: number }>) => {
    if (!seekRegion) return;
    patchRegion(seekRegion.id, { kind: "slider-arc", arc: { ...seekArc, ...patch }, path: undefined });
  };
  const makeSeekPath = () => {
    if (!seekRegion) return;
    const path: Pt[] = [
      { x: 0.06, y: 0.7 }, { x: 0.3, y: 0.3 }, { x: 0.5, y: 0.6 },
      { x: 0.7, y: 0.3 }, { x: 0.94, y: 0.7 },
    ];
    patchRegion(seekRegion.id, { kind: "slider-path", path, arc: undefined });
  };

  // ---- visualizer shape ----------------------------------------------------
  const [visShape, setVisShape] = useState<"circle" | "poly" | "blob">("circle");
  const [visSides, setVisSides] = useState(6);
  const [visCorner, setVisCorner] = useState(0.25);
  const applyVisShape = useCallback(() => {
    if (!visRegion) return;
    if (visShape === "circle") {
      patchRegion(visRegion.id, { shape: "ellipse", path: undefined, vis: undefined });
    } else {
      const path = shapePointsInRect(visShape, visSides, visCorner);
      patchRegion(visRegion.id, { shape: undefined, path, vis: "blob" });
    }
  }, [visRegion, visShape, visSides, visCorner, patchRegion]);

  // ---- envelope (backdrop) -------------------------------------------------
  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (uploaded) URL.revokeObjectURL(uploaded);
    setUploaded(URL.createObjectURL(file));
  };
  const backdrop = uploaded ?? `/skins/${skin}/frame.png`;

  // ---- add / remove region -------------------------------------------------
  const addRegion = () => {
    const id = `region-${regions.length + 1}-${Math.random().toString(36).slice(2, 5)}`;
    setTpl((t) => ({
      ...t,
      regions: [...t.regions, mk(id, "button", { x: 0.45, y: 0.5, w: 0.08, h: 0.06 },
        { content: "sprite", layer: "components", label: id })],
    }));
    setSelId(id);
  };
  const removeRegion = (id: string) => {
    setTpl((t) => ({ ...t, regions: t.regions.filter((r) => r.id !== id) }));
    if (selId === id) setSelId(null);
  };

  // ---- export --------------------------------------------------------------
  const json = useMemo(() => JSON.stringify(tpl, null, 2), [tpl]);
  const [copied, setCopied] = useState(false);
  const copyJson = async () => {
    try { await navigator.clipboard.writeText(json); } catch { /* clipboard blocked (headless) */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="wk-root">
      <header className="wk-head">
        <strong>Template Editor</strong>
        <span className="wk-sub">workshop — place &amp; shape controls, copy a valid Template</span>
      </header>

      <div className="wk-body">
        {/* ---- STAGE ---- */}
        <div className="wk-stage-wrap">
          <div
            ref={stageRef}
            className="wk-stage"
            style={{ aspectRatio: `${tpl.canvas.w} / ${tpl.canvas.h}`, backgroundImage: `url(${backdrop})` }}
            onPointerDown={() => setSelId(null)}
          >
            {seekRegion && <SeekOverlay region={seekRegion} />}
            {regions.map((r) => (
              <RegionBox
                key={r.id}
                region={r}
                selected={r.id === selId}
                onDown={(e) => startDrag(e, r.id, "")}
                onResize={(e) => startDrag(e, r.id, "se")}
              />
            ))}
          </div>
        </div>

        {/* ---- PANEL ---- */}
        <aside className="wk-panel">
          <section>
            <h3>Envelope (backdrop)</h3>
            <label className="wk-row">
              <span>skin frame</span>
              <select value={skin} onChange={(e) => { setUploaded(null); setSkin(e.target.value); }}>
                {SKINS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="wk-row">
              <span>upload silhouette</span>
              <input type="file" accept="image/*" onChange={onUpload} data-testid="upload" />
            </label>
            {uploaded && <button className="wk-btn ghost" onClick={() => setUploaded(null)}>clear upload</button>}
          </section>

          <section>
            <h3>Transport buttons ({buttonRegions.length})</h3>
            <div className="wk-seg" role="tablist">
              <button data-on={btnMode === "grid"} onClick={() => setBtnMode("grid")} data-testid="btn-grid">grid row</button>
              <button data-on={btnMode === "curve"} onClick={() => setBtnMode("curve")} data-testid="btn-curve">along curve (Y2K)</button>
            </div>
            {btnMode === "curve" && <>
              <Range label="curve radius" min={0.1} max={0.5} step={0.005} value={btnCurveR} onChange={setBtnCurveR} />
              <Range label="start°" min={0} max={360} step={2} value={btnA0} onChange={setBtnA0} />
              <Range label="end°" min={0} max={360} step={2} value={btnA1} onChange={setBtnA1} />
            </>}
            <label className="wk-check">
              <input type="checkbox" checked={btnRepack} onChange={(e) => setBtnRepack(e.target.checked)} />
              repack (no overlap)
            </label>
            <button className="wk-btn" onClick={applyButtonLayout} data-testid="apply-layout">apply layout</button>
            <p className="wk-stat">overlaps: <b data-bad={btnOverlaps > 0}>{btnOverlaps}</b></p>
          </section>

          <section>
            <h3>Seek — CAD curve</h3>
            {seekRegion ? <>
              <div className="wk-seg">
                <button data-on={seekRegion.kind === "slider-arc"} onClick={() => setSeekArc({})}>arc</button>
                <button data-on={seekRegion.kind === "slider-path"} onClick={makeSeekPath}>spline path</button>
              </div>
              {seekRegion.kind === "slider-arc" && <>
                <Range label="start°" min={0} max={360} step={2} value={seekArc.start} onChange={(v) => setSeekArc({ start: v })} />
                <Range label="end°" min={0} max={360} step={2} value={seekArc.end} onChange={(v) => setSeekArc({ end: v })} />
              </>}
              {seekRegion.kind === "slider-path" &&
                <p className="wk-stat">spline path · {seekRegion.path?.length ?? 0} pts (value = arc-length)</p>}
            </> : <p className="wk-stat">no seek region</p>}
          </section>

          <section>
            <h3>Visualizer shape</h3>
            {visRegion ? <>
              <div className="wk-seg">
                <button data-on={visShape === "circle"} onClick={() => setVisShape("circle")} data-testid="vis-circle">circle</button>
                <button data-on={visShape === "poly"} onClick={() => setVisShape("poly")} data-testid="vis-poly">round-poly</button>
                <button data-on={visShape === "blob"} onClick={() => setVisShape("blob")} data-testid="vis-blob">blob</button>
              </div>
              {visShape === "poly" && <>
                <Range label="sides" min={3} max={10} step={1} value={visSides} onChange={setVisSides} />
                <Range label="corner" min={0} max={0.5} step={0.01} value={visCorner} onChange={setVisCorner} />
              </>}
              <button className="wk-btn" onClick={applyVisShape} data-testid="apply-shape">apply shape</button>
            </> : <p className="wk-stat">no display region</p>}
          </section>

          <section>
            <h3>Region inspector</h3>
            <label className="wk-row">
              <span>select</span>
              <select value={selId ?? ""} onChange={(e) => setSelId(e.target.value || null)}>
                <option value="">—</option>
                {regions.map((r) => <option key={r.id} value={r.id}>{r.id} · {r.kind}</option>)}
              </select>
            </label>
            {sel && <>
              <label className="wk-row">
                <span>kind</span>
                <select value={sel.kind} onChange={(e) => patchRegion(sel.id, { kind: e.target.value as Kind })}>
                  {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
              <label className="wk-row"><span>label</span>
                <input value={sel.label ?? ""} onChange={(e) => patchRegion(sel.id, { label: e.target.value })} />
              </label>
              <button className="wk-btn ghost" onClick={() => removeRegion(sel.id)}>delete region</button>
            </>}
            <button className="wk-btn" onClick={addRegion}>+ add region</button>
          </section>

          <section>
            <h3>Export</h3>
            <button className="wk-btn primary" onClick={copyJson} data-testid="copy">{copied ? "copied ✓" : "Copy template JSON"}</button>
            <textarea className="wk-json" readOnly value={json} data-testid="export-json" />
          </section>
        </aside>
      </div>
    </div>
  );
}

/* ---- a draggable / resizable region box on the stage ---------------------- */
function RegionBox({ region: r, selected, onDown, onResize }: {
  region: Region; selected: boolean;
  onDown: (e: React.PointerEvent) => void;
  onResize: (e: React.PointerEvent) => void;
}) {
  const style: React.CSSProperties = {
    left: `${r.rect.x * 100}%`, top: `${r.rect.y * 100}%`,
    width: `${r.rect.w * 100}%`, height: `${r.rect.h * 100}%`,
  };
  return (
    <div
      className={`wk-region kind-${r.kind} ${selected ? "is-sel" : ""}`}
      style={style}
      onPointerDown={onDown}
      data-id={r.id}
    >
      {regionShapeSvg(r)}
      <span className="wk-region-label">{r.label ?? r.id}</span>
      <span className="wk-handle" onPointerDown={onResize} />
    </div>
  );
}

// preview of the region's stored shape inside its box
function regionShapeSvg(r: Region): React.ReactNode {
  if (r.kind === "display" && r.path && r.path.length) {
    const d = r.path.map((p, i) => `${i ? "L" : "M"}${(p.x * 100).toFixed(2)} ${(p.y * 100).toFixed(2)}`).join(" ") + " Z";
    return <svg className="wk-shape" viewBox="0 0 100 100" preserveAspectRatio="none"><path d={d} /></svg>;
  }
  if (r.shape === "ellipse")
    return <svg className="wk-shape" viewBox="0 0 100 100" preserveAspectRatio="none"><ellipse cx="50" cy="50" rx="49" ry="49" /></svg>;
  if (r.kind === "slider-path" && r.path?.length) {
    const d = r.path.map((p, i) => `${i ? "L" : "M"}${(p.x * 100).toFixed(2)} ${(p.y * 100).toFixed(2)}`).join(" ");
    return <svg className="wk-shape line" viewBox="0 0 100 100" preserveAspectRatio="none"><path d={d} fill="none" /></svg>;
  }
  return null;
}

/* ---- seek curve overlay (full-stage SVG so the arc reads as a CAD curve) --- */
function SeekOverlay({ region: r }: { region: Region }) {
  const cx = r.rect.x + r.rect.w / 2;
  const cy = r.rect.y + r.rect.h / 2;
  let d = "";
  if (r.kind === "slider-arc") {
    const radius = Math.min(r.rect.w, r.rect.h) / 2 || 0.1;
    d = arcPath(cx, cy, radius, r.arc?.start ?? 200, r.arc?.end ?? 340);
  } else if (r.kind === "slider-path" && r.path?.length) {
    d = r.path.map((p, i) =>
      `${i ? "L" : "M"}${((r.rect.x + p.x * r.rect.w) * 100).toFixed(2)} ${((r.rect.y + p.y * r.rect.h) * 100).toFixed(2)}`,
    ).join(" ");
  } else return null;
  return (
    <svg className="wk-seek-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
      <path d={d} fill="none" />
    </svg>
  );
}

/* ---- labeled range row ---------------------------------------------------- */
function Range({ label, min, max, step, value, onChange }: {
  label: string; min: number; max: number; step: number; value: number; onChange: (v: number) => void;
}) {
  return (
    <label className="wk-range">
      <span className="wk-range-top">{label}<b>{value}</b></span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(+e.target.value)} />
    </label>
  );
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}
