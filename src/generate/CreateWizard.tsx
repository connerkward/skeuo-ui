import { useEffect, useRef, useState } from "react";
import type { GenerateRequest } from "./api";
import { postGenerate } from "./postGenerate";
import { finishCutout } from "./cutoutClient";
import { apiUrl } from "../platform";
import { MODELS, DEFAULT_MODEL, type ModelId } from "./pipeline";
import { regionsForVariant, layoutRandom, type LayoutVariant } from "./layouts";
import type { Region, Kind, DynamicType } from "../template/schema";
import type { RuntimeSkin } from "./CreatePanel";
import { LayoutStage } from "../template/LayoutStage";

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
  "a cute Y2K virtual-pet egg",
  "a translucent grape jelly gadget",
  "a baby-blue clamshell flip phone",
  "a frosted see-through handheld game console",
  "a glittery butterfly hair clip",
  "a glossy gummy frog on a lilypad",
  "a chunky inflatable vinyl chair",
  "a holographic dolphin sticker pod",
  "a pastel heart-shaped compact mirror",
  "a fuzzy big-eyed robot pet",
  "a bubblegum-pink jelly bug",
  "a star-shaped candy boombox",
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

export function CreateWizard({ onCreated }: { onCreated: (s: RuntimeSkin) => void }) {
  const [step, setStep] = useState<Step>(0);

  // step 1 — idea
  const [prompt, setPrompt] = useState("a cute Y2K virtual-pet egg");
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
          font: data.font,
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

      {/* on the Layout step the stage becomes the hero (big canvas, panel shrinks) */}
      <div className={`wiz-body ${step === 1 ? "wiz-body-layout" : ""}`}>
        {/* live layout preview sits beside every step so the artifact is always visible */}
        <div className="wiz-preview">
          <LayoutStage regions={regions} onChange={setRegions} editable={step === 1} />
          <div className="wiz-preview-cap">
            {step === 1 ? "drag to move (snaps to align · magenta = symmetry · hold Alt to disable) · 8 handles resize · drag empty space to box-select · shift-click multi-select · arrows nudge · ⌫ deletes"
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
                  placeholder="a cute Y2K virtual-pet egg" />
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
              <button className="wiz-randomize" onClick={() => setRegions(layoutRandom())}
                title="Heuristically lay out a fresh, complete player">🎲 Randomize layout</button>
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
    <>
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
      </div>
      {/* mascot loading animation — the gremlin runs across rolling the knob while
          the paint cooks. It sits OUTSIDE the blue progress card, on the wizard's
          near-black panel (#0d0d10); the clip is on pure black and mix-blend:screen
          keys that black out so only the gremlin shows, floating on the dark bg. */}
      <video
        className="wiz-paint-vid"
        src="/loading-mascot.mp4"
        autoPlay loop muted playsInline
        aria-hidden="true"
      />
    </>
  );
}
