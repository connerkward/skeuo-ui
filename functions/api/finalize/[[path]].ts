// POST /api/finalize/<id>                  → upload the cut device frame.png
// POST /api/finalize/<id>/sprites/<bind>   → upload one cut control sprite.png
//
// WHY THIS EXISTS: the single-pass pipeline paints the device + control strip in
// ONE image and persists the RAW combined paint (the cutout is pure-JS CPU that
// trips the Pages Function CPU ceiling → CF 1102). The browser does the cutout:
// it background-removes the device region (via /api/cutout), cuts each control
// sprite by cell geometry, and POSTs the finished PNGs back here. Writing an R2
// object is pure I/O — no CPU — so this Function never trips the ceiling. After
// this, the skin is complete: skins/<id>/frame.png and skins/<id>/sprites/<bind>.png
// exist and the render team can size each sprite to its template region rect.
// See src/generate/cutoutClient.ts.
//
// CONTRACT (shared with the render team):
//   • device frame  → /api/asset/skins/<id>/frame.png
//   • per-skin sprite → /api/asset/skins/<id>/sprites/<bind>.png
//
// ABUSE GUARDS (this is an unauthenticated write):
//   • id must be the slug format /api/generate produces; bind must be a safe token.
//   • template.json for <id> MUST already exist — proves a real prior generation
//     (bounded by the $10 lifetime spend cap), so this can't write arbitrary keys.
//   • WRITE-ONCE: an existing frame/sprite no-ops (200) instead of overwriting.
//   • image/png only, body size capped.

interface Env {
  SKINS?: R2Bucket;
  ASSETS_BASE_URL?: string;
}

const ID_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
const BIND_RE = /^[a-z0-9][a-z0-9_-]{0,39}$/i;
const MAX_BYTES = 8 * 1024 * 1024; // a 2K RGBA PNG is well under this

export const onRequestPost = async (
  ctx: { request: Request; params: { path: string | string[] }; env: Env }
): Promise<Response> => {
  const { request, params, env } = ctx;
  const parts = (Array.isArray(params.path) ? params.path : [params.path]).map((p) => decodeURIComponent(p));
  const id = parts[0];
  if (!id || !ID_RE.test(id)) return json({ error: "bad id" }, 400);
  if (!env.SKINS) return json({ error: "storage not configured" }, 503);

  // route: /<id> (frame) | /<id>/sprites/<bind> (control sprite)
  let bind: string | null = null;
  if (parts.length === 3 && parts[1] === "sprites") {
    bind = parts[2];
    if (!bind || !BIND_RE.test(bind)) return json({ error: "bad bind" }, 400);
  } else if (parts.length !== 1) {
    return json({ error: "bad finalize path" }, 400);
  }

  const assetBase = env.ASSETS_BASE_URL ?? "/api/asset";
  const objKey = bind ? `skins/${id}/sprites/${bind}.png` : `skins/${id}/frame.png`;
  const objUrl = `${assetBase}/${objKey}`;

  // gate on a real prior generation, and make the write idempotent / once-only.
  const [tpl, existing] = await Promise.all([
    env.SKINS.head(`skins/${id}/template.json`),
    env.SKINS.head(objKey),
  ]);
  if (!tpl) return json({ error: "unknown skin (generate first)" }, 404);
  if (existing) {
    return bind
      ? json({ id, bind, spriteUrl: objUrl, alreadyFinalized: true })
      : json({ id, frameUrl: objUrl, alreadyFinalized: true });
  }

  const ct = request.headers.get("content-type") ?? "";
  if (!ct.includes("image/png")) return json({ error: "image/png body required" }, 415);

  const buf = await request.arrayBuffer();
  if (buf.byteLength === 0) return json({ error: "empty body" }, 400);
  if (buf.byteLength > MAX_BYTES) return json({ error: "image too large" }, 413);

  await env.SKINS.put(objKey, buf, { httpMetadata: { contentType: "image/png" } });
  return bind ? json({ id, bind, spriteUrl: objUrl }) : json({ id, frameUrl: objUrl });
};

// CORS: native shells (iOS app, macOS widget) POST cut PNGs here from the tauri://
// origin; image/png is a non-simple content type → preflight OPTIONS.
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
