import { useRef, useState } from "react";
import type { GenerateRequest, GenerateResponse } from "./api";
import type { DonorStyle } from "./pipeline";
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
}

// Style + layout-variant pickers were removed from the UI for now — the panel is
// just prompt → generate. Defaults are applied internally; the pickers come back
// as a feature later (see git history for the dropdowns).
const DEFAULT_STYLE: DonorStyle = "biomech";
const DEFAULT_VARIANT: LayoutVariant = "radial";

export function CreatePanel({ onCreated }: { onCreated: (s: RuntimeSkin) => void }) {
  const [prompt, setPrompt] = useState("a fanged anglerfish jaw");
  const [refImage, setRefImage] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [stage, setStage] = useState<string>("");
  const fileRef = useRef<HTMLInputElement>(null);

  const pickRef = (f: File | undefined) => {
    if (!f) { setRefImage(undefined); return; }
    const r = new FileReader();
    r.onload = () => setRefImage(typeof r.result === "string" ? r.result : undefined);
    r.readAsDataURL(f);
  };

  const submit = async () => {
    setBusy(true); setErr(null); setStage("envelope → paint (~30-90s)…");
    const req: GenerateRequest = { prompt: prompt.trim(), style: DEFAULT_STYLE, variant: DEFAULT_VARIANT, refImage };
    try {
      const r = await fetch("/api/generate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
      });
      const data: GenerateResponse = await r.json();
      if (data.status === "error") { setErr(data.error); return; }
      if (data.status !== "done") { setErr("unexpected pending response (no poller wired in v1)"); return; }
      onCreated({
        id: data.id,
        name: `${prompt.trim().slice(0, 22)} ✦`,
        blurb: "generated",
        style: data.style,
        frameUrl: data.frameUrl,
        template: data.template,
      });
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
          placeholder="a fanged anglerfish jaw" />
      </label>
      <label className="cp-field">
        <span>Reference image (optional)</span>
        <input ref={fileRef} type="file" accept="image/*"
          onChange={(e) => pickRef(e.target.files?.[0])} />
        {refImage && <img className="cp-ref-thumb" src={refImage} alt="reference" />}
      </label>
      <button className="cp-submit" disabled={busy || !prompt.trim()} onClick={submit}>
        {busy ? "Generating…" : "Generate (~$0.30 fal)"}
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
