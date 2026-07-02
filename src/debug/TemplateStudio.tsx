// DEV-ONLY Template Studio (?studio). A human-facing interface to SEED / GENERATE a data
// template and see it PACKED live — all on the REAL shipping heuristics:
//   • cheap heuristic randomizer  → layoutRandomP / layoutArch (the 10 archetypes)
//   • LLM data-template generator → deriveLayout via POST /api/derive (heuristic-guided prompt)
//   • packer                      → repackTemplate (canon-size + resolveOverlaps), live
// Each component has a CENTROID (draggable), an ARBITRARY SHAPE connected to it, and a modular
// DIFFUSENESS (soft-guide spread). Left = raw seeded template, right = packed result.
import { useMemo, useState, useCallback } from "react";
import {
  layoutRandomP, layoutArch, repackTemplate, ARCHETYPES, DEFAULT_PARAMS,
  GEN_W, GEN_H, type Params,
} from "../generate/layouts";
import type { Region, Kind } from "../template/schema";

type SR = Region & { shapeKind?: string; diff?: number };
const KINDS: Kind[] = ["button", "knob", "toggle", "slider-h", "slider-v", "slider-arc", "display"];
const SHAPEKINDS = ["auto", "circle", "square", "hexagon", "wedge", "kidney", "lozenge", "teardrop", "blob", "arc"];
const KCOL: Record<string, string> = {
  button: "#ff9a3c", knob: "#3ce07f", toggle: "#40c8ff", "slider-h": "#ff6a6a",
  "slider-v": "#c47cff", "slider-arc": "#ff6a6a", display: "#8a8a99", flourish: "#556",
};

// unit polygon (0..1 space) for an arbitrary shape centred in the component's rect. circle→null (ellipse).
function unitPoly(kind: string): [number, number][] | null {
  switch (kind) {
    case "square": return [[.06, .06], [.94, .06], [.94, .94], [.06, .94]];
    case "hexagon": return [[.5, .02], [.95, .27], [.95, .73], [.5, .98], [.05, .73], [.05, .27]];
    case "wedge": return [[.04, .16], [.72, .02], [.98, .5], [.72, .98], [.04, .84], [.24, .5]];
    case "kidney": return [[.1, .28], [.5, .12], [.9, .3], [.82, .55], [.92, .78], [.5, .95], [.14, .76], [.24, .5]];
    case "lozenge": return [[.5, .02], [.98, .5], [.5, .98], [.02, .5]];
    case "teardrop": return [[.5, .03], [.86, .3], [.9, .68], [.62, .96], [.36, .96], [.1, .68], [.14, .3]];
    case "blob": return [[.24, .1], [.62, .06], [.92, .28], [.86, .6], [.96, .84], [.56, .96], [.2, .88], [.06, .56], [.16, .3]];
    case "arc": return [[.02, .34], [.5, .06], [.98, .34], [.86, .5], [.98, .66], [.5, .5], [.02, .66], [.14, .5]];
    default: return null;   // circle / auto → ellipse
  }
}
const autoShape = (r: SR): string => r.shapeKind && r.shapeKind !== "auto" ? r.shapeKind
  : r.kind === "knob" ? "circle" : r.kind === "button" ? "wedge" : r.kind === "display" ? "square"
  : r.kind === "slider-arc" ? "arc" : "square";
const cx = (r: SR) => r.rect.x + r.rect.w / 2;
const cy = (r: SR) => r.rect.y + r.rect.h / 2;

export default function TemplateStudio() {
  const [P, setP] = useState<Params>({ ...DEFAULT_PARAMS });
  const [regions, setRegions] = useState<SR[]>(() => layoutArch("console", DEFAULT_PARAMS) as SR[]);
  const [sel, setSel] = useState<string | null>(null);
  const [globalDiff, setGlobalDiff] = useState(0.35);
  const [prompt, setPrompt] = useState("a wild organic Y2K Winamp media player");
  const [llmMsg, setLlmMsg] = useState("");
  const [drag, setDrag] = useState<string | null>(null);

  // PACKER — the real repackTemplate, live. (repack canon-sizes by kind + resolveOverlaps.)
  const packed = useMemo(() => repackTemplate(regions as Region[]) as SR[], [regions]);

  const randomize = () => { setRegions(layoutRandomP(P) as SR[]); setSel(null); };
  const archGen = (a: string) => { setRegions(layoutArch(a, P) as SR[]); setSel(null); };
  const llmGen = async () => {
    setLlmMsg("generating…");
    try {
      const r = await fetch("/api/derive", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
      const d = await r.json();
      if (d.regions?.length) { setRegions(d.regions as SR[]); setSel(null); setLlmMsg(`LLM: ${d.regions.length} regions`); }
      else setLlmMsg(d.hasKey ? "LLM returned no usable layout (fell back)" : "no OpenAI key on server");
    } catch (e) { setLlmMsg("error: " + (e instanceof Error ? e.message : String(e))); }
  };

  const patchSel = (patch: Partial<SR>) => setRegions((rs) => rs.map((r) => r.id === sel ? { ...r, ...patch } : r));
  const delSel = () => { setRegions((rs) => rs.filter((r) => r.id !== sel)); setSel(null); };
  const addComp = () => {
    const id = "c" + Math.random().toString(36).slice(2, 6);
    setRegions((rs) => [...rs, { id, kind: "button", content: "sprite", layer: "components", bind: id, rect: { x: 0.44, y: 0.44, w: 0.12, h: 0.08 }, shapeKind: "auto", diff: globalDiff } as SR]);
    setSel(id);
  };

  // drag a centroid on the RAW canvas (pointer coords → normalized, recentre the rect)
  const onMove = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    if (!drag) return;
    const svg = e.currentTarget; const b = svg.getBoundingClientRect();
    const nx = (e.clientX - b.left) / b.width, ny = (e.clientY - b.top) / b.height;
    setRegions((rs) => rs.map((r) => r.id === drag ? { ...r, rect: { ...r.rect, x: Math.max(0, Math.min(1 - r.rect.w, nx - r.rect.w / 2)), y: Math.max(0, Math.min(1 - r.rect.h, ny - r.rect.h / 2)) } } : r));
  }, [drag]);

  const renderShape = (r: SR, editable: boolean) => {
    const W = GEN_W, H = GEN_H; const x = r.rect.x * W, y = r.rect.y * H, w = r.rect.w * W, h = r.rect.h * H;
    const col = KCOL[r.kind] ?? "#888"; const sk = autoShape(r); const poly = unitPoly(sk);
    const diff = r.diff ?? globalDiff; const blur = diff * Math.min(w, h) * 0.5;   // diffuseness → soft edge
    const fid = `f_${r.id}`; const selected = sel === r.id;
    const shape = poly
      ? <polygon points={poly.map(([px, py]) => `${x + px * w},${y + py * h}`).join(" ")} fill={col} fillOpacity={0.5} stroke={col} strokeWidth={selected ? 5 : 2} filter={blur > 0.6 ? `url(#${fid})` : undefined} />
      : <ellipse cx={x + w / 2} cy={y + h / 2} rx={w / 2} ry={h / 2} fill={col} fillOpacity={0.5} stroke={col} strokeWidth={selected ? 5 : 2} filter={blur > 0.6 ? `url(#${fid})` : undefined} />;
    return (
      <g key={r.id} onClick={() => editable && setSel(r.id)} style={{ cursor: editable ? "pointer" : "default" }}>
        {blur > 0.6 && <filter id={fid} x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation={blur} /></filter>}
        {shape}
        <circle cx={x + w / 2} cy={y + h / 2} r={editable ? 11 : 6} fill={selected ? "#fff" : col}
          stroke="#000" strokeWidth={2} style={{ cursor: editable ? "grab" : "default" }}
          onPointerDown={editable ? (e) => { e.stopPropagation(); setSel(r.id); setDrag(r.id); (e.target as Element).setPointerCapture(e.pointerId); } : undefined} />
        <text x={x + w / 2} y={y - 6} fill={col} fontSize={26} textAnchor="middle" style={{ pointerEvents: "none", fontWeight: 700 }}>{(r.bind || r.id).slice(0, 8)}</text>
      </g>
    );
  };

  const Canvas = ({ regs, editable, title }: { regs: SR[]; editable: boolean; title: string }) => (
    <div style={{ flex: "1 1 320px", minWidth: 260 }}>
      <div style={{ color: "#cfcfe0", fontWeight: 600, marginBottom: 6 }}>{title} <span style={{ color: "#8a8a96", fontWeight: 400, fontSize: 12 }}>({regs.length} regions)</span></div>
      <svg viewBox={`0 0 ${GEN_W} ${GEN_H}`} width="100%" style={{ maxWidth: 460, aspectRatio: `${GEN_W}/${GEN_H}`, background: "#15151c", border: "1px solid #2a2a34", borderRadius: 10, touchAction: "none" }}
        onPointerMove={editable ? onMove : undefined} onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)}>
        {regs.map((r) => renderShape(r, editable))}
      </svg>
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
    <div style={{ background: "#0c0c10", color: "#e8e8ee", minHeight: "100vh", font: "14px system-ui,sans-serif", padding: "clamp(10px,2.5vw,24px)" }}>
      <h1 style={{ fontSize: 20, margin: "0 0 2px" }}>Template Studio</h1>
      <p style={{ color: "#9a9aa6", margin: "0 0 12px", maxWidth: "80ch" }}>Seed or generate a DATA template, then see it packed live — on the real shipping heuristics (layoutRandomP · repackTemplate · deriveLayout). Drag centroids; pick shape + diffuseness per component.</p>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {/* left: generators + heuristic params */}
        <div style={{ flex: "0 0 220px", display: "flex", flexDirection: "column", gap: 10 }}>
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
          <div style={{ borderTop: "1px solid #26262f", paddingTop: 8 }}>
            <label style={{ fontSize: 12, color: "#b8b8c4" }}>global diffuseness <b style={{ color: "#7fe0a0" }}>{globalDiff.toFixed(2)}</b>
              <input type="range" min={0} max={1} step={0.05} value={globalDiff} onChange={(e) => setGlobalDiff(+e.target.value)} style={{ width: "100%" }} /></label>
          </div>
          <div style={{ borderTop: "1px solid #26262f", paddingTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ fontSize: 12, color: "#8a8a96" }}>LLM generate (heuristic-guided):</div>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2} style={{ background: "#15151c", color: "#e8e8ee", border: "1px solid #2a2a34", borderRadius: 6, padding: 6, fontSize: 12, resize: "vertical" }} />
            <button style={btn} onClick={llmGen}>🧠 Generate (deriveLayout)</button>
            <div style={{ fontSize: 11, color: "#8a8a96" }}>{llmMsg}</div>
          </div>
        </div>

        {/* center + right: raw + packed canvases */}
        <Canvas regs={regions} editable title="RAW template (seed / edit)" />
        <Canvas regs={packed} editable={false} title="PACKED (repackTemplate, live)" />

        {/* inspector */}
        <div style={{ flex: "0 0 200px", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ color: "#cfcfe0", fontWeight: 600 }}>Inspector</div>
          {selR ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12, color: "#b8b8c4" }}>
              <div>id <b style={{ color: "#e8e8ee" }}>{selR.id}</b></div>
              <label>kind<select value={selR.kind} onChange={(e) => patchSel({ kind: e.target.value as Kind })} style={{ width: "100%", background: "#15151c", color: "#fff", border: "1px solid #2a2a34", borderRadius: 6, padding: 4 }}>{KINDS.map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
              <label>bind<input value={selR.bind || ""} onChange={(e) => patchSel({ bind: e.target.value })} style={{ width: "100%", background: "#15151c", color: "#fff", border: "1px solid #2a2a34", borderRadius: 6, padding: 4 }} /></label>
              <label>shape<select value={selR.shapeKind || "auto"} onChange={(e) => patchSel({ shapeKind: e.target.value })} style={{ width: "100%", background: "#15151c", color: "#fff", border: "1px solid #2a2a34", borderRadius: 6, padding: 4 }}>{SHAPEKINDS.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
              <label>diffuseness <b style={{ color: "#7fe0a0" }}>{(selR.diff ?? globalDiff).toFixed(2)}</b>
                <input type="range" min={0} max={1} step={0.05} value={selR.diff ?? globalDiff} onChange={(e) => patchSel({ diff: +e.target.value })} style={{ width: "100%" }} /></label>
              <label>size <input type="range" min={0.03} max={0.4} step={0.01} value={selR.rect.w} onChange={(e) => { const w = +e.target.value; patchSel({ rect: { ...selR.rect, w, h: w * 0.7 } }); }} style={{ width: "100%" }} /></label>
              <button style={{ ...btn, background: "#3a1c1c", borderColor: "#5a2a2a" }} onClick={delSel}>🗑 Delete</button>
            </div>
          ) : <div style={{ color: "#8a8a96", fontSize: 12 }}>Click a component (or its centroid) to edit its kind, bind, shape, diffuseness, size.</div>}
          <div style={{ marginTop: "auto", fontSize: 11, color: "#66666f", borderTop: "1px solid #26262f", paddingTop: 8 }}>
            Packed uses the SHIPPING packer (repackTemplate → resolveOverlaps). Edit raw → packed updates live.
          </div>
        </div>
      </div>
    </div>
  );
}
