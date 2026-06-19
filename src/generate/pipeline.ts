// ============================================================
// The LAYOUT-FIRST generation pipeline, ported from wild_sculpt.py's
// main() radial/capsule/minimal branch — runtime-agnostic (uses fetch).
//
// Flow (identical to the Python, minus the CV the layout-first path
// never needed):
//   1. pick the constant layout for the chosen variant
//   2. draw the wells-only blueprint → PNG  (envelope step input)
//   3. fal ENVELOPE pass (gemini-3-pro-image-preview/edit): grow a
//      flat dark-gray silhouette AROUND the wells       [ENVELOPE_PROMPT]
//   4. fal PAINT pass (same endpoint): restyle the blueprint into the
//      material, wells stay empty                       [STYLE + MATERIAL]
//   5. alpha = the PAINTED SILHOUETTE keyed out of the paint PNG (the
//      prompt forces "everything outside the silhouette stays pure
//      white", so the non-white body IS the real outline — no shrink-wrap)
//   6. the cutout returns the framed RGBA directly; emit template.json
//
// The caller injects `rasterize` (SVG→PNG bytes) and `cutout`
// (paint PNG → RGBA PNG with white keyed transparent, holes filled,
// largest connected component kept) so the SAME pipeline runs under
// resvg-wasm in a CF Worker or resvg-js + UPNG in Node.
// ============================================================
import type { Region, Template } from "../template/schema";
import { GEN_W, GEN_H, regionsForVariant, type LayoutVariant } from "./layouts";
import { wellsOnlySvg } from "./blueprint";

// ---- prompts: verbatim from wild_sculpt.py so output matches the Python ----
export const ENVELOPE_PROMPT =
  "Keep every dark control socket, round well, ring groove and dark screen EXACTLY where it is, " +
  "pixel-identical, unchanged. Around and BEHIND them, paint ONE flat solid dark-gray SILHOUETTE " +
  "shape on the pure white background: the outline of {brief}. The silhouette must fully CONTAIN " +
  "every socket and screen with generous margin on all sides, and its wild parts — horns, fins, " +
  "tendrils, legs, jaws — grow outward from that mass. Completely flat dark-gray fill, no interior " +
  "detail, no shading, no outline strokes. Everything else stays pure white.";

export const STYLE_PROMPT =
  "Restyle this blueprint into a photoreal, wildly-shaped skeuomorphic MP3-player device. CRITICAL: " +
  "keep the EXACT silhouette, and keep EVERY dark recessed well and screen EXACTLY where it is, same " +
  "size and shape — every recessed well stays a DEEP DARK EMPTY socket: a near-black matte cavity " +
  "with a crisp raised rim, NOTHING mounted inside, NOT glowing, NOT filled with material; and every " +
  "screen — INCLUDING the thin marquee strip — stays switched-off NEAR-BLACK glass, a CLEAN FLAT " +
  "RECTANGLE never tinted or overgrown by the body material (no text, no graphics). Make the body rich and detailed BETWEEN the wells. Everything outside the silhouette stays pure white. Front-on " +
  "orthographic, even light, high detail. MATERIAL: ";

export const MATERIAL: Record<string, string> = {
  biomech: "H.R. Giger biomechanical nightmare: fused bone and sinew, ribbed chitin tubes wrapping " +
    "the body, vertebrae ridges, wet organic sheen, sickly green-amber bioluminescence glowing from the recesses.",
  winamp: "polished chrome and brushed gunmetal over dark charcoal plastic, thin green LED accent lines tracing the curves, tiny screws.",
  frog: "glossy moulded rubber toy-frog skin in vivid green with subtle mottling, bulging highlights, bright orange plastic hardware accents.",
  wmp: "Windows Media Player 9 / XP Luna capsule hardware: glossy silver-white plastic shells, translucent aqua-blue gel inlays, polished chrome trim rings, soft blue gradients, subtle green LED accents.",
  halo: "Halo 2 UNSC military hardware: olive-drab armored metal plating with scuffed edges, hex bolts, vents, layered angular armor ridges, amber-orange holographic tick marks and warning chevrons glowing from recesses.",
};
export const DONOR_STYLES = Object.keys(MATERIAL);
export type DonorStyle = keyof typeof MATERIAL;

// ---- image-model registry: the three selectable edit endpoints ----
// label  → the fal edit endpoint + an est per-skin cost (2 passes: envelope+paint).
export type ModelId =
  | "fal-ai/gemini-3-pro-image-preview/edit"
  | "fal-ai/gemini-3.1-flash-image-preview/edit"
  | "openai/gpt-image-2/edit";

export interface ModelInfo {
  id: ModelId;
  label: string;
  costPerSkin: number;   // est $ for the two passes
  approx?: boolean;      // mark approximate pricing
}

export const MODELS: ModelInfo[] = [
  { id: "fal-ai/gemini-3-pro-image-preview/edit", label: "nano-banana-pro", costPerSkin: 0.30 },
  { id: "fal-ai/gemini-3.1-flash-image-preview/edit", label: "nano-banana-2", costPerSkin: 0.16 },
  { id: "openai/gpt-image-2/edit", label: "gpt-image-2", costPerSkin: 0.34, approx: true },
];
// default to nano-banana-2 — the cheapest paint endpoint
export const DEFAULT_MODEL: ModelId = "fal-ai/gemini-3.1-flash-image-preview/edit";
const modelLabel = (id: ModelId): string => MODELS.find((m) => m.id === id)?.label ?? id;

export interface RuntimeDeps {
  falKey: string;
  // optional: OpenAI key for the Director (prompt → material). When absent, the
  // handler falls back to a default style and the MATERIAL dict.
  openaiKey?: string;
  // SVG string → PNG bytes (resvg-wasm in CF, resvg-js in Node)
  rasterize: (svg: string) => Promise<Uint8Array>;
  // paint PNG → RGBA PNG bytes with the near-white background keyed out:
  // alpha follows the PAINTED silhouette (largest connected component,
  // internal holes filled so dark control wells stay opaque, light feather).
  // OPTIONAL: this is ~2s of pure-JS CPU. Runtimes with no CPU ceiling (the Node
  // dev server) provide it and cut server-side. The CF Pages Function OMITS it —
  // that CPU trips the Function ceiling (CF 1102) — so the pipeline persists the
  // RAW paint instead and the browser does the cutout + uploads frame.png back.
  cutout?: (paintPng: Uint8Array) => Promise<Uint8Array>;
  // optional: persist one artifact for skin <id>, return its public URL. frame/paint
  // are binary PNG (Uint8Array); template/meta are JSON strings. When omitted, the
  // image is returned inline as a data: URL (demo — no R2 needed) and template/meta
  // are simply not persisted. Wiring R2 (env.SKINS) makes EVERY generated skin a
  // shared cloud artifact under skins/<id>/ (frame.png OR paint.png + template.json +
  // meta.json), reconstructable by id via /api/skin/<id>.
  store?: (id: string, kind: "frame" | "paint" | "template" | "meta", data: Uint8Array | string) => Promise<string>;
  log?: (msg: string) => void;
}

// Small per-skin record persisted alongside the frame + template so a shared link
// can show what made the skin without re-deriving it. Lives at skins/<id>/meta.json.
export interface SkinMeta {
  prompt: string;
  model: ModelId;
  style: string;
  variant: string;
  createdAt: string;   // ISO
}

export interface GenerateInput {
  id: string;
  variant: LayoutVariant;
  style: DonorStyle;
  materialPrompt?: string; // Director-derived custom material; overrides the MATERIAL dict when set
  brief: string;          // the silhouette brief, e.g. "a fanged anglerfish jaw"
  refImageUrls?: string[]; // optional reference-style images (palette/material steer)
  model?: ModelId;        // image edit endpoint (default DEFAULT_MODEL)
  envelope?: boolean;     // run the AI envelope pass first (default true)
  envelopeUrl?: string;   // optional fal-hosted user-uploaded envelope; paints from it directly, skipping the AI envelope pass
  regions?: Region[];     // custom authored layout (else the variant preset)
}

export interface GenerateResult {
  id: string;
  style: DonorStyle;
  variant: LayoutVariant;
  model: ModelId;
  template: Template;
  frameUrl: string;       // public URL or data: URL of the CUT frame
  needsCutout?: boolean;  // true when the cutout was deferred to the browser (CF Worker path)
  paintUrl?: string;      // raw paint PNG to cut client-side — present when needsCutout
  timingMs: { envelope: number; paint: number; total: number };
}

// ---- fal REST helpers (mirror generate.py's post/get/upload/submit) ----
async function falPost(falKey: string, url: string, body: unknown): Promise<any> {
  const r = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Key ${falKey}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`fal POST ${url} → ${r.status} ${await r.text()}`);
  return r.json();
}
async function falGet(falKey: string, url: string): Promise<any> {
  const r = await fetch(url, { headers: { Authorization: `Key ${falKey}` } });
  if (!r.ok) throw new Error(`fal GET ${url} → ${r.status}`);
  return r.json();
}
async function falUpload(falKey: string, png: Uint8Array): Promise<string> {
  const init = await falPost(falKey, "https://rest.alpha.fal.ai/storage/upload/initiate", {
    file_name: "blueprint.png", content_type: "image/png",
  });
  const put = await fetch(init.upload_url, {
    method: "PUT", headers: { "Content-Type": "image/png" }, body: png as unknown as ArrayBuffer,
  });
  if (!put.ok) throw new Error(`fal upload PUT → ${put.status}`);
  return init.file_url;
}
// submit one edit job (blueprint first = layout authority). The fal input schema
// differs by model: the gemini endpoints take resolution + aspect_ratio; gpt-image-2
// takes image_size + quality and rejects resolution/aspect_ratio — so branch the body.
function falSubmit(falKey: string, model: ModelId, imageUrls: string[], prompt: string) {
  const body: Record<string, unknown> =
    model === "openai/gpt-image-2/edit"
      ? { prompt, image_urls: imageUrls, image_size: { width: 1024, height: 1536 }, quality: "high", output_format: "png" }
      : { prompt, image_urls: imageUrls, resolution: "2K", aspect_ratio: "2:3", output_format: "png" };
  return falPost(falKey, `https://queue.fal.run/${model}`, body);
}
async function falPoll(falKey: string, job: any, timeoutMs: number): Promise<string> {
  const t0 = Date.now();
  for (;;) {
    const s = (await falGet(falKey, job.status_url)).status;
    if (s === "COMPLETED") break;
    if (s === "FAILED" || s === "ERROR") throw new Error("fal job failed");
    if (Date.now() - t0 > timeoutMs) throw new Error("fal job timeout");
    await new Promise((res) => setTimeout(res, 3500));
  }
  return (await falGet(falKey, job.response_url)).images[0].url;
}
async function fetchPng(url: string): Promise<Uint8Array> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`fetch image ${url} → ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

export async function generateSkin(deps: RuntimeDeps, input: GenerateInput): Promise<GenerateResult> {
  const log = deps.log ?? (() => {});
  const model = input.model ?? DEFAULT_MODEL;
  const useEnvelope = input.envelope ?? true;
  // custom layout from the wizard wins; otherwise the constant variant preset.
  const regs: Region[] = input.regions?.length ? input.regions : regionsForVariant(input.variant);
  const template: Template = { id: input.id, name: "wild-sculpt", canvas: { w: GEN_W, h: GEN_H }, regions: regs };
  const tAll = Date.now();

  // 2. wells-only blueprint PNG (envelope input)
  const wellsPng = await deps.rasterize(wellsOnlySvg(regs));

  // 3. ENVELOPE pass — grow a flat silhouette around the wells. This is the
  //    DEFAULT (useEnvelope defaults true): with no uploaded envelope the body
  //    auto-expands from the prompt instead of freeform-shrinking to the wells.
  //    Only an uploaded envelopeUrl skips it; explicitly passing envelope:false
  //    falls back to painting straight from the wells-only blueprint.
  let paintInputPng = wellsPng;
  let envMs = 0;
  if (input.envelopeUrl) {
    // user-uploaded envelope wins: paint straight from it, skip the AI envelope pass.
    paintInputPng = await fetchPng(input.envelopeUrl);
    log(`[${input.id}] using uploaded envelope`);
  } else if (useEnvelope) {
    const tEnv = Date.now();
    const wellsUrl = await falUpload(deps.falKey, wellsPng);
    const envJob = await falSubmit(deps.falKey, model, [wellsUrl], ENVELOPE_PROMPT.replace("{brief}", input.brief));
    const envUrl = await falPoll(deps.falKey, envJob, 7 * 60_000);
    paintInputPng = await fetchPng(envUrl);
    envMs = Date.now() - tEnv;
    log(`[${input.id}] envelope (${modelLabel(model)}) ${(envMs / 1000) | 0}s`);
  }

  // 4. PAINT pass — restyle the ENVELOPE (silhouette + wells) into the material.
  //    The envelope already carries the wells (pixel-identical) plus the body
  //    silhouette, so it is the layout authority for the paint, exactly like the
  //    Python draw_blueprint() output. Reference-style images ride along.
  const tPaint = Date.now();
  const paintInputUrl = await falUpload(deps.falKey, paintInputPng);
  let prompt = STYLE_PROMPT + (input.materialPrompt || MATERIAL[input.style] || MATERIAL.winamp);
  const refs = input.refImageUrls ?? [];
  if (refs.length) {
    prompt += " Borrow the palette, materials and surface-detail vocabulary of the REFERENCE " +
      "image(s) provided, but DO NOT copy their layout or shape — the silhouette and wells come only from the blueprint.";
  }
  const paintJob = await falSubmit(deps.falKey, model, [paintInputUrl, ...refs], prompt);
  const paintUrl = await falPoll(deps.falKey, paintJob, 9 * 60_000);
  const paintPng = await fetchPng(paintUrl);
  const paintMs = Date.now() - tPaint;
  log(`[${input.id}] paint (${modelLabel(model)}) ${(paintMs / 1000) | 0}s`);

  // 5/6. alpha = the PAINTED silhouette, keyed out of the paint PNG. The paint
  //    prompt forces "everything outside the silhouette stays pure white", so the
  //    non-white region IS the real (expanded) outline. cutout() keys white →
  //    transparent, keeps the largest connected component, and fills internal
  //    holes so dark control wells inside the body stay opaque. No region-union
  //    shrink-wrap.
  //
  //    cutout is ~2s of pure-JS CPU. Two paths:
  //      • deps.cutout PRESENT (Node dev, no CPU limit): cut server-side, store the
  //        finished frame.png — the contract's frameUrl is the cut frame, done.
  //      • deps.cutout ABSENT (CF Pages Function): that CPU trips the Function
  //        ceiling (CF 1102 exceededCpu), so DEFER it. Persist the RAW paint and
  //        return needsCutout + paintUrl; the browser cuts and uploads frame.png
  //        back to skins/<id>/ via /api/finalize/<id> (a no-CPU R2 write).
  const meta: SkinMeta = {
    prompt: input.brief, model, style: input.style, variant: input.variant,
    createdAt: new Date().toISOString(),
  };
  const storeSidecars = async () => {
    if (!deps.store) return;
    try {
      await deps.store!(input.id, "template", JSON.stringify(template));
      await deps.store!(input.id, "meta", JSON.stringify(meta));
    } catch (e) { log(`[${input.id}] sidecar store failed: ${e instanceof Error ? e.message : e}`); }
  };

  let frameUrl: string;
  let needsCutout: boolean | undefined;
  let paintOut: string | undefined;   // raw paint URL returned to the client to cut

  if (deps.cutout) {
    // server-side cutout (no CPU ceiling) — store/inline the finished frame
    const framePng = await deps.cutout(paintPng);
    if (deps.store) {
      frameUrl = await deps.store(input.id, "frame", framePng);
      await storeSidecars();
    } else {
      frameUrl = `data:image/png;base64,${toBase64(framePng)}`;
    }
  } else {
    // deferred cutout (CF Worker) — persist the raw paint; the browser finishes it.
    needsCutout = true;
    if (deps.store) {
      paintOut = await deps.store(input.id, "paint", paintPng);
      // frame.png is the sibling key the browser will upload to (same skins/<id>/
      // prefix). Derive it from the paint URL so it tracks ASSETS_BASE_URL.
      frameUrl = paintOut.replace(/paint\.png(\?.*)?$/, "frame.png");
      await storeSidecars();
    } else {
      // demo (no R2): hand the raw paint to the client inline; it cuts in-memory
      // and there is no durable frame URL to point at.
      paintOut = `data:image/png;base64,${toBase64(paintPng)}`;
      frameUrl = paintOut;
    }
  }

  return {
    id: input.id, style: input.style, variant: input.variant, model, template, frameUrl,
    needsCutout, paintUrl: paintOut,
    timingMs: { envelope: envMs, paint: paintMs, total: Date.now() - tAll },
  };
}

function toBase64(bytes: Uint8Array): string {
  // chunked to avoid call-stack limits on large frames; btoa exists in
  // browsers, Workers and modern Node (the only runtimes we target here).
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}
