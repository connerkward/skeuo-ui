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
import { handleGenerate } from "../src/generate/handler";
import { removeBackground, type RuntimeDeps } from "../src/generate/pipeline";

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

// NOTE: the alpha cutout runs in the BROWSER (see src/generate/cutoutClient.ts),
// not here — dev mirrors the deployed CF Worker path exactly: /api/generate stores
// the RAW paint, the client cuts it and uploads frame.png back via /api/finalize.
// (The Worker must defer it to dodge the Function CPU ceiling / CF 1102; dev mirrors
// it so the one code path is what gets tested locally.)

export function devApiPlugin(): Plugin {
  return {
    name: "skeuo-dev-api",
    configureServer(server: ViteDevServer) {
      const falKey = loadKey(server.config.root, "FAL_KEY");
      const openaiKey = loadKey(server.config.root, "OPENAI_API_KEY");
      // persist generated artifacts to public/generated/ so a page reload or dev-server
      // restart no longer wipes a just-created skin (the client stores only the URL).
      // Mirrors the prod R2 layout: frame.png + template.json + meta.json per skin, so
      // local dev exercises the same store path as the deployed pipeline.
      const genDir = resolve(server.config.root, "public", "generated");
      const store = async (
        id: string,
        kind: "frame" | "paint" | "template" | "meta" | "layout",
        data: Uint8Array | string,
      ): Promise<string> => {
        mkdirSync(genDir, { recursive: true });
        const ext = kind === "frame" || kind === "paint" ? "png" : "json";
        const file = `${id}-${kind}.${ext}`;
        writeFileSync(resolve(genDir, file), data as Uint8Array | string);
        return `/generated/${file}`;
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
          // no `cutout`: deferred to the browser, mirroring the deployed Worker.
          const deps: RuntimeDeps = { falKey, openaiKey, rasterize, store, log: (m) => server.config.logger.info(m) };
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

      // POST /api/cutout — local parity with functions/api/cutout.ts. BiRefNet
      // background removal, server-side (FAL_KEY never reaches the browser). The
      // browser POSTs the cropped device PNG; we return the transparent PNG.
      server.middlewares.use("/api/cutout", (req, res) => {
        if (req.method !== "POST") { res.statusCode = 405; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "POST only" })); return; }
        if (!falKey) { res.statusCode = 500; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "server missing FAL_KEY (.dev.vars)" })); return; }
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c as Buffer));
        req.on("end", async () => {
          try {
            const ct = (req.headers["content-type"] ?? "").toString();
            let png: Uint8Array;
            if (ct.includes("application/json")) {
              const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}") as { imageUrl?: string };
              if (!body.imageUrl) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "imageUrl required" })); return; }
              const r = await fetch(body.imageUrl);
              png = new Uint8Array(await r.arrayBuffer());
            } else {
              png = new Uint8Array(Buffer.concat(chunks));
            }
            const cut = await removeBackground(falKey, png);
            res.statusCode = 200;
            res.setHeader("Content-Type", "image/png");
            res.setHeader("Cache-Control", "no-store");
            res.end(Buffer.from(cut));
          } catch (e) {
            res.statusCode = 502;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }));
          }
        });
      });

      // POST /api/finalize/<id>            → frame.png
      // POST /api/finalize/<id>/sprites/<bind> → sprites/<bind>.png
      // Local parity with functions/api/finalize/[id].ts. The browser uploads the
      // cut device frame and each per-control sprite here, next to the other
      // artifacts, so /api/skin + /share + per-skin sprites work end-to-end.
      const ID_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
      const BIND_RE = /^[a-z0-9][a-z0-9_-]{0,39}$/i;
      server.middlewares.use("/api/finalize/", (req, res) => {
        res.setHeader("Content-Type", "application/json");
        if (req.method !== "POST") { res.statusCode = 405; res.end(JSON.stringify({ error: "POST only" })); return; }
        const pathOnly = (req.url ?? "").replace(/^\/+/, "").split(/[?#]/)[0];
        const segs = pathOnly.split("/").map((s) => decodeURIComponent(s));
        const id = segs[0];
        if (!id || !ID_RE.test(id)) { res.statusCode = 400; res.end(JSON.stringify({ error: "bad id" })); return; }
        if (!existsSync(resolve(genDir, `${id}-template.json`))) { res.statusCode = 404; res.end(JSON.stringify({ error: "unknown skin" })); return; }
        // sprite upload: /<id>/sprites/<bind>
        let bind: string | null = null;
        if (segs.length >= 3 && segs[1] === "sprites") {
          bind = segs[2];
          if (!bind || !BIND_RE.test(bind)) { res.statusCode = 400; res.end(JSON.stringify({ error: "bad bind" })); return; }
        } else if (segs.length !== 1) {
          res.statusCode = 400; res.end(JSON.stringify({ error: "bad finalize path" })); return;
        }
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c as Buffer));
        req.on("end", () => {
          try {
            mkdirSync(genDir, { recursive: true });
            if (bind) {
              // dev flattens R2's skins/<id>/sprites/<bind>.png into one dir.
              const file = `${id}-sprite-${bind}.png`;
              writeFileSync(resolve(genDir, file), Buffer.concat(chunks));
              res.statusCode = 200;
              res.end(JSON.stringify({ id, bind, spriteUrl: `/generated/${file}` }));
            } else {
              writeFileSync(resolve(genDir, `${id}-frame.png`), Buffer.concat(chunks));
              res.statusCode = 200;
              res.end(JSON.stringify({ id, frameUrl: `/generated/${id}-frame.png` }));
            }
          } catch (e) {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }));
          }
        });
      });

      // GET /api/skin/<id> — local parity with the CF Function: reconstruct a
      // shared skin from the files the dev `store` wrote to public/generated/.
      // This makes /share?id=<id> work end-to-end in `npm run dev` for skins
      // generated locally.
      server.middlewares.use("/api/skin/", (req, res) => {
        const id = decodeURIComponent((req.url ?? "").replace(/^\/+/, "").split(/[?#]/)[0]);
        const tplPath = resolve(genDir, `${id}-template.json`);
        const metaPath = resolve(genDir, `${id}-meta.json`);
        res.setHeader("Content-Type", "application/json");
        if (!id || !existsSync(tplPath)) { res.statusCode = 404; res.end(JSON.stringify({ error: "skin not found" })); return; }
        try {
          const template = JSON.parse(readFileSync(tplPath, "utf8"));
          const meta = existsSync(metaPath) ? JSON.parse(readFileSync(metaPath, "utf8")) : null;
          res.statusCode = 200;
          res.end(JSON.stringify({ id, frameUrl: `/generated/${id}-frame.png`, template, meta }));
        } catch (e) {
          res.statusCode = 502;
          res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }));
        }
      });

      // GET /api/budget — local stub of the lifetime spend ledger. There is no KV
      // in dev, so report the full cap as remaining (the real ceiling is enforced
      // at the edge). SPEND_CAP_CENTS env overrides the default $10.
      server.middlewares.use("/api/budget", (_req, res) => {
        const capCents = Number(process.env.SPEND_CAP_CENTS ?? "1000");
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ capCents, spentCents: 0, remainingCents: capCents }));
      });
    },
  };
}
