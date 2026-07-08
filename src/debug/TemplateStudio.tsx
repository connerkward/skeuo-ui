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
import type { Region, Kind } from "../template/schema";

type SR = Region & { shapeKind?: string; diff?: number };
const KINDS: Kind[] = ["button", "knob", "toggle", "slider-h", "slider-v", "slider-arc", "display"];
const DEF_ARC = { start: 200, end: 340 };   // default partial-circle sweep for a slider-arc
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
  const [sel, setSel] = useState<string | null>(null);
  const [showOverlays, setShowOverlays] = useState(false);  // studio annotations on the blueprint — OFF by default (see the exact image sent to FAL); toggle on to label cells
  const [globalDiff, setGlobalDiff] = useState(0.35);
  const [prompt, setPrompt] = useState("a wild organic Y2K Winamp media player");
  const [llmMsg, setLlmMsg] = useState("");
  const [drag, setDrag] = useState<string | null>(null);
  // human-authored flag: once the human edits (drag/add/patch/nudge), the packer becomes a
  // PASS-THROUGH — packing must not rearrange a human-authored template. Generators reset it.
  const [authored, setAuthored] = useState(false);

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
    try { return bakeButtons(packed.map((r) => ({ ...r, diff: r.diff ?? globalDiff })) as Region[]); }
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

  const randomize = () => { mutate(() => layoutRandomP(P) as SR[]); setSel(null); setAuthored(false); };
  const archGen = (a: string) => { mutate(() => layoutArch(a, P) as SR[]); setSel(null); setAuthored(false); };
  const llmGen = async () => {
    setLlmMsg("generating…");
    try {
      const r = await fetch("/api/derive", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
      const d = await r.json();
      if (d.regions?.length) { mutate(() => d.regions as SR[]); setSel(null); setAuthored(false); setLlmMsg(`LLM: ${d.regions.length} regions`); }
      else setLlmMsg(d.hasKey ? "LLM returned no usable layout (fell back)" : "no OpenAI key on server");
    } catch (e) { setLlmMsg("error: " + (e instanceof Error ? e.message : String(e))); }
  };

  const patchSel = (patch: Partial<SR>) => { setAuthored(true); mutate((rs) => enforceZeroDiff(rs.map((r) => r.id === sel ? { ...r, ...patch } : r))); };
  const delSel = useCallback(() => { setSel((s) => { if (s) { setAuthored(true); mutate((rs) => rs.filter((r) => r.id !== s)); } return null; }); }, [mutate]);
  const addComp = () => {
    const id = "c" + Math.random().toString(36).slice(2, 6);
    setAuthored(true);
    mutate((rs) => enforceZeroDiff([...rs, { id, kind: "button", content: "sprite", layer: "components", bind: id, rect: { x: 0.44, y: 0.44, w: 0.12, h: 0.08 }, shapeKind: "auto", diff: globalDiff } as SR]));
    setSel(id);
  };

  // normal expected keyboard shortcuts (guarded: never intercept while typing in a field)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
      if (e.key === "Escape") { setSel(null); return; }
      if (!sel) return;
      if (e.key === "Backspace" || e.key === "Delete") { e.preventDefault(); delSel(); return; }
      const step = e.shiftKey ? 0.02 : 0.005;
      const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
      const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
      if (dx || dy) {
        e.preventDefault(); setAuthored(true);
        mutate((rs) => enforceZeroDiff(rs.map((r) => r.id === sel ? { ...r, rect: { ...r.rect, x: Math.max(0, Math.min(1 - r.rect.w, r.rect.x + dx)), y: Math.max(0, Math.min(1 - r.rect.h, r.rect.y + dy)) } } : r)));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sel, mutate, undo, redo, delSel, enforceZeroDiff]);

  // drag a centroid on the RAW canvas (pointer coords → normalized, recentre the rect)
  const onMove = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    if (!drag) return;
    const svg = e.currentTarget; const b = svg.getBoundingClientRect();
    const nx = (e.clientX - b.left) / b.width, ny = (e.clientY - b.top) / b.height;
    setRegions((rs) => rs.map((r) => r.id === drag ? { ...r, rect: { ...r.rect, x: Math.max(0, Math.min(1 - r.rect.w, nx - r.rect.w / 2)), y: Math.max(0, Math.min(1 - r.rect.h, ny - r.rect.h / 2)) } } : r));
  }, [drag]);

  const renderShape = (r: SR, editable: boolean) => {
    const W = GEN_W, H = GEN_H;
    const x = r.rect.x * W, y = r.rect.y * H, w = r.rect.w * W, h = r.rect.h * H;
    const cx = x + w / 2, cy = y + h / 2;
    const col = colorOf(r);
    const diff = r.diff ?? globalDiff;
    const s = Math.min(w, h);
    // SAME anchor as the combined blueprint (blueprint.ts anchorMark): a soft SIZE DISC + a
    // crisp CENTROID CROSSHAIR, coloured by this component's identity. No fake silhouette
    // (shape is the model's choice — that's why there are no wedge/kidney outlines), and the
    // diffuseness maths is IDENTICAL to the blueprint, so diff reads the same in both.
    const blur = s * 0.10 + diff * s * 0.55;
    const op = 0.95 - diff * 0.45;
    const rx = (w / 2) * 0.74, ry = (h / 2) * 0.74;
    const arm = s * 0.27, lw = Math.max(2.5, s * 0.03), dot = Math.max(3, s * 0.05);
    // slider TRACK: a straight line (slider-h / slider-v) or a partial-circle arc (slider-arc)
    // — the only two slider geometries supported. Same colour + arc maths as the blueprint.
    const tw = Math.max(3, s * 0.07);
    const track = r.kind === "slider-h"
      ? <line x1={x + w * 0.12} y1={cy} x2={x + w * 0.88} y2={cy} stroke={col} strokeWidth={tw} strokeLinecap="round" opacity={0.9} />
      : r.kind === "slider-v"
        ? <line x1={cx} y1={y + h * 0.12} x2={cx} y2={y + h * 0.88} stroke={col} strokeWidth={tw} strokeLinecap="round" opacity={0.9} />
        : r.kind === "slider-arc"
          ? <path d={arcD(cx, cy, (s / 2) * 0.86, (r.arc ?? DEF_ARC).start, (r.arc ?? DEF_ARC).end)} fill="none" stroke={col} strokeWidth={tw} strokeLinecap="round" opacity={0.9} />
          : null;
    const fid = `f_${r.id}`; const selected = sel === r.id;
    return (
      <g key={r.id} onClick={() => editable && setSel(r.id)} style={{ cursor: editable ? "pointer" : "default" }}>
        <filter id={fid} x="-90%" y="-90%" width="280%" height="280%"><feGaussianBlur stdDeviation={blur} /></filter>
        <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill={col} fillOpacity={0.36} filter={`url(#${fid})`} />
        <g stroke={col} strokeWidth={lw} strokeLinecap="round" opacity={op}>
          <line x1={cx - arm} y1={cy} x2={cx + arm} y2={cy} />
          <line x1={cx} y1={cy - arm} x2={cx} y2={cy + arm} />
        </g>
        {track}
        {selected && <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="none" stroke="#fff" strokeWidth={2.5} strokeDasharray="7 5" opacity={0.7} />}
        <circle cx={cx} cy={cy} r={editable ? Math.max(dot, 12) : dot} fill={selected ? "#fff" : col} stroke="#000" strokeWidth={2} opacity={editable ? 1 : op}
          style={{ cursor: editable ? "grab" : "default" }}
          onPointerDown={editable ? (e) => { e.stopPropagation(); snapshot(); setAuthored(true); setSel(r.id); setDrag(r.id); (e.target as Element).setPointerCapture(e.pointerId); } : undefined} />
        <text x={cx} y={y - 6} fill={col} fontSize={26} textAnchor="middle" style={{ pointerEvents: "none", fontWeight: 700 }}>{(r.bind || r.id).slice(0, 10)}</text>
      </g>
    );
  };

  // height-fit canvas: the stage derives its width from the viewport height via aspect-ratio,
  // so all three panels are fully visible at once (no page scroll).
  const Canvas = ({ regs, editable, title }: { regs: SR[]; editable: boolean; title: string }) => (
    <div className="tsCanvas dev">
      <div className="tsCap">{title} <span>({regs.length} regions)</span></div>
      <svg className="tsStage" viewBox={`0 0 ${GEN_W} ${GEN_H}`}
        onPointerMove={editable ? onMove : undefined}
        onPointerUp={() => { setDrag(null); if (editable) setRegions(enforceZeroDiff); }}
        onPointerLeave={() => setDrag(null)}>
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
    <div className="tsRoot">
      <style>{`
        .tsRoot{position:fixed;inset:0;display:grid;grid-template-columns:218px minmax(0,1fr) 236px;grid-template-rows:auto minmax(0,1fr) auto;background:#0c0c10;color:#e8e8ee;font:14px system-ui,sans-serif}
        .tsHead{grid-column:1/-1;display:flex;align-items:baseline;gap:12px;padding:7px 14px;border-bottom:1px solid #1e1e26;flex-wrap:wrap}
        .tsHead h1{font-size:16px;margin:0}
        .tsHead span{color:#8a8a96;font-size:11.5px}
        .tsLeft{overflow-y:auto;min-height:0;padding:10px;border-right:1px solid #1e1e26;display:flex;flex-direction:column;gap:10px}
        .tsMain{display:flex;gap:12px;padding:8px 12px;min-width:0;min-height:0;justify-content:center;align-items:flex-start;overflow:hidden}
        .tsRight{overflow-y:auto;min-height:0;padding:10px;border-left:1px solid #1e1e26;display:flex;flex-direction:column;gap:8px}
        .tsFoot{grid-column:1/-1;display:flex;gap:10px;align-items:center;padding:6px 14px;border-top:1px solid #1e1e26;flex-wrap:wrap}
        .tsCanvas{display:flex;flex-direction:column;min-width:0;align-items:stretch}
        /* width derives from viewport HEIGHT (fit-to-height, exact aspect — no letterboxing),
           clamped by the column's share of width. 150px ≈ header+footer+caption chrome. */
        .tsCanvas.dev{width:min(24%,calc((100vh - 150px) * ${(GEN_W / GEN_H).toFixed(4)}))}
        .tsCanvas.bp{width:min(24%,calc((100vh - 150px) * ${(GEN_W / 1820).toFixed(4)}))}
        /* combined column WITH the FAL text-prompt box under it — blueprint takes ~62% of the
           height so the scrollable prompt gets the rest; column fills the row height. */
        .tsCanvas.bpc{width:min(23%,calc((100vh - 150px) * ${(GEN_W / 1820).toFixed(4)} * 0.62));height:100%}
        .tsCap{color:#cfcfe0;font-weight:600;font-size:12.5px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .tsCap span{color:#8a8a96;font-weight:400;font-size:11px}
        .tsStage{width:100%;aspect-ratio:${GEN_W}/${GEN_H};background:#15151c;border:1px solid #2a2a34;border-radius:10px;touch-action:none}
        .tsBP{width:100%;aspect-ratio:${GEN_W}/1820;position:relative;border-radius:10px;overflow:hidden;border:1px solid #2a2a34}
        .tsBP svg{display:block;width:100%;height:100%}
        @media (max-width:1020px){
          .tsRoot{position:static;height:auto;grid-template-columns:1fr;grid-template-rows:auto}
          .tsMain{flex-wrap:wrap;overflow:visible}
          .tsCanvas.dev,.tsCanvas.bp{width:min(100%,420px)}
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
        <div style={{ borderTop: "1px solid #26262f", paddingTop: 8 }}>
          <label style={{ fontSize: 12, color: "#b8b8c4" }}>global diffuseness <b style={{ color: "#7fe0a0" }}>{globalDiff.toFixed(2)}</b>
            <input type="range" min={0} max={1} step={0.05} value={globalDiff} onChange={(e) => setGlobalDiff(+e.target.value)} style={{ width: "100%" }} /></label>
        </div>
        <div style={{ marginTop: "auto", fontSize: 11, color: "#66666f", borderTop: "1px solid #26262f", paddingTop: 8 }}>
          Repack is OFF — packed mirrors raw 1:1. Edit raw → packed + blueprint update live.
        </div>
      </aside>

      {/* CENTER — everything at once: raw, packed, combined blueprint (height-fit) */}
      <main className="tsMain">
        <Canvas regs={regions} editable title="RAW template (seed / edit)" />
        <Canvas regs={packed} editable={false} title={authored ? "PACKED — repack off (mirrors edited raw)" : "PACKED — repack off (mirrors raw)"} />
        {combined && (
          <div className="tsCanvas bpc">
            <div className="tsCap" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>COMBINED blueprint <span>(device + {combined.layout.cells.length} sprite cells)</span></span>
              <button onClick={() => setShowOverlays((v) => !v)} title="toggle studio overlays — the bind labels + divider are annotations, NOT part of the image sent to FAL"
                style={{ marginLeft: "auto", flex: "0 0 auto", background: showOverlays ? "#243524" : "#15151c", color: showOverlays ? "#7fe0a0" : "#8a8a96", border: "1px solid #2a2a34", borderRadius: 5, padding: "1px 7px", cursor: "pointer", fontSize: 10, fontWeight: 600, whiteSpace: "nowrap" }}>
                {showOverlays ? "◉" : "◯"} overlays
              </button>
            </div>
            <div className="tsBP" style={{ flex: "0 0 auto" }}>
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
            </div>
            {/* scrollable view of the TEXT prompt that ALSO goes to FAL with the blueprint image */}
            <div style={{ flex: "1 1 0", minHeight: 70, marginTop: 6, overflowY: "auto", background: "#0b0b11", border: "1px solid #26262f", borderRadius: 8, padding: "0 8px 8px" }}>
              <div style={{ position: "sticky", top: 0, background: "#0b0b11", fontSize: 10, color: "#8a8a96", fontWeight: 600, padding: "6px 0 4px", marginBottom: 4, borderBottom: "1px solid #1e1e26" }}>
                text prompt → FAL <span style={{ color: "#66666f", fontWeight: 400 }}>(sent with the blueprint image · {promptPreview.length.toLocaleString()} chars)</span>
              </div>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 10, lineHeight: 1.45, color: "#c2c2ce", fontFamily: "ui-monospace,SFMono-Regular,monospace" }}>{promptPreview}</pre>
            </div>
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
            <div key={r.id} onClick={() => setSel(r.id)}
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
            <label>diffuseness <b style={{ color: "#7fe0a0" }}>{(selR.diff ?? globalDiff).toFixed(2)}</b>
              <input type="range" min={0} max={1} step={0.05} value={selR.diff ?? globalDiff} onChange={(e) => patchSel({ diff: +e.target.value })} style={{ width: "100%" }} /></label>
            <label>size <input type="range" min={0.03} max={0.4} step={0.01} value={selR.rect.w} onChange={(e) => { const w = +e.target.value; patchSel({ rect: { ...selR.rect, w, h: w * 0.7 } }); }} style={{ width: "100%" }} /></label>
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
        ) : <div style={{ color: "#8a8a96", fontSize: 12 }}>Click a component (in the list or its centroid) to edit kind, bind, diffuseness, or size.</div>}
      </aside>

      {/* BOTTOM — LLM command bar + shortcuts */}
      <footer className="tsFoot">
        <span style={{ fontSize: 13 }}>🧠</span>
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="LLM theme — e.g. a wild organic Y2K Winamp media player"
          onKeyDown={(e) => { if (e.key === "Enter") void llmGen(); }}
          style={{ flex: "1 1 260px", maxWidth: 560, background: "#15151c", color: "#e8e8ee", border: "1px solid #2a2a34", borderRadius: 6, padding: "5px 9px", fontSize: 12 }} />
        <button style={btn} onClick={llmGen}>Generate (deriveLayout)</button>
        <span style={{ fontSize: 11, color: "#8a8a96" }}>{llmMsg}</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#66666f" }}>⌫ delete · arrows nudge (⇧ coarse) · esc deselect · ⌘Z undo · ⇧⌘Z redo</span>
      </footer>
    </div>
  );
}
