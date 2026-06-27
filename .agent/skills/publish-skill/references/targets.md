# Publish targets — where a public skill goes to be found

Goal: maximize GEO/SEO + community reach. The ecosystem moves fast — **verify each target's
current submission mechanics at publish time** (counts/URLs below are June 2026 snapshots).

## Tier 0 — the owned canonical repo (do this first, it feeds everything else)

The public GitHub repo IS the canonical entity. Get it right and the automated crawlers
ingest it for free:
- README H1 = entity name + "X is a Y that does Z" one-liner ([[geo-seo]]).
- **GitHub topics** (the crawl signal): `claude-code`, `claude-skill`, `claude-code-skill`,
  `agent-skills`, `anthropic`, `skills`, + skill-specific tags.
- `LICENSE` (MIT unless reason otherwise), `llms.txt`, release with working artifacts.
- An `agentskills.io`-style `SKILL.md` at the root so portable-skill tooling recognizes it.

## Tier 1 — automated GitHub crawlers (no PR; tagging is the submission)

These index public repos automatically and are the largest discovery surfaces:
- **claudemarketplaces.com** — aggregator, ~21.6k skills / ~2.5k marketplaces, updated daily
  from GitHub. Correct topics → indexed.
- **quemsah/awesome-claude-plugins** — automated metrics crawl (~15k plugin repos).
- **claudepluginhub.com** — "largest plugin directory."
Action: ensure topics + a valid manifest; then confirm the repo appears within a crawl cycle.

## Tier 2 — curated installable libraries (PR / submit)

Bigger reach, manual entry. Open a PR adding the skill:
- **jeremylongshore/claude-code-plugins-plus-skills** (tonsofskills.com, `ccpi` CLI).
- **sickn33/antigravity-awesome-skills** (1,500+ skills, installer CLI).
- **alirezarezvani/claude-skills** (300+ skills, multi-agent).
- **netresearch/claude-code-marketplace** (agentskills.io open standard).
- **awesome-claude-code** curated lists (several; pick the actively-maintained, high-star one).

## Tier 3 — official / first-party

- Anthropic's plugin/marketplace mechanism (a `.claude-plugin/marketplace.json`) so the skill
  is installable via `claude` natively. Verify the current official format before publishing.

## Tier 4 — MCP-server registries (separate ecosystem; verify mechanics at publish time)

If the repo ships an **MCP server** (not just a skill), it belongs in the MCP-server discovery
surfaces too. This is a **separate ecosystem from the skill scrapers above** — the two barely
overlap, which is why a triple-duty repo (MCP server + plugin + skill) gets listed in BOTH.
Mechanics move fast — **verify current submission method at publish time.**

- **Official MCP Registry** (`registry.modelcontextprotocol.io`) — `mcp-publisher` CLI
  (`brew install mcp-publisher`), GitHub OIDC login → publishes a `server.json` to the
  namespace `io.github.<user>/*`. Auto-republish on release via the **"Publish MCP Server"**
  GitHub Action. **Metadata-only** registry: it points to where the package lives (npm, etc.),
  it does **not** host the server.
- **Smithery** (`smithery.ai`) — registry **+** hosting; uses a `smithery.yaml`; connect via
  GitHub. Note: oriented to **remote/hostable** servers — a local-FDA stdio server may only
  partially qualify (it can list but not be hosted). Verify before relying on it.
- **mcp.so**, **Glama** (`glama.ai`), **PulseMCP** — mostly **auto-crawl** public GitHub MCP
  repos by topic. No PR; ensure the topics below are set so they ingest it.
- **punkpeye/awesome-mcp-servers** — curated list; **PR** to add.
- **`.mcpb` / Desktop Extension bundle** — one-click install for Claude Desktop; **build the
  `.mcpb` bundle and attach it to a GitHub Release**.

**GitHub topics = the MCP crawl signal** (set these in addition to the skill topics in Tier 0):
`mcp`, `mcp-server`, `model-context-protocol`, `modelcontextprotocol`.

### Proven recipe — non-npm bun/TS stdio server → official registry (mcp-apple-notes, 2026-06-17)

A local stdio server that isn't on npm publishes via the **`.mcpb` package path**, fully
automated by a `v*`-tagged GitHub Action (build bundle → attach to Release → publish). Files
needed in the repo: `server.json` (registry manifest, `registryType: "mcpb"`, identifier = the
release-asset URL), `manifest.json` (MCPB bundle manifest), `.github/workflows/publish-mcp.yml`.
Packer is **`@anthropic-ai/mcpb`** (bin `mcpb`; `@modelcontextprotocol/mcpb` does NOT exist).
Auth is GitHub OIDC in CI (no stored secret). Once `active`, **PulseMCP mirrors it and Glama
auto-crawls** — no separate submission.

Three validation gotchas that each cost a failed run (fix up front):
1. **`mcpb validate` is strict** — rejects unknown manifest keys. No custom keys (e.g.
   `_setup_note`), and `compatibility.runtimes` does **not** accept `bun` — drop it, keep only
   `platforms: ["darwin"]`. The bun launch is via `server.mcp_config.command: "bun"`.
2. **Registry `server.json` `description` ≤ 100 chars** (422 otherwise). Keep a short
   registry-specific description; the long GEO entity line is fine in README/plugin.json/manifest.
3. **Forks**: `gh run list` resolves workflows against the *parent* repo — pass
   `--repo <you>/<repo>`. Actions may be disabled on forks (check
   `repos/<you>/<repo>/actions/permissions`); the `.mcpb` asset URL must contain the substring
   `mcp`.

## Process per target

1. Confirm the target still exists and its current submission method (crawl vs PR vs form).
2. For crawlers: verify topics/manifest, then check indexing after a cycle — don't assume.
3. For curated lists: PR with the entity-name + one-line definition (consistent across all
   spokes — same wording everywhere helps GEO; see [[geo-seo]]).
4. Record where it was submitted so republishes update the same entries.

Then **crosspost** the announcement ([[crosspost]]) — social reach is separate from these
index/marketplace surfaces and both matter.
