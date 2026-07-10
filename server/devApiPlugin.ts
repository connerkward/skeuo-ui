// Vite dev-server middleware that serves POST /api/generate LOCALLY using the
// SAME shared pipeline as the Cloudflare Function (src/generate/*). Lets the
// Create panel work in `npm run dev` with no Cloudflare account. Rasterizes with
// the native @resvg/resvg-js (fast, no wasm init) and composites with UPNG.
//
// FAL_KEY is read SERVER-SIDE ONLY here — from .dev.vars (gitignored) or, as a
// dev convenience on this machine, central/.env. It is never bundled into client
// code and never returned to the browser.
import type { Plugin, ViteDevServer } from "vite";
import { readFileSync, existsSync, mkdirSync, writeFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { Resvg } from "@resvg/resvg-js";
import { handleGenerate } from "../src/generate/handler";
import { removeBackground, segmentControls, type RuntimeDeps, type SamBoxPx } from "../src/generate/pipeline";
import { extractSlots, extractMasks, deriveLayout, type SlotControl, type DirectorKeys } from "../src/generate/director";
import { getVertexAccessToken } from "../src/generate/vertexAuth";
import { getGcloudAccessToken } from "./gcloudAuth";

// Read a key from .dev.vars → process.env → central/.env (dev convenience),
// the same precedence used for both FAL_KEY and GCP_SERVICE_ACCOUNT_KEY.
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
      // Director calls (deriveMaterial/deriveLayout/extractSlots/extractMasks) are
      // Vertex-only (src/generate/director.ts) — ZERO OpenAI. In dev they authenticate
      // via the developer's own `gcloud auth print-access-token` session (this machine
      // is already `gcloud auth login`-ed against muser-2605300220 — proven working by
      // tools/mask-align-exp/gen12/genskin.py), so NO key needs to be set here at all.
      // GCP_SERVICE_ACCOUNT_KEY is optional: set it in .dev.vars only to exercise the
      // PROD auth path (the service-account JWT flow) locally instead of gcloud.
      const gcpServiceAccountKey = loadKey(server.config.root, "GCP_SERVICE_ACCOUNT_KEY");
      // resolve a Vertex bearer token fresh per call (cheap — cached ~50min by
      // getGcloudAccessToken / getVertexAccessToken); undefined when gcloud isn't
      // installed/logged-in and no service-account key is set — callers degrade to
      // their deterministic fallback, never throw.
      const directorAuth = (): DirectorKeys => ({ gcpServiceAccountKey, devToken: getGcloudAccessToken() });
      // persist generated artifacts to public/generated/ so a page reload or dev-server
      // restart no longer wipes a just-created skin (the client stores only the URL).
      // Mirrors the prod R2 layout: frame.png + template.json + meta.json per skin, so
      // local dev exercises the same store path as the deployed pipeline.
      const genDir = resolve(server.config.root, "public", "generated");
      const store = async (
        id: string,
        kind: "frame" | "paint" | "template" | "meta" | "layout" | "rawlayout" | "blueprint",
        data: Uint8Array | string,
      ): Promise<string> => {
        mkdirSync(genDir, { recursive: true });
        const ext = kind === "frame" || kind === "paint" || kind === "blueprint" ? "png" : "json";
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
          // STREAM NDJSON, mirroring the CF Function: each pass emits a {stage,url}
          // line as it completes, then the final GenerateResponse is the last line.
          res.statusCode = 200;
          res.setHeader("Content-Type", "application/x-ndjson");
          const write = (obj: unknown) => res.write(JSON.stringify(obj) + "\n");
          // no `cutout`: deferred to the browser, mirroring the deployed Worker.
          const auth = directorAuth();
          const deps: RuntimeDeps = {
            falKey, gcpServiceAccountKey: auth.gcpServiceAccountKey, vertexDevToken: auth.devToken, rasterize, store,
            log: (m) => server.config.logger.info(m),
            onStage: (stage, url) => write({ stage, url }),
          };
          try {
            const out = await handleGenerate({ body, ip, deps });
            write(out);
            res.end();
          } catch (e) {
            write({ status: "error", error: e instanceof Error ? e.message : String(e) });
            res.end();
          }
        });
      });

      // POST /api/derive — the LLM data-template generator for the template studio.
      // Calls the SAME deriveLayout (Gemini 3.1 Pro via Vertex, heuristic-guided
      // LAYOUT_SYS) the pipeline uses, returns the raw Region[] so the studio can
      // seed + pack it. { prompt } → { regions }.
      server.middlewares.use("/api/derive", (req, res) => {
        if (req.method !== "POST") { res.statusCode = 405; res.end("POST only"); return; }
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c as Buffer));
        req.on("end", async () => {
          res.setHeader("Content-Type", "application/json");
          try {
            const { prompt } = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
            const auth = directorAuth();
            const token = await getVertexAccessToken({ serviceAccountKey: auth.gcpServiceAccountKey, devToken: auth.devToken });
            const regions = token ? await deriveLayout(auth, String(prompt || "")) : null;
            res.end(JSON.stringify({ regions: regions ?? [], ok: !!regions, hasKey: !!token }));
          } catch (e) { res.statusCode = 500; res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) })); }
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
            const modelQ = new URL(req.url ?? "", "http://x").searchParams.get("model");
            const model = (modelQ === "General Use (Heavy)" || modelQ === "Matting") ? modelQ : undefined;
            let png: Uint8Array;
            if (ct.includes("application/json")) {
              const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}") as { imageUrl?: string };
              if (!body.imageUrl) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "imageUrl required" })); return; }
              const r = await fetch(body.imageUrl);
              png = new Uint8Array(await r.arrayBuffer());
            } else {
              png = new Uint8Array(Buffer.concat(chunks));
            }
            const cut = await removeBackground(falKey, png, model);
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

      // POST /api/segment — SAM-3.1 per-control masks (server-side FAL_KEY). Body:
      // { imageUrl?|imageDataUrl?, boxes:[{x_min,y_min,x_max,y_max}] } in pixel coords
      // of the posted image. Returns { masks:[{maskUrl,box,score}] } aligned to input.
      server.middlewares.use("/api/segment", (req, res) => {
        if (req.method !== "POST") { res.statusCode = 405; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "POST only" })); return; }
        if (!falKey) { res.statusCode = 500; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "server missing FAL_KEY (.dev.vars)" })); return; }
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c as Buffer));
        req.on("end", async () => {
          try {
            const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}") as
              { imageUrl?: string; imageDataUrl?: string; boxes?: SamBoxPx[] };
            const boxes = body.boxes ?? [];
            if (!boxes.length) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "boxes required" })); return; }
            let png: Uint8Array;
            if (body.imageDataUrl?.startsWith("data:")) {
              png = new Uint8Array(Buffer.from(body.imageDataUrl.split(",")[1], "base64"));
            } else if (body.imageUrl) {
              const r = await fetch(body.imageUrl.startsWith("http") ? body.imageUrl : `http://localhost:${(server.config.server.port ?? 5180)}${body.imageUrl}`);
              png = new Uint8Array(await r.arrayBuffer());
            } else { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "imageUrl or imageDataUrl required" })); return; }
            const masks = await segmentControls(falKey, png, boxes);
            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json");
            res.setHeader("Cache-Control", "no-store");
            res.end(JSON.stringify({ masks }));
          } catch (e) {
            res.statusCode = 502;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }));
          }
        });
      });

      // POST /api/extract — local parity with functions/api/extract.ts. The Director
      // vision model (Gemini 3.1 Pro via Vertex — see director.ts) locates each
      // expected control in the device image. No key required in dev (gcloud auth);
      // returns { boxes: [] } (never a 500) when no Vertex auth is available.
      server.middlewares.use("/api/extract", (req, res) => {
        if (req.method !== "POST") { res.statusCode = 405; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "POST only" })); return; }
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c as Buffer));
        req.on("end", async () => {
          try {
            const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}") as
              { imageDataUrl?: string; imageUrl?: string; controls?: SlotControl[] };
            const image = body.imageDataUrl || body.imageUrl;
            if (!image) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "imageDataUrl required" })); return; }
            if (!Array.isArray(body.controls) || !body.controls.length) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "controls required" })); return; }
            const boxes = await extractSlots(directorAuth(), image, body.controls);
            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json");
            res.setHeader("Cache-Control", "no-store");
            res.end(JSON.stringify({ boxes }));
          } catch (e) {
            res.statusCode = 502;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }));
          }
        });
      });

      // POST /api/maskvlm — VLM-masking arm (head-to-head vs SAM). The Director vision
      // model returns a tight silhouette POLYGON per control. Body { imageDataUrl|imageUrl, controls }.
      server.middlewares.use("/api/maskvlm", (req, res) => {
        if (req.method !== "POST") { res.statusCode = 405; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "POST only" })); return; }
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c as Buffer));
        req.on("end", async () => {
          try {
            const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}") as
              { imageDataUrl?: string; imageUrl?: string; controls?: SlotControl[] };
            const image = body.imageDataUrl || body.imageUrl;
            if (!image) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "imageDataUrl required" })); return; }
            if (!Array.isArray(body.controls) || !body.controls.length) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "controls required" })); return; }
            const polys = await extractMasks(directorAuth(), image, body.controls);
            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json");
            res.setHeader("Cache-Control", "no-store");
            res.end(JSON.stringify({ polys }));
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
        // publish: /<id>/publish — write the dev published marker (<id>-published.json)
        // carrying the small display fields. Parity with the CF Function's
        // published/<id> R2 marker. GET /api/skins lists these as published.
        if (segs.length === 2 && segs[1] === "publish") {
          const chunks2: Buffer[] = [];
          req.on("data", (c) => chunks2.push(c as Buffer));
          req.on("end", () => {
            try {
              let body: Record<string, unknown> = {};
              try { body = JSON.parse(Buffer.concat(chunks2).toString("utf8") || "{}"); } catch { /* ignore */ }
              const marker: Record<string, unknown> = { publishedAt: new Date().toISOString() };
              for (const k of ["name", "blurb", "font", "style"]) {
                if (typeof body[k] === "string") marker[k] = (body[k] as string).slice(0, 200);
              }
              mkdirSync(genDir, { recursive: true });
              writeFileSync(resolve(genDir, `${id}-published.json`), JSON.stringify(marker));
              res.statusCode = 200;
              res.end(JSON.stringify({ id, published: true }));
            } catch (e) {
              res.statusCode = 500;
              res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }));
            }
          });
          return;
        }
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

      // GET /api/skins — local parity with functions/api/skins.ts: the cloud skin
      // INDEX the app merges into the gallery. Lists finalized skins in
      // public/generated/ (ids having BOTH <id>-template.json and <id>-frame.png)
      // and returns the SAME shape. A skin counts as published if its <id>-published.json
      // marker exists; if NO markers exist at all, dev treats every finalized skin as
      // published (so a fresh local skin shows up without an extra publish step).
      const titleFromPrompt = (prompt: string): string => {
        const words = prompt.trim().replace(/^(a|an|the)\s+/i, "").replace(/[^\w\s-]/g, "")
          .split(/\s+/).filter(Boolean).slice(0, 3);
        const t = words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        return t || "New Skin";
      };
      const blurbFromPrompt = (prompt: string): string => {
        const p = prompt.trim().replace(/\s+/g, " ");
        const s = p.charAt(0).toUpperCase() + p.slice(1);
        return s.length > 64 ? s.slice(0, 61).trimEnd() + "…" : s;
      };
      server.middlewares.use("/api/skins", (_req, res) => {
        res.setHeader("Content-Type", "application/json");
        res.setHeader("Cache-Control", "no-store");
        let files: string[] = [];
        try { files = readdirSync(genDir); } catch { files = []; }
        const fileSet = new Set(files);
        const hasAnyMarker = files.some((f) => f.endsWith("-published.json"));
        const readJson = (file: string): any => {
          try { return JSON.parse(readFileSync(resolve(genDir, file), "utf8")); } catch { return null; }
        };
        const skins: any[] = [];
        for (const f of files) {
          const m = f.match(/^(.+)-template\.json$/);
          if (!m) continue;
          const id = m[1];
          if (!fileSet.has(`${id}-frame.png`)) continue;            // not finalized yet
          const marker = fileSet.has(`${id}-published.json`) ? readJson(`${id}-published.json`) : null;
          // published if it has a marker, OR (no markers anywhere) dev shows all finalized.
          if (hasAnyMarker && !marker) continue;
          const meta = fileSet.has(`${id}-meta.json`) ? readJson(`${id}-meta.json`) : null;
          const tpl = readJson(`${id}-template.json`) || {};
          const prompt = meta?.prompt ?? "";
          const name = marker?.name || tpl.name || (prompt ? titleFromPrompt(prompt) : id);
          const blurb = marker?.blurb || tpl.blurb || (prompt ? blurbFromPrompt(prompt) : "");
          const style = marker?.style || meta?.style || id;
          const sprites = files.some((x) => x.startsWith(`${id}-sprite-`) && x.endsWith(".png"));
          skins.push({
            id, name, blurb, style,
            frameUrl: `/api/asset/skins/${id}/frame.png`,
            sprites, font: marker?.font, createdAt: meta?.createdAt,
          });
        }
        skins.sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""));
        res.statusCode = 200;
        res.end(JSON.stringify({ skins }));
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
          // per-control cut sprites present? (dev flattens R2's skins/<id>/sprites/<bind>.png
          // to <id>-sprite-<bind>.png) — tells the player to render cut sprites, not donor set.
          const sprites = readdirSync(genDir).some((f) => f.startsWith(`${id}-sprite-`) && f.endsWith(".png"));
          res.statusCode = 200;
          res.end(JSON.stringify({ id, frameUrl: `/generated/${id}-frame.png`, template, meta, sprites }));
        } catch (e) {
          res.statusCode = 502;
          res.end(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }));
        }
      });

      // GET /api/asset/skins/<id>/<path> — local parity with functions/api/asset.
      // In dev the store flattens R2's skins/<id>/<path> into public/generated/ as
      // <id>-frame.png, <id>-paint.png, <id>-sprite-<bind>.png. The PLAYER builds
      // /api/asset/skins/<id>/sprites/<bind>.png URLs at render time, so without
      // this route they fall through to Vite's SPA index.html (200 text/html) and
      // every per-skin sprite silently fails to decode. Map them back to the files.
      server.middlewares.use("/api/asset/", (req, res, next) => {
        const m = (req.url ?? "").replace(/^\/+/, "").split(/[?#]/)[0].match(/^skins\/([^/]+)\/(.+)$/);
        if (!m) return next();
        const id = decodeURIComponent(m[1]);
        const rest = m[2];
        const file = rest.startsWith("sprites/")
          ? `${id}-sprite-${rest.slice("sprites/".length)}`
          : `${id}-${rest}`;
        const path = resolve(genDir, file);
        if (!existsSync(path)) { res.statusCode = 404; res.setHeader("Cache-Control", "no-store"); res.end("not found"); return; }
        res.setHeader("Content-Type", file.endsWith(".json") ? "application/json" : "image/png");
        res.end(readFileSync(path));
      });

      // GET /api/dev/gens — DEV-ONLY: list generations that have paint + layout +
      // template sidecars on disk, so the cut-inspection harness (?cutcheck) can
      // re-run the REAL cutSprite against fixed paints. Newest first.
      server.middlewares.use("/api/dev/gens", (_req, res) => {
        let ids: { id: string; mtime: number }[] = [];
        try {
          const files = readdirSync(genDir);
          const seen = new Set<string>();
          for (const f of files) {
            const m = f.match(/^(.+)-paint\.png$/);
            if (!m) continue;
            const id = m[1];
            if (seen.has(id)) continue;
            const hasLayout = existsSync(resolve(genDir, `${id}-layout.json`));
            const hasTemplate = existsSync(resolve(genDir, `${id}-template.json`));
            if (!hasLayout || !hasTemplate) continue;
            seen.add(id);
            let mtime = 0;
            try { mtime = statSync(resolve(genDir, `${id}-paint.png`)).mtimeMs; } catch { /* ignore */ }
            ids.push({ id, mtime });
          }
        } catch { /* genDir may not exist yet */ }
        ids.sort((a, b) => b.mtime - a.mtime); // newest first
        res.setHeader("Content-Type", "application/json");
        res.setHeader("Cache-Control", "no-store");
        res.end(JSON.stringify({ ids: ids.map((x) => x.id) }));
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
