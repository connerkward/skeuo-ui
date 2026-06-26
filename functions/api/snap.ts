// POST /api/snap — the ALIGN pass: SAM-3.1 snaps each control's template rect onto the
// ACTUAL painted control (see src/generate/samSnap.ts, ported from generation/sam_snap.py).
//
// The painter places controls/screens near the blueprint sockets but not pixel-on, so the
// template rects land off the paint ("everything outside bounds"). This corrects them with
// a real segmentation model. The browser calls this after the device frame is cut+uploaded
// (it passes that public frame URL + the regions); we run SAM server-side (FAL_KEY), snap,
// re-store the corrected template.json (so cloud + reload use the aligned layout), and
// return the snapped regions for immediate render.
//
// Metered against the same edge spend ledger as generate/cutout (one paid SAM call).

import { snapFromUrl } from "../../src/generate/samSnap";
import { reserve, refund, CUT_BUCKET, BIREFNET_COST_CENTS, type MeterEnv } from "../../src/generate/meter";

interface Env extends MeterEnv {
  FAL_KEY: string;
  SKINS?: R2Bucket;
}

const ID_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;

function clientIp(req: Request): string {
  return req.headers.get("CF-Connecting-IP") || req.headers.get("X-Forwarded-For") || "anon";
}

export const onRequestPost = async (ctx: { request: Request; env: Env }): Promise<Response> => {
  const { request, env } = ctx;
  if (!env.FAL_KEY) return json({ error: "server missing FAL_KEY" }, 500);
  let body: { id?: string; imageUrl?: string; regions?: unknown[] };
  try { body = await request.json(); } catch { return json({ error: "invalid JSON" }, 400); }
  const { id, imageUrl, regions } = body;
  if (!imageUrl || !Array.isArray(regions)) return json({ error: "imageUrl + regions required" }, 400);
  if (id && !ID_RE.test(id)) return json({ error: "bad id" }, 400);
  // imageUrl must be our own asset (no SSRF / arbitrary-host SAM billing)
  if (!/^(https?:)?\/\/[^/]+\/api\/asset\/|^\/api\/asset\//.test(imageUrl) && !imageUrl.includes("/api/asset/")) {
    return json({ error: "imageUrl must be a same-origin /api/asset URL" }, 400);
  }

  const ip = clientIp(request);
  const r = await reserve(env, ip, BIREFNET_COST_CENTS, CUT_BUCKET);
  if (!r.ok) return json({ error: r.reason }, 429);
  try {
    const absUrl = new URL(imageUrl, request.url).href; // resolve to absolute so we can fetch our own asset
    const out = await snapFromUrl(env.FAL_KEY, absUrl, regions as Parameters<typeof snapFromUrl>[2]);
    // re-store the corrected template so cloud + reload use the aligned layout
    if (id && env.SKINS) {
      try {
        const head = await env.SKINS.get(`skins/${id}/template.json`);
        if (head) {
          const tpl = JSON.parse(await head.text());
          tpl.regions = out.regions;
          await env.SKINS.put(`skins/${id}/template.json`, JSON.stringify(tpl), { httpMetadata: { contentType: "application/json" } });
        }
      } catch { /* re-store best-effort; the client still gets snapped regions */ }
    }
    return json({ regions: out.regions, snapped: out.snapped, total: out.total }, 200);
  } catch (e) {
    await refund(env, ip, BIREFNET_COST_CENTS, CUT_BUCKET);
    return json({ error: `sam-snap: ${e instanceof Error ? e.message : String(e)}` }, 502);
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
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...CORS } });
}
