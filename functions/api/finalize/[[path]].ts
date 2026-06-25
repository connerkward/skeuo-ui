// POST /api/finalize/<id>                  → upload the cut device frame.png
// POST /api/finalize/<id>/sprites/<bind>   → upload one cut control sprite.png
// POST /api/finalize/<id>/publish          → mark the skin PUBLISHED (gallery index)
//
// PUBLISH: writes the marker object `published/<id>` whose JSON body carries the
// display fields the pipeline does NOT persist (name/blurb/font/style — those live
// only in the generate response client-side). GET /api/skins lists that prefix to
// build the cloud gallery index. Idempotent: re-publishing just overwrites the
// marker (cheap, lets the client refresh display metadata). Gated on a real prior
// generation (template.json must exist) like the asset uploads.
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
// ABUSE GUARDS:
//   • PUBLISH is OWNER-ONLY: requires the X-Owner-Key header == PUBLISH_KEY secret,
//     so only the owner can curate the shared gallery (not any visitor). Marker
//     fields are sanitized (no stored XSS).
//   • frame/sprite uploads are unauthenticated but bounded: id must be the slug
//     format /api/generate produces; bind must be a safe token; template.json for
//     <id> MUST already exist (proves a real prior gen, bounded by the spend cap),
//     so this can't write arbitrary keys.
//   • WRITE-ONCE: an existing frame/sprite no-ops (200) instead of overwriting.
//   • image/png only, body size capped.

interface Env {
  SKINS?: R2Bucket;
  ASSETS_BASE_URL?: string;
  PUBLISH_KEY?: string;   // owner-only publish secret (wrangler secret; absent → publish disabled)
}

const ID_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
const BIND_RE = /^[a-z0-9][a-z0-9_-]{0,39}$/i;
const MAX_BYTES = 8 * 1024 * 1024; // a 2K RGBA PNG is well under this

// strip HTML/markup-significant chars so a marker field can never carry stored XSS
// into a gallery client that renders it; collapse whitespace, cap length.
const sanitizeField = (s: string): string =>
  s.replace(/[<>&"'`]/g, " ").replace(/\s+/g, " ").trim().slice(0, 120);

export const onRequestPost = async (
  ctx: { request: Request; params: { path: string | string[] }; env: Env }
): Promise<Response> => {
  const { request, params, env } = ctx;
  const parts = (Array.isArray(params.path) ? params.path : [params.path]).map((p) => decodeURIComponent(p));
  const id = parts[0];
  if (!id || !ID_RE.test(id)) return json({ error: "bad id" }, 400);
  if (!env.SKINS) return json({ error: "storage not configured" }, 503);

  // route: /<id>/publish — write the published marker carrying display metadata.
  // OWNER-ONLY: requires the X-Owner-Key header to match the PUBLISH_KEY secret.
  // Without this gate ANYONE could publish/overwrite/hijack arbitrary skins into the
  // shared gallery. If PUBLISH_KEY isn't configured, publishing is disabled (safe).
  if (parts.length === 2 && parts[1] === "publish") {
    if (!env.PUBLISH_KEY) return json({ error: "publishing disabled" }, 403);
    if (request.headers.get("X-Owner-Key") !== env.PUBLISH_KEY) return json({ error: "not authorized to publish" }, 403);
    const tpl = await env.SKINS.head(`skins/${id}/template.json`);
    if (!tpl) return json({ error: "unknown skin (generate first)" }, 404);
    const marker: Record<string, unknown> = {};
    try {
      const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
      // keep only the small display fields, sanitized; ignore anything else the client sends.
      for (const k of ["name", "blurb", "font", "style"]) {
        if (typeof body[k] === "string") marker[k] = sanitizeField(body[k] as string);
      }
    } catch { /* empty/invalid body → marker with no overrides is still valid */ }
    marker.publishedAt = new Date().toISOString();
    await env.SKINS.put(`published/${id}`, JSON.stringify(marker), {
      httpMetadata: { contentType: "application/json" },
    });
    return json({ id, published: true });
  }

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
