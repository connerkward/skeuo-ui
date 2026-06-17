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

export const onRequestGet = async (
  ctx: { params: { path: string | string[] }; env: Env }
): Promise<Response> => {
  const { params, env } = ctx;
  if (!env.SKINS) return new Response("storage not configured", { status: 503 });

  const parts = Array.isArray(params.path) ? params.path : [params.path];
  const key = parts.map((p) => decodeURIComponent(p)).join("/");
  if (!key) return new Response("not found", { status: 404 });

  const obj = await env.SKINS.get(key);
  if (!obj) return new Response("not found", { status: 404 });

  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set("etag", obj.httpEtag);
  // immutable: skins/<id>/… is content-addressed by a unique id, never overwritten.
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/octet-stream");
  headers.set("Cache-Control", "public, max-age=31536000, immutable");
  return new Response(obj.body, { headers });
};
