// POST /api/finalize/<id> — upload the browser-cut frame.png for skin <id>.
//
// WHY THIS EXISTS: the alpha cutout is ~2s of pure-JS CPU and trips the Pages
// Function CPU ceiling (CF 1102). So /api/generate persists the RAW paint and
// returns needsCutout; the browser keys out the white background (the shared
// cutoutAlpha) and POSTs the finished frame.png here. Writing an R2 object is
// pure I/O — no CPU — so this Function never trips the ceiling. After this, the
// skin is complete: skins/<id>/frame.png exists and /api/skin/<id> + the share
// page serve it like any other generated skin. See src/generate/cutoutClient.ts.
//
// ABUSE GUARDS (this is an unauthenticated write):
//   • id must be the slug format /api/generate produces.
//   • template.json for <id> MUST already exist — proves a real prior generation
//     (which is itself bounded by the $10 lifetime spend cap), so this can't be
//     used to write arbitrary objects into the bucket.
//   • WRITE-ONCE: if frame.png already exists we no-op (200) instead of
//     overwriting, so the endpoint can't be used to clobber a finished skin.
//   • image/png only, body size capped.

interface Env {
  SKINS?: R2Bucket;
  ASSETS_BASE_URL?: string;
}

const ID_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
const MAX_BYTES = 8 * 1024 * 1024; // a 2K RGBA PNG is well under this

export const onRequestPost = async (
  ctx: { request: Request; params: { id: string }; env: Env }
): Promise<Response> => {
  const { request, params, env } = ctx;
  const id = params.id;
  if (!id || !ID_RE.test(id)) return json({ error: "bad id" }, 400);
  if (!env.SKINS) return json({ error: "storage not configured" }, 503);

  const assetBase = env.ASSETS_BASE_URL ?? "/api/asset";
  const frameKey = `skins/${id}/frame.png`;
  const frameUrl = `${assetBase}/${frameKey}`;

  // gate on a real prior generation, and make the write idempotent / once-only.
  const [tpl, existing] = await Promise.all([
    env.SKINS.head(`skins/${id}/template.json`),
    env.SKINS.head(frameKey),
  ]);
  if (!tpl) return json({ error: "unknown skin (generate first)" }, 404);
  if (existing) return json({ id, frameUrl, alreadyFinalized: true });

  const ct = request.headers.get("content-type") ?? "";
  if (!ct.includes("image/png")) return json({ error: "image/png body required" }, 415);

  const buf = await request.arrayBuffer();
  if (buf.byteLength === 0) return json({ error: "empty body" }, 400);
  if (buf.byteLength > MAX_BYTES) return json({ error: "frame too large" }, 413);

  await env.SKINS.put(frameKey, buf, { httpMetadata: { contentType: "image/png" } });
  return json({ id, frameUrl });
};

// CORS: native shells (iOS app, macOS widget) POST the cut frame here from the
// tauri:// origin; image/png is a non-simple content type → preflight OPTIONS.
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
