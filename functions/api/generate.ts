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
import { reserve, refund, GEN_BUCKET } from "../../src/generate/meter";

interface Env {
  FAL_KEY: string;
  // Director auth (prompt/vision → material/layout/control-boxes). NEVER sent to the
  // client. Vertex-only (src/generate/director.ts + vertexAuth.ts) — ZERO OpenAI, ZERO
  // gpt-4o. A service-account JSON key exchanged for a Vertex access token via the
  // standard JWT-bearer flow (RS256, WebCrypto — no gcloud/child_process needed in the
  // Worker). Also used by the vision-based extractSlots/extractMasks control-locator
  // calls in functions/api/extract.ts (same Vertex Gemini model, same secret).
  //
  // DEPLOY STEP REQUIRED (one-time):
  //   1. gcloud iam service-accounts create skeuo-vertex --project=muser-2605300220
  //   2. gcloud projects add-iam-policy-binding muser-2605300220 \
  //        --member="serviceAccount:skeuo-vertex@muser-2605300220.iam.gserviceaccount.com" \
  //        --role="roles/aiplatform.user"
  //   3. gcloud iam service-accounts keys create sa-key.json \
  //        --iam-account=skeuo-vertex@muser-2605300220.iam.gserviceaccount.com
  //   4. npx wrangler pages secret put GCP_SERVICE_ACCOUNT_KEY < sa-key.json
  //   5. rm sa-key.json (never commit it — see security-rule)
  // Until this secret is set, every Director call transparently falls back to the
  // deterministic heuristic (heuristic() in director.ts) / null layout / empty boxes —
  // generation never breaks, it just loses the LLM-derived material/layout/VLM-align.
  GCP_SERVICE_ACCOUNT_KEY?: string;
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

// Estimate the cost of ONE generation's PAINT pass in cents. The pipeline is now
// single-pass (the envelope pass was removed), so costPerSkin is already the
// upper-bound estimate for that one paint pass — no envelope factor. The separate
// BiRefNet cutout the client runs afterward is metered by /api/cutout, so it is
// NOT double-counted here. Math.ceil → lean toward stopping early, not overspending.
function estCostCents(model: ModelId): number {
  const m = MODELS.find((x) => x.id === model) ?? MODELS.find((x) => x.id === DEFAULT_MODEL)!;
  return Math.ceil(m.costPerSkin * 100);
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
    gcpServiceAccountKey: env.GCP_SERVICE_ACCOUNT_KEY,
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

  // LIFETIME spend cap + per-IP/day cap, both edge-shared via the RATELIMIT KV
  // (see src/generate/meter.ts). RESERVE the estimated cost up front; refuse BEFORE
  // paying fal if it would exceed the cap or the per-IP/day limit, and refund the
  // reservation below if the generation didn't actually incur cost.
  const ip = clientIp(request);
  const model = (body?.model as ModelId) ?? DEFAULT_MODEL;
  const est = estCostCents(model);
  const res0 = await reserve(env, ip, est, GEN_BUCKET);
  if (!res0.ok) return json({ status: "error", error: res0.reason }, 429);

  // STREAM the response as NDJSON: each pipeline pass emits a {stage,url} line as it
  // completes (blueprint → grown body → painted skin) so the client can preview the
  // user's ACTUAL skin forming, then the final GenerateResponse is the LAST line.
  // The fal awaits are I/O (not CPU), so streaming doesn't change the Function's CPU
  // budget — the cutout still runs in the browser. Spend pre-check already happened
  // above (a plain JSON 429); billing the ledger happens after a successful gen here.
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const write = (obj: unknown) => {
        try { controller.enqueue(encoder.encode(JSON.stringify(obj) + "\n")); } catch { /* client disconnected */ }
      };
      const streamDeps: RuntimeDeps = { ...deps, onStage: (stage, url) => write({ stage, url }) };
      let res: Awaited<ReturnType<typeof handleGenerate>>;
      try {
        res = await handleGenerate({ body, ip, deps: streamDeps });
      } catch (e) {
        res = { status: "error", error: e instanceof Error ? e.message : String(e) };
      }
      write(res);   // final line (carries `status`, no `stage`)
      // Cost was RESERVED up front; refund it if the generation didn't actually
      // incur fal cost (error / no paint pass run). A `done` keeps the reservation.
      if (res.status !== "done") await refund(env, ip, est, GEN_BUCKET);
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "application/x-ndjson", ...CORS } });
};

// CORS: the native shells (iOS app, macOS widget) POST here from the tauri://
// origin. application/json is a non-simple content type, so the browser sends a
// preflight OPTIONS first. Generation is public + spend-capped — `*` is fine.
const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};
export const onRequestOptions = (): Response => new Response(null, { status: 204, headers: CORS });

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...CORS } });
}
