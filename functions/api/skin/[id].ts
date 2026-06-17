// GET /api/skin/<id> — reconstruct a shared skin from R2.
//
// Returns { id, frameUrl, template, meta } by reading skins/<id>/template.json and
// skins/<id>/meta.json out of the SKINS bucket and pointing frameUrl at the public
// asset route. This is how a ?id=<skinId> share link rebuilds the player without
// the client ever having generated the skin. 404 if the skin doesn't exist.

interface Env {
  SKINS?: R2Bucket;
  ASSETS_BASE_URL?: string;
}

export const onRequestGet = async (
  ctx: { params: { id: string }; env: Env }
): Promise<Response> => {
  const { params, env } = ctx;
  const id = params.id;
  if (!id) return json({ error: "id required" }, 400);
  if (!env.SKINS) return json({ error: "storage not configured" }, 503);

  const [tplObj, metaObj] = await Promise.all([
    env.SKINS.get(`skins/${id}/template.json`),
    env.SKINS.get(`skins/${id}/meta.json`),
  ]);
  // the template is the authoritative artifact — without it the skin can't render.
  if (!tplObj) return json({ error: "skin not found" }, 404);

  const template = await tplObj.json().catch(() => null);
  if (!template) return json({ error: "skin template unreadable" }, 502);
  const meta = metaObj ? await metaObj.json().catch(() => null) : null;

  const assetBase = env.ASSETS_BASE_URL ?? "/api/asset";
  const frameUrl = `${assetBase}/skins/${id}/frame.png`;
  return json({ id, frameUrl, template, meta });
};

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": status === 200 ? "public, max-age=300" : "no-store" },
  });
}
