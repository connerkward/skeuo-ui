// ============================================================
// POST /api/generate — Cloudflare Pages Function.
//
// Runs the LAYOUT-FIRST pipeline (radial/capsule/minimal) entirely
// server-side: ports of layout_radial/capsule/minimal + the wells
// blueprint draw, then the two fal passes (envelope → paint). The final
// alpha is keyed out of the PAINTED silhouette (cutout), so the body
// follows the expanded outline instead of shrink-wrapping the controls.
// FAL_KEY comes from the env binding and is NEVER sent to the client.
//
// ------------------------------------------------------------------
// HONEST PRODUCTION-STUB LIST (what is NOT production-grade here):
//   1. RATE LIMIT is in-memory per isolate (src/generate/ratelimit.ts).
//      It does NOT persist across restarts and is NOT shared across CF
//      edge locations — each isolate has its own counter, so the real
//      ceiling is (locations × cap). For production, back it with KV or
//      a Durable Object keyed by IP+day, and the cost cap with the same.
//   2. STORAGE: with no R2 binding, the frame is returned as a data: URL
//      (fine to demo, heavy on the wire). Bind R2 (env.SKINS) and the
//      pipeline's store() persists frame.png + template.json + meta.json
//      under skins/<id>/ and returns public /api/asset URLs, so every skin
//      is a shared cloud artifact rebuildable by id (see /api/skin/<id>).
//   3. (fixed) ALPHA MASK now traces the wild outline: it is keyed out of
//      the PAINTED silhouette (cutout — non-white body, largest connected
//      component, internal holes filled), so horns/jaws/legs are kept and
//      the body no longer shrink-wraps to the control cluster. Controls
//      never get holes (their dark wells are non-white → filled as body).
//   4. SYNCHRONOUS: this awaits both fal passes inline (~30-90s). A CF
//      Function can exceed the default execution window on slow paints;
//      production should enqueue (Queues/DO) and let the client poll the
//      /api/generate?jobId=… branch (contract already has "pending").
//   5. No auth, no abuse detection beyond the IP cap; no input
//      moderation on the free-text prompt.
// ------------------------------------------------------------------
import { initWasm, Resvg } from "@resvg/resvg-wasm";
// @ts-expect-error — wasm asset import resolved by the CF/wrangler bundler
import resvgWasm from "@resvg/resvg-wasm/index_bg.wasm";
import { handleGenerate } from "../../src/generate/handler";
import { MODELS, DEFAULT_MODEL, type ModelId, type RuntimeDeps } from "../../src/generate/pipeline";

interface Env {
  FAL_KEY: string;
  OPENAI_API_KEY?: string;   // optional: Director (prompt → material). NEVER sent to client.
  SKINS?: R2Bucket;          // optional R2 bucket binding
  ASSETS_BASE_URL?: string;  // public base for stored frames (e.g. https://cdn/skins)
  RATELIMIT?: KVNamespace;   // lifetime spend ledger (edge-shared) — see below
  SPEND_CAP_CENTS?: string;  // lifetime budget ceiling in cents (default 1000 = $10)
}

// ---- $10 LIFETIME spend cap (KV ledger, NOT auto-resetting) -----------------
// A cumulative dollar budget for the whole public endpoint. We keep a single
// running total `spend:cents` in the RATELIMIT KV — NO TTL, so it never silently
// resets the way the old per-day count did. The cap is SPEND_CAP_CENTS (default
// 1000 = $10). Each request estimates its own cost from the chosen model and the
// envelope factor; if spend + estCost would exceed the cap we refuse BEFORE
// paying fal, and only ADD the cost AFTER a successful (cost-incurring) gen.
//
// TOP-UP / RESET (owner only): the budget does not refill itself. To reopen
// generation, either zero the ledger or raise the cap:
//   npx wrangler kv key put --binding RATELIMIT spend:cents 0 --remote
//   (or set a higher SPEND_CAP_CENTS env var in the Pages dashboard)
// Read the current total any time:
//   npx wrangler kv key get --binding RATELIMIT spend:cents --remote
const SPEND_KEY = "spend:cents";
const DEFAULT_CAP_CENTS = 1000;

// Estimate the cost of ONE generation in cents. costPerSkin in MODELS already
// covers the two paid passes (envelope + paint) at full price; when the envelope
// pass is skipped (envelope:false or a user-uploaded envelope) only the paint
// pass runs, so we bill the ~0.55 fraction. This is an ESTIMATE for the ceiling —
// the real bill is whatever fal charges. We Math.ceil so we lean toward stopping
// early, not overspending.
function estCostCents(model: ModelId, envelope: boolean): number {
  const m = MODELS.find((x) => x.id === model) ?? MODELS.find((x) => x.id === DEFAULT_MODEL)!;
  const dollars = m.costPerSkin * (envelope ? 1 : 0.55);
  return Math.ceil(dollars * 100);
}

let wasmReady: Promise<void> | null = null;
function ensureWasm(): Promise<void> {
  if (!wasmReady) wasmReady = initWasm(resvgWasm as ArrayBuffer | WebAssembly.Module);
  return wasmReady;
}

async function rasterize(svg: string): Promise<Uint8Array> {
  await ensureWasm();
  const r = new Resvg(svg, { fitTo: { mode: "original" } });
  return r.render().asPng();
}

// NOTE: the alpha cutout (UPNG decode/encode + cutoutAlpha connected-components/
// flood-fill, ~2s of pure-JS CPU on a 2K paint) used to run HERE and tripped the
// Pages Function CPU ceiling → CF 1102 "Worker exceeded CPU time limit". It now
// runs in the BROWSER: this Function omits `cutout` from deps, so the pipeline
// persists the raw paint and the client cuts + uploads frame.png back to R2 via
// /api/finalize/<id> (a no-CPU write). See src/generate/pipeline.ts step 5/6 and
// src/generate/cutoutClient.ts.

function clientIp(req: Request): string {
  return req.headers.get("CF-Connecting-IP") || req.headers.get("X-Forwarded-For") || "anon";
}

export const onRequestPost = async (ctx: { request: Request; env: Env }): Promise<Response> => {
  const { request, env } = ctx;
  if (!env.FAL_KEY) return json({ status: "error", error: "server missing FAL_KEY" }, 500);
  let body: any;
  try { body = await request.json(); } catch { return json({ status: "error", error: "invalid JSON" }, 400); }

  // R2 store for EVERY generated skin: frame.png (binary) + template.json + meta.json
  // (JSON strings) under skins/<id>/, served publicly via /api/asset/skins/<id>/…
  // (ASSETS_BASE_URL defaults to the same-origin asset route, so a deploy needs no
  // extra var). Returns each object's public URL.
  const assetBase = env.ASSETS_BASE_URL ?? "/api/asset";
  const deps: RuntimeDeps = {
    falKey: env.FAL_KEY,
    openaiKey: env.OPENAI_API_KEY,
    rasterize,
    // NO `cutout`: deferred to the browser to stay under the Function CPU ceiling.
    store: env.SKINS
      ? async (id, kind, data) => {
          const isImg = kind === "frame" || kind === "paint";
          const ext = isImg ? "png" : "json";
          const contentType = isImg ? "image/png" : "application/json";
          const key = `skins/${id}/${kind}.${ext}`;
          await env.SKINS!.put(key, data, { httpMetadata: { contentType } });
          return `${assetBase}/${key}`;
        }
      : undefined,
  };

  // $10 LIFETIME spend cap (edge-shared via KV ledger) — a cumulative-dollars
  // budget that does NOT auto-reset. Estimate THIS request's cost from the model +
  // envelope factor; refuse BEFORE paying fal if it would push us over the cap.
  // Per-IP limiting still happens inside handleGenerate; this is the cost backstop.
  const cap = Number(env.SPEND_CAP_CENTS ?? String(DEFAULT_CAP_CENTS));
  const model = (body?.model as ModelId) ?? DEFAULT_MODEL;
  const envelope = body?.envelope ?? true;
  const est = estCostCents(model, envelope);
  let spent = 0;
  if (env.RATELIMIT) {
    spent = Number((await env.RATELIMIT.get(SPEND_KEY)) ?? "0");
    if (spent + est > cap) {
      return json({ status: "error", error: "Budget exhausted — generation paused until the owner tops up." }, 429);
    }
  }

  const res = await handleGenerate({ body, ip: clientIp(request), deps });

  // Only a SUCCESSFUL (cost-incurring) generation adds to the ledger. KV is
  // eventually consistent, so a couple of concurrent gens could under-count under
  // burst — acceptable slack for a cost ceiling. No TTL: it's a lifetime budget.
  if (env.RATELIMIT && res.status === "done") {
    const cur = Number((await env.RATELIMIT.get(SPEND_KEY)) ?? "0");
    await env.RATELIMIT.put(SPEND_KEY, String(cur + est));
  }
  return json(res, res.status === "error" ? 429 : 200);
};

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
}
