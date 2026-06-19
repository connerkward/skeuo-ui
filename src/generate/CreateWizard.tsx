import { useEffect, useRef, useState } from "react";
import type { GenerateRequest } from "./api";
import { postGenerate } from "./postGenerate";
import { finishCutout } from "./cutoutClient";
import { apiUrl } from "../platform";
import { MODELS, DEFAULT_MODEL, type ModelId } from "./pipeline";
import { regionsForVariant, type LayoutVariant } from "./layouts";
import type { Region, Rect, Kind, DynamicType } from "../template/schema";
import type { RuntimeSkin } from "./CreatePanel";

// ─────────────────────────────────────────────────────────────────────────────
// CreateWizard — ONE guided flow that replaces the old create drawer + standalone
// workshop. Four steps, always a live layout preview:
//   1 · Idea      — type the sentence (+ optional reference image)
//   2 · Layout    — pick a preset, then drag the controls where you want them
//   3 · Body      — a body auto-grows around the controls (uploaded body optional); material derives from the prompt
//   4 · Generate  — pick one/many image models, see the price, go
// The authored layout is sent to /api/generate (regions[]) so dragging actually
// changes the painted skin, not just the preview.
// ─────────────────────────────────────────────────────────────────────────────

const STEPS = ["Idea", "Layout", "Body", "Generate"] as const;
type Step = 0 | 1 | 2 | 3;

// curated skeuomorphic-player prompts for the 🎲 Random button (idea step)
const RANDOM_PROMPTS = [
  "a chunky red toy crab with huge claws",
  "a glossy frog puck on a lilypad",
  "a brushed-chrome boombox",
  "a translucent Y2K grape gadget",
  "an Aztec stone eagle console",
  "a deep-sea anglerfish jaw",
  "a melting neon ice-cream pod",
  "a worn leather hip-flask radio",
  "a porcelain cat with blinking eyes",
  "a rusted submarine control panel",
  "a bubblegum-pink jelly bug",
  "a carved obsidian beetle deck",
];

const VARIANTS: { id: LayoutVariant; label: string; blurb: string }[] = [
  { id: "simple", label: "Simple", blurb: "big visualizer, marquee + seek, prev/play/next" },
  { id: "radial", label: "Radial dial", blurb: "round dial, buttons orbiting, ring seek" },
  { id: "capsule", label: "Capsule pod", blurb: "WMP-style pod, pill marquee, EQ" },
  { id: "minimal", label: "Minimal puck", blurb: "now-playing puck, big play, one knob" },
];

// control kinds the palette can drop. Each adds a REAL player control with a
// meaningful name/bind — never a generic "display"/"slider-h". `screen` cycles
// its dynamicType (visualizer → marquee → playlist); the others pick an unused
// transport/bind so repeated clicks don't pile up duplicates of the same thing.
type PaletteKind = "screen" | "button" | "knob" | "toggle" | "slider";
const PALETTE: { palette: PaletteKind; label: string }[] = [
  { palette: "screen", label: "Screen" },
  { palette: "button", label: "Button" },
  { palette: "knob", label: "Knob" },
  { palette: "toggle", label: "Toggle" },
  { palette: "slider", label: "Slider" },
];
// kind used for color-coding the palette button
const PALETTE_KIND: Record<PaletteKind, Kind> = {
  screen: "display", button: "button", knob: "knob", toggle: "toggle", slider: "slider-h",
};

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
  // rotating counter (NOT Math.random — banned here) so each 🎲 press advances
  const [diceIdx, setDiceIdx] = useState(0);

  // step 2 — layout (defaults to the SIMPLE 6-control layout)
  const [variant, setVariant] = useState<LayoutVariant>("simple");
  const [regions, setRegions] = useState<Region[]>(() => regionsForVariant("simple"));

  // step 3 — body. Bodies auto-grow now (envelope: true on the server by
  // default), so there's no toggle — only the optional uploaded-body override.
  const [envImage, setEnvImage] = useState<string | undefined>(); // user-uploaded body envelope (data URL); when set it's used directly
  const envFileRef = useRef<HTMLInputElement>(null);
  // optional: run the extra ENVELOPE pass to sculpt a wilder, more elaborate body
  // (2× cost). Default OFF — one pass already expands the shape (the fixed cutout
  // alpha follows the painted silhouette, so it no longer shrink-wraps).
  const [sculpt, setSculpt] = useState(false);

  // step 4 — generate
  const [models, setModels] = useState<ModelId[]>([DEFAULT_MODEL]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // live paint-pass progress: which model is in flight + when its pass started
  const [progress, setProgress] = useState<GenProgress | null>(null);
  const [elapsed, setElapsed] = useState(0); // seconds since the current pass began

  const usePreset = (v: LayoutVariant) => { setVariant(v); setRegions(regionsForVariant(v)); };

  // 🎲 fill the prompt with the next curated idea (rotates; never repeats current)
  const rollPrompt = () => {
    let i = (diceIdx + 1) % RANDOM_PROMPTS.length;
    if (RANDOM_PROMPTS[i] === prompt.trim()) i = (i + 1) % RANDOM_PROMPTS.length;
    setDiceIdx(i);
    setPrompt(RANDOM_PROMPTS[i]);
  };

  const pickRef = (f: File | undefined) => {
    if (!f) { setRefImage(undefined); return; }
    const r = new FileReader();
    r.onload = () => setRefImage(typeof r.result === "string" ? r.result : undefined);
    r.readAsDataURL(f);
  };

  const pickEnv = (f: File | undefined) => {
    if (!f) { setEnvImage(undefined); return; }
    const r = new FileReader();
    r.onload = () => setEnvImage(typeof r.result === "string" ? r.result : undefined);
    r.readAsDataURL(f);
  };
  const clearEnv = () => { setEnvImage(undefined); if (envFileRef.current) envFileRef.current.value = ""; };

  const toggleModel = (id: ModelId) =>
    setModels((cur) => (cur.includes(id) ? cur.filter((m) => m !== id) : [...cur, id]));

  // Default = ONE pass: the paint model invents + expands its own body, and the
  // cutout alpha follows that silhouette (no shrink-wrap). The envelope "sculpt"
  // pass is an OPTIONAL second pass for a wilder, more controlled shape (2× cost).
  // An uploaded body is also one pass (painted directly).
  const grows = !envImage && sculpt;            // does the extra envelope pass run?
  const factor = grows ? 1 : 0.55;
  const total = MODELS.filter((m) => models.includes(m.id)).reduce((s, m) => s + m.costPerSkin * factor, 0);
  const anyApprox = MODELS.some((m) => models.includes(m.id) && m.approx);

  const canNext = step === 0 ? prompt.trim().length > 0 : step === 3 ? models.length > 0 : true;

  const generate = async () => {
    if (!models.length) { setErr("pick at least one model"); return; }
    setBusy(true); setErr(null);
    try {
      for (let i = 0; i < models.length; i++) {
        const model = models[i];
        setProgress({ idx: i, total: models.length, model, startedAt: Date.now() });
        const req: GenerateRequest = {
          // envelope:true runs the extra sculpt pass (opt-in). Otherwise one pass:
          // the model expands its own shape. An uploaded body is used directly.
          prompt: prompt.trim(), variant, refImage, model, envelope: grows, envelopeImage: envImage, regions,
        };
        const data = await postGenerate(req);
        if (data.status === "error") { setErr(`${modelLabel(model)}: ${data.error}`); continue; }
        if (data.status !== "done") { setErr("unexpected pending response"); continue; }
        // The CF Worker defers the alpha cutout to here (CPU ceiling) — cut the raw
        // paint in-browser and upload the finished frame.png back. No-op server-side.
        let frameUrl = apiUrl(data.frameUrl);
        if (data.needsCutout && data.paintUrl) {
          try { frameUrl = await finishCutout(data.id, data.paintUrl, data.frameUrl); }
          catch (e) { setErr(`${modelLabel(model)}: cutout failed: ${e instanceof Error ? e.message : String(e)}`); continue; }
        }
        onCreated({
          id: data.id,
          name: `${prompt.trim().slice(0, 18)} · ${modelLabel(data.model)}`,
          blurb: `generated · ${modelLabel(data.model)}`,
          style: data.style,
          frameUrl,
          template: data.template,
        });
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false); setProgress(null);
    }
  };

  // drive the elapsed-seconds counter while a paint pass is in flight. Resets on
  // each new pass (progress.startedAt changes), stops when progress clears.
  useEffect(() => {
    if (!progress) { setElapsed(0); return; }
    setElapsed(0);
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - progress.startedAt) / 1000)), 250);
    return () => clearInterval(t);
  }, [progress]);

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
            {step === 1 ? "drag to move (snaps to align) · corner handles resize · drag empty space to box-select · shift+click to multi-select · ⌫ deletes"
              : `${regions.length} controls · ${variant} layout`}
          </div>
        </div>

        <div className="wiz-panel">
          {step === 0 && (
            <>
              <h3>What is it?</h3>
              <label className="wiz-field">
                <span className="wiz-field-row">
                  Describe the silhouette
                  <button type="button" className="wiz-dice" onClick={rollPrompt}
                    title="Fill with a random idea">🎲 Random</button>
                </span>
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
                  <button key={p.palette} className="wiz-add" style={{ borderColor: colorFor(PALETTE_KIND[p.palette]) }}
                    onClick={() => setRegions((rs) => [...rs, newRegion(p.palette, rs)])}>+ {p.label}</button>
                ))}
                <button className="wiz-reset" onClick={() => usePreset(variant)}>↺ Reset preset</button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h3>Body</h3>
              <p className="wiz-hint">The material is read from your prompt — the Director picks the finish (glossy rubber, brushed chrome, biomech sinew…).</p>
              <div className={`wiz-env wiz-env-auto ${envImage ? "disabled" : ""}`}>
                <span className="wiz-env-mark">✓</span>
                <span className="wiz-env-txt">
                  <strong>No action needed</strong>
                  <small>{envImage
                    ? "Overridden — you uploaded your own body below, so it's used directly."
                    : "The model expands its own body around your controls from your prompt — one pass, cheapest."}</small>
                </span>
              </div>

              <label className={`wiz-env wiz-env-sculpt ${sculpt && !envImage ? "on" : ""} ${envImage ? "disabled" : ""}`}>
                <input type="checkbox" checked={sculpt && !envImage} disabled={!!envImage}
                  onChange={(e) => setSculpt(e.target.checked)} />
                <span className="wiz-env-txt">
                  <strong>✦ Sculpt a wilder body (optional)</strong>
                  <small>Adds a shaping pass that grows a more elaborate silhouette — horns, fins, tendrils — and guarantees the body wraps the controls with margin. ~2× cost, a bit slower.</small>
                </span>
              </label>

              <label className={`wiz-env wiz-env-upload ${envImage ? "on" : ""}`}>
                <span className="wiz-env-txt">
                  <strong>…or upload your own body</strong>
                  <small>{envImage
                    ? "Uploaded body — the paint pass uses this directly (auto-grow skipped)."
                    : "A pre-made silhouette PNG (drawn by hand or in another tool). The paint pass paints straight onto it, skipping the auto-grow."}</small>
                  <input ref={envFileRef} type="file" accept="image/*"
                    onChange={(e) => pickEnv(e.target.files?.[0])} />
                </span>
                {envImage && (
                  <span className="wiz-env-thumb">
                    <img src={envImage} alt="uploaded body envelope" />
                    <button type="button" className="wiz-env-rm" onClick={clearEnv}>× remove</button>
                  </span>
                )}
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
                <div>{variant} · {regions.length} controls · material from prompt
                  {envImage ? " · uploaded body" : grows ? " · sculpted body (2 passes)" : " · auto body (1 pass)"}</div>
                <div className="wiz-total"><strong>{models.length} model{models.length === 1 ? "" : "s"}</strong> · ~{fmt$(total)}{anyApprox ? "*" : ""} total</div>
              </div>
              {progress && <PaintProgress progress={progress} elapsed={elapsed} autoBody={grows} />}
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

// ── new region from a palette entry — always a REAL player control ─────────────
// Each palette kind owns a list of meaningful names; we add the first one not
// already present so repeated clicks cycle through real controls instead of
// piling up duplicates. Ids are friendly (the bind/dynamicType), never "slider-h-14sr".
const SCREEN_TYPES: DynamicType[] = ["visualizer", "marquee", "playlist"];
const BUTTON_BINDS = ["play", "prev", "next", "stop"];
const KNOB_BINDS = ["volume", "balance"];
const TOGGLE_BINDS = ["shuffle", "eqOn"];
const SLIDER_BINDS = ["seek", "volume"];

// first option not already used by an existing region (matched on bind or
// dynamicType); falls back to the first when all are taken.
function firstFree(used: Set<string>, opts: string[]): string {
  return opts.find((o) => !used.has(o)) ?? opts[0];
}
// make the id unique even if its base name repeats (volume slider vs volume knob)
function uniqueId(base: string, regions: Region[]): string {
  if (!regions.some((r) => r.id === base)) return base;
  for (let n = 2; ; n++) { const id = `${base}-${n}`; if (!regions.some((r) => r.id === id)) return id; }
}

function newRegion(palette: PaletteKind, regions: Region[]): Region {
  const usedBinds = new Set(regions.map((r) => r.bind).filter(Boolean) as string[]);
  const usedTypes = new Set(regions.map((r) => r.dynamicType).filter(Boolean) as string[]);

  if (palette === "screen") {
    const dt = firstFree(usedTypes, SCREEN_TYPES) as DynamicType;
    return {
      id: uniqueId(dt, regions), kind: "display", content: "dynamic", layer: "screen",
      rect: { x: 0.3, y: 0.4, w: 0.4, h: 0.16 }, dynamicType: dt, label: dt,
    };
  }
  if (palette === "button") {
    const bind = firstFree(usedBinds, BUTTON_BINDS);
    return {
      id: uniqueId(bind, regions), kind: "button", content: "sprite", layer: "components",
      rect: { x: 0.44, y: 0.45, w: 0.1, h: 0.067 }, bind, label: bind, shape: "ellipse",
    };
  }
  if (palette === "knob") {
    const bind = firstFree(usedBinds, KNOB_BINDS);
    return {
      id: uniqueId(bind, regions), kind: "knob", content: "sprite", layer: "components",
      rect: { x: 0.42, y: 0.44, w: 0.12, h: 0.08 }, bind, label: bind,
    };
  }
  if (palette === "toggle") {
    const bind = firstFree(usedBinds, TOGGLE_BINDS);
    return {
      id: uniqueId(bind, regions), kind: "toggle", content: "sprite", layer: "components",
      rect: { x: 0.45, y: 0.44, w: 0.06, h: 0.09 }, bind, label: bind,
    };
  }
  // slider
  const bind = firstFree(usedBinds, SLIDER_BINDS);
  return {
    id: uniqueId(bind, regions), kind: "slider-h", content: "sprite", layer: "components",
    rect: { x: 0.28, y: 0.5, w: 0.44, h: 0.02 }, bind, label: bind,
  };
}

// ── paint-pass progress: a labeled, phase-walking bar for the ~40–90s paint ────
type GenProgress = { idx: number; total: number; model: ModelId; startedAt: number };

// the honest phases the pipeline walks through. We can't read true server
// progress, so the bar eases toward ~90% over the expected duration and the
// phase label advances on a time schedule that mirrors the real pass.
const PAINT_PHASES = [
  "Reading your prompt",
  "Drawing the blueprint",
  "Growing the body",
  "Painting the material",
  "Cutting it out",
] as const;
// cumulative fraction of the (expected) duration each phase ends at
const PHASE_ENDS = [0.06, 0.18, 0.42, 0.86, 1.0];

function PaintProgress({ progress, elapsed, autoBody }: {
  progress: GenProgress; elapsed: number; autoBody: boolean;
}) {
  // expected duration of THIS pass — two passes (auto-grow) run longer than one.
  const expected = autoBody ? 75 : 45;
  // eased fill: asymptotes toward ~92% so we never claim "done" before the server
  // returns; completes to 100% only when the pass actually resolves (component unmounts).
  const fill = Math.min(0.92, 1 - Math.exp(-1.9 * (elapsed / expected)));
  // pick the phase by elapsed-fraction (auto-grow skips "Growing the body" cheaply
  // when no body is grown, but the label list is honest for the common path).
  const frac = elapsed / expected;
  let phaseIdx = PHASE_ENDS.findIndex((end) => frac < end);
  if (phaseIdx < 0) phaseIdx = PAINT_PHASES.length - 1;
  // an uploaded body skips the grow phase — collapse that label so it stays honest
  const phases = autoBody ? PAINT_PHASES : PAINT_PHASES.filter((p) => p !== "Growing the body");
  const phaseLabel = phases[Math.min(phaseIdx, phases.length - 1)];

  return (
    <div className="wiz-paint" role="status" aria-live="polite">
      <div className="wiz-paint-head">
        <span className="wiz-paint-model">
          {progress.total > 1 && <b>model {progress.idx + 1}/{progress.total} · </b>}
          {modelLabel(progress.model)}
        </span>
        <span className="wiz-paint-elapsed">{elapsed}s</span>
      </div>
      <div className="wiz-paint-bar"><div className="wiz-paint-fill" style={{ width: `${fill * 100}%` }} /></div>
      <div className="wiz-paint-phase">
        <span className="wiz-paint-dot" />{phaseLabel}…
        <span className="wiz-paint-steps">{Math.min(phaseIdx + 1, phases.length)}/{phases.length}</span>
      </div>
      {/* mascot loading animation — the gremlin runs across rolling the knob while
          the paint cooks. The clip is on pure black; mix-blend:screen on the card
          (#101622) keys the black out so he floats on the progress card itself. */}
      <video
        className="wiz-paint-vid"
        src="/loading-mascot.mp4"
        autoPlay loop muted playsInline
        aria-hidden="true"
      />
    </div>
  );
}

// ── draggable layout stage (move + corner resize + snap + multi-select), 2:3 ────
type Dir = "move" | "se" | "sw" | "ne" | "nw";
const SNAP = 0.008; // ~8px on a 1024-wide canvas

type Band = { x0: number; y0: number; x1: number; y1: number };
// reference lines collected from every OTHER region + canvas, for alignment snapping
function refsFor(regions: Region[], exclude: Set<string>) {
  const vx: number[] = [0, 0.5, 1]; // canvas left/center/right
  const hy: number[] = [0, 0.5, 1]; // canvas top/center/bottom
  for (const r of regions) {
    if (exclude.has(r.id)) continue;
    const { x, y, w, h } = r.rect;
    vx.push(x, x + w, x + w / 2);
    hy.push(y, y + h, y + h / 2);
  }
  return { vx, hy };
}
// snap a list of candidate positions to the nearest reference within threshold.
// returns the chosen delta to apply + the snapped reference line (for the guide).
function snapAxis(candidates: number[], refs: number[]): { delta: number; guide: number | null } {
  let best: { delta: number; guide: number; dist: number } | null = null;
  for (const cand of candidates) {
    for (const ref of refs) {
      const dist = Math.abs(cand - ref);
      if (dist <= SNAP && (!best || dist < best.dist)) best = { delta: ref - cand, guide: ref, dist };
    }
  }
  return best ? { delta: best.delta, guide: best.guide } : { delta: 0, guide: null };
}

function LayoutStage({ regions, onChange, editable }: {
  regions: Region[]; onChange: (r: Region[]) => void; editable: boolean;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [guides, setGuides] = useState<{ vx: number[]; hy: number[] }>({ vx: [], hy: [] });
  const [band, setBand] = useState<Band | null>(null);
  // drag.rects holds the START rect of every region being moved (keyed by id) so a
  // group move applies the same dx/dy to all; single resize only touches `id`.
  const drag = useRef<{ id: string; dir: Dir; px: number; py: number; rects: Record<string, Rect> } | null>(null);
  // live rubber-band coords in a ref (px/py = start, ex/ey = current end) so the
  // pointerup handler reads them directly, independent of React's render timing.
  const select = useRef<{ px: number; py: number; ex: number; ey: number } | null>(null);
  // keep latest regions/sel for the window-level pointer handlers without re-binding.
  // updated in an effect (not during render) so React's ref-safety lint stays happy;
  // the handlers only fire after a render has committed, so .current is current.
  const regionsRef = useRef(regions);
  const selRef = useRef(sel);
  useEffect(() => { regionsRef.current = regions; selRef.current = sel; });

  useEffect(() => {
    const norm = (e: PointerEvent) => {
      const st = stageRef.current!; const box = st.getBoundingClientRect();
      return { nx: (e.clientX - box.left) / box.width, ny: (e.clientY - box.top) / box.height, box };
    };

    const move = (e: PointerEvent) => {
      const st = stageRef.current; if (!st) return;

      // rubber-band selection in progress
      if (select.current) {
        const { nx, ny } = norm(e);
        select.current.ex = clamp(nx, 0, 1); select.current.ey = clamp(ny, 0, 1);
        setBand({ x0: select.current.px, y0: select.current.py, x1: select.current.ex, y1: select.current.ey });
        return;
      }

      const d = drag.current; if (!d) return;
      const box = st.getBoundingClientRect();
      const dx = (e.clientX - d.px) / box.width, dy = (e.clientY - d.py) / box.height;
      const min = 0.02;
      const guideVx: number[] = [], guideHy: number[] = [];

      if (d.dir === "move") {
        const movingIds = new Set(Object.keys(d.rects));
        const primary = d.rects[d.id];
        // raw target for the primary region
        let tx = primary.x + dx, ty = primary.y + dy;
        // snap the primary box's left/centerX/right & top/centerY/bottom to refs
        const { vx, hy } = refsFor(regionsRef.current, movingIds);
        const sx = snapAxis([tx, tx + primary.w / 2, tx + primary.w], vx);
        const sy = snapAxis([ty, ty + primary.h / 2, ty + primary.h], hy);
        tx += sx.delta; ty += sy.delta;
        if (sx.guide != null) guideVx.push(sx.guide);
        if (sy.guide != null) guideHy.push(sy.guide);
        // resolve the actual applied delta from the (snapped) primary, then clamp the
        // whole group so no member leaves [0,1]; shrink the delta to keep rigidity.
        let gdx = tx - primary.x, gdy = ty - primary.y;
        for (const id of movingIds) {
          const r = d.rects[id];
          gdx = clamp(r.x + gdx, 0, 1 - r.w) - r.x;
          gdy = clamp(r.y + gdy, 0, 1 - r.h) - r.y;
        }
        onChange(regionsRef.current.map((r) =>
          movingIds.has(r.id) ? { ...r, rect: { ...r.rect, x: d.rects[r.id].x + gdx, y: d.rects[r.id].y + gdy } } : r));
      } else {
        const base = d.rects[d.id];
        let { x, y, w, h } = base;
        const { vx, hy } = refsFor(regionsRef.current, new Set([d.id]));
        if (d.dir.includes("e")) {
          let right = clamp(base.x + base.w + dx, base.x + min, 1);
          const s = snapAxis([right], vx); right += s.delta; if (s.guide != null) guideVx.push(s.guide);
          w = right - base.x;
        }
        if (d.dir.includes("s")) {
          let bot = clamp(base.y + base.h + dy, base.y + min, 1);
          const s = snapAxis([bot], hy); bot += s.delta; if (s.guide != null) guideHy.push(s.guide);
          h = bot - base.y;
        }
        if (d.dir.includes("w")) {
          let nx = clamp(base.x + dx, 0, base.x + base.w - min);
          const s = snapAxis([nx], vx); nx += s.delta; if (s.guide != null) guideVx.push(s.guide);
          nx = clamp(nx, 0, base.x + base.w - min); w = base.w + (base.x - nx); x = nx;
        }
        if (d.dir.includes("n")) {
          let ny = clamp(base.y + dy, 0, base.y + base.h - min);
          const s = snapAxis([ny], hy); ny += s.delta; if (s.guide != null) guideHy.push(s.guide);
          ny = clamp(ny, 0, base.y + base.h - min); h = base.h + (base.y - ny); y = ny;
        }
        onChange(regionsRef.current.map((r) => (r.id === d.id ? { ...r, rect: { x, y, w, h } } : r)));
      }
      setGuides({ vx: guideVx, hy: guideHy });
    };

    const up = () => {
      // finish rubber-band: select everything intersecting the band
      if (select.current) {
        const b = select.current;
        const lo = { x: Math.min(b.px, b.ex), y: Math.min(b.py, b.ey) };
        const hi = { x: Math.max(b.px, b.ex), y: Math.max(b.py, b.ey) };
        const dragged = Math.abs(b.ex - b.px) > 0.005 || Math.abs(b.ey - b.py) > 0.005;
        if (dragged) {
          const hit = new Set<string>();
          for (const r of regionsRef.current) {
            const { x, y, w, h } = r.rect;
            if (x < hi.x && x + w > lo.x && y < hi.y && y + h > lo.y) hit.add(r.id);
          }
          setSel(hit);
        } else {
          setSel(new Set()); // a click on empty space (no drag) clears
        }
        select.current = null; setBand(null);
      }
      drag.current = null;
      setGuides({ vx: [], hy: [] });
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, [onChange]);

  const start = (e: React.PointerEvent, id: string, dir: Dir) => {
    if (!editable) return;
    e.stopPropagation();
    // figure out which set to move: a drag on a non-selected region selects just it,
    // unless shift is held (toggle). resize always operates on the single selection.
    let active = sel;
    if (dir === "move") {
      if (e.shiftKey) {
        active = new Set(sel);
        if (active.has(id)) active.delete(id); else active.add(id);
        setSel(active);
        return; // shift+click toggles selection without starting a drag
      }
      if (!sel.has(id)) { active = new Set([id]); setSel(active); }
    } else {
      active = new Set([id]);
    }
    const rects: Record<string, Rect> = {};
    const moveSet = dir === "move" ? active : new Set([id]);
    for (const r of regions) if (moveSet.has(r.id)) rects[r.id] = { ...r.rect }; // prop is current at press time
    drag.current = { id, dir, px: e.clientX, py: e.clientY, rects };
  };

  const onStagePointerDown = (e: React.PointerEvent) => {
    if (!editable) return;
    // empty-area press starts a rubber band (and tentatively clears on a no-drag click)
    const st = stageRef.current; if (!st) return;
    const box = st.getBoundingClientRect();
    const nx = clamp((e.clientX - box.left) / box.width, 0, 1);
    const ny = clamp((e.clientY - box.top) / box.height, 0, 1);
    select.current = { px: nx, py: ny, ex: nx, ey: ny };
    setBand({ x0: nx, y0: ny, x1: nx, y1: ny });
  };

  // delete from a given source list (the keyboard path passes the ref's latest;
  // the render path passes the live `regions` prop so no ref is read during render).
  const delFrom = (src: Region[], ids: Set<string>) => {
    onChange(src.filter((r) => !ids.has(r.id)));
    setSel(new Set());
  };

  // delete / backspace removes all selected; arrows nudge — but never when typing.
  useEffect(() => {
    if (!editable) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      const cur = selRef.current; if (!cur.size) return;
      if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); delFrom(regionsRef.current, cur); return; }
      const step = 0.005;
      let dx = 0, dy = 0;
      if (e.key === "ArrowLeft") dx = -step; else if (e.key === "ArrowRight") dx = step;
      else if (e.key === "ArrowUp") dy = -step; else if (e.key === "ArrowDown") dy = step; else return;
      e.preventDefault();
      onChange(regionsRef.current.map((r) => cur.has(r.id)
        ? { ...r, rect: { ...r.rect, x: clamp(r.rect.x + dx, 0, 1 - r.rect.w), y: clamp(r.rect.y + dy, 0, 1 - r.rect.h) } }
        : r));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editable, onChange]);

  const single = sel.size === 1 ? [...sel][0] : null;

  return (
    <div ref={stageRef} className={`wiz-stage ${editable ? "edit" : ""}`} onPointerDown={onStagePointerDown}>
      {regions.map((r) => {
        const c = colorFor(r.kind), ell = r.shape === "ellipse" || r.kind === "knob";
        // arc/path seeks fill the whole dial bbox — draw them as a faint dashed ring
        // so they read as "thumb rides this area", not a solid control slab.
        const arc = r.kind === "slider-arc" || r.kind === "slider-path";
        const on = sel.has(r.id);
        const isSingle = single === r.id;
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
            <span className="wiz-region-tag" style={{ color: c }}>{r.bind || r.dynamicType || r.label || r.kind}</span>
            {isSingle && editable && (["nw", "ne", "sw", "se"] as Dir[]).map((d) => (
              <span key={d} className={`wiz-h h-${d}`} style={{ borderColor: c }} onPointerDown={(e) => start(e, r.id, d)} />
            ))}
            {isSingle && editable && <button className="wiz-region-del" onClick={(e) => { e.stopPropagation(); delFrom(regions, new Set([r.id])); }}>×</button>}
          </div>
        );
      })}

      {/* alignment guide lines (only while a snap is active) */}
      {editable && guides.vx.map((x, i) => (
        <div key={`gv${i}`} className="wiz-guide v" style={{ left: `${x * 100}%` }} />
      ))}
      {editable && guides.hy.map((y, i) => (
        <div key={`gh${i}`} className="wiz-guide h" style={{ top: `${y * 100}%` }} />
      ))}

      {/* rubber-band selection rectangle */}
      {editable && band && (
        <div className="wiz-band" style={{
          left: `${Math.min(band.x0, band.x1) * 100}%`, top: `${Math.min(band.y0, band.y1) * 100}%`,
          width: `${Math.abs(band.x1 - band.x0) * 100}%`, height: `${Math.abs(band.y1 - band.y0) * 100}%`,
        }} />
      )}
    </div>
  );
}
