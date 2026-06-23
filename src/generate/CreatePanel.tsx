import { useRef, useState } from "react";
import type { GenerateRequest } from "./api";
import { postGenerate } from "./postGenerate";
import { finishCutout } from "./cutoutClient";
import { apiUrl } from "../platform";
import { MODELS, DEFAULT_MODEL, type DonorStyle, type ModelId } from "./pipeline";
import type { LayoutVariant } from "./layouts";
import type { Template } from "../template/schema";

// A skin produced at runtime by POST /api/generate — frame inline (data: URL or
// public URL) + its template, registered client-side and selected immediately.
export interface RuntimeSkin {
  id: string;
  name: string;
  blurb: string;
  style: DonorStyle;    // donor for sprites/palette (resolves via [data-skin])
  frameUrl: string;
  template: Template;
  // true when the pipeline produced per-skin control sprites for THIS skin
  // (served at /api/asset/skins/<id>/sprites/<bind>.png). When set, the player
  // renders those instead of the donor style's bundled sprites. Set by
  // GenerateDone (owned by the pipeline team) and consumed in Composite.
  sprites?: boolean;
}

// Style + layout-variant pickers were removed from the UI for now — the panel is
// just prompt → generate. Defaults are applied internally; the pickers come back
// as a feature later (see git history for the dropdowns).
const DEFAULT_STYLE: DonorStyle = "biomech";
const DEFAULT_VARIANT: LayoutVariant = "radial";

const fmt$ = (n: number) => `$${n.toFixed(2)}`;
const modelLabel = (id: ModelId) => MODELS.find((m) => m.id === id)?.label ?? id;

export function CreatePanel({ onCreated }: { onCreated: (s: RuntimeSkin) => void }) {
  const [prompt, setPrompt] = useState("a cute Y2K virtual-pet egg");
  const [refImage, setRefImage] = useState<string | undefined>();
  // selected image models — one OR many; default to nano-banana-pro only.
  const [selected, setSelected] = useState<ModelId[]>([DEFAULT_MODEL]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [stage, setStage] = useState<string>("");
  const fileRef = useRef<HTMLInputElement>(null);

  const toggleModel = (id: ModelId) =>
    setSelected((cur) =>
      cur.includes(id) ? cur.filter((m) => m !== id) : [...cur, id]);

  const total = MODELS.filter((m) => selected.includes(m.id))
    .reduce((sum, m) => sum + m.costPerSkin, 0);
  const anyApprox = MODELS.some((m) => selected.includes(m.id) && m.approx);

  const pickRef = (f: File | undefined) => {
    if (!f) { setRefImage(undefined); return; }
    const r = new FileReader();
    r.onload = () => setRefImage(typeof r.result === "string" ? r.result : undefined);
    r.readAsDataURL(f);
  };

  const submit = async () => {
    if (!selected.length) { setErr("pick at least one model"); return; }
    setBusy(true); setErr(null);
    // one generation per selected model — each registers as its own runtime skin
    // so the user can compare. Sequential so the stage line reflects real progress.
    try {
      for (let i = 0; i < selected.length; i++) {
        const model = selected[i];
        setStage(`model ${i + 1}/${selected.length} · ${modelLabel(model)} — envelope → paint (~30-90s)…`);
        const req: GenerateRequest = {
          prompt: prompt.trim(), style: DEFAULT_STYLE, variant: DEFAULT_VARIANT, refImage, model,
        };
        const data = await postGenerate(req);
        if (data.status === "error") { setErr(`${modelLabel(model)}: ${data.error}`); continue; }
        if (data.status !== "done") { setErr("unexpected pending response (no poller wired in v1)"); continue; }
        // CF Worker defers the alpha cutout to the browser (CPU ceiling) — cut the
        // raw paint here and upload the finished frame.png back. No-op server-side.
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
          // the pipeline flags per-skin sprites on the response (api.ts is owned
          // by the pipeline team and doesn't type this yet) — forward it so the
          // player renders THIS skin's own sprites the moment they're produced.
          sprites: (data as { sprites?: boolean }).sprites,
        });
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false); setStage("");
    }
  };

  return (
    <div className="create-panel">
      <h2>Create a skin</h2>
      <label className="cp-field">
        <span>Prompt (silhouette)</span>
        <textarea value={prompt} rows={2} onChange={(e) => setPrompt(e.target.value)}
          placeholder="a cute Y2K virtual-pet egg" />
      </label>
      <label className="cp-field">
        <span>Reference image (optional)</span>
        <input ref={fileRef} type="file" accept="image/*"
          onChange={(e) => pickRef(e.target.files?.[0])} />
        {refImage && <img className="cp-ref-thumb" src={refImage} alt="reference" />}
      </label>

      <fieldset className="cp-field cp-models">
        <span className="cp-models-legend">Image model(s)</span>
        <div className="cp-model-list">
          {MODELS.map((m) => {
            const on = selected.includes(m.id);
            return (
              <label key={m.id} className={`cp-model ${on ? "on" : ""}`}>
                <input type="checkbox" checked={on} onChange={() => toggleModel(m.id)} />
                <span className="cp-model-name">{m.label}</span>
                <span className="cp-model-cost">
                  ~{fmt$(m.costPerSkin)}{m.approx ? "*" : ""}/skin
                </span>
              </label>
            );
          })}
        </div>
        <div className="cp-total">
          <strong>{selected.length} model{selected.length === 1 ? "" : "s"}</strong>
          <span> · ~{fmt$(total)}{anyApprox ? "*" : ""} total</span>
        </div>
        <p className="cp-models-hint">
          Each selected model produces its own variant — they give interestingly
          different results.{anyApprox ? " * approximate pricing." : ""}
        </p>
      </fieldset>

      <button className="cp-submit" disabled={busy || !prompt.trim() || !selected.length} onClick={submit}>
        {busy
          ? "Generating…"
          : `Generate ${selected.length} skin${selected.length === 1 ? "" : "s"} (~${fmt$(total)}${anyApprox ? "*" : ""} fal)`}
      </button>
      {stage && <div className="cp-stage">{stage}</div>}
      {err && <div className="cp-error">{err}</div>}
      <p className="cp-note">
        Describe a silhouette; the layout-first pipeline sculpts a body around the
        controls server-side (FAL_KEY stays on the server). Hard cap 5/day per IP.
      </p>
    </div>
  );
}
