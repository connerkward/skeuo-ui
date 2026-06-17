#!/usr/bin/env node
// ============================================================
// skeuo MCP server — a sentence → a real, working skeuomorphic
// music-player skin.
//
// Exposes:
//   • tool   generate_skin(prompt, variant?, style?) — POSTs to the
//            skeuo generate pipeline (the deployed Cloudflare endpoint by
//            default) and returns the finished skin: a wildly-shaped
//            photoreal device body whose switches flip / knobs turn /
//            faders slide. The image-model key (FAL_KEY) lives on the
//            SERVER side at the endpoint and is NEVER handled here.
//   • tool   open_skeuo_studio() — surfaces the live skeuo Create/preview
//            UI as an MCP ext-app (an embedded interactive app) so a UI-
//            capable client renders the player inline.
//   • resource  ui://skeuo/studio.html — the ext-app HTML the tool points at.
//
// MCP-UI / ext-app pattern: a tool returns a UI resource (a `ui://` HTML
// resource) and references it via `_meta.ui.resourceUri`. UI-capable MCP
// hosts (Claude Desktop ext-apps, mcp-ui clients) render that resource as
// an embedded app; text-only hosts fall back to the text content. This is
// implemented on the stable @modelcontextprotocol/sdk primitives so it
// builds and runs with no fast-moving extra dependency.
//
// Secrets: NONE are needed in this package. The generate endpoint holds
// FAL_KEY / OPENAI_API_KEY server-side. Only an optional, non-secret base
// URL override (SKEUO_API_BASE) is read from the environment.
// ------------------------------------------------------------------
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

// The deployed skeuo generate endpoint. The image-model key lives there,
// server-side, so this package ships no secrets. Override for self-hosting.
const API_BASE = (process.env.SKEUO_API_BASE ?? "https://skeuo-ui.pages.dev").replace(/\/$/, "");
const GENERATE_URL = `${API_BASE}/api/generate`;
const STUDIO_URL = `${API_BASE}/?create=1`;

const STUDIO_RESOURCE_URI = "ui://skeuo/studio.html";
// MIME the ext-app/mcp-ui ecosystem uses for embedded HTML app resources.
const UI_MIME_TYPE = "text/html+skybridge";

const VARIANTS = ["simple", "radial", "capsule", "minimal"] as const;
const STYLES = ["biomech", "winamp", "frog", "wmp", "halo"] as const;

function loadStudioHtml(): string {
  // Resolve ui/studio.html whether running from source (./ui) or from the
  // compiled dist/ (../ui).
  for (const p of [join(__dirname, "ui", "studio.html"), join(__dirname, "..", "ui", "studio.html")]) {
    try {
      return readFileSync(p, "utf-8").replace(/__STUDIO_URL__/g, STUDIO_URL);
    } catch {
      /* try next */
    }
  }
  return `<!doctype html><meta charset=utf-8><body style="margin:0;font:14px ui-monospace;background:#111;color:#eee"><iframe src="${STUDIO_URL}" style="border:0;width:100vw;height:100vh"></iframe></body>`;
}

function textResult(text: string, meta?: Record<string, unknown>) {
  return { content: [{ type: "text" as const, text }], ...(meta ? { _meta: meta } : {}) };
}

function createServer(): McpServer {
  const server = new McpServer({ name: "skeuo", version: "1.0.0" });

  // ---- ext-app UI resource: the embedded skeuo studio ----------------
  server.registerResource(
    "skeuo-studio",
    STUDIO_RESOURCE_URI,
    {
      title: "skeuo studio",
      description:
        "Interactive skeuo Create/preview app — generate a skin from a prompt and play it with working hardware, embedded inline.",
      mimeType: UI_MIME_TYPE,
    },
    async () => ({
      contents: [{ uri: STUDIO_RESOURCE_URI, mimeType: UI_MIME_TYPE, text: loadStudioHtml() }],
    })
  );

  // ---- tool: generate a skin from a sentence -------------------------
  server.registerTool(
    "generate_skin",
    {
      title: "Generate skeuomorphic skin",
      description:
        "Turn a sentence into a real, working skeuomorphic music-player skin: a wildly-shaped photoreal device body (the prompt is its silhouette brief, e.g. 'a fanged anglerfish jaw') with genuinely working hardware — switches that flip, knobs that turn, faders that slide. Returns the finished skin (frame image URL + control template + timing). The image-model key lives server-side; none is needed here.",
      inputSchema: {
        prompt: z
          .string()
          .min(1)
          .describe("Silhouette brief for the device body, e.g. 'a fanged anglerfish jaw', 'a smooth river pebble', 'a brutalist concrete monolith'."),
        variant: z
          .enum(VARIANTS)
          .optional()
          .describe("Control layout: 'radial' (knobs around a hub), 'capsule' (WMP-style), 'minimal', or 'simple'. Default 'minimal'."),
        style: z
          .enum(STYLES)
          .optional()
          .describe("Optional material donor: biomech | winamp | frog | wmp | halo. Omit to let the pipeline derive material from the prompt."),
      },
    },
    async ({ prompt, variant, style }) => {
      const body = { prompt, variant: variant ?? "minimal", ...(style ? { style } : {}) };
      let res: Response;
      try {
        res = await fetch(GENERATE_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } catch (e) {
        return textResult(`Failed to reach skeuo endpoint ${GENERATE_URL}: ${(e as Error).message}`);
      }
      let data: any;
      try {
        data = await res.json();
      } catch {
        return textResult(`skeuo endpoint returned non-JSON (HTTP ${res.status}).`);
      }
      if (data?.status === "error") {
        return textResult(`Generation failed: ${data.error}`);
      }
      if (data?.status === "pending") {
        return textResult(`Generation queued (jobId ${data.jobId}). This endpoint is async; poll ${GENERATE_URL}?jobId=${data.jobId}.`);
      }
      if (data?.status === "done") {
        const summary = [
          `Generated skin "${data.id}".`,
          `style: ${data.style} · variant: ${data.variant} · model: ${data.model}`,
          `frame: ${data.frameUrl?.startsWith("data:") ? "(inline data URL)" : data.frameUrl}`,
          `timing: envelope ${data.timingMs?.envelope}ms, paint ${data.timingMs?.paint}ms, total ${data.timingMs?.total}ms`,
          ``,
          `Open the embedded studio (open_skeuo_studio) to play it with working hardware.`,
        ].join("\n");
        // Echo the structured result + point UI hosts at the studio app.
        return {
          content: [
            { type: "text" as const, text: summary },
            { type: "text" as const, text: JSON.stringify(data) },
          ],
          _meta: { ui: { resourceUri: STUDIO_RESOURCE_URI } },
        };
      }
      return textResult(`Unexpected response (HTTP ${res.status}): ${JSON.stringify(data).slice(0, 400)}`);
    }
  );

  // ---- tool: surface the live studio as an ext-app -------------------
  server.registerTool(
    "open_skeuo_studio",
    {
      title: "Open skeuo studio",
      description:
        "Open the interactive skeuo Create/preview app inline — generate a skin from a prompt and play it with real working hardware, embedded in the client.",
      inputSchema: {},
      _meta: { ui: { resourceUri: STUDIO_RESOURCE_URI } },
    },
    async () =>
      textResult(`Opening skeuo studio. If your client can't render embedded apps, visit ${STUDIO_URL}`, {
        ui: { resourceUri: STUDIO_RESOURCE_URI },
      })
  );

  return server;
}

async function main() {
  const server = createServer();
  await server.connect(new StdioServerTransport());
  // stderr only — stdout is the MCP stdio channel.
  console.error(`skeuo MCP server up (endpoint: ${GENERATE_URL})`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

export { createServer };
