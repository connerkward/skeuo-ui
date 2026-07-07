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
import { GEN_W, GEN_H, regionsForVariant, repackTemplate, bakeButtons, type LayoutVariant } from "./layouts";
import { combinedBlueprint, type BlueprintLayout, type RGB } from "./blueprint";

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
  "CRITICAL — control POSITIONS are LOCKED: keep every socket/button/screen at its marked position and keep the same overall dimensions. But the SHAPES are FREE — sculpt the body outline and each control's silhouette WILD and organic (see below); do NOT regularize them into boxes or circles.\n\n" +
  "TOP DEVICE BODY:\n" +
  "- The faint gray shape marks the ROUGH BODY FOOTPRINT — restyle it into the material above and SCULPT its outline into a WILD, organic, era-correct silhouette (a blobby teardrop, a faceted pod, an amoeba, a curved shield, a melted-metal form — like a Winamp / WMP-XP / Sonique skin), NOT a plain rounded rectangle. Keep roughly the same overall footprint and KEEP every control at its marked position, but the body OUTLINE should be characterful and organic, never boxy.\n" +
  "- The body MUST be a SINGLE SOLID CONTINUOUS silhouette with NO fully-enclosed see-through holes, interior cut-outs, open loops, ring/donut gaps, or handle-holes punched THROUGH the body — the housing is one unbroken solid mass. ANY negative space or concavity MUST open to the OUTER edge of the silhouette: an inward bite from the outside edge is fine, but a hole or gap FULLY SURROUNDED by body is ABSOLUTELY FORBIDDEN.\n" +
  "- BACKDROP (top device region): the area AROUND the body is a flat {BG} backdrop. Paint it as a CLEAN, " +
  "FLAT, perfectly UNIFORM {BG} — it is a separate backdrop that gets keyed out, so it must NOT tint, reflect, " +
  "bleed or spill onto the device; the device keeps its OWN material colour and neutral studio lighting, with a " +
  "crisp edge against the {BG}. (BOTH the device backdrop AND the bottom control-strip background are this SAME {BG} — one uniform neutral behind everything, so both cut out cleanly.)\n" +
  "- Each control is marked by a bright GREEN CROSSHAIR at its exact centre, wrapped in a soft " +
  "green disc showing ROUGHLY how big it is (the SHAPE is yours to sculpt). Paint ONE socket per green " +
  "crosshair, centred on it. NEVER duplicate, remove, or add a socket. Read each mark's diffuseness: a " +
  "TIGHT bright crosshair + small disc = the position is FIRM (place it exactly there); a FADED crosshair " +
  "+ LARGE soft blurry disc = the position is approximate — nudge the control anywhere within that soft region.\n" +
  "- The big dark rounded rectangles / bars are recessed SCREENS — paint them as dark glassy inset displays, in place. Leave them BLANK dark glass: NO text, NO numbers, NO track names, NO fake UI, NO waveform, NO menu, NO icons on the screen — the screen content is added live afterwards.\n" +
  "- A GREEN crosshair with NO colour is an EMPTY recessed socket — paint a dark empty hole centred on it (do NOT put a button there).\n" +
  "- A COLOURED crosshair+disc marks a REAL BUTTON (not an empty well). At EACH coloured mark paint ONE finished, tactile, pressable button MOLDED SEAMLESSLY INTO the sculpted housing here, in the body material, with the correct icon embossed on its face. EACH button's COLOUR tells you WHICH control it is and WHAT icon to emboss on its face — follow this colour→control→icon map EXACTLY: {bakeLegend}. Each button gets a WILD, era-correct, ORGANIC silhouette — a curved WEDGE or arc-segment (jog dial), a KIDNEY or half-oval, a TRAPEZOID or faceted polygon, a LOZENGE or teardrop lobe — like a real early-2000s Winamp / Windows-Media-Player / Sonique skin where the controls are facets of the housing. The soft disc hints only at SIZE, never shape.\n" +
  "- The buttons do NOT need to be uniform: they MAY be different shapes and sizes, sit at different angles, and follow the organic contour of the body — do NOT force them into an even straight row, a uniform grid, or identical evenly-spaced keys. Where blue marks sit adjacent you MAY flow them into one sculpted housing facet with thin raised seams, but the arrangement stays organic and characterful, not a regimented row. Each button is molded into the body (it stays in the render), not a loose part on top.\n" +
  "- BUTTON COUNT IS EXACT — CRITICAL: there are EXACTLY {NBUTTONS} buttons on the ENTIRE device: the {NBUTTONS} colour-marked positions and ABSOLUTELY NO OTHERS. Do NOT hallucinate or add ANY extra button, a second/conventional transport row, another play/pause/skip cluster, jog-dial keys, or any media-control ANYWHERE else on the body — NOT EVEN if the device 'looks like it should have' a normal transport row. It does NOT. Media players you have seen have a conventional button row; THIS device's buttons are ONLY the {NBUTTONS} marked ones, wherever they sit. Count the coloured button marks, paint exactly that many buttons, and paint NONE beyond them. Every non-marked area of the body is smooth material with NO buttons.\n" +
  "- (GREEN crosshairs remain EMPTY dark holes as described above — only the COLOUR-marked regions get real painted controls.)\n" +
  "- REMOVE every crosshair and soft disc (green AND coloured) from your output completely (guides only, not part of the device); the dark socket / painted button they marked stays exactly where it was.\n" +
  "- ABSOLUTELY DO NOT invent or paint ANY extra control — no button, knob, dial, switch, toggle, slider, key, jack, port, " +
  "vent/grille that reads as a button, badge, or label — ANYWHERE on the body except the defined sockets above. The body " +
  "BETWEEN and AROUND the sockets must be SMOOTH, continuous material only (seams, sheen, bevels are fine; anything that " +
  "looks pressable/turnable is NOT). Only the sockets (top) and the strip parts (bottom) may look interactive.\n" +
  "- KEEP A CLEAR MARGIN of plain, uninterrupted material immediately around EVERY socket and control cluster — a smooth " +
  "buffer zone at least one socket-width wide. Do NOT place ANY circle, ring, pill, disc, rounded-rect, dark recess, hole, " +
  "stud, rivet, boss, dot, embossed medallion, grille of dots, or ANY shape with a control-like silhouette NEAR a socket or " +
  "control. Such decoys are indistinguishable from real controls to an automatic shape detector and corrupt it: the region " +
  "around each socket must be featureless material so every real control stays isolated and unambiguous. Push all decorative " +
  "detail FAR from the controls, and never let decoration form a button/knob/well-like shape anywhere on the body.\n" +
  "- Go easy on printed iconography on the body itself: a maker's mark or a small model name is fine, but avoid " +
  "scattering control symbols (play triangles, power circles, arrows, EQ glyphs, ▶ ⏸ ⏹ ⏮ ⏭ ⏏) across the bare " +
  "material — those symbols belong on the actual control parts in the strip, not printed on the empty skin.\n\n" +
  "BOTTOM CONTROL-PARTS STRIP — a row of LOOSE, ISOLATED physical control PARTS photographed on a seamless " +
  "flat {BG} sweep (the SAME neutral backdrop as the device region above):\n" +
  "- This strip is NOT a diagram, NOT a UI mockup, NOT a labeled parts catalog, NOT an instruction sheet. It is simply " +
  "individual finished hardware parts laid out on an empty white surface, like loose components on a clean studio table.\n" +
  "- The bottom band has evenly-spaced slots left-to-right, EACH marked by a bright GREEN CROSSHAIR + soft disc. The crosshair marks WHERE a part " +
  "goes and the disc ROUGHLY HOW BIG — it does NOT dictate the part's SHAPE. Do NOT fill a box: give each part its own sculpted, era-correct " +
  "SILHOUETTE (often NON-rectangular — a half-oval, D-shape, wedge / arc-segment, lozenge, curved trapezoid — matching real hardware of this device), " +
  "centered on its crosshair; it may be smaller than the soft disc. Paint ONE finished, " +
  "glossy control PART per green slot, in the SAME material as the body, in this EXACT left-to-right order. There is " +
  "exactly ONE part per green slot: paint a part in EVERY slot, fill ALL of them, do NOT leave a slot empty, do NOT merge two " +
  "parts into one slot, and do NOT omit or add any. Count the green slots and match them one-to-one with the list below:\n" +
  "    {strip}\n" +
  "- REMOVE the green crosshairs + discs in your output (guides ONLY, exactly like the device sockets' marks) — only the finished " +
  "part remains, on the flat {BG} backdrop; the green must be completely gone.\n" +
  "- THE STRIP BACKGROUND MUST BE A SINGLE FLAT {BG}, perfectly uniform across the whole band: NO gradient, " +
  "NO texture, NO vignette, NO panel, NO tray, NO surface markings, NO grid, NO shading — just that flat uniform {BG} behind " +
  "and between every part. This is REQUIRED so each control can be cleanly isolated and cut out. (The device body above keeps " +
  "its material; the strip background is the SAME neutral {BG} as the device backdrop.)\n" +
  "- Each control is a BARE part: NO square plate, card, tile, rounded-rectangle or box behind it, NO frame, NO shadow. " +
  "Center each in its slot, evenly spaced, not touching neighbours, with clean empty {BG} space around it.\n" +
  "- ABSOLUTELY NO TEXT ANYWHERE in this strip. NO text, NO letters, NO words, NO captions, NO labels, NO names, NO numbers, " +
  "NO legend, NO key, NO title, NO annotation — under, over, beside, or on ANY part, and none in the white space between parts. " +
  "Do NOT write 'PLAY', 'STOP', 'REWIND', 'POWER', 'OFF', 'ON', 'VOLUME', or any other word, abbreviation, or number next to a " +
  "control. This is a row of bare physical parts, not a labeled catalog — there is ZERO typography in the strip.\n" +
  "- Each control's ONLY marking is its own icon EMBOSSED ON ITS FACE (e.g. the play triangle is molded ON the button face) — " +
  "do NOT draw any separate floating icon, glyph, arrow, symbol, or text ABOVE, BELOW or beside the control. Nothing floats " +
  "next to a part; the surrounding white is completely empty.\n\n" +
  "RENDER: flat front-on product render. The top device region AND the bottom control strip both sit on the SAME " +
  "flat {BG} backdrop — perfectly clean and uniform. CRITICAL: NO shadows of any kind anywhere — " +
  "no drop shadow, no cast shadow, no contact shadow, no ambient occlusion onto the backdrop. Every element " +
  "must have clean hard edges against its backdrop so it can be perfectly masked. No reflections on the ground. " +
  "Reminder: the bottom control-parts strip carries NO text, NO labels, NO captions, NO numbers of any kind — only the " +
  "bare parts on the flat {BG} backdrop.";
// ---- CUTOUT KEY COLOUR ----------------------------------------------------
// The device is painted on a flat CONTRASTING backdrop (a hue OUTSIDE its own
// palette) so the cutout keys it out unambiguously — fixing the white-key bugs
// (near-white screens lost; backdrop bleeding into thin gaps kept). The key colour
// is chosen DETERMINISTICALLY from the material text (no extra LLM cost). Translucent
// & iridescent finishes route to WHITE: their body legitimately carries every hue
// (light through / shifting sheen), so a coloured-key despill would desaturate the
// real material — see cutoutColorAware. Validated 2026-06-23 (see TODO.md).
export interface KeyChoice { key: RGB; css: string; phrase: string }
// NEUTRAL contrasting backdrops (2026-07-01 — replaces the chroma-key scheme). BiRefNet cutout
// is object-based (needs NO chroma to find the device), and a saturated key (magenta/cyan) is
// physically TRANSMITTED into translucent bodies (a see-through skin picked up the backdrop
// hue) and reflected by chrome. A neutral grey/white/black never tints, so we pick one by the
// material's LIGHTNESS for a hard cut edge: light body → dark backdrop, dark body → light
// backdrop, mid/colourful → mid grey. Used for BOTH the device region AND the control strip.
const BG_DARK: KeyChoice  = { key: [18, 18, 20],   css: "rgb(18,18,20)",    phrase: "a flat, uniform near-black charcoal (#121214)" };
const BG_LIGHT: KeyChoice = { key: [242, 242, 244], css: "rgb(242,242,244)", phrase: "a flat, uniform near-white light grey (#F2F2F4)" };
const BG_GREY: KeyChoice  = { key: [128, 128, 130], css: "rgb(128,128,130)", phrase: "a flat, uniform neutral mid-grey (#808082)" };
// LIGHT bodies (need a dark backdrop) vs DARK bodies (need a light backdrop). Everything else
// (colourful, translucent, unknown) takes mid-grey, which contrasts in both directions.
const LIGHT_MAT = /white|pearl|pearlescent|cream|ivory|chrome|silver|steel|alumini?um|platinum|pastel|\blight\b|pale|bone|milk|snow|mirror|glossy silver/gi;
const DARK_MAT  = /black|charcoal|obsidian|onyx|graphite|gunmetal|\bjet\b|ebony|\bdark\b|midnight|carbon|slate|coal|soot|tar|ink/gi;
// Translucent/iridescent bodies carry many hues; a coloured key would desaturate them, so they
// legitimately keep neutral mid-grey rather than a contrasting backdrop.
const MULTIHUE_MAT = /translucent|iridescent|clear|see-through|see through|\bgel\b|frosted|holographic|pearlescent[- ]shift/i;
export function pickKeyColor(materialText: string): KeyChoice {
  const t = materialText.toLowerCase();
  if (MULTIHUE_MAT.test(t)) return BG_GREY;                      // translucent/iridescent → neutral (carve-out)
  const light = (t.match(LIGHT_MAT) || []).length;
  const dark  = (t.match(DARK_MAT)  || []).length;
  // Ambiguity → pick the contrasting backdrop of the DOMINANT lightness (a silver body with a
  // stray "dark trim" is still light-dominant, so it gets a dark backdrop for a clean matte edge).
  if (light > dark) return BG_DARK;                              // light-dominant body → dark backdrop
  if (dark > light) return BG_LIGHT;                             // dark-dominant body → light backdrop
  return BG_GREY;                                                // balanced / neither / colourful → mid grey
}

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
  store?: (id: string, kind: "frame" | "paint" | "template" | "meta" | "layout" | "rawlayout" | "blueprint", data: Uint8Array | string) => Promise<string>;
  log?: (msg: string) => void;
  // optional: emit a live progress artifact as each pass completes (blueprint →
  // grown body → painted skin), so the loading UI can preview the user's ACTUAL
  // skin forming instead of a placeholder. blueprint is a data: URL; envelope/paint
  // are fal CDN URLs. Best-effort + fire-and-forget — never blocks the pipeline.
  onStage?: (stage: "blueprint" | "envelope" | "paint", url: string) => void;
}

// Small per-skin record persisted alongside the frame + template so a shared link
// can show what made the skin without re-deriving it. Lives at skins/<id>/meta.json.
export interface SkinMeta {
  prompt: string;
  model: ModelId;
  style: string;
  variant: string;
  seed?: number;       // paint seed that produced the shipped image (reproducibility; gemini only)
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
  seed?: number;          // paint base seed; absent ⇒ random-but-recorded (every gen reproducible)
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
  seed?: number;          // the paint seed that produced the shipped image (gemini only)
  keyColor: RGB;          // backdrop the device was painted on — the colour the cutout keys out (white = legacy)
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
// 31-bit non-negative seed (random-but-recorded so every generation is reproducible).
const randomSeed = (): number => Math.floor(Math.random() * 0x7fffffff);

function falSubmit(falKey: string, model: ModelId, imageUrls: string[], prompt: string, seed?: number) {
  const body: Record<string, unknown> =
    model === "openai/gpt-image-2/edit"
      // gpt-image-2 has no seed parameter (rejects unknown keys) → its paints can't be seed-reproduced.
      ? { prompt, image_urls: imageUrls, image_size: { width: 1024, height: 1820 }, quality: "high", output_format: "png" }
      // the gemini edit endpoints accept an optional seed → pass it to fix the paint for reproducibility.
      : { prompt, image_urls: imageUrls, resolution: "2K", aspect_ratio: "9:16", output_format: "png", ...(seed !== undefined ? { seed } : {}) };
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

// ── ALIGNMENT GATE: re-roll the paint until a strong VISION MODEL confirms the
//    transport BUTTON bank is clean + EVENLY spaced. The painter places the baked bank
//    well most of the time but drifts on hard/lumpy bodies; instead of trying to detect
//    + move controls (SAM/heuristics — rejected, they make it worse), we KEEP the
//    blueprint coords and just re-roll the paint a few times, gated by Gemini 2.5 Pro
//    (via fal/OpenRouter — the strongest reachable, far better than my own eyes). Only a
//    paint whose bank Gemini approves ships. Fail-OPEN: any judge error/timeout treats
//    the bank as OK so a flaky model never blocks generation.
const BANK_GATE_ENABLED = false;   // 2026-07-01: buttons are now baked wild + NON-uniform; the
// "even button bank" judge fights that (and would reroll up to 4× against the wild look). Off.
const MAX_BANK_TRIES = 4;
const BANK_MODEL = "google/gemini-2.5-pro";
const BANK_PROMPT =
  "This is the PAINTED hardware of a skeuomorphic music player. Judge ONLY the transport BUTTON cluster " +
  "(play / stop / previous-rewind / next-forward). Are the buttons EVENLY spaced with identical gaps, " +
  "consistently sized (play may be larger), cleanly formed, undistorted, and seated in one tidy row/housing — " +
  "like real manufactured hardware? Any uneven gap, crowded/merged/drifting/tilted/distorted key, or a missing " +
  "button = FAIL. Ignore knobs, screens, colours, the disc, and art style.\n" +
  'Return ONLY strict JSON: {"buttons_perfect":true|false,"issue":"<short>"}';

async function judgeBankOnce(falKey: string, paintUrl: string): Promise<boolean> {
  try {
    const job = await falPost(falKey, "https://queue.fal.run/openrouter/router/vision", {
      model: BANK_MODEL, reasoning: true, temperature: 0, max_tokens: 3500,
      image_urls: [paintUrl], prompt: BANK_PROMPT,
    });
    const t0 = Date.now();
    for (;;) {
      const s = (await falGet(falKey, job.status_url)).status;
      if (s === "COMPLETED") break;
      if (s === "FAILED" || s === "ERROR" || Date.now() - t0 > 120_000) return true; // fail-open
      await new Promise((r) => setTimeout(r, 2000));
    }
    const out: string = (await falGet(falKey, job.response_url)).output ?? "";
    const a = out.indexOf("{"), b = out.lastIndexOf("}");
    if (a < 0) return true;
    return !!JSON.parse(out.slice(a, b + 1)).buttons_perfect;
  } catch { return true; } // fail-open: never block a generation on a judge hiccup
}

// consensus of 3 runs (Gemini's verdict varies — 2/3 let borderline banks slip through);
// perfect only if ALL THREE agree. Stricter → rejects marginal banks, re-rolls instead.
async function bankPerfect(falKey: string, paintUrl: string): Promise<boolean> {
  const v = await Promise.all([
    judgeBankOnce(falKey, paintUrl), judgeBankOnce(falKey, paintUrl), judgeBankOnce(falKey, paintUrl),
  ]);
  return v.every(Boolean);
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

// music/disc-themed prompts that make a spinning-CD screen feel right (cd-visualizer)
const CD_THEME = /\b(cd|disc|jukebox|juke[\s-]?box|boom[\s-]?box|hi[\s-]?fi|stereo|turntable|vinyl|record\s*player|walkman|discman|gramophone|phonograph|dj\b|sound\s*system|ghetto\s*blaster)\b/i;
// Keep the VISUALIZER (the default screen) unless the prompt is CD-thematic (then usually
// a spinning CD) or, rarely, at random — so the CD is a treat, not the norm. Returns a new
// array; the swapped region is cloned so the shared preset isn't mutated. (cd-visualizer)
function maybeCdScreen(regs: Region[], brief: string): Region[] {
  const wantCd = CD_THEME.test(brief) ? Math.random() < 0.7 : Math.random() < 0.08;
  if (!wantCd) return regs;
  let swapped = false;
  return regs.map((r) => {
    if (!swapped && r.dynamicType === "visualizer") { swapped = true; return { ...r, dynamicType: "cd" as const, label: "cd" }; }
    return r;
  });
}

export async function generateSkin(deps: RuntimeDeps, input: GenerateInput): Promise<GenerateResult> {
  const log = deps.log ?? (() => {});
  const model = input.model ?? DEFAULT_MODEL;
  // custom layout from the wizard wins; otherwise the constant variant preset.
  //
  // ALIGNMENT ROOT CAUSE (fixed 2026-06-24): the preset layouts (layoutSimple /
  // layoutRadial / layoutCapsule / layoutMinimal) are ALREADY clean — sane per-kind
  // sizes, GROUPED controls (the 6-band EQ as a tight evenly-spaced row, paired knobs),
  // and intentional dial/arc overlaps the renderer handles. Running repackTemplate over
  // them DESTROYED that baseline: CANON forced every EQ slider-v to h=0.24 (3× the
  // authored 0.085), which triggered resolveOverlaps to scatter the band row across the
  // body + sliver the knobs — so the painted controls (drawn at the MANGLED guide
  // positions) and the live overlays both landed nowhere coherent. This is the
  // "trust the clean procedural baseline, don't run a noisy mangling step on it" lesson
  // (ai-image-coords-rule): repackTemplate is for the DIRECTOR's raw rects (often
  // slivers/oversized/overlapping), NOT for the hand-authored presets.
  //   • custom regions (input.regions, from the wizard/Director) → repack as before.
  //   • preset variant → use AS-IS (it's the load-bearing truth). Then bakeButtons
  //     (bake ALL buttons in place — no snapping; the layout's organic arrangement stands).
  // maybeCdScreen: cd-visualizer feature — swap the first screen → spinning CD for
  // music/disc-themed prompts (mostly) or rarely at random.
  const baseRegs: Region[] = input.regions?.length
    ? repackTemplate(input.regions)            // messy Director input → sane + de-overlap
    : regionsForVariant(input.variant);        // clean authored preset → keep its geometry
  const regs: Region[] = maybeCdScreen(bakeButtons(baseRegs), input.brief);
  const template: Template = { id: input.id, name: "wild-sculpt", canvas: { w: GEN_W, h: GEN_H }, regions: regs };
  const tAll = Date.now();

  // CUTOUT KEY COLOUR — the DEVICE is painted on a contrasting backdrop chosen from
  // the material so the cutout keys it out cleanly (translucent/iridescent → white).
  // Threaded into the combined blueprint's DEVICE-region background, the paint prompt
  // ({BG}), and the client cutout (cleanDeviceFrame). The STRIP stays flat white so
  // connected-component sprite cutting is unambiguous. Material is prompt-driven, so
  // the fallback is the brief itself — never a canned donor preset.
  const matText = input.materialPrompt || input.brief;
  // COLOUR BACKDROP + COLOUR-KEY device cutout. The DEVICE is painted on a contrasting
  // backdrop (a hue far from its palette; translucent/iridescent → white) and cut with a
  // pure-JS COLOUR KEY (cutoutColorAware), NOT BiRefNet. VERIFIED 2026-06-24: BiRefNet
  // eats a coloured body on a colour backdrop (61% of cut holes were body) AND eats a
  // near-white body on white (white-on-white) — the colour key beats both (green frog
  // bbox-fill 93.5%, dark screens kept, zero fringe). The STRIP stays white + BiRefNet+CC.
  const keyc = pickKeyColor(matText);
  log(`[${input.id}] key colour ${keyc.css} (${keyc.phrase})`);

  // 1. COMBINED blueprint PNG — device body (faint envelope + magenta-ringed
  //    sockets) on the KEY-COLOUR backdrop + a bottom sprite strip on WHITE. ONE image.
  const { svg, layout, width: bpW, height: bpH, stripDesc, bakeLegend } = combinedBlueprint(regs, keyc.css);
  // CHECK (pre-paint): the blueprint/template MUST be a model-reproducible aspect so
  // the paint returns near 1:1 — otherwise the normalized strip cells + device sockets
  // map to the wrong place on a reshaped output (mis-cut sprites). It's built to 9:16;
  // assert that BEFORE spending a paint call so a sizing regression fails loud, here.
  const bpAspect = bpW / bpH;
  if (Math.abs(bpAspect - 9 / 16) > 0.02) {
    throw new Error(`blueprint aspect ${bpW}x${bpH} (${bpAspect.toFixed(3)}) is not ~9:16 (0.5625) — the paint model won't reproduce it 1:1; fix STRIP_FRAC so device+strip = 9:16`);
  }
  const blueprintPng = await deps.rasterize(svg);
  if (deps.store) { try { await deps.store(input.id, "blueprint", blueprintPng); } catch { /* debug artifact only */ } }

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
    .replace("{strip}", stripDesc)
    .replace("{bakeLegend}", bakeLegend || "each button carries no prescribed icon — leave each face cleanly molded")  // per-button colour→identity→icon map
    .replace(/\{NBUTTONS\}/g, String(regs.filter((r) => r.kind === "button").length))  // exact button count → anti-hallucination
    .replace(/\{BG\}/g, keyc.phrase);   // device-region backdrop colour (keyed out by the cutout)
  const refs = input.refImageUrls ?? [];
  if (refs.length) {
    prompt += " Borrow the palette, materials and surface-detail vocabulary of the REFERENCE " +
      "image(s) provided, but DO NOT copy their layout or shape — the silhouette, sockets and cells come only from the blueprint.";
  }
  // RE-ROLL until the vision model approves the button bank (alignment gate above).
  // SEED for reproducibility: a base seed (caller-supplied or random-but-recorded). Each
  // reroll uses base+(bt-1) so a reroll actually changes the image (a fixed seed would
  // re-roll the identical paint), and we record the seed of the attempt that SHIPPED
  // (paintSeed) into meta + the result. gpt-image-2 has no seed, so it stays unseeded.
  const baseSeed = input.seed ?? randomSeed();
  let paintUrl = "";
  let paintSeed = baseSeed;
  const tries = BANK_GATE_ENABLED ? MAX_BANK_TRIES : 1;
  for (let bt = 1; bt <= tries; bt++) {
    paintSeed = baseSeed + (bt - 1);
    const paintJob = await falSubmit(deps.falKey, model, [blueprintUrl, ...refs], prompt, paintSeed);
    paintUrl = await falPoll(deps.falKey, paintJob, 9 * 60_000);
    deps.onStage?.("paint", paintUrl);   // stream each attempt so the user watches it form
    if (!BANK_GATE_ENABLED || bt === tries) break;
    if (await bankPerfect(deps.falKey, paintUrl)) { log(`[${input.id}] button bank OK (try ${bt}, seed ${paintSeed})`); break; }
    log(`[${input.id}] button bank uneven — reroll ${bt}/${tries}`);
  }
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
    seed: paintSeed,
    createdAt: new Date().toISOString(),
  };
  const storeSidecars = async () => {
    if (!deps.store) return;
    try {
      await deps.store!(input.id, "template", JSON.stringify(template));   // PACKED template (post repackTemplate + bakeButtons)
      await deps.store!(input.id, "meta", JSON.stringify(meta));
      await deps.store!(input.id, "layout", JSON.stringify(layout));
      // ORIGINAL template = the Director's raw layout, BEFORE repackTemplate/bakeButtons — dumped so
      // the pipeline steps (original → packed → blueprint → paint) are all inspectable.
      if (input.regions?.length) await deps.store!(input.id, "rawlayout", JSON.stringify({ canvas: { w: GEN_W, h: GEN_H }, regions: input.regions }));
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
    needsCutout: true, paintUrl: paintOut, seed: paintSeed, keyColor: keyc.key,
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
