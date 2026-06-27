# Right way to structure a repo — skill, MCP server, or both

Verified against docs 2026-06-17: [Claude Code skills](https://code.claude.com/docs/en/skills.md),
[plugins](https://code.claude.com/docs/en/plugins.md) / [reference](https://code.claude.com/docs/en/plugins-reference.md),
[MCP registry quickstart](https://modelcontextprotocol.io/registry/quickstart),
[build an MCP server](https://modelcontextprotocol.io/quickstart/server). Don't assume — these are the layouts the tooling actually loads.

## A. A skill (Agent Skills open standard, agentskills.io)

Minimum = one `SKILL.md` with YAML frontmatter:
```
---
name: my-skill                 # invocation name (optional in skills/<dir>/ form — dir name wins)
description: <when to use this — Claude reads THIS to auto-trigger; make it specific/pushy>
---
<the instructions as markdown; supporting files referenced relative to the dir>
```
Optional frontmatter: `disable-model-invocation: true` (require explicit `/name`). Supporting files
(`scripts/`, `references/`, assets) live beside `SKILL.md` and load on demand.

**Where SKILL.md lives, by context:**
- Personal skill: `~/.claude/skills/<name>/SKILL.md` (auto-discovered every session).
- Project skill: `<repo>/.claude/skills/<name>/SKILL.md` (auto-discovered in that repo).
- **Inside a plugin** (the distributable form): EITHER `skills/<name>/SKILL.md` (one or many — dir
  name = invocation name), OR a single `SKILL.md` at the plugin ROOT (the frontmatter `name` is the
  invocation name). **Both are valid and documented** — a root `SKILL.md` is NOT broken.

There is **no central "skill registry"** — a skill is distributed by being a repo that plugin
marketplaces list and crawlers index. (Contrast MCP servers, which have the official registry.)

## B. An MCP server

Built with an MCP SDK (TS `@modelcontextprotocol/sdk`, Python `mcp`); exposes **tools / resources /
prompts**; launched over **stdio** (a `command` + `args`) or **HTTP**. Minimal repo:
```
package.json            # name, version, main, the SDK dep
index.ts                # creates the server, registers tools, connects StdioServerTransport
```
That alone is a working server you can register in any client's config. To make it **discoverable**,
add the distribution manifests below.

### Publishing to the official MCP Registry (the canonical, cross-client directory)
The registry hosts **metadata only**, pointing at where the package lives. You need a `server.json`:
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.<user>/<slug>",      // GitHub-OIDC namespace; MUST be io.github.<user>/*
  "description": "<= 100 chars (registry rejects longer with 422)",
  "repository": { "url": "...", "source": "github" },
  "version": "1.0.0",
  "packages": [{ "registryType": "...", "identifier": "...", "version": "...", "transport": {"type":"stdio"} }]
}
```
Publish with the **`mcp-publisher`** CLI: `init` → `login github` (device-code OIDC) → `publish`.
GitHub auth grants the `io.github.<user>/*` namespace; the `name` must start with it.

**Package types** (how the registry resolves your artifact — pick one):
- **`npm`** (the doc's default TS path): you must `npm publish` first AND add `"mcpName": "io.github.<user>/<slug>"` to `package.json` matching the server.json name. The registry verifies the npm package carries that field.
- **`pypi` / `nuget` / `oci`**: same idea for those package managers.
- **`mcpb`**: a Desktop-Extension bundle attached to a **GitHub Release** (no npm needed) — the path used when the server isn't on a package manager. Needs a `manifest.json` (MCPB bundle manifest) + the built `.mcpb`, asset URL containing the substring `mcp`, + `fileSha256`.
- **`remotes`**: for **hosted HTTP/SSE** servers (not local stdio).

Optional extra manifests: `smithery.yaml` (Smithery), `glama.json` (Glama claim).

## C. Both — one repo as MCP server + plugin + skill (triple-duty, what apple-notes does)

A single repo can be installable via `/plugin` AND listed in the MCP registry AND crawled as a skill:
```
<repo>/
├── index.ts                         # the MCP server
├── package.json                     # (+ "mcpName" if using the npm registry path)
├── .claude-plugin/plugin.json       # plugin manifest — declares the MCP server + bundles the skill
│     { "name": "...", "mcpServers": { "x": {"command":"bun","args":["${CLAUDE_PLUGIN_ROOT}/index.ts","--stdio"]} } }
├── skills/<name>/SKILL.md           # the bundled operating-manual skill
├── server.json                      # official MCP registry manifest (mcpb or npm)
├── manifest.json                    # MCPB bundle manifest (if registryType: mcpb)
└── .github/workflows/publish-mcp.yml# tag → build .mcpb → Release → mcp-publisher publish
```
On `/plugin install`, **both** the MCP server (from `plugin.json` `mcpServers`) **and** the bundled
skill (from `skills/`) activate — confirmed. The runtime (bun/node) + OS permissions are NOT
installed by the plugin; the bundled SKILL.md must guide that setup.

## D. The plugin + marketplace wrapper (the `/plugin` install layer)

- **Plugin manifest** `.claude-plugin/plugin.json`: `name`, `description`, `version`, optional
  `author/homepage/repository/license/keywords`, and any of `mcpServers` block / `commands/` /
  `hooks/` / `skills/`. Components are auto-discovered — no field needs to point at the skills.
- **Marketplace** `.claude-plugin/marketplace.json` (in a catalog repo, e.g. ckw-skills): a `name`
  (the install suffix `@<name>`) + `plugins[]`, each `{ name, description, source: {source:"github", repo:"owner/repo"} }`.
  Install: `/plugin marketplace add owner/catalog-repo` → `/plugin install <plugin>@<marketplace-name>`.
  `source.repo` can point at a whole repo or a subdir; the marketplace entry is just a pointer (tracks HEAD).

## `/plugin` vs the official MCP Registry — NOT the same thing
- **`/plugin` (Claude Code marketplaces)** = Claude-Code-specific **install** mechanism. Decentralized:
  any GitHub repo with a `marketplace.json` you `/plugin marketplace add`. Distributes **skills AND
  MCP-servers-bundled-as-plugins**. It's how a *Claude Code user* installs.
- **Official MCP Registry** = a **central, first-party, cross-client directory of MCP *servers* only**
  (`registry.modelcontextprotocol.io`), with a queryable API that **many** clients/tools read. No
  skills. It's a **discovery + citation** surface, not a Claude-Code installer.
- An MCP server can live in **both**; a skill can only be in `/plugin` marketplaces. For GEO, the
  registry is a single authoritative entity AI tools cite; `/plugin` marketplaces are fragmented and
  Claude-Code-scoped.
