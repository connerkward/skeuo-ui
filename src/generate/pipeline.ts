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
//   5. alpha = the constant drawn region mask (NO BiRefNet)
//   6. composite paint × alpha → frame.png; emit template.json
//
// The caller injects `rasterize` (SVG→PNG bytes) and `composite`
// (paint × alpha → RGBA PNG bytes) so the SAME pipeline runs under
// resvg-wasm in a CF Worker or resvg-js + sharp in Node.
// ============================================================
import type { Region, Template } from "../template/schema";
import { GEN_W, GEN_H, regionsForVariant, type LayoutVariant } from "./layouts";
import { wellsOnlySvg, regionMaskSvg } from "./blueprint";

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

const ENDPOINT = "fal-ai/gemini-3-pro-image-preview/edit";

export interface RuntimeDeps {
  falKey: string;
  // SVG string → PNG bytes (resvg-wasm in CF, resvg-js in Node)
  rasterize: (svg: string) => Promise<Uint8Array>;
  // paint PNG × alpha PNG (8-bit L) → RGBA PNG bytes
  composite: (paintPng: Uint8Array, alphaPng: Uint8Array) => Promise<Uint8Array>;
  // optional: persist a frame for skin <id>, return its public URL. If omitted,
  // the caller gets a data: URL (v1 default — no R2 needed to demo).
  store?: (id: string, kind: "frame", png: Uint8Array) => Promise<string>;
  log?: (msg: string) => void;
}

export interface GenerateInput {
  id: string;
  variant: LayoutVariant;
  style: DonorStyle;
  brief: string;          // the silhouette brief, e.g. "a fanged anglerfish jaw"
  refImageUrls?: string[]; // optional reference-style images (palette/material steer)
}

export interface GenerateResult {
  id: string;
  style: DonorStyle;
  variant: LayoutVariant;
  template: Template;
  frameUrl: string;       // public URL or data: URL
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
// submit one gemini-3-pro edit job (blueprint first = layout authority)
function falSubmit(falKey: string, imageUrls: string[], prompt: string) {
  return falPost(falKey, `https://queue.fal.run/${ENDPOINT}`, {
    prompt, image_urls: imageUrls, resolution: "2K", aspect_ratio: "2:3", output_format: "png",
  });
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
  const regs: Region[] = regionsForVariant(input.variant);
  const template: Template = { id: input.id, name: "wild-sculpt", canvas: { w: GEN_W, h: GEN_H }, regions: regs };
  const tAll = Date.now();

  // 2. wells-only blueprint PNG (envelope input)
  const wellsPng = await deps.rasterize(wellsOnlySvg(regs));

  // 3. ENVELOPE pass — grow a flat silhouette around the wells
  const tEnv = Date.now();
  const wellsUrl = await falUpload(deps.falKey, wellsPng);
  const envJob = await falSubmit(deps.falKey, [wellsUrl], ENVELOPE_PROMPT.replace("{brief}", input.brief));
  const envUrl = await falPoll(deps.falKey, envJob, 7 * 60_000);
  const envPng = await fetchPng(envUrl);
  const envMs = Date.now() - tEnv;
  log(`[${input.id}] envelope ${(envMs / 1000) | 0}s`);

  // 4. PAINT pass — restyle the ENVELOPE (silhouette + wells) into the material.
  //    The envelope already carries the wells (pixel-identical) plus the body
  //    silhouette, so it is the layout authority for the paint, exactly like the
  //    Python draw_blueprint() output. Reference-style images ride along.
  const tPaint = Date.now();
  const envUploadUrl = await falUpload(deps.falKey, envPng);
  let prompt = STYLE_PROMPT + (MATERIAL[input.style] ?? MATERIAL.winamp);
  const refs = input.refImageUrls ?? [];
  if (refs.length) {
    prompt += " Borrow the palette, materials and surface-detail vocabulary of the REFERENCE " +
      "image(s) provided, but DO NOT copy their layout or shape — the silhouette and wells come only from the blueprint.";
  }
  const paintJob = await falSubmit(deps.falKey, [envUploadUrl, ...refs], prompt);
  const paintUrl = await falPoll(deps.falKey, paintJob, 9 * 60_000);
  const paintPng = await fetchPng(paintUrl);
  const paintMs = Date.now() - tPaint;
  log(`[${input.id}] paint ${(paintMs / 1000) | 0}s`);

  // 5. alpha = constant region mask (no BiRefNet); 6. composite
  const alphaPng = await deps.rasterize(regionMaskSvg(regs));
  const framePng = await deps.composite(paintPng, alphaPng);

  // 6. store or inline
  const frameUrl = deps.store
    ? await deps.store(input.id, "frame", framePng)
    : `data:image/png;base64,${toBase64(framePng)}`;

  return {
    id: input.id, style: input.style, variant: input.variant, template, frameUrl,
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
