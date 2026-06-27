# Connecting Drive / Cloudflare MCP outside Claude Code

Read-on-demand reference (kept out of the always-loaded SKILL.md). Only needed when
wiring Drive/Cloudflare MCP into a non-Anthropic harness (Cursor, Qwen, OpenCode, Gemini).

**Key fact: `claude.ai` connectors are NOT portable.** They're Anthropic-managed remote
endpoints authorized through claude.ai's own pre-registered OAuth client. Cursor / Qwen /
OpenCode / Gemini cannot consume `mcp__claude_ai_*` — that one-click convenience exists
only inside Anthropic surfaces (claude.ai web + Claude Code). To get the same capability
elsewhere you connect to the **same underlying remote MCP server directly**, registering
your own OAuth — or run a local stdio server with your own creds.

**Cloudflare — easy.** Cloudflare publishes ~13 managed remote MCP servers; any MCP-spec
client connects via OAuth (browser consent on first use). Streamable HTTP at `/mcp`
(legacy SSE at `/sse`):
- `https://bindings.mcp.cloudflare.com/mcp` — Workers/D1/R2/KV (the exact endpoint the
  `claude.ai Cloudflare Developer Platform` connector uses)
- `observability` · `builds` · `radar` · `containers` · `browser` · `ai-gateway` ·
  `auditlogs` · `dns-analytics` · `docs` (all `<name>.mcp.cloudflare.com/mcp`)
- Native-remote client config: `{ "url": "https://bindings.mcp.cloudflare.com/mcp" }`.
  Stdio-only client → bridge with `npx mcp-remote https://bindings.mcp.cloudflare.com/mcp`.
- Non-MCP fallback that works in *any* harness: the `cloudflare` skill's REST recipes
  (token in `central/.env`, plain `curl`).

**Google Drive — needs your own OAuth client.** There is no open one-click Google remote
MCP; the `claude.ai`/Google endpoint (`drivemcp.googleapis.com/mcp/v1`) is gated behind
Anthropic's registered OAuth client. To use Drive elsewhere you supply **your own** Google
Cloud OAuth client ID/secret:
- **Remote (official):** add `https://drivemcp.googleapis.com/mcp/v1` as a *custom
  connector* with your GCP OAuth client ID/secret. In Cursor, the redirect URI is
  `cursor://anysphere.cursor-mcp/oauth/callback`. (`gcloud` skill provisions the client.)
- **Local stdio (self-hosted):** create a Desktop-app OAuth client in GCP, drop
  `gcp-oauth.keys.json` in the server's creds dir, run the auth flow once to mint
  `credentials.json`, then point a maintained server at it — `@google/gemini-cli`'s gdrive
  server, or community `piotr-agier/google-drive-mcp` / `felores/gdrive-mcp-server`.
  (Avoid the deprecated `@modelcontextprotocol/server-gdrive`.)

**General rule for any harness:** a hosted connector you click in claude.ai → find its
underlying remote URL and register it yourself (OAuth), OR self-host a stdio server with
your own credentials. The `sync-mcp-servers` script only propagates **stdio** servers;
remote URLs must be added per-tool in each client's own remote-MCP config shape.

## Browser-driving outside Anthropic surfaces — Chrome Relay

`claude-in-chrome` (Anthropic's first-party Claude-for-Chrome extension, launched
Aug 2025, Max/Pro-gated) is **not portable** off Anthropic surfaces — same constraint as
the `claude.ai` connectors above. The provider-agnostic substitute for "agent drives the
real Chrome I'm signed into" is **Chrome Relay** (`https://chrome-relay.kushalsm.com`,
Kushal SM; Chrome Web Store `cpdiapbifblhlcpnmlmfpgfjlacebokb`): a local CLI bridge +
native-messaging host that lets **any** terminal coding agent (Claude Code, Cursor,
OpenCode, Gemini CLI) operate your authenticated Chrome — cookies, SSO, extensions,
localhost — fully local, nothing to a vendor cloud.

- **When it matters:** only if the harness moves off Claude/Anthropic. Inside Claude Code,
  `claude-in-chrome` already fills this slot — adding Chrome Relay now is redundant
  ([[restraint-rule]]). This is a *future-alternative* pointer, not a current install.
- **Security caveat:** handing any agent your live authenticated browser (banking, email,
  SSO) is a real prompt-injection surface — "fully local" stops vendor exfiltration, not
  what a malicious page makes the agent do as you. Vet before installing. See the
  "Browser Relay: When Your AI Assistant Gets Hands on Your Browser" writeup
  (boringappsec.com).
