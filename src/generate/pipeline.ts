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
import { GEN_W, GEN_H, regionsForVariant, repackTemplate, bankTransport, type LayoutVariant } from "./layouts";
import { combinedBlueprint, type BlueprintLayout } from "./blueprint";

// ---- single-pass paint prompt — ported from /tmp/prompt_egg_v3.txt (the winning
// prototype prompt), generalized over the chosen material + brief. The blueprint
// is COMBINED (device body + bottom sprite strip) so ONE paint produces both the
// device (body grown around fixed sockets) and the bare control parts. CRITICAL
// rules carried over: sockets are FIXED anchors (never move/resize/add/remove);
// REMOVE the magenta rings in output; the bottom strip = BARE finished controls
// (round buttons with icons, knob with notch, SEEK = a SMALL thumb NOT a pill)
// on a FLAT PURE-WHITE strip background with ZERO text/labels (the model kept
// drawing caption text + non-white strip backgrounds — forbidden forcefully now);
// and — so the masker isn't confused — "no shadows/AO/reflections, pure white
// background, clean hard edges". {brief} and {material} are filled per request.
export const PAINT_PROMPT =
  "You are restyling a fixed UI blueprint into a finished product render. The image has TWO regions: " +
  "a DEVICE BODY (top) and a STRIP OF CONTROL PARTS (bottom). Repaint everything as a device shaped " +
  "like {brief}, in this material: {material}\n\n" +
  "CRITICAL — the blueprint geometry is LOCKED. Output the SAME dimensions and SAME positions for every element.\n\n" +
  "TOP DEVICE BODY:\n" +
  "- The faint gray rounded shape is the BODY — restyle ONLY it into the material above; grow detailing " +
  "only into the gray body and the white margins. Do NOT change the body outline, position, or size.\n" +
  "- Each dark shape ringed in bright PINK/MAGENTA is a FIXED SOCKET. KEEP every socket at its EXACT " +
  "position, size and shape. NEVER move, resize, rotate, duplicate, remove, or add a socket.\n" +
  "- The big dark rounded rectangles / bars are recessed SCREENS — paint them as dark glassy inset displays, in place.\n" +
  "- The round dark wells are EMPTY recessed sockets — paint them as dark empty holes, in place (do NOT put buttons in them).\n" +
  "- SHARED HOUSING: where several sockets sit DIRECTLY ADJACENT in a row (a button bank), paint them as ONE inset, recessed HOUSING / bezel of the body material that CONTAINS those wells — a single sunken panel with thin raised SEAMS between the individual empty wells (like a car-console climate keypad or a Walkman transport cluster), NOT separate free-floating holes. The wells themselves stay empty and dark; only the surrounding bezel/seams are added.\n" +
  "- REMOVE the bright pink/magenta rings in your output (guides only); the dark socket they ringed stays exactly where it was.\n" +
  "- ABSOLUTELY DO NOT invent or paint ANY extra control — no button, knob, dial, switch, toggle, slider, key, jack, port, " +
  "vent/grille that reads as a button, badge, or label — ANYWHERE on the body except the defined sockets above. The body " +
  "BETWEEN and AROUND the sockets must be SMOOTH, continuous material only (seams, sheen, bevels are fine; anything that " +
  "looks pressable/turnable is NOT). Only the sockets (top) and the strip parts (bottom) may look interactive.\n" +
  "- Go easy on printed iconography on the body itself: a maker's mark or a small model name is fine, but avoid " +
  "scattering control symbols (play triangles, power circles, arrows, EQ glyphs, ▶ ⏸ ⏹ ⏮ ⏭ ⏏) across the bare " +
  "material — those symbols belong on the actual control parts in the strip, not printed on the empty skin.\n\n" +
  "BOTTOM CONTROL-PARTS STRIP — a row of LOOSE, ISOLATED physical control PARTS photographed on a seamless " +
  "FLAT PURE-WHITE sweep:\n" +
  "- This strip is NOT a diagram, NOT a UI mockup, NOT a labeled parts catalog, NOT an instruction sheet. It is simply " +
  "individual finished hardware parts laid out on an empty white surface, like loose components on a clean studio table.\n" +
  "- The bottom band has evenly-spaced slots left-to-right, EACH outlined by a bright PINK/MAGENTA KEYLINE. Paint ONE finished, " +
  "glossy control PART filling each magenta slot, in the SAME material as the body, in this EXACT left-to-right order. There is " +
  "exactly ONE part per magenta slot: paint a part in EVERY slot, fill ALL of them, do NOT leave a slot empty, do NOT merge two " +
  "parts into one slot, and do NOT omit or add any. Count the magenta slots and match them one-to-one with the list below:\n" +
  "    {strip}\n" +
  "- REMOVE the magenta keyline outlines in your output (guides ONLY, exactly like the device sockets' rings) — only the finished " +
  "part remains, on flat pure-white; the magenta must be completely gone.\n" +
  "- THE STRIP BACKGROUND MUST BE A SINGLE FLAT PURE WHITE (#FFFFFF), perfectly uniform across the whole band: NO gradient, " +
  "NO texture, NO vignette, NO panel, NO tray, NO surface markings, NO grid, NO shading — just flat pure white #FFFFFF behind " +
  "and between every part. This is REQUIRED so each control can be cleanly isolated and cut out. (The device body above keeps " +
  "its material; ONLY this strip background must be flat pure white.)\n" +
  "- Each control is a BARE part: NO square plate, card, tile, rounded-rectangle or box behind it, NO frame, NO shadow. " +
  "Center each in its slot, evenly spaced, not touching neighbours, with clean empty pure-white space around it.\n" +
  "- ABSOLUTELY NO TEXT ANYWHERE in this strip. NO text, NO letters, NO words, NO captions, NO labels, NO names, NO numbers, " +
  "NO legend, NO key, NO title, NO annotation — under, over, beside, or on ANY part, and none in the white space between parts. " +
  "Do NOT write 'PLAY', 'STOP', 'REWIND', 'POWER', 'OFF', 'ON', 'VOLUME', or any other word, abbreviation, or number next to a " +
  "control. This is a row of bare physical parts, not a labeled catalog — there is ZERO typography in the strip.\n" +
  "- Each control's ONLY marking is its own icon EMBOSSED ON ITS FACE (e.g. the play triangle is molded ON the button face) — " +
  "do NOT draw any separate floating icon, glyph, arrow, symbol, or text ABOVE, BELOW or beside the control. Nothing floats " +
  "next to a part; the surrounding white is completely empty.\n\n" +
  "RENDER: flat front-on product render on a PERFECTLY CLEAN PURE-WHITE background. CRITICAL: NO shadows of any kind " +
  "anywhere — no drop shadow, no cast shadow, no contact shadow, no ambient occlusion onto the white. Every element " +
  "must have clean hard edges against pure white so it can be perfectly masked. No reflections on the ground. " +
  "Reminder: the bottom control-parts strip carries NO text, NO labels, NO captions, NO numbers of any kind — only the " +
  "bare parts on flat pure white.";

// Donor registry. These descriptions are NO LONGER forced onto the paint pass — the
// paint material is always prompt-driven (handler.ts → deriveMaterial / raw prompt).
// This dict survives only to define the donor PALETTE/SPRITE ids ([data-skin]) via its
// keys (DONOR_STYLES / DonorStyle); the value strings are reference descriptions only.
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
// label  → the fal edit endpoint + an est per-skin cost (SINGLE paint pass; the
// envelope pass was removed — costPerSkin is now an upper-bound ceiling estimate).
export type ModelId =
  | "fal-ai/gemini-3-pro-image-preview/edit"
  | "fal-ai/gemini-3.1-flash-image-preview/edit"
  | "openai/gpt-image-2/edit";

export interface ModelInfo {
  id: ModelId;
  label: string;
  costPerSkin: number;   // est $ upper bound for the single paint pass
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
  // handler drives the paint material from the raw prompt text instead.
  openaiKey?: string;
  // SVG string → PNG bytes (resvg-wasm in CF, resvg-js in Node)
  rasterize: (svg: string) => Promise<Uint8Array>;
  // optional: persist one artifact for skin <id>, return its public URL. frame/paint
  // are binary PNG (Uint8Array); template/meta are JSON strings. When omitted, the
  // image is returned inline as a data: URL (demo — no R2 needed) and template/meta
  // are simply not persisted. Wiring R2 (env.SKINS) makes EVERY generated skin a
  // shared cloud artifact under skins/<id>/ (frame.png OR paint.png + template.json +
  // meta.json), reconstructable by id via /api/skin/<id>.
  store?: (id: string, kind: "frame" | "paint" | "template" | "meta" | "layout", data: Uint8Array | string) => Promise<string>;
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
  materialPrompt?: string; // prompt-driven paint material (Director-derived, or raw prompt); the {material} token. Falls back to brief.
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
  frameUrl: string;       // public URL or data: URL of the CUT device frame
  layout: BlueprintLayout; // devFrac + per-control rects + sprite-strip cells (browser cuts by this)
  sprites?: boolean;       // true once per-skin control sprites exist at skins/<id>/sprites/<bind>.png
  needsCutout?: boolean;  // true when the cutout was deferred to the browser (single-pass: always)
  paintUrl?: string;      // raw combined paint PNG to cut client-side — present when needsCutout
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
// The combined blueprint (device + strip) is 9:16; the paint MUST be requested at
// that SAME aspect or the model reshapes it and the normalized strip cells + device
// sockets land in the wrong place. gpt-image-2 takes an explicit image_size; the
// gemini endpoints take aspect_ratio. Keep both at 9:16 (1024×1820).
function falSubmit(falKey: string, model: ModelId, imageUrls: string[], prompt: string) {
  const body: Record<string, unknown> =
    model === "openai/gpt-image-2/edit"
      ? { prompt, image_urls: imageUrls, image_size: { width: 1024, height: 1820 }, quality: "high", output_format: "png" }
      : { prompt, image_urls: imageUrls, resolution: "2K", aspect_ratio: "9:16", output_format: "png" };
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
// width/height from a PNG's IHDR (no full decode; works in Worker + Node).
function pngDims(b: Uint8Array): { w: number; h: number } | null {
  if (b.length < 24 || b[0] !== 0x89 || b[1] !== 0x50) return null;
  const u32 = (o: number) => ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0;
  const w = u32(16), h = u32(20);
  return w > 0 && h > 0 ? { w, h } : null;
}

// ---- BiRefNet background removal (server-side; FAL_KEY never leaves the server) --
// Upload device-region PNG bytes → fal-ai/birefnet/v2 → transparent PNG bytes.
// Used by /api/cutout (functions/api/cutout.ts + the dev plugin). BiRefNet input is
// {image_url}, output is result.image.url. Reuses the same fal queue helpers as the
// paint pass so there is ONE fal-REST implementation.
export const BIREFNET_MODEL = "fal-ai/birefnet/v2";
// model variants for the "tune on fail" retry: Light is fast/default; Heavy is slower but
// segments low-contrast (e.g. white-on-white controls) better; Matting gives finer edges.
export type BiRefNetModel = "General Use (Light 2K)" | "General Use (Heavy)" | "Matting";
export async function removeBackground(
  falKey: string, png: Uint8Array, model: BiRefNetModel = "General Use (Heavy)",
): Promise<Uint8Array> {
  const imageUrl = await falUpload(falKey, png);
  const job = await falPost(falKey, `https://queue.fal.run/${BIREFNET_MODEL}`, {
    image_url: imageUrl,
    model,
    operating_resolution: "2048x2048",
    output_format: "png",
  });
  const t0 = Date.now();
  for (;;) {
    const s = (await falGet(falKey, job.status_url)).status;
    if (s === "COMPLETED") break;
    if (s === "FAILED" || s === "ERROR") throw new Error("birefnet job failed");
    if (Date.now() - t0 > 5 * 60_000) throw new Error("birefnet job timeout");
    await new Promise((res) => setTimeout(res, 2000));
  }
  const out = await falGet(falKey, job.response_url);
  const url = out?.image?.url;
  if (!url) throw new Error("birefnet returned no image url");
  return fetchPng(url);
}

// ---- SAM-3.1 per-control segmentation (server-side; FAL_KEY never leaves) -------
// Box-prompt fal-ai/sam-3-1 with each control's box (pixel coords in the uploaded
// image) → precise per-pixel masks. Mirrors generation/sam_snap.py. Returns, aligned
// to the input box order, each control's mask PNG URL + normalized box + score. The
// browser applies each mask as alpha and tight-crops → true-shape transparent sprite
// (no imposed ellipse, no halo, no neighbour bleed). One call for all boxes.
export const SAM_MODEL = "fal-ai/sam-3-1/image";
export interface SamBoxPx { x_min: number; y_min: number; x_max: number; y_max: number }
export interface SamMask { maskUrl: string | null; box: [number, number, number, number] | null; score: number }
const urlOf = (m: unknown): string | null =>
  typeof m === "string" ? m : (m && typeof m === "object" && "url" in m ? String((m as { url: unknown }).url) : null);

// ONE SAM call per control (single box). Multi-box-in-one-call mis-aligns masks to
// boxes (return_multiple_masks yields ambiguous/duplicated masks); per-control single
// box is exact. The image is uploaded ONCE and reused across all box calls (parallel).
async function segmentOne(falKey: string, imageUrl: string, b: SamBoxPx): Promise<SamMask> {
  const box = { x_min: Math.round(b.x_min), y_min: Math.round(b.y_min), x_max: Math.round(b.x_max), y_max: Math.round(b.y_max) };
  const job = await falPost(falKey, `https://queue.fal.run/${SAM_MODEL}`, {
    image_url: imageUrl, box_prompts: [box],
    include_boxes: true, include_scores: true, apply_mask: false, output_format: "png",
  });
  const t0 = Date.now();
  for (;;) {
    const s = (await falGet(falKey, job.status_url)).status;
    if (s === "COMPLETED") break;
    if (s === "FAILED" || s === "ERROR") throw new Error("sam job failed");
    if (Date.now() - t0 > 90_000) throw new Error("sam job timeout");
    await new Promise((res) => setTimeout(res, 1200));
  }
  const out = await falGet(falKey, job.response_url);
  const masks: unknown[] = Array.isArray(out?.masks) ? out.masks : [];
  const meta: Array<{ box?: number[]; score?: number }> = Array.isArray(out?.metadata) ? out.metadata : [];
  const m0 = meta[0];
  return {
    maskUrl: urlOf(masks[0]),
    box: (m0?.box && m0.box.length === 4 ? [m0.box[0], m0.box[1], m0.box[2], m0.box[3]] : null),
    score: m0?.score ?? (Array.isArray(out?.scores) ? out.scores[0] : 0) ?? 0,
  };
}
export async function segmentControls(
  falKey: string, png: Uint8Array, boxes: SamBoxPx[],
): Promise<SamMask[]> {
  if (!boxes.length) return [];
  const imageUrl = await falUpload(falKey, png);
  return Promise.all(boxes.map((b) => segmentOne(falKey, imageUrl, b).catch(() => ({ maskUrl: null, box: null, score: 0 }))));
}

export async function generateSkin(deps: RuntimeDeps, input: GenerateInput): Promise<GenerateResult> {
  const log = deps.log ?? (() => {});
  const model = input.model ?? DEFAULT_MODEL;
  // custom layout from the wizard wins; otherwise the constant variant preset.
  // REPACK the template before the painter: sane per-kind sizes + move-based
  // de-overlap (no slivers). A template with overlapping/sliver interactables must
  // NEVER reach the painter — this is the root of alignment quality.
  const regs: Region[] = bankTransport(repackTemplate(input.regions?.length ? input.regions : regionsForVariant(input.variant)));
  const template: Template = { id: input.id, name: "wild-sculpt", canvas: { w: GEN_W, h: GEN_H }, regions: regs };
  const tAll = Date.now();

  // 1. COMBINED blueprint PNG — device body (faint envelope + magenta-ringed
  //    sockets) + a bottom sprite strip of labeled control cells. ONE image.
  const { svg, layout, width: bpW, height: bpH, stripDesc } = combinedBlueprint(regs);
  // CHECK (pre-paint): the blueprint/template MUST be a model-reproducible aspect so
  // the paint returns near 1:1 — otherwise the normalized strip cells + device sockets
  // map to the wrong place on a reshaped output (mis-cut sprites). It's built to 9:16;
  // assert that BEFORE spending a paint call so a sizing regression fails loud, here.
  const bpAspect = bpW / bpH;
  if (Math.abs(bpAspect - 9 / 16) > 0.02) {
    throw new Error(`blueprint aspect ${bpW}x${bpH} (${bpAspect.toFixed(3)}) is not ~9:16 (0.5625) — the paint model won't reproduce it 1:1; fix STRIP_FRAC so device+strip = 9:16`);
  }
  const blueprintPng = await deps.rasterize(svg);

  // 2. SINGLE PAINT PASS — restyle the whole combined blueprint into the material
  //    in ONE shot (NO separate envelope pass). The blueprint IS the layout
  //    authority: the model grows the body around the fixed sockets and paints the
  //    bare control parts in the strip. Reference-style images ride along.
  const tPaint = Date.now();
  const blueprintUrl = await falUpload(deps.falKey, blueprintPng);
  let prompt = PAINT_PROMPT
    .replace(/\{brief\}/g, input.brief)
    // material is PROMPT-DRIVEN: the Director's derived materialPrompt (or, with no
    // OpenAI key, the raw prompt text). Fall back to the brief itself — NEVER a canned
    // donor preset — so a missing material can't silently force a winamp/biomech look.
    .replace("{material}", input.materialPrompt || input.brief)
    .replace("{strip}", stripDesc);
  const refs = input.refImageUrls ?? [];
  if (refs.length) {
    prompt += " Borrow the palette, materials and surface-detail vocabulary of the REFERENCE " +
      "image(s) provided, but DO NOT copy their layout or shape — the silhouette, sockets and cells come only from the blueprint.";
  }
  const paintJob = await falSubmit(deps.falKey, model, [blueprintUrl, ...refs], prompt);
  const paintUrl = await falPoll(deps.falKey, paintJob, 9 * 60_000);
  const paintPng = await fetchPng(paintUrl);
  const paintMs = Date.now() - tPaint;
  log(`[${input.id}] paint (${modelLabel(model)}) ${(paintMs / 1000) | 0}s`);

  // ASPECT CHECK: the blueprint is 9:16; if the model reshaped the output, the
  // normalized strip cells + device sockets map to the wrong place (mis-cut sprites).
  // Parse the PNG IHDR for dims (no full decode) and warn loudly on a mismatch.
  const dims = pngDims(paintPng);
  if (dims && Math.abs(dims.w / dims.h - 9 / 16) > 0.03) {
    log(`[${input.id}] ⚠️ ASPECT MISMATCH: paint ${dims.w}x${dims.h} (${(dims.w / dims.h).toFixed(3)}) ≠ requested 9:16 (0.5625) — sprite cells will be off.`);
  }

  // 3. CUTOUT is always deferred to the browser. The combined paint must be
  //    background-removed (device region) AND each control sprite cut from its
  //    cell — both are pure-JS CPU that trips the CF Function ceiling (CF 1102),
  //    so the Worker persists the RAW combined paint and the browser finishes:
  //    crops the device region (top devFrac), POSTs it to /api/cutout (BiRefNet,
  //    server-side key) for a transparent device frame, cuts each control sprite
  //    by cell geometry, and uploads frame.png + sprites/<bind>.png back to R2.
  //
  //    deps.cutout (server-side, Node dev with no CPU ceiling) is still honored
  //    for the device background-removal, but the per-control sprite cut + the
  //    sprite uploads happen in the browser regardless (they need the cell layout
  //    + the finalize sprite endpoint), so we always return needsCutout + layout.
  const meta: SkinMeta = {
    prompt: input.brief, model, style: input.style, variant: input.variant,
    createdAt: new Date().toISOString(),
  };
  const storeSidecars = async () => {
    if (!deps.store) return;
    try {
      await deps.store!(input.id, "template", JSON.stringify(template));
      await deps.store!(input.id, "meta", JSON.stringify(meta));
      await deps.store!(input.id, "layout", JSON.stringify(layout));
    } catch (e) { log(`[${input.id}] sidecar store failed: ${e instanceof Error ? e.message : e}`); }
  };

  let frameUrl: string;
  let paintOut: string | undefined;   // raw combined paint URL returned to the client to cut

  if (deps.store) {
    // persist the RAW combined paint; the browser cuts the device + sprites and
    // uploads frame.png (+ sprites/<bind>.png) back via /api/finalize/<id>.
    paintOut = await deps.store(input.id, "paint", paintPng);
    // frame.png is the sibling key the browser will upload to (same skins/<id>/
    // prefix). Derive it from the paint URL so it tracks ASSETS_BASE_URL.
    frameUrl = paintOut.replace(/paint\.png(\?.*)?$/, "frame.png");
    await storeSidecars();
  } else {
    // demo (no R2): hand the raw combined paint to the client inline; it cuts
    // in-memory and there is no durable frame URL to point at.
    paintOut = `data:image/png;base64,${toBase64(paintPng)}`;
    frameUrl = paintOut;
  }

  return {
    id: input.id, style: input.style, variant: input.variant, model, template, frameUrl, layout,
    needsCutout: true, paintUrl: paintOut,
    timingMs: { envelope: 0, paint: paintMs, total: Date.now() - tAll },
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
