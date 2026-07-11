// Runtime-agnostic request handler for POST /api/generate. Validates the body,
// enforces the rate limit, runs the pipeline, returns a GenerateResponse object.
// Both the CF Pages Function and the Node dev server wrap this with their own
// (req → body, ip) extraction and (response → HTTP) serialization.
import type { GenerateRequest, GenerateResponse } from "./api";
import type { RuntimeDeps } from "./pipeline";
import { generateSkin, DONOR_STYLES, MODELS, DEFAULT_MODEL, type DonorStyle, type ModelId } from "./pipeline";
import { LAYOUT_VARIANTS, type LayoutVariant } from "./layouts";
import { deriveMaterial, deriveLayout, titleFromPrompt, blurbFromPrompt, type DirectorKeys } from "./director";
import type { Region } from "../template/schema";

function slug(s: string): string {
  return (s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 24) || "skin");
}

export interface HandlerInput {
  body: Partial<GenerateRequest>;
  // Rate limiting lives in the CALLER now (meter.ts, KV-backed) — ip is no longer
  // consulted inside this handler. Kept on the interface (optional) so callers don't
  // need to change their call sites; a future per-request audit/log could use it.
  ip?: string;
  deps: RuntimeDeps;
}

export async function handleGenerate({ body, deps }: HandlerInput): Promise<GenerateResponse> {
  const prompt = (body.prompt ?? "").trim();
  const reqStyle = body.style as DonorStyle | undefined;
  const variant = body.variant as LayoutVariant;
  const model = (body.model ?? DEFAULT_MODEL) as ModelId;
  const envelope = body.envelope ?? true;
  if (!prompt) return { status: "error", error: "prompt is required" };
  if (!LAYOUT_VARIANTS.includes(variant)) return { status: "error", error: `variant must be one of ${LAYOUT_VARIANTS.join(", ")}` };
  if (!MODELS.some((m) => m.id === model)) return { status: "error", error: `model must be one of ${MODELS.map((m) => m.id).join(", ")}` };

  // Resolve the PAINT MATERIAL and the PALETTE id separately — these are two
  // different things and must NOT be conflated:
  //   • materialPrompt → the paint look. ALWAYS derived from the user's PROMPT
  //     (never a canned donor preset), so the model interprets the sentence freely.
  //   • style          → the runtime [data-skin] palette/sprite id (a separate CSS
  //     concern). A donor named in the request, or the Director's closest-fit, just
  //     picks the palette; it does NOT force the paint material.
  // deriveMaterial is ALWAYS attempted (Vertex-only Director — see director.ts): with
  // Vertex auth it returns a rich LLM-derived material + closest-fit palette; with NO
  // auth (no GCP_SERVICE_ACCOUNT_KEY / gcloud session) it degrades internally to its
  // OWN deterministic keyword heuristic — never throws, never calls OpenAI.
  const directorKeys: DirectorKeys = { gcpServiceAccountKey: deps.gcpServiceAccountKey, devToken: deps.vertexDevToken };
  const derived = await deriveMaterial(directorKeys, prompt, body.avoidFonts);
  const materialPrompt = derived.materialPrompt;   // paint look — prompt-driven, never a canned donor
  const font = derived.font;                       // logomark title font (Director pick)
  const name = derived.name || titleFromPrompt(prompt);
  const blurb = derived.blurb || blurbFromPrompt(prompt);
  // an explicitly-requested donor still picks the PALETTE; else the Director's fit
  const style: DonorStyle = reqStyle && DONOR_STYLES.includes(reqStyle) ? reqStyle : derived.style;

  // Rate limiting / spend cap: handled by the CALLER (functions/api/generate.ts,
  // src/generate/meter.ts — an edge-shared KV ledger, RESERVE-before-spend). This
  // handler used to also run its own in-memory per-isolate cap (ratelimit.ts) as a
  // second, redundant, non-durable check — removed 2026-07 once the KV meter covered
  // the same ground correctly (durable, edge-shared) so the stale duplicate wasn't
  // left as dead/misleading code. The Node dev server (server/devApiPlugin.ts) has no
  // RATELIMIT KV, so local iteration is intentionally uncapped, same as prod when the
  // binding is absent (meter.ts: "no KV binding → don't block iteration").

  // optional reference image (data: URL) → upload to fal so it can ride the paint pass
  const refUrls: string[] = [];
  try {
    if (body.refImage?.startsWith("data:")) refUrls.push(await uploadDataUrl(deps.falKey, body.refImage, "ref.png"));
  } catch { /* ref upload is best-effort; ignore and paint without it */ }

  // optional user-uploaded body envelope (data: URL) → upload to fal; paints from it directly
  let envelopeUrl: string | undefined;
  try {
    if (body.envelopeImage?.startsWith("data:")) envelopeUrl = await uploadDataUrl(deps.falKey, body.envelopeImage, "envelope.png");
  } catch { /* envelope upload is best-effort; fall back to the normal path */ }

  const modelTag = MODELS.find((m) => m.id === model)?.label ?? "model";
  const id = `${slug(prompt)}-${variant}-${modelTag}-${Date.now().toString(36).slice(-4)}`;
  try {
    // Template source, in priority: explicit wizard regions → Director-generated layout
    // (the prompt drives the control set, varied per theme) → constant variant preset.
    let regions: Region[] | undefined =
      Array.isArray(body.regions) && body.regions.length ? (body.regions as Region[]) : undefined;
    // body.regions = HUMAN-authored (wizard drag / Template Studio) → pipeline uses them as-is;
    // Director-derived regions below are messy LLM output → pipeline repacks them.
    const authored = !!regions;
    if (!regions) {
      // deriveLayout is Vertex-only (director.ts) and degrades to null with no auth —
      // caller falls back to the constant variant preset (regionsForVariant), below.
      regions = (await deriveLayout(directorKeys, prompt)) ?? undefined;
    }
    const r = await generateSkin(deps, { id, variant, style, materialPrompt, brief: prompt, refImageUrls: refUrls, model, envelope, envelopeUrl, regions, authored, seed: body.seed, maskPanel: body.maskPanel === true });
    return {
      status: "done", id: r.id, style: r.style, variant: r.variant, model: r.model, font, name, blurb,
      template: r.template, frameUrl: r.frameUrl, layout: r.layout, sprites: r.sprites,
      needsCutout: r.needsCutout, paintUrl: r.paintUrl, seed: r.seed, keyColor: r.keyColor, timingMs: r.timingMs,
    };
  } catch (e) {
    // spend-cap refund on failure is handled by the caller (generate.ts refund()),
    // which reserved against the KV ledger before invoking this handler.
    return { status: "error", error: e instanceof Error ? e.message : String(e) };
  }
}

// upload a data: URL PNG to fal storage (initiate → PUT), return its file_url.
async function uploadDataUrl(falKey: string, dataUrl: string, fileName: string): Promise<string> {
  const png = dataUrlToBytes(dataUrl);
  const init = (await (await fetch("https://rest.alpha.fal.ai/storage/upload/initiate", {
    method: "POST",
    headers: { Authorization: `Key ${falKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ file_name: fileName, content_type: "image/png" }),
  })).json()) as { upload_url: string; file_url: string };
  await fetch(init.upload_url, { method: "PUT", headers: { "Content-Type": "image/png" }, body: png as unknown as ArrayBuffer });
  return init.file_url;
}

function dataUrlToBytes(dataUrl: string): Uint8Array {
  const b64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  const bin = atob(b64);   // present in browsers, Workers and modern Node
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
