---
name: mcp
description: MCP server inventory and configuration. Use when adding/removing MCP servers, debugging tool availability, or explaining the difference between Claude Code MCPs and claude.ai connectors.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# MCP Servers

Reference for the MCP (Model Context Protocol) servers wired into this user's agent stack. Two distinct layers exist and they are NOT the same surface:

| Layer | Config location | Tools surfaced as |
|-------|-----------------|-------------------|
| **Claude Code CLI** | `~/.claude.json` → `mcpServers` (global) + per-project overrides under `projects.<path>.mcpServers` | `mcp__<server>__<tool>` |
| **claude.ai connectors** | claude.ai Settings → Connectors (OAuth web flow) | `mcp__claude_ai_<Service>__<tool>` |

The CLI servers are local subprocesses (`npx`, `uvx`, etc.) under the user's control. The claude.ai connectors are managed services configured through the website; they don't appear in `~/.claude.json`.

## Currently configured — regenerate, don't trust a hand-list

`~/.claude.json` is the source of truth and it drifts. A hand-maintained server table used to live here and rotted between every edit — deleted. Get ground truth live:

```bash
claude mcp list   # CLI servers (global + per-project) with health status
```

What's wired (orientation only — `claude mcp list` is authoritative): the `playwright` trio + `chrome-devtools` (browser; see `web-dev-rule` / `browser-tool-routing-rule`), `blender`, `fal-ai` (see `fal` skill), `ios-simulator` (used by `cross-browser-preview`), `github`, `context7`, **`feed-demon`** (the local taste-ranked RSS reader exposed as an MCP — tools: digest/search/recent/feeds/read_article/mark_read; `~/dev/feed-demon/.venv/bin/python -m feed_demon.mcp_server` with `env.PYTHONPATH=~/dev/feed-demon`; also in the Claude Desktop config). Per-project: `apple-notes` (`/Users/conner`, used by `apple-notes-export`), `ios-simulator` (`portfolio-2026`).

**claude.ai connectors** — OAuth, account-bound, surface as `mcp__claude_ai_*`, **not** in `~/.claude.json` so the CLI won't list them: Figma · Gmail · Google Calendar · Google Drive · Hugging Face · Linear · Spotify · Cloudflare Developer Platform. Plus **claude-in-chrome** (drives your real Chrome profile — see `browser-tool-routing-rule.md`).

**Removed 2026-06-04 — `google-drive` + `cloudflare` stdio servers**: dead local duplicates of the working claude.ai connectors (deprecated package / unconfigured). Don't re-add on Claude Code. For other harnesses that can't use claude.ai connectors, see [`references/mcp-outside-claude-code.md`](references/mcp-outside-claude-code.md).

## Installation method: `npx`/`uvx` cache vs global install

None of the configured servers are "installed globally" in the package-manager sense. They run on-demand:

| Launcher | What happens | Where the package lives |
|----------|-------------|--------------------------|
| `npx -y <pkg>@latest` | First run downloads, subsequent runs reuse cache | `~/.npm/_npx/<hash>/node_modules/<pkg>/` |
| `uvx --from <git>` | First run clones+builds in cache, subsequent runs reuse | `~/.cache/uv/` |
| `npm i -g <pkg>` (not used here) | Eagerly installed, binary on `$PATH` | `$(npm config get prefix)/lib/node_modules/<pkg>/` |

`npx -y` is the right default — cache stays warm across launches (sub-second cold start once primed), gets updates on `@latest` resolution, and there's nothing to uninstall when you drop a server. Don't switch to `npm i -g` unless you specifically need:
- Binary on `$PATH` for scripting outside MCP
- Protection from npx cache GC (rare)
- Reproducibility pinned to an installed version rather than what `@latest` resolves to

To verify what's actually cached vs configured:
```bash
# configured
python3 -c "import json; print(list(json.load(open('/Users/conner/.claude.json'))['mcpServers'].keys()))"
# npx-cached
find ~/.npm/_npx -maxdepth 4 -name "package.json" -exec grep -l '"<pkg-name>"' {} \;
# on PATH
which <pkg-name>
```

## Adding a new MCP server (Claude Code CLI)

```bash
# stdio server (most common)
claude mcp add <name> -- <command> <args...>

# example: filesystem MCP scoped to /Users/conner/dev
claude mcp add fs -- npx -y @modelcontextprotocol/server-filesystem /Users/conner/dev

# verify
claude mcp list
```

Or hand-edit `~/.claude.json` under `mcpServers`:
```json
{
  "mcpServers": {
    "<name>": {
      "type": "stdio",
      "command": "<bin>",
      "args": ["<arg1>", "<arg2>"],
      "env": {}
    }
  }
}
```

Per-project scope lives under `projects.<absolute-path>.mcpServers` in the same file. Per-project overrides take precedence over global.

## Cross-tool MCP support

The MCP protocol itself is shared, but each agent reads it from its own config file:

| Tool | Config path | JSON shape |
|------|-------------|------------|
| Claude Code | `~/.claude.json` → `mcpServers` (+ per-project under `projects.<path>.mcpServers`) | **Source of truth.** `{type: "stdio", command, args, env}` per server |
| Cursor | `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project) → `mcpServers` | Same as Claude — copy verbatim |
| Qwen Code | `~/.qwen/settings.json` → `mcpServers` | Same as Claude — copy verbatim |
| OpenCode | `~/.config/opencode/opencode.json` (global) or `opencode.json` (project) → `mcp` | Different: `{type: "local", command: [bin, ...args], enabled, environment}` — translation required |
| Antigravity (`.agent`) | `.agent/mcp.json` → `mcpServers` | Same as Claude |

## Syncing across tools

`central/scripts/sync-mcp-servers` reads `~/.claude.json` `mcpServers` (globals only) and propagates to Cursor, Qwen, and OpenCode. Run it after `claude mcp add` to keep the others in lockstep:

```bash
python3 ~/dev/central/scripts/sync-mcp-servers
# or, after running setup-machine + source ~/.zshrc:
sync-mcp-servers
```

`~/dev/central/scripts/setup-machine` auto-runs `sync-mcp-servers` on bootstrap, so a fresh machine has all four tools aligned after the initial setup. Re-run the sync manually after every `claude mcp add` / hand-edit of `~/.claude.json`.

What it does:
- Reads `~/.claude.json` → `mcpServers` (the globals; per-project overrides are NOT synced)
- Writes verbatim to `~/.cursor/mcp.json` and `~/.qwen/settings.json` under `mcpServers`
- Translates and writes to `~/.config/opencode/opencode.json` under `mcp` (Claude's stdio shape → OpenCode's local shape)
- Atomic writes (tmp + rename) and preserves other keys in each destination file

Trade-offs:
- **Claude wins all ties.** Any MCP added directly to Cursor/Qwen/OpenCode that isn't also in `~/.claude.json` gets wiped on the next sync.
- **No per-project sync.** Only the global `mcpServers` block is propagated; per-project overrides stay Claude-only.
- **Secrets in `env`.** If a server needs an API key, that key now lives in three more config files. None should ever be committed.

## Debugging

- **Tool not appearing in `mcp__*`:** check the server is in `mcpServers`, restart the agent (Claude Code reads `.claude.json` at startup), and watch for errors during launch. `claude --debug` surfaces MCP handshake failures.
- **`Browser is already in use`:** another agent window holds the Playwright profile lock. Either add `--isolated` to the args (no persistence) or drop a per-project `.mcp.json` with `--user-data-dir <unique-path>`. See `web-dev-rule.md`.
- **Per-project override not taking effect:** the `projects.<path>` key in `~/.claude.json` must match the resolved absolute path of `cwd` exactly. Symlinked paths can mismatch.

## When to NOT add an MCP server

MCPs cost context window — every available tool's schema loads into every conversation. Prefer the deferred-tools pattern (Claude Code's `ToolSearch`) over enabling MCPs globally if a tool is rarely used. The user already has 100+ deferred tools available via `ToolSearch` without polluting the always-on tool list. Adding to `mcpServers` makes a tool *always on*; adding nothing keeps it available via `ToolSearch` on demand.

Note: `ToolSearch`-style deferred loading is a Claude Code feature. Cursor, Qwen, and OpenCode load all configured MCP servers eagerly, so they pay the full context cost for any server in their config. The cross-tool sync replicates that cost — if a server is rarely useful but you sync it, Cursor/Qwen/OpenCode pay context for every conversation while Claude can defer it. Worth being selective about what lands in `~/.claude.json` for that reason.

## See also

- `universal-rule-skill-export` — rule/skill sync across Claude/Cursor/Qwen/OpenCode and the global symlink wiring on this machine.
- `central/scripts/setup-machine` — idempotent bootstrap that establishes symlinks AND runs `sync-mcp-servers`.
- `central/rules/browser-tool-routing-rule.md` — when to use Playwright vs chrome-devtools vs claude-in-chrome MCP.
