// ============================================================
// skeuo MCP server — a sentence → a real, working skeuomorphic
// music-player skin.
//
//   • tool  generate_skin(prompt, variant?, style?) — POSTs to the skeuo
//           generate pipeline and returns the finished skin.
//   • tool  open_skeuo_studio() — opens the live Create/preview app inline
//           as an MCP ext-app (an embedded interactive UI).
//   • resource ui://skeuo/studio.html — the ext-app HTML.
//
// Uses @modelcontextprotocol/ext-apps (registerAppResource / registerAppTool),
// the SAME primitives mcp-apple-notes uses, so UI-capable hosts (Claude Desktop)
// actually render the embedded app. Run with bun (no build step):
//   bun /Users/conner/dev/skeuo-ui/mcp/index.ts
//
// Secrets: NONE. The generate endpoint holds FAL_KEY/OPENAI_API_KEY server-side.
// Only the optional, non-secret SKEUO_API_BASE override is read from env.
// ------------------------------------------------------------------
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";

const __dirname = dirname(new URL(import.meta.url).pathname);

const API_BASE = (process.env.SKEUO_API_BASE ?? "https://skeuo-ui.pages.dev").replace(/\/$/, "");
const GENERATE_URL = `${API_BASE}/api/generate`;
const STUDIO_URL = `${API_BASE}/?create=1`;
const STUDIO_RESOURCE_URI = "ui://skeuo/studio.html";

const VARIANTS = ["simple", "radial", "capsule", "minimal"] as const;
const STYLES = ["biomech", "winamp", "frog", "wmp", "halo"] as const;

function studioHtml(): string {
  for (const p of [join(__dirname, "ui", "studio.html"), join(__dirname, "..", "ui", "studio.html")]) {
    try { return readFileSync(p, "utf-8").replace(/__STUDIO_URL__/g, STUDIO_URL); } catch { /* next */ }
  }
  return `<!doctype html><meta charset=utf-8><body style="margin:0">`
    + `<iframe src="${STUDIO_URL}" style="border:0;width:100vw;height:100vh"></iframe></body>`;
}
const text = (t: string) => ({ content: [{ type: "text" as const, text: t }] });

function createServer(): McpServer {
  const server = new McpServer({ name: "skeuo", version: "1.0.0" });

  // ext-app UI resource — the embedded live studio
  registerAppResource(
    server,
    STUDIO_RESOURCE_URI,
    STUDIO_RESOURCE_URI,
    { mimeType: RESOURCE_MIME_TYPE },
    async () => ({ contents: [{ uri: STUDIO_RESOURCE_URI, mimeType: RESOURCE_MIME_TYPE, text: studioHtml() }] }),
  );

  // generate a skin from a sentence
  server.registerTool(
    "generate_skin",
    {
      title: "Generate skeuomorphic skin",
      description:
        "Turn a sentence into a real, working skeuomorphic music-player skin: a wildly-shaped photoreal device body (the prompt is its silhouette brief, e.g. 'a fanged anglerfish jaw') with genuinely working hardware — switches that flip, knobs that turn, faders that slide. Returns the finished skin (frame URL + control template + timing). No key needed here.",
      inputSchema: {
        prompt: z.string().min(1).describe("Silhouette brief for the device body, e.g. 'a fanged anglerfish jaw', 'a smooth river pebble'."),
        variant: z.enum(VARIANTS).optional().describe("Control layout: simple | radial | capsule | minimal. Default minimal."),
        style: z.enum(STYLES).optional().describe("Optional material donor: biomech|winamp|frog|wmp|halo. Omit to derive from the prompt."),
      },
    },
    async ({ prompt, variant, style }) => {
      let data: any;
      try {
        const res = await fetch(GENERATE_URL, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, variant: variant ?? "minimal", ...(style ? { style } : {}) }),
        });
        data = await res.json();
      } catch (e) {
        return text(`Failed to reach skeuo endpoint ${GENERATE_URL}: ${(e as Error).message}`);
      }
      if (data?.status === "error") return text(`Generation failed: ${data.error}`);
      if (data?.status !== "done") return text(`Unexpected response: ${JSON.stringify(data).slice(0, 400)}`);
      const summary = `Generated skin "${data.id}" — ${data.style}/${data.variant} via ${data.model}. `
        + `Share: ${API_BASE}/share?id=${data.id}. Open open_skeuo_studio to play it with working hardware.`;
      return { content: [{ type: "text" as const, text: summary }, { type: "text" as const, text: JSON.stringify(data) }] };
    },
  );

  // open the live studio inline as an ext-app
  registerAppTool(
    server,
    "open_skeuo_studio",
    {
      title: "Open skeuo studio",
      description: "Open the interactive skeuo Create/preview app inline — generate a skin from a prompt and play it with real working hardware, embedded in the client.",
      inputSchema: {},
      _meta: { ui: { resourceUri: STUDIO_RESOURCE_URI } },
    },
    async () => text(`Opening skeuo studio. If your client can't render embedded apps, visit ${STUDIO_URL}`),
  );

  return server;
}

async function main() {
  const server = createServer();
  await server.connect(new StdioServerTransport());
  console.error(`skeuo MCP up (endpoint: ${GENERATE_URL})`);
}
main().catch((e) => { console.error(e); process.exit(1); });

export { createServer };
