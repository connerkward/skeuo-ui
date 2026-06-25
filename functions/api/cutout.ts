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
//   • Request body is image/png BYTES (the cropped device/strip region). That is the
//     ONLY accepted shape — the legacy application/json {imageUrl} branch was removed
//     because (a) the shipping client never used it and (b) fetching an arbitrary
//     attacker-supplied URL server-side is an SSRF + blind-relay hole.
//   • Response is image/png bytes of the transparent (background-removed) image.
//   • SECURITY/COST: this calls paid fal BiRefNet, so it is metered against the SAME
//     edge spend ledger + a per-IP/day cap as /api/generate (src/generate/meter.ts).
//     Without that, anyone could loop POSTs and run up an unbounded fal bill the $10
//     cap never saw. Reserve up front, refund if BiRefNet fails.

import { removeBackground, BIREFNET_MODEL } from "../../src/generate/pipeline";
import { reserve, refund, CUT_BUCKET, BIREFNET_COST_CENTS, type MeterEnv } from "../../src/generate/meter";

interface Env extends MeterEnv {
  FAL_KEY: string;
}

const MAX_BYTES = 12 * 1024 * 1024; // a 2K RGBA device PNG is well under this

function clientIp(req: Request): string {
  return req.headers.get("CF-Connecting-IP") || req.headers.get("X-Forwarded-For") || "anon";
}

export const onRequestPost = async (ctx: { request: Request; env: Env }): Promise<Response> => {
  const { request, env } = ctx;
  if (!env.FAL_KEY) return json({ error: "server missing FAL_KEY" }, 500);

  const ct = request.headers.get("content-type") ?? "";
  if (!ct.includes("image/png")) return json({ error: "image/png body required" }, 415);
  const buf = await request.arrayBuffer();
  if (buf.byteLength === 0) return json({ error: "empty body" }, 400);
  if (buf.byteLength > MAX_BYTES) return json({ error: "image too large" }, 413);
  const png = new Uint8Array(buf);

  // meter BEFORE the paid BiRefNet call; refuse over budget, refund on failure.
  const ip = clientIp(request);
  const r = await reserve(env, ip, BIREFNET_COST_CENTS, CUT_BUCKET);
  if (!r.ok) return json({ error: r.reason }, 429);
  try {
    const cut = await removeBackground(env.FAL_KEY, png);
    return new Response(cut as unknown as ArrayBuffer, {
      status: 200,
      headers: { "Content-Type": "image/png", "Cache-Control": "no-store", ...CORS },
    });
  } catch (e) {
    await refund(env, ip, BIREFNET_COST_CENTS, CUT_BUCKET);
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
