// Vite dev-server middleware that serves POST /api/generate LOCALLY using the
// SAME shared pipeline as the Cloudflare Function (src/generate/*). Lets the
// Create panel work in `npm run dev` with no Cloudflare account. Rasterizes with
// the native @resvg/resvg-js (fast, no wasm init) and composites with UPNG.
//
// FAL_KEY is read SERVER-SIDE ONLY here — from .dev.vars (gitignored) or, as a
// dev convenience on this machine, central/.env. It is never bundled into client
// code and never returned to the browser.
import type { Plugin, ViteDevServer } from "vite";
import { readFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { Resvg } from "@resvg/resvg-js";
import UPNG from "upng-js";
import { handleGenerate } from "../src/generate/handler";
import type { RuntimeDeps } from "../src/generate/pipeline";
import { cutoutAlpha } from "../src/generate/blueprint";

// Read a key from .dev.vars → process.env → central/.env (dev convenience),
// the same precedence used for both FAL_KEY and OPENAI_API_KEY.
function loadKey(root: string, name: string): string | undefined {
  const devVars = resolve(root, ".dev.vars");
  if (existsSync(devVars)) {
    const m = readFileSync(devVars, "utf8").match(new RegExp(`^${name}=(.+)$`, "m"));
    if (m) return m[1].trim();
  }
  if (process.env[name]) return process.env[name];
  const central = "/Users/conner/dev/central/.env";
  if (existsSync(central)) {
    const m = readFileSync(central, "utf8").match(new RegExp(`^${name}=(.+)$`, "m"));
    if (m) return m[1].trim();
  }
  return undefined;
}

function rasterize(svg: string): Promise<Uint8Array> {
  const r = new Resvg(svg, { fitTo: { mode: "original" } });
  return Promise.resolve(new Uint8Array(r.render().asPng()));
}

// Key the near-white background out of the PAINTED silhouette → RGBA PNG.
// The paint prompt forces "everything outside the silhouette stays pure white",
// so the non-white region is the real (expanded) body outline. Steps: threshold
// non-white → body mask; keep the largest connected component (drop stray specks);
// fill internal holes (so dark control wells inside the body stay opaque); a light
// 1px erode to kill the white halo at the edge. See cutoutAlpha() (shared logic).
function cutout(paintPng: Uint8Array): Promise<Uint8Array> {
  const p = UPNG.decode(toAB(paintPng));
  const pr = new Uint8Array(UPNG.toRGBA8(p)[0]);
  const W = p.width, H = p.height;
  const alpha = cutoutAlpha(pr, W, H);
  for (let i = 0; i < W * H; i++) pr[i * 4 + 3] = alpha[i];
  return Promise.resolve(new Uint8Array(UPNG.encode([pr.buffer], W, H, 0)));
}
const toAB = (u: Uint8Array): ArrayBuffer => u.buffer.slice(u.byteOffset, u.byteOffset + u.byteLength) as ArrayBuffer;

export function devApiPlugin(): Plugin {
  return {
    name: "skeuo-dev-api",
    configureServer(server: ViteDevServer) {
      const falKey = loadKey(server.config.root, "FAL_KEY");
      const openaiKey = loadKey(server.config.root, "OPENAI_API_KEY");
      // persist generated frames to public/generated/ so a page reload or dev-server
      // restart no longer wipes a just-created skin (the client stores only the URL).
      const genDir = resolve(server.config.root, "public", "generated");
      const store = async (id: string, kind: "frame", png: Uint8Array): Promise<string> => {
        mkdirSync(genDir, { recursive: true });
        writeFileSync(resolve(genDir, `${id}-${kind}.png`), png);
        return `/generated/${id}-${kind}.png`;
      };
      server.middlewares.use("/api/generate", (req, res) => {
        if (req.method !== "POST") { res.statusCode = 405; res.end("POST only"); return; }
        if (!falKey) { res.statusCode = 500; res.end(JSON.stringify({ status: "error", error: "server missing FAL_KEY (.dev.vars)" })); return; }
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c as Buffer));
        req.on("end", async () => {
          let body: any = {};
          try { body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"); }
          catch { res.statusCode = 400; res.end(JSON.stringify({ status: "error", error: "invalid JSON" })); return; }
          const ip = (req.socket.remoteAddress || "local").toString();
          const deps: RuntimeDeps = { falKey, openaiKey, rasterize, cutout, store, log: (m) => server.config.logger.info(m) };
          try {
            const out = await handleGenerate({ body, ip, deps });
            res.statusCode = out.status === "error" ? 429 : 200;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify(out));
          } catch (e) {
            res.statusCode = 500;
            res.end(JSON.stringify({ status: "error", error: e instanceof Error ? e.message : String(e) }));
          }
        });
      });
    },
  };
}
