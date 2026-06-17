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
//      pipeline's store() persists frame.png and returns a public URL.
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
import UPNG from "upng-js";
import { handleGenerate } from "../../src/generate/handler";
import type { RuntimeDeps } from "../../src/generate/pipeline";
import { cutoutAlpha } from "../../src/generate/blueprint";

interface Env {
  FAL_KEY: string;
  OPENAI_API_KEY?: string;   // optional: Director (prompt → material). NEVER sent to client.
  SKINS?: R2Bucket;          // optional R2 bucket binding
  ASSETS_BASE_URL?: string;  // public base for stored frames (e.g. https://cdn/skins)
  RATELIMIT?: KVNamespace;   // global daily spend cap (edge-shared) — see below
  GEN_DAILY_CAP?: string;    // max paid generations/day across ALL users (default 40)
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

// Key the near-white background out of the PAINTED silhouette → RGBA PNG.
// The paint prompt forces "everything outside the silhouette stays pure white",
// so the non-white region is the real (expanded) outline. cutoutAlpha (shared,
// in blueprint.ts) does the threshold + largest-CC + hole-fill + 1px erode; we
// only decode the PNG here and stamp the returned alpha plane back in.
// Pure-JS via UPNG so it runs in the Worker with no native sharp.
const toAB = (u: Uint8Array): ArrayBuffer => u.buffer.slice(u.byteOffset, u.byteOffset + u.byteLength) as ArrayBuffer;
async function cutout(paintPng: Uint8Array): Promise<Uint8Array> {
  const p = UPNG.decode(toAB(paintPng));
  const pr = new Uint8Array(UPNG.toRGBA8(p)[0]);   // RGBA, p.width×p.height
  const W = p.width, H = p.height;
  const alpha = cutoutAlpha(pr, W, H);
  for (let i = 0; i < W * H; i++) pr[i * 4 + 3] = alpha[i];
  return new Uint8Array(UPNG.encode([pr.buffer], W, H, 0));
}

function clientIp(req: Request): string {
  return req.headers.get("CF-Connecting-IP") || req.headers.get("X-Forwarded-For") || "anon";
}

export const onRequestPost = async (ctx: { request: Request; env: Env }): Promise<Response> => {
  const { request, env } = ctx;
  if (!env.FAL_KEY) return json({ status: "error", error: "server missing FAL_KEY" }, 500);
  let body: any;
  try { body = await request.json(); } catch { return json({ status: "error", error: "invalid JSON" }, 400); }

  const deps: RuntimeDeps = {
    falKey: env.FAL_KEY,
    openaiKey: env.OPENAI_API_KEY,
    rasterize,
    cutout,
    store: env.SKINS
      ? async (id, kind, png) => {
          const key = `skins/${id}/${kind}.png`;
          await env.SKINS!.put(key, png, { httpMetadata: { contentType: "image/png" } });
          const base = env.ASSETS_BASE_URL ?? "";
          return `${base}/${key}`;
        }
      : undefined,
  };

  // GLOBAL daily spend cap (edge-shared via KV) — hard ceiling on paid generations
  // so a public, discoverable endpoint can't run away with the account's fal/OpenAI
  // bill. Per-IP limiting still happens inside handleGenerate; this is the backstop.
  // Only SUCCESSFUL (cost-incurring) generations count. KV is eventually consistent,
  // so a few may slip under burst — fine for a cost ceiling. 2-day TTL auto-cleans.
  const cap = Number(env.GEN_DAILY_CAP ?? "40");
  const capKey = `gen:${new Date().toISOString().slice(0, 10)}`;
  if (env.RATELIMIT) {
    const used = Number((await env.RATELIMIT.get(capKey)) ?? "0");
    if (used >= cap) {
      return json({ status: "error", error: `Daily generation limit reached (${cap}/day across everyone). Try again tomorrow.` }, 429);
    }
  }

  const res = await handleGenerate({ body, ip: clientIp(request), deps });

  if (env.RATELIMIT && res.status === "done") {
    const used = Number((await env.RATELIMIT.get(capKey)) ?? "0");
    await env.RATELIMIT.put(capKey, String(used + 1), { expirationTtl: 172800 });
  }
  return json(res, res.status === "error" ? 429 : 200);
};

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
}
