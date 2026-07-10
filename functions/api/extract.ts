// POST /api/extract — the VLM ALIGN pass. The Director vision model (Gemini 3.1 Pro
// via Vertex AI — src/generate/director.ts + vertexAuth.ts; ZERO gpt-4o/OpenAI)
// locates each expected control in the painted device image (matched by bind/icon)
// and returns its normalized box. GCP_SERVICE_ACCOUNT_KEY stays SERVER-SIDE (never
// reaches the browser); when unset, extractSlots returns an empty boxes array
// (never throws, never calls OpenAI) — see functions/api/generate.ts for the
// one-time service-account deploy steps.
//
// CONTRACT:
//   • Request: application/json { imageDataUrl: "data:image/png;base64,…",
//                                 controls: [{bind, kind, label?}] }
//   • Response: { boxes: [{bind, x, y, w, h, conf?}] } — normalized 0..1, only
//     the controls the model could locate (others omitted; caller keeps prior).

import { extractSlots, type SlotControl } from "../../src/generate/director";

interface Env {
  GCP_SERVICE_ACCOUNT_KEY?: string;
}
interface Body {
  imageDataUrl?: string;
  imageUrl?: string;
  controls?: SlotControl[];
}

export const onRequestPost = async (ctx: { request: Request; env: Env }): Promise<Response> => {
  const { request, env } = ctx;
  try {
    const body = (await request.json()) as Body;
    const image = body.imageDataUrl || body.imageUrl;
    if (!image) return json({ error: "imageDataUrl or imageUrl required" }, 400);
    if (!Array.isArray(body.controls) || !body.controls.length) return json({ error: "controls required" }, 400);
    const boxes = await extractSlots({ gcpServiceAccountKey: env.GCP_SERVICE_ACCOUNT_KEY }, image, body.controls);
    return json({ boxes }, 200);
  } catch (e) {
    return json({ error: `extract: ${e instanceof Error ? e.message : String(e)}` }, 502);
  }
};

const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};
export const onRequestOptions = (): Response => new Response(null, { status: 204, headers: CORS });

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...CORS },
  });
}
