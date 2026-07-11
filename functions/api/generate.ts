// ============================================================
// POST /api/generate — Cloudflare Pages Function.
// GET  /api/generate?jobId=<id> — poll a job started by the POST above.
//
// Runs the LAYOUT-FIRST pipeline (radial/capsule/minimal) entirely
// server-side: ports of layout_radial/capsule/minimal + the wells
// blueprint draw, then the fal paint pass. The final alpha is keyed out
// of the PAINTED silhouette via BiRefNet (see below), so the body follows
// the real painted outline instead of shrink-wrapping the controls.
// FAL_KEY comes from the env binding and is NEVER sent to the client.
//
// ------------------------------------------------------------------
// PRODUCTION-HARDENING STATUS (2026-07-11 audit — see TODO.md "Generation
// feature — production hardening" for the source ask). Reconciled honestly
// against what's ACTUALLY deployed, not what a stale comment used to claim:
//
//   1. ALPHA MASK — DONE, via a better mechanism than originally proposed.
//      The TODO asked for a server-side envelope-threshold pass (porting the
//      Python pipeline's threshold-the-envelope-PNG approach). That's NOT
//      what shipped — instead, the device frame AND every control sprite are
//      background-removed by fal-ai/birefnet/v2 (a real trained segmentation
//      model) called server-side via /api/cutout, matting the ACTUAL painted
//      pixels rather than thresholding a synthetic envelope. Verified live
//      against skeuo.fm 2026-07-11: the returned alpha traces gear teeth,
//      notches and cut-through holes — an 84% fill ratio inside its bbox,
//      not a rectangle/ellipse constant mask. The only remaining constant-
//      mask path is the LEGACY/DEMO fallback in cutoutClient.ts
//      (whiteKeyCanvas), which only fires when there's no `layout` (an old
//      caller) or the paint is a data: URL (offline demo, no R2) — GenerateDone.layout
//      is a REQUIRED field in production, so this path never runs for a real
//      deployed generation.
//   2. STORAGE — DONE. The SKINS R2 bucket (skeuo-skins, created 2026-06-17)
//      is bound below and `store()` persists paint.png/template.json/meta.json
//      under skins/<id>/ at generation time; the browser then uploads the cut
//      frame.png + sprites/<bind>.png via /api/finalize (see cutoutClient.ts).
//      Every asset is served publicly + immutably via /api/asset/<key>
//      (functions/api/asset), and a whole skin is rebuildable by id via
//      /api/skin/<id>. No response returns a data: URL frame in production.
//   3. RATE LIMIT — DONE (KV, not a Durable Object — see justification
//      below). src/generate/meter.ts is an edge-shared KV ledger: a lifetime
//      spend cap (RATELIMIT key spend:cents, read by /api/budget) PLUS a
//      per-IP/day bucket, both RESERVED before the paid fal call and
//      refunded on failure. This already replaced the in-memory per-isolate
//      limiter the TODO was written against; as of this pass the OLD
//      duplicate (src/generate/ratelimit.ts, still wired into handler.ts as
//      a second non-durable check) was deleted so there is exactly ONE rate
//      limiter, and it's the durable one. KV over a Durable Object: this is
//      a hobby endpoint with single-digit-dollar spend caps, not a system
//      needing strict per-request atomicity — a DO would remove the
//      documented eventual-consistency race (a concurrent burst can
//      overshoot the cap slightly) but that's a acceptable coarse-window
//      tradeoff here, not a real production risk at this traffic level.
//   4. ASYNC / 75s SYNCHRONOUS REQUEST — PARTIAL, documented honestly below
//      (search "JOB STATE").
// ------------------------------------------------------------------
import { initWasm, Resvg } from "@resvg/resvg-wasm";
// @ts-expect-error — wasm asset import resolved by the CF/wrangler bundler
import resvgWasm from "@resvg/resvg-wasm/index_bg.wasm";
import { handleGenerate } from "../../src/generate/handler";
import { MODELS, DEFAULT_MODEL, type ModelId, type RuntimeDeps } from "../../src/generate/pipeline";
import type { GenerateResponse, GenerateDone, GenerateError } from "../../src/generate/api";
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
  RATELIMIT?: KVNamespace;   // lifetime spend ledger (edge-shared) + job state — see below
  SPEND_CAP_CENTS?: string;  // lifetime budget ceiling in cents (default 1000 = $10)
}

// Cloudflare Pages Functions' EventContext carries `waitUntil` (extend execution past
// the point the Response is returned / the client disconnects) even though the ad-hoc
// ctx type below historically omitted it. Needed for JOB STATE below.
type Ctx = { request: Request; env: Env; waitUntil: (promise: Promise<unknown>) => void };

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
// Pages Function CPU ceiling → CF error 1102 "Worker exceeded CPU time limit". It now
// runs in the BROWSER via fal BiRefNet (server-proxied through /api/cutout so FAL_KEY
// never reaches the client): this Function omits `cutout` from deps, so the pipeline
// persists the raw paint and the client cuts + uploads frame.png back to R2 via
// /api/finalize/<id> (a no-CPU write). See src/generate/pipeline.ts step 5/6 and
// src/generate/cutoutClient.ts.

function clientIp(req: Request): string {
  return req.headers.get("CF-Connecting-IP") || req.headers.get("X-Forwarded-For") || "anon";
}

// ---- JOB STATE (item 4: async queue for the ~75s synchronous request) ------------
//
// HONEST CONSTRAINT, checked against Cloudflare's own docs before building this
// (verify-external-claims-rule): Pages Functions CAN bind a Queues PRODUCER, but
// CANNOT consume a queue — consuming requires a separate standalone Worker service
// (its own deployment, its own wrangler.toml), not a Pages Function. Standing up a
// second Worker just to consume one queue is disproportionate for a hobby app whose
// whole generation feature lives in this one Pages project — ruled out.
//
// The other documented option, `ctx.waitUntil()`, extends execution AT MOST ~30s
// past the point the client disconnects or the response is returned — it does NOT
// make a 30-90s pipeline durable against an early disconnect. So this is NOT a real
// queue: it's the best available shape given those two constraints —
//   • the existing NDJSON stream stays the PRIMARY path (unchanged UX — the user
//     watches their actual skin form, via PipelineVisualizer/AgentObserver);
//   • a jobId is minted up front and the LAST-KNOWN state is checkpointed into KV
//     (RATELIMIT, `job:<jobId>`, 1h TTL) as the pipeline runs;
//   • the whole pipeline execution is also wrapped in ctx.waitUntil(), so a client
//     disconnect in roughly the LAST 30s of a paint (mobile Safari backgrounding the
//     tab, a flaky connection) still lets the run finish and land in KV instead of
//     silently wasting the paid fal call;
//   • GET /api/generate?jobId=<id> lets the client RECOVER that result instead of
//     re-submitting (and re-paying for) a duplicate generation. This is the
//     GeneratePending branch already defined in src/generate/api.ts.
// A disconnect EARLIER than ~30s before completion genuinely loses the job — the
// isolate is torn down and nothing runs to persist it. That's the honest limit of
// what's available without standing up a second Worker + Queues consumer.
const JOB_TTL_SECONDS = 3600;          // 1h — ample for polling/recovery, not a permanent store
const JOB_STALE_MS = 150_000;          // longer than any observed paint (23-90s) + the waitUntil grace

interface JobPendingState { status: "pending"; startedAt: number }
// NOT `GenerateResponse` — that union's own GeneratePending has a DIFFERENT "pending"
// shape ({status,jobId}, no startedAt). We only ever persist our own JobPendingState
// while running, and a terminal GenerateDone/GenerateError once the pipeline finishes.
type JobState = JobPendingState | GenerateDone | GenerateError;

async function readJob(env: Env, jobId: string): Promise<JobState | null> {
  if (!env.RATELIMIT) return null;
  const raw = await env.RATELIMIT.get(`job:${jobId}`);
  if (!raw) return null;
  try { return JSON.parse(raw) as JobState; } catch { return null; }
}
async function writeJob(env: Env, jobId: string, state: JobState): Promise<void> {
  if (!env.RATELIMIT) return;
  try { await env.RATELIMIT.put(`job:${jobId}`, JSON.stringify(state), { expirationTtl: JOB_TTL_SECONDS }); }
  catch { /* best-effort — the stream is still the primary path */ }
}

// GET /api/generate?jobId=<id> — poll a job. `{status:"pending", jobId}` matches
// GeneratePending in src/generate/api.ts; the client already has that branch's shape.
export const onRequestGet = async (ctx: Ctx): Promise<Response> => {
  const { request, env } = ctx;
  const jobId = new URL(request.url).searchParams.get("jobId");
  if (!jobId) return json({ status: "error", error: "jobId required" }, 400);
  const job = await readJob(env, jobId);
  if (!job) return json({ status: "error", error: "job not found or expired" }, 404);
  if (job.status === "pending") {
    if (Date.now() - job.startedAt > JOB_STALE_MS) {
      return json({ status: "error", error: "generation likely interrupted (connection lost) — try again" }, 200);
    }
    return json({ status: "pending", jobId }, 200);
  }
  return json(job, 200);
};

export const onRequestPost = async (ctx: Ctx): Promise<Response> => {
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

  const jobId = crypto.randomUUID();
  await writeJob(env, jobId, { status: "pending", startedAt: Date.now() });

  // STREAM the response as NDJSON: each pipeline pass emits a {stage,url} line as it
  // completes (blueprint → grown body → painted skin) so the client can preview the
  // user's ACTUAL skin forming, then the final GenerateResponse is the LAST line. The
  // very FIRST line carries {jobId} so the client can recover via GET on disconnect
  // (see "JOB STATE" above). The fal awaits are I/O (not CPU), so streaming doesn't
  // change the Function's CPU budget — the cutout still runs in the browser. Spend
  // pre-check already happened above (a plain JSON 429); billing the ledger happens
  // after a successful gen here.
  const encoder = new TextEncoder();
  const run = async (controller: ReadableStreamDefaultController<Uint8Array>): Promise<void> => {
    const write = (obj: unknown) => {
      try { controller.enqueue(encoder.encode(JSON.stringify(obj) + "\n")); } catch { /* client disconnected */ }
    };
    write({ jobId });
    const streamDeps: RuntimeDeps = { ...deps, onStage: (stage, url) => write({ stage, url }) };
    let res: GenerateResponse;
    try {
      res = await handleGenerate({ body, ip, deps: streamDeps });
    } catch (e) {
      res = { status: "error", error: e instanceof Error ? e.message : String(e) };
    }
    write(res);   // final line (carries `status`, no `stage`)
    // handleGenerate only ever returns "done" | "error" (GeneratePending is purely a
    // client-facing polling-response shape, never something the handler produces) —
    // narrow defensively so a hypothetical future "pending" from the handler can't
    // silently corrupt the job store's own pending marker (JobPendingState).
    await writeJob(env, jobId, res.status === "pending"
      ? { status: "error", error: "internal: handler returned pending unexpectedly" }
      : res);
    // Cost was RESERVED up front; refund it if the generation didn't actually
    // incur fal cost (error / no paint pass run). A `done` keeps the reservation.
    if (res.status !== "done") await refund(env, ip, est, GEN_BUCKET);
    try { controller.close(); } catch { /* already closed by a client-disconnect cancel() */ }
  };
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      // Extend execution ~30s past a client disconnect (Cloudflare's documented
      // waitUntil ceiling) so a late-stage drop still finishes + lands in KV instead
      // of silently discarding a paid fal call. Not awaited here — the stream stays
      // open (and keeps writing) exactly as before for a connected client; waitUntil
      // is purely the disconnect-survival path.
      const p = run(controller);
      ctx.waitUntil(p);
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "application/x-ndjson", ...CORS } });
};

// CORS: the native shells (iOS app, macOS widget) POST here from the tauri://
// origin. application/json is a non-simple content type, so the browser sends a
// preflight OPTIONS first. Generation is public + spend-capped — `*` is fine.
const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};
export const onRequestOptions = (): Response => new Response(null, { status: 204, headers: CORS });

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...CORS } });
}
