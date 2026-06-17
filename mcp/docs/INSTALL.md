# Install, self-host, and how to publish/index this package

## Manual MCP registration

Requires Node 18+ (for global `fetch`).

```bash
git clone https://github.com/connerkward/skeuo-mcp
cd skeuo-mcp/mcp
npm install
npm run build          # tsc → dist/index.js
# Claude Code:
claude mcp add skeuo -- node "$(pwd)/dist/index.js"
# Claude Desktop (claude_desktop_config.json):
#   "mcpServers": { "skeuo": { "command": "node",
#     "args": ["/abs/path/skeuo-mcp/mcp/dist/index.js"] } }
```

Then restart the client. No API key is required — the generate endpoint holds
`FAL_KEY` / `OPENAI_API_KEY` server-side.

## Configuration

| Env var | Required | Secret | Meaning |
|---------|----------|--------|---------|
| `SKEUO_API_BASE` | no | no | Base URL of the skeuo generate endpoint. Default `https://skeuo-ui.pages.dev`. Override only to point at a self-hosted deployment. |

There are **no secret env vars** in this package. The image-model key lives at
the generate endpoint (a Cloudflare Pages Function binding), never in the client.

## Self-hosting the generate endpoint

The MCP only calls `POST {SKEUO_API_BASE}/api/generate`. To self-host, deploy
the [skeuo-ui](https://github.com/connerkward/skeuo-ui) app to Cloudflare Pages
with a `FAL_KEY` binding (and optionally `OPENAI_API_KEY`, an R2 `SKINS` bucket,
and a `RATELIMIT` KV namespace for the daily spend cap), then point this MCP at
it with `SKEUO_API_BASE=https://your-deployment`.

## How this package gets auto-indexed (publish checklist)

This repo is **triple-duty**: one repo discoverable as an MCP server, a Claude
Code plugin, and a skill. Nothing here pushes to a registry — this is the
checklist for when you do.

1. **Push to the public repo** `connerkward/skeuo-mcp` (the `mcp/` dir is the
   package root). Add GitHub topics so crawlers ingest it:
   `mcp`, `model-context-protocol`, `claude-code`, `claude-skill`,
   `agent-skills`, `skeuomorphic`, `generative-ui`.
2. **Build the `.mcpb` bundle** and attach it to a GitHub release
   `v1.0.0` so `server.json`'s `packages[].identifier` URL resolves:
   ```bash
   npx @anthropic-ai/mcpb pack    # produces skeuo-mcp.mcpb
   ```
   Upload `skeuo-mcp.mcpb` to the `v1.0.0` release.
3. **MCP registries** (e.g. the official MCP registry / registry.modelcontextprotocol.io)
   crawl `server.json` from the repo via its `mcp` topics — no manual submit for
   the crawler-based ones; verify the current submission mechanics at publish time.
4. **`ckw-skills` marketplace** distributes it as an installable plugin via
   `.claude-plugin/plugin.json` — add this repo to the marketplace's plugin list.
   Skill scrapers pick up the bundled `skills/skeuo-skin-generator/SKILL.md` via
   the `claude-skill` topics.
5. **Announce** (crosspost) once live.

See the private `publish-skill` skill for the full sanitize → README → register →
crosspost flow; mirror what `mcp-apple-notes` did.
