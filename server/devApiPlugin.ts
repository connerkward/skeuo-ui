// Vite dev-server middleware that serves POST /api/generate LOCALLY using the
// SAME shared pipeline as the Cloudflare Function (src/generate/*). Lets the
// Create panel work in `npm run dev` with no Cloudflare account. Rasterizes with
// the native @resvg/resvg-js (fast, no wasm init) and composites with UPNG.
//
// FAL_KEY is read SERVER-SIDE ONLY here — from .dev.vars (gitignored) or, as a
// dev convenience on this machine, central/.env. It is never bundled into client
// code and never returned to the browser.
import type { Plugin, ViteDevServer } from "vite";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { Resvg } from "@resvg/resvg-js";
import UPNG from "upng-js";
import { handleGenerate } from "../src/generate/handler";
import type { RuntimeDeps } from "../src/generate/pipeline";

function loadFalKey(root: string): string | undefined {
  // 1. .dev.vars in repo root (Cloudflare convention, gitignored)
  const devVars = resolve(root, ".dev.vars");
  if (existsSync(devVars)) {
    const m = readFileSync(devVars, "utf8").match(/^FAL_KEY=(.+)$/m);
    if (m) return m[1].trim();
  }
  // 2. process env
  if (process.env.FAL_KEY) return process.env.FAL_KEY;
  // 3. dev convenience: central/.env on this machine
  const central = "/Users/conner/dev/central/.env";
  if (existsSync(central)) {
    const m = readFileSync(central, "utf8").match(/^FAL_KEY=(.+)$/m);
    if (m) return m[1].trim();
  }
  return undefined;
}

function rasterize(svg: string): Promise<Uint8Array> {
  const r = new Resvg(svg, { fitTo: { mode: "original" } });
  return Promise.resolve(new Uint8Array(r.render().asPng()));
}

function composite(paintPng: Uint8Array, alphaPng: Uint8Array): Promise<Uint8Array> {
  const p = UPNG.decode(toAB(paintPng));
  const pr = new Uint8Array(UPNG.toRGBA8(p)[0]);
  const a = UPNG.decode(toAB(alphaPng));
  const ar = new Uint8Array(UPNG.toRGBA8(a)[0]);
  const W = p.width, H = p.height;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const ax = Math.min(a.width - 1, ((x * a.width) / W) | 0);
      const ay = Math.min(a.height - 1, ((y * a.height) / H) | 0);
      pr[(y * W + x) * 4 + 3] = ar[(ay * a.width + ax) * 4];
    }
  }
  return Promise.resolve(new Uint8Array(UPNG.encode([pr.buffer], W, H, 0)));
}
const toAB = (u: Uint8Array): ArrayBuffer => u.buffer.slice(u.byteOffset, u.byteOffset + u.byteLength) as ArrayBuffer;

export function devApiPlugin(): Plugin {
  return {
    name: "skeuo-dev-api",
    configureServer(server: ViteDevServer) {
      const falKey = loadFalKey(server.config.root);
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
          const deps: RuntimeDeps = { falKey, rasterize, composite, log: (m) => server.config.logger.info(m) };
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
