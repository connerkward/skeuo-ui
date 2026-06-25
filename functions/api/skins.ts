// GET /api/skins — the CLOUD SKIN INDEX the app fetches at startup and merges
// into the gallery AFTER the bundled built-ins. Lets new skins reach the app
// WITHOUT a rebuild: a published skin's id appears here, the client maps it to a
// gallery entry, and it renders through the existing <Composite>.
//
// PUBLISHED = an R2 marker object `published/<id>` exists (written by
// POST /api/finalize/<id>/publish — see functions/api/finalize/[[path]].ts).
// We list that prefix to get the published ids, then read each skin's
// template.json + meta.json (+ the marker's own JSON body) to fill the row.
// The marker body carries the display fields the pipeline does NOT persist to R2
// (name/blurb/font live only in the generate response), so the client passes them
// through at publish time; meta/template/prompt are the fallbacks.
//
// Shape returned (one row per published skin):
//   { skins: [{ id, name, blurb, style, frameUrl, sprites, font, createdAt }] }
// This carries enough to BUILD a runtime view {frameUrl, style, sprites} for the
// gallery thumb; the full template is fetched lazily via /api/skin/<id> when a
// cloud skin becomes active (App already does this for runtime skins).

interface Env {
  SKINS?: R2Bucket;
  ASSETS_BASE_URL?: string;
}

interface SkinMetaLike {
  prompt?: string;
  style?: string;
  variant?: string;
  createdAt?: string;
}
interface PublishMarker {
  name?: string;
  blurb?: string;
  font?: string;
  style?: string;
}
interface SkinTemplateLike {
  name?: string;
  blurb?: string;
}

interface SkinRow {
  id: string;
  name: string;
  blurb: string;
  style: string;
  frameUrl: string;
  sprites: boolean;
  font?: string;
  createdAt?: string;
}

// Deterministic display-name fallback when the publish marker / meta don't carry
// one. Mirrors src/generate/director.ts titleFromPrompt (kept inline so this
// Function doesn't import the heavy pipeline graph).
function titleFromPrompt(prompt: string): string {
  const words = prompt.trim().replace(/^(a|an|the)\s+/i, "").replace(/[^\w\s-]/g, "")
    .split(/\s+/).filter(Boolean).slice(0, 3);
  const t = words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  return t || "New Skin";
}
function blurbFromPrompt(prompt: string): string {
  const p = prompt.trim().replace(/\s+/g, " ");
  const s = p.charAt(0).toUpperCase() + p.slice(1);
  return s.length > 64 ? s.slice(0, 61).trimEnd() + "…" : s;
}

async function readJson<T>(bucket: R2Bucket, key: string): Promise<T | null> {
  const obj = await bucket.get(key).catch(() => null);
  if (!obj) return null;
  return (await obj.json().catch(() => null)) as T | null;
}

async function buildRow(env: Env, id: string): Promise<SkinRow | null> {
  const bucket = env.SKINS!;
  const [tpl, meta, marker, spritesList] = await Promise.all([
    readJson<SkinTemplateLike>(bucket, `skins/${id}/template.json`),
    readJson<SkinMetaLike>(bucket, `skins/${id}/meta.json`),
    readJson<PublishMarker>(bucket, `published/${id}`),
    bucket.list({ prefix: `skins/${id}/sprites/`, limit: 1 }).catch(() => null),
  ]);
  // the template is the authoritative artifact — a published id without it is a
  // dangling marker (skin never finalized); skip it rather than ship a broken row.
  if (!tpl) return null;

  const prompt = meta?.prompt ?? "";
  const name = marker?.name || tpl.name || (prompt ? titleFromPrompt(prompt) : id);
  const blurb = marker?.blurb || tpl.blurb || (prompt ? blurbFromPrompt(prompt) : "");
  const style = marker?.style || meta?.style || id;
  const sprites = !!spritesList && spritesList.objects.length > 0;

  const assetBase = env.ASSETS_BASE_URL ?? "/api/asset";
  const frameUrl = `${assetBase}/skins/${id}/frame.png`;

  return { id, name, blurb, style, frameUrl, sprites, font: marker?.font, createdAt: meta?.createdAt };
}

export const onRequestGet = async (ctx: { env: Env }): Promise<Response> => {
  const { env } = ctx;
  if (!env.SKINS) return json({ skins: [] });

  // collect every published id by listing the marker prefix (paginated).
  const ids: string[] = [];
  let cursor: string | undefined;
  do {
    const page = await env.SKINS.list({ prefix: "published/", cursor }).catch(() => null);
    if (!page) break;
    for (const o of page.objects) {
      const id = o.key.slice("published/".length);
      if (id) ids.push(id);
    }
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);

  const rows = (await Promise.all(ids.map((id) => buildRow(env, id).catch(() => null))))
    .filter((r): r is SkinRow => r !== null);
  // newest first when createdAt is present (stable for the rest)
  rows.sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""));

  return json({ skins: rows });
};

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": status === 200 ? "public, max-age=60" : "no-store",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
