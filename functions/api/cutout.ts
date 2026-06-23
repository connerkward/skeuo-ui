// POST /api/cutout — server-side background removal (BiRefNet) for a device frame.
//
// WHY THIS EXISTS: the single-pass pipeline paints the device + control strip in ONE
// image on a pure-white background. The browser crops the device region and needs it
// background-removed into a transparent PNG, but the masking model runs on fal and the
// FAL_KEY must NEVER reach the browser. So the browser POSTs the cropped device PNG
// here; this Function calls fal-ai/birefnet/v2 SERVER-SIDE with FAL_KEY and streams the
// transparent PNG back. See src/generate/cutoutClient.ts (the caller) and
// src/generate/pipeline.ts removeBackground() (the fal call).
//
// CONTRACT:
//   • Request body is image/png bytes (the cropped device region), OR
//     application/json {"imageUrl": "<public same-origin /api/asset URL>"}.
//   • Response is image/png bytes of the transparent (background-removed) device.
//   • image/png only, body size capped; this is an unauthenticated call but it only
//     forwards to BiRefNet (no storage write) and is bounded by the per-request size.

import { removeBackground, BIREFNET_MODEL } from "../../src/generate/pipeline";

interface Env {
  FAL_KEY: string;
}

const MAX_BYTES = 12 * 1024 * 1024; // a 2K RGBA device PNG is well under this

export const onRequestPost = async (ctx: { request: Request; env: Env }): Promise<Response> => {
  const { request, env } = ctx;
  if (!env.FAL_KEY) return json({ error: "server missing FAL_KEY" }, 500);

  const ct = request.headers.get("content-type") ?? "";
  let png: Uint8Array;
  try {
    if (ct.includes("application/json")) {
      const body = (await request.json()) as { imageUrl?: string };
      if (!body?.imageUrl) return json({ error: "imageUrl required" }, 400);
      const r = await fetch(body.imageUrl);
      if (!r.ok) return json({ error: `fetch imageUrl → ${r.status}` }, 400);
      png = new Uint8Array(await r.arrayBuffer());
    } else if (ct.includes("image/png")) {
      const buf = await request.arrayBuffer();
      if (buf.byteLength === 0) return json({ error: "empty body" }, 400);
      if (buf.byteLength > MAX_BYTES) return json({ error: "image too large" }, 413);
      png = new Uint8Array(buf);
    } else {
      return json({ error: "image/png body or application/json {imageUrl} required" }, 415);
    }
    const cut = await removeBackground(env.FAL_KEY, png);
    return new Response(cut as unknown as ArrayBuffer, {
      status: 200,
      headers: { "Content-Type": "image/png", "Cache-Control": "no-store", ...CORS },
    });
  } catch (e) {
    return json({ error: `${BIREFNET_MODEL}: ${e instanceof Error ? e.message : String(e)}` }, 502);
  }
};

// CORS: native shells (iOS app, macOS widget) POST here from the tauri:// origin;
// image/png + application/json are non-simple content types → preflight OPTIONS.
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
