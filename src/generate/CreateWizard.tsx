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
  const [envImage, setEnvImage] = useState<string | undefined>(); // user-uploaded body envelope (data URL); when set it wins
  const envFileRef = useRef<HTMLInputElement>(null);

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

  const pickEnv = (f: File | undefined) => {
    if (!f) { setEnvImage(undefined); return; }
    const r = new FileReader();
    r.onload = () => setEnvImage(typeof r.result === "string" ? r.result : undefined);
    r.readAsDataURL(f);
  };
  const clearEnv = () => { setEnvImage(undefined); if (envFileRef.current) envFileRef.current.value = ""; };

  const toggleModel = (id: ModelId) =>
    setModels((cur) => (cur.includes(id) ? cur.filter((m) => m !== id) : [...cur, id]));

  // a user-uploaded envelope skips the AI envelope pass, so it costs like freeform.
  // two passes (full price) only when the AI envelope actually runs.
  const aiEnvelope = envelope && !envImage;
  // envelope OFF ≈ one image pass instead of two → roughly half the per-skin cost.
  const factor = aiEnvelope ? 1 : 0.55;
  const total = MODELS.filter((m) => models.includes(m.id)).reduce((s, m) => s + m.costPerSkin * factor, 0);
  const anyApprox = MODELS.some((m) => models.includes(m.id) && m.approx);

  const canNext = step === 0 ? prompt.trim().length > 0 : step === 3 ? models.length > 0 : true;

  const generate = async () => {
    if (!models.length) { setErr("pick at least one model"); return; }
    setBusy(true); setErr(null);
    try {
      for (let i = 0; i < models.length; i++) {
        const model = models[i];
        setStage(`model ${i + 1}/${models.length} · ${modelLabel(model)} — ${aiEnvelope ? "envelope → paint" : "paint"} (~30–90s)…`);
        const req: GenerateRequest = {
          prompt: prompt.trim(), style: material, variant, refImage, model, envelope, envelopeImage: envImage, regions,
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
            {step === 1 ? "drag to move (snaps to align) · corner handles resize · drag empty space to box-select · shift+click to multi-select · ⌫ deletes"
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
              <label className={`wiz-env ${envelope && !envImage ? "on" : ""} ${envImage ? "disabled" : ""}`}>
                <input type="checkbox" checked={envelope && !envImage} disabled={!!envImage}
                  onChange={(e) => setEnvelope(e.target.checked)} />
                <span className="wiz-env-txt">
                  <strong>Grow an AI body envelope around the controls</strong>
                  <small>{envImage
                    ? "Disabled — you uploaded your own body below, so the AI envelope is skipped."
                    : envelope
                    ? "Two image passes: first sculpts a silhouette around your wells, then paints it. More control over shape, ~2× the cost."
                    : "Off (default): one pass — the model paints a freeform body straight from your control layout. Cheaper, wilder shapes."}</small>
                </span>
              </label>

              <label className={`wiz-env wiz-env-upload ${envImage ? "on" : ""}`}>
                <span className="wiz-env-txt">
                  <strong>…or upload your own body</strong>
                  <small>{envImage
                    ? "Uploaded body — the paint pass uses this directly (AI envelope skipped)."
                    : "A pre-made silhouette PNG (drawn by hand or in another tool). The paint pass paints straight onto it."}</small>
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
                <div>{variant} · {regions.length} controls · {MATERIALS.find((m) => m.id === material)?.label}
                  {envImage ? " · uploaded body" : aiEnvelope ? " · AI body" : " · freeform body"}</div>
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
