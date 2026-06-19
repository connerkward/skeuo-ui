// GET /api/asset/<key…> — stream a public R2 object.
//
// The generate pipeline persists every skin under skins/<id>/ (frame.png,
// template.json, meta.json) into the SKINS bucket and stores public URLs of the
// form /api/asset/skins/<id>/frame.png. This catch-all serves those objects so the
// frames are publicly fetchable (e.g. by the share page's <img> and the player).
// Read-only: only GET, and the key is taken verbatim from the path (an R2 get of a
// non-existent key just 404s — no traversal risk since R2 keys are a flat namespace).

interface Env {
  SKINS?: R2Bucket;
}

// A MISS must NOT be cached: generated skins are written in two steps (the Worker
// stores paint.png; the browser uploads the cut frame.png afterward — see
// /api/finalize), so frame.png is briefly absent. If a 404 in that window got
// cached (a crawler, an early share-open, a probe), the long immutable cache would
// serve a stale 404 forever — even after the frame lands. So 404/503 carry
// `no-store`, and the immutable cache lives ONLY on the 200 below (NOT in _headers,
// which can't condition on status). The object is content-addressed → immutable.
// CORS: the native shells (iOS app, macOS widget) fetch these from the tauri://
// origin and read the paint PNG into a canvas for the client-side cutout, which
// requires Access-Control-Allow-Origin. Public read-only assets — `*` is fine.
const miss = (msg: string, status: number) =>
  new Response(msg, { status, headers: { "Cache-Control": "no-store", "Access-Control-Allow-Origin": "*" } });

export const onRequestGet = async (
  ctx: { params: { path: string | string[] }; env: Env }
): Promise<Response> => {
  const { params, env } = ctx;
  if (!env.SKINS) return miss("storage not configured", 503);

  const parts = Array.isArray(params.path) ? params.path : [params.path];
  const key = parts.map((p) => decodeURIComponent(p)).join("/");
  if (!key) return miss("not found", 404);

  const obj = await env.SKINS.get(key);
  if (!obj) return miss("not found", 404);

  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set("etag", obj.httpEtag);
  // immutable: skins/<id>/… is content-addressed by a unique id, never overwritten.
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/octet-stream");
  headers.set("Cache-Control", "public, max-age=31536000, immutable");
  headers.set("Access-Control-Allow-Origin", "*");
  return new Response(obj.body, { headers });
};
