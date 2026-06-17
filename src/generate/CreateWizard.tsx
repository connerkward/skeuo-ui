import { useEffect, useRef, useState } from "react";
import type { GenerateRequest, GenerateResponse } from "./api";
import { MODELS, DEFAULT_MODEL, MATERIAL, type DonorStyle, type ModelId } from "./pipeline";
import { regionsForVariant, type LayoutVariant } from "./layouts";
import type { Region, Rect, Kind } from "../template/schema";
import type { RuntimeSkin } from "./CreatePanel";

// ─────────────────────────────────────────────────────────────────────────────
// CreateWizard — ONE guided flow that replaces the old create drawer + standalone
// workshop. Four steps, always a live layout preview:
//   1 · Idea      — type the sentence (+ optional reference image)
//   2 · Layout    — pick a preset, then drag the controls where you want them
//   3 · Body      — material + whether to grow an AI envelope (optional, off by default)
//   4 · Generate  — pick one/many image models, see the price, go
// The authored layout is sent to /api/generate (regions[]) so dragging actually
// changes the painted skin, not just the preview.
// ─────────────────────────────────────────────────────────────────────────────

const STEPS = ["Idea", "Layout", "Body", "Generate"] as const;
type Step = 0 | 1 | 2 | 3;

const VARIANTS: { id: LayoutVariant; label: string; blurb: string }[] = [
  { id: "radial", label: "Radial dial", blurb: "round dial, buttons orbiting, ring seek" },
  { id: "capsule", label: "Capsule pod", blurb: "WMP-style pod, pill marquee, EQ" },
  { id: "minimal", label: "Minimal puck", blurb: "now-playing puck, big play, one knob" },
];

const MATERIALS: { id: DonorStyle; label: string }[] = Object.keys(MATERIAL).map((k) => ({
  id: k as DonorStyle,
  label: { biomech: "Biomech", winamp: "Chrome", frog: "Rubber frog", wmp: "Aqua (WMP)", halo: "Military (Halo)" }[k] ?? k,
}));

// control kinds the palette can drop, with a default rect + bind
const PALETTE: { kind: Kind; label: string; bind?: string; shape?: "ellipse" }[] = [
  { kind: "button", label: "Button", bind: "play", shape: "ellipse" },
  { kind: "knob", label: "Knob", bind: "volume" },
  { kind: "toggle", label: "Toggle", bind: "shuffle" },
  { kind: "slider-h", label: "Slider", bind: "seek" },
  { kind: "display", label: "Screen", },
];

const KIND_COLOR: Record<string, string> = {
  button: "#5aff82", knob: "#5ab4ff", toggle: "#ff8a3d", "slider-h": "#ff5a6e",
  "slider-v": "#ffd246", "slider-arc": "#ff5a6e", display: "#b496ff",
};
const colorFor = (k: string) => KIND_COLOR[k] ?? "#c8c8c8";

const fmt$ = (n: number) => `$${n.toFixed(2)}`;
const modelLabel = (id: ModelId) => MODELS.find((m) => m.id === id)?.label ?? id;
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export function CreateWizard({ onCreated }: { onCreated: (s: RuntimeSkin) => void }) {
  const [step, setStep] = useState<Step>(0);

  // step 1 — idea
  const [prompt, setPrompt] = useState("a fanged anglerfish jaw");
  const [refImage, setRefImage] = useState<string | undefined>();
  const fileRef = useRef<HTMLInputElement>(null);

  // step 2 — layout
  const [variant, setVariant] = useState<LayoutVariant>("radial");
  const [regions, setRegions] = useState<Region[]>(() => regionsForVariant("radial"));

  // step 3 — body
  const [material, setMaterial] = useState<DonorStyle>("biomech");
  const [envelope, setEnvelope] = useState(false); // AI body is OPT-IN (cheaper/freeform by default)

  // step 4 — generate
  const [models, setModels] = useState<ModelId[]>([DEFAULT_MODEL]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [stage, setStage] = useState("");

  const usePreset = (v: LayoutVariant) => { setVariant(v); setRegions(regionsForVariant(v)); };

  const pickRef = (f: File | undefined) => {
    if (!f) { setRefImage(undefined); return; }
    const r = new FileReader();
    r.onload = () => setRefImage(typeof r.result === "string" ? r.result : undefined);
    r.readAsDataURL(f);
  };

  const toggleModel = (id: ModelId) =>
    setModels((cur) => (cur.includes(id) ? cur.filter((m) => m !== id) : [...cur, id]));

  // envelope OFF ≈ one image pass instead of two → roughly half the per-skin cost.
  const factor = envelope ? 1 : 0.55;
  const total = MODELS.filter((m) => models.includes(m.id)).reduce((s, m) => s + m.costPerSkin * factor, 0);
  const anyApprox = MODELS.some((m) => models.includes(m.id) && m.approx);

  const canNext = step === 0 ? prompt.trim().length > 0 : step === 3 ? models.length > 0 : true;

  const generate = async () => {
    if (!models.length) { setErr("pick at least one model"); return; }
    setBusy(true); setErr(null);
    try {
      for (let i = 0; i < models.length; i++) {
        const model = models[i];
        setStage(`model ${i + 1}/${models.length} · ${modelLabel(model)} — ${envelope ? "envelope → paint" : "paint"} (~30–90s)…`);
        const req: GenerateRequest = {
          prompt: prompt.trim(), style: material, variant, refImage, model, envelope, regions,
        };
        const r = await fetch("/api/generate", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
        });
        const data: GenerateResponse = await r.json();
        if (data.status === "error") { setErr(`${modelLabel(model)}: ${data.error}`); continue; }
        if (data.status !== "done") { setErr("unexpected pending response"); continue; }
        onCreated({
          id: data.id,
          name: `${prompt.trim().slice(0, 18)} · ${modelLabel(data.model)}`,
          blurb: `generated · ${modelLabel(data.model)}`,
          style: data.style,
          frameUrl: data.frameUrl,
          template: data.template,
        });
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false); setStage("");
    }
  };

  return (
    <div className="wiz">
      <ol className="wiz-steps">
        {STEPS.map((s, i) => (
          <li key={s} className={`wiz-step ${i === step ? "on" : ""} ${i < step ? "done" : ""}`}
            onClick={() => i < step && setStep(i as Step)}>
            <span className="wiz-num">{i + 1}</span><span className="wiz-lbl">{s}</span>
          </li>
        ))}
      </ol>

      <div className="wiz-body">
        {/* live layout preview sits beside every step so the artifact is always visible */}
        <div className="wiz-preview">
          <LayoutStage regions={regions} onChange={setRegions} editable={step === 1} />
          <div className="wiz-preview-cap">
            {step === 1 ? "drag a control to move · corner handles resize · click empty space to deselect"
              : `${regions.length} controls · ${variant} layout`}
          </div>
        </div>

        <div className="wiz-panel">
          {step === 0 && (
            <>
              <h3>What is it?</h3>
              <label className="wiz-field">
                <span>Describe the silhouette</span>
                <textarea rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)}
                  placeholder="a fanged anglerfish jaw" />
              </label>
              <label className="wiz-field">
                <span>Reference image (optional — steers palette &amp; material)</span>
                <input ref={fileRef} type="file" accept="image/*" onChange={(e) => pickRef(e.target.files?.[0])} />
                {refImage && <img className="wiz-ref" src={refImage} alt="reference" />}
              </label>
            </>
          )}

          {step === 1 && (
            <>
              <h3>Lay out the controls</h3>
              <p className="wiz-hint">Start from a preset, then drag the controls on the preview. This layout is what the art is grown around.</p>
              <div className="wiz-presets">
                {VARIANTS.map((v) => (
                  <button key={v.id} className={`wiz-preset ${variant === v.id ? "on" : ""}`} onClick={() => usePreset(v.id)}>
                    <strong>{v.label}</strong><span>{v.blurb}</span>
                  </button>
                ))}
              </div>
              <div className="wiz-palette">
                <span className="wiz-palette-lbl">Add:</span>
                {PALETTE.map((p) => (
                  <button key={p.kind} className="wiz-add" style={{ borderColor: colorFor(p.kind) }}
                    onClick={() => setRegions((rs) => [...rs, newRegion(p)])}>+ {p.label}</button>
                ))}
                <button className="wiz-reset" onClick={() => usePreset(variant)}>↺ Reset preset</button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h3>Body &amp; material</h3>
              <div className="wiz-field">
                <span>Material the body is painted in</span>
                <div className="wiz-mats">
                  {MATERIALS.map((m) => (
                    <button key={m.id} className={`wiz-mat ${material === m.id ? "on" : ""}`} onClick={() => setMaterial(m.id)}>
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
              <label className={`wiz-env ${envelope ? "on" : ""}`}>
                <input type="checkbox" checked={envelope} onChange={(e) => setEnvelope(e.target.checked)} />
                <span className="wiz-env-txt">
                  <strong>Grow an AI body envelope around the controls</strong>
                  <small>{envelope
                    ? "Two image passes: first sculpts a silhouette around your wells, then paints it. More control over shape, ~2× the cost."
                    : "Off (default): one pass — the model paints a freeform body straight from your control layout. Cheaper, wilder shapes."}</small>
                </span>
              </label>
            </>
          )}

          {step === 3 && (
            <>
              <h3>Generate</h3>
              <p className="wiz-hint">Pick one or several image models — each gives an interestingly different result.</p>
              <div className="wiz-models">
                {MODELS.map((m) => {
                  const on = models.includes(m.id);
                  return (
                    <label key={m.id} className={`wiz-model ${on ? "on" : ""}`}>
                      <input type="checkbox" checked={on} onChange={() => toggleModel(m.id)} />
                      <span className="wiz-model-name">{m.label}</span>
                      <span className="wiz-model-cost">~{fmt$(m.costPerSkin * factor)}{m.approx ? "*" : ""}</span>
                    </label>
                  );
                })}
              </div>
              <div className="wiz-summary">
                <div><b>{prompt.trim().slice(0, 32) || "—"}</b></div>
                <div>{variant} · {regions.length} controls · {MATERIALS.find((m) => m.id === material)?.label}
                  {envelope ? " · AI body" : " · freeform body"}</div>
                <div className="wiz-total"><strong>{models.length} model{models.length === 1 ? "" : "s"}</strong> · ~{fmt$(total)}{anyApprox ? "*" : ""} total</div>
              </div>
              {stage && <div className="wiz-genstage">{stage}</div>}
              {err && <div className="wiz-err">{err}</div>}
            </>
          )}
        </div>
      </div>

      <div className="wiz-nav">
        <button className="wiz-back" disabled={step === 0 || busy} onClick={() => setStep((s) => (s - 1) as Step)}>← Back</button>
        {step < 3 ? (
          <button className="wiz-next" disabled={!canNext} onClick={() => setStep((s) => (s + 1) as Step)}>
            Next: {STEPS[step + 1]} →
          </button>
        ) : (
          <button className="wiz-go" disabled={busy || !models.length} onClick={generate}>
            {busy ? "Generating…" : `Generate ${models.length} skin${models.length === 1 ? "" : "s"} (~${fmt$(total)}${anyApprox ? "*" : ""})`}
          </button>
        )}
      </div>
    </div>
  );
}

// ── new region from a palette entry (centered, sensible default size) ──────────
function newRegion(p: { kind: Kind; bind?: string; shape?: "ellipse" }): Region {
  const id = `${p.kind}-${Math.random().toString(36).slice(2, 6)}`;
  const size: Record<string, Rect> = {
    button: { x: 0.44, y: 0.45, w: 0.1, h: 0.067 },
    knob: { x: 0.42, y: 0.44, w: 0.12, h: 0.08 },
    toggle: { x: 0.45, y: 0.44, w: 0.06, h: 0.09 },
    "slider-h": { x: 0.28, y: 0.5, w: 0.44, h: 0.02 },
    display: { x: 0.3, y: 0.4, w: 0.4, h: 0.16 },
  };
  return {
    id, kind: p.kind, content: p.kind === "display" ? "dynamic" : "sprite",
    layer: p.kind === "display" ? "screen" : "components",
    rect: size[p.kind] ?? { x: 0.44, y: 0.45, w: 0.1, h: 0.08 },
    bind: p.bind, label: p.bind ?? p.kind, ...(p.shape ? { shape: p.shape } : {}),
    ...(p.kind === "display" ? { dynamicType: "visualizer" as const } : {}),
  };
}

// ── draggable layout stage (move + corner resize), 2:3, scales to width ────────
type Dir = "move" | "se" | "sw" | "ne" | "nw";
function LayoutStage({ regions, onChange, editable }: {
  regions: Region[]; onChange: (r: Region[]) => void; editable: boolean;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState<string | null>(null);
  const drag = useRef<{ id: string; dir: Dir; px: number; py: number; rect: Rect } | null>(null);

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = drag.current, st = stageRef.current; if (!d || !st) return;
      const box = st.getBoundingClientRect();
      const dx = (e.clientX - d.px) / box.width, dy = (e.clientY - d.py) / box.height;
      let { x, y, w, h } = d.rect; const min = 0.02;
      if (d.dir === "move") { x = clamp(d.rect.x + dx, 0, 1 - w); y = clamp(d.rect.y + dy, 0, 1 - h); }
      else {
        if (d.dir.includes("e")) w = clamp(d.rect.w + dx, min, 1 - d.rect.x);
        if (d.dir.includes("s")) h = clamp(d.rect.h + dy, min, 1 - d.rect.y);
        if (d.dir.includes("w")) { const nx = clamp(d.rect.x + dx, 0, d.rect.x + d.rect.w - min); w = d.rect.w + (d.rect.x - nx); x = nx; }
        if (d.dir.includes("n")) { const ny = clamp(d.rect.y + dy, 0, d.rect.y + d.rect.h - min); h = d.rect.h + (d.rect.y - ny); y = ny; }
      }
      onChange(regions.map((r) => (r.id === d.id ? { ...r, rect: { x, y, w, h } } : r)));
    };
    const up = () => (drag.current = null);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, [regions, onChange]);

  const start = (e: React.PointerEvent, id: string, dir: Dir) => {
    if (!editable) return;
    e.stopPropagation(); setSel(id);
    const r = regions.find((x) => x.id === id); if (!r) return;
    drag.current = { id, dir, px: e.clientX, py: e.clientY, rect: { ...r.rect } };
  };
  const del = (id: string) => { onChange(regions.filter((r) => r.id !== id)); setSel(null); };

  return (
    <div ref={stageRef} className={`wiz-stage ${editable ? "edit" : ""}`} onPointerDown={() => editable && setSel(null)}>
      {regions.map((r) => {
        const c = colorFor(r.kind), ell = r.shape === "ellipse" || r.kind === "knob";
        // arc/path seeks fill the whole dial bbox — draw them as a faint dashed ring
        // so they read as "thumb rides this area", not a solid control slab.
        const arc = r.kind === "slider-arc" || r.kind === "slider-path";
        const on = r.id === sel;
        return (
          <div key={r.id}
            className={`wiz-region ${on ? "sel" : ""}`}
            style={{
              left: `${r.rect.x * 100}%`, top: `${r.rect.y * 100}%`,
              width: `${r.rect.w * 100}%`, height: `${r.rect.h * 100}%`,
              borderColor: c, background: arc ? "transparent" : `${c}22`,
              borderStyle: arc ? "dashed" : "solid", opacity: arc ? 0.55 : 1,
              borderRadius: ell || arc ? "50%" : "4px",
              alignItems: arc ? "flex-start" : "center",
              cursor: editable ? "move" : "default",
            }}
            onPointerDown={(e) => start(e, r.id, "move")}>
            <span className="wiz-region-tag" style={{ color: c }}>{r.bind || r.label || r.kind}</span>
            {on && editable && (["nw", "ne", "sw", "se"] as Dir[]).map((d) => (
              <span key={d} className={`wiz-h h-${d}`} style={{ borderColor: c }} onPointerDown={(e) => start(e, r.id, d)} />
            ))}
            {on && editable && <button className="wiz-region-del" onClick={(e) => { e.stopPropagation(); del(r.id); }}>×</button>}
          </div>
        );
      })}
    </div>
  );
}
