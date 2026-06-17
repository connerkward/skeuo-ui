// ============================================================
// POST /api/generate — Cloudflare Pages Function.
//
// Runs the LAYOUT-FIRST pipeline (radial/capsule/minimal) entirely
// server-side: ports of layout_radial/capsule/minimal + the wells
// blueprint draw, then the two fal passes (envelope → paint), with the
// constant drawn region mask as alpha (no BiRefNet). FAL_KEY comes from
// the env binding and is NEVER sent to the client.
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
//   3. ALPHA MASK is the LOOSE constant region mask (union of dilated
//      well/screen footprints), not the wild outline the Python derives
//      from the fal-generated envelope image. The frame therefore keeps
//      a rectangular-ish bounding alpha rather than tracing horns/jaws.
//      Tightening it means thresholding the envelope PNG server-side
//      (an extra decode) — deferred for v1. Controls never get holes.
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

interface Env {
  FAL_KEY: string;
  OPENAI_API_KEY?: string;   // optional: Director (prompt → material). NEVER sent to client.
  SKINS?: R2Bucket;          // optional R2 bucket binding
  ASSETS_BASE_URL?: string;  // public base for stored frames (e.g. https://cdn/skins)
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

// paint (RGBA PNG) × alpha (grayscale PNG, white=opaque) → RGBA PNG.
// Pure-JS via UPNG so it runs in the Worker with no native sharp.
const toAB = (u: Uint8Array): ArrayBuffer => u.buffer.slice(u.byteOffset, u.byteOffset + u.byteLength) as ArrayBuffer;
async function composite(paintPng: Uint8Array, alphaPng: Uint8Array): Promise<Uint8Array> {
  const p = UPNG.decode(toAB(paintPng));
  const pr = new Uint8Array(UPNG.toRGBA8(p)[0]);   // RGBA, p.width×p.height
  const a = UPNG.decode(toAB(alphaPng));
  const ar = new Uint8Array(UPNG.toRGBA8(a)[0]);
  const W = p.width, H = p.height;
  // alpha image may differ in size; sample nearest
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const ax = Math.min(a.width - 1, (x * a.width / W) | 0);
      const ay = Math.min(a.height - 1, (y * a.height / H) | 0);
      pr[(y * W + x) * 4 + 3] = ar[(ay * a.width + ax) * 4]; // red of mask → alpha
    }
  }
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
    composite,
    store: env.SKINS
      ? async (id, kind, png) => {
          const key = `skins/${id}/${kind}.png`;
          await env.SKINS!.put(key, png, { httpMetadata: { contentType: "image/png" } });
          const base = env.ASSETS_BASE_URL ?? "";
          return `${base}/${key}`;
        }
      : undefined,
  };

  const res = await handleGenerate({ body, ip: clientIp(request), deps });
  return json(res, res.status === "error" ? 429 : 200);
};

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
}
