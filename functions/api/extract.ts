// POST /api/extract — the VLM ALIGN pass. gpt-4o vision locates each expected
// control in the painted device image (matched by bind/icon) and returns its
// normalized box. OPENAI_API_KEY stays SERVER-SIDE (never reaches the browser).
//
// CONTRACT:
//   • Request: application/json { imageDataUrl: "data:image/png;base64,…",
//                                 controls: [{bind, kind, label?}] }
//   • Response: { boxes: [{bind, x, y, w, h, conf?}] } — normalized 0..1, only
//     the controls the model could locate (others omitted; caller keeps prior).

import { extractSlots, type SlotControl } from "../../src/generate/director";

interface Env {
  OPENAI_API_KEY: string;
}
interface Body {
  imageDataUrl?: string;
  imageUrl?: string;
  controls?: SlotControl[];
}

export const onRequestPost = async (ctx: { request: Request; env: Env }): Promise<Response> => {
  const { request, env } = ctx;
  if (!env.OPENAI_API_KEY) return json({ error: "server missing OPENAI_API_KEY" }, 500);
  try {
    const body = (await request.json()) as Body;
    const image = body.imageDataUrl || body.imageUrl;
    if (!image) return json({ error: "imageDataUrl or imageUrl required" }, 400);
    if (!Array.isArray(body.controls) || !body.controls.length) return json({ error: "controls required" }, 400);
    const boxes = await extractSlots(env.OPENAI_API_KEY, image, body.controls);
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
