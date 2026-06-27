# How distribution actually works — the 4 propagation mechanisms

The mental model for getting a **skill OR an MCP server** seen everywhere, and knowing what a
`git push` vs a `git tag` actually updates. Every endpoint uses exactly ONE of four mechanisms.
Identify the mechanism → you know whether (and how) it auto-updates.

## The 4 mechanisms

### 1. Crawl / auto-index — passive, updates on PUSH (no action per release)
The directory **scrapes GitHub on a schedule** and finds you by **GitHub topics** + a valid
**manifest** (`.claude-plugin/marketplace.json`, `plugin.json`, or `server.json`). You set the
topics + manifest ONCE; thereafter every push is picked up on their next crawl cycle (~daily).
- Skills **and** MCP.
- Examples: claudemarketplaces.com, claudepluginhub.com, quemsah/awesome-claude-plugins,
  Glama (MCP), claude-plugins.dev / aitmpl.com, agentskill.sh (24h "daily sync"),
  PulseMCP (mirrors the official MCP registry).
- **The lever is GitHub topics.** No topics → invisible to every crawler. This is the
  highest-ROI passive move and it's one `gh api -X PUT .../topics` call.

### 2. Webhook / API sync — programmatic, INSTANT on push (strongest)
Some directories accept a **GitHub webhook**; every push fires it → they update immediately
(no crawl-cycle wait). This is the closest thing to true "push = instantly live everywhere."
- Add via `gh api repos/<owner>/<repo>/hooks` (config.url = the directory's webhook endpoint,
  content_type json, events `["push"]`).
- Example: agentskill.sh (`https://agentskill.sh/api/webhooks/github`). (Caveat 2026-06-17:
  agentskill.sh's import parser rejected a real SKILL.md as `failed` — verify a directory
  actually ingests before wiring its webhook.)

### 3. Registry publish — programmatic, version-pinned, updates on TAG (MCP-ONLY)
The official **MCP Registry** is NOT crawled — you **publish** to it, pinned to a version.
- Trigger: `git tag vX.Y.Z` → CI (`publish-mcp.yml`) builds the `.mcpb` bundle, cuts the GitHub
  Release, and runs `mcp-publisher publish` (GitHub OIDC, no secret).
- Downstream: **PulseMCP and Glama mirror the registry** → from there it falls back into
  mechanism 1 (crawl/mirror) on the consumers.
- **Skills have NO equivalent** — there is no "skill registry publish." A skill is just a repo
  that mechanisms 1/2/4 pick up. Only MCP servers have a version-pinned registry.

### 4. Curated submission — one-time, gated, needs a maintainer/human
You submit to a hand-curated list. It's a ONE-TIME act and the list reflects you only after a
human accepts. Two axes: **how you submit** and **how it updates after merge**.

How you submit (decreasing automatability):
- **PR via `gh`** (fork → branch → commit → PR) — fully programmatic. Most lists.
- **Issue-form** — some allow `gh issue create` with their template; some **ban automation**
  (e.g. hesreallyhim/awesome-claude-code: web UI only, `gh` = CoC violation + ban risk; it even
  requires a human "I am not circuits" attestation). Read CONTRIBUTING before automating an issue.
- **Web form + login** — needs the user's account/OAuth (anthropics official directory at
  `clau.de/plugin-directory-submission`, Smithery, claudepluginhub's form). **Not automatable —
  the agent must not authenticate as the user or create accounts.** The user does these.

How it updates after merge:
- **Pointer** entry (their file points at your repo — `sources.yaml`, a `source.repo` in their
  marketplace.json) → re-syncs from your repo = **push-tracking** (auto). e.g. jeremylongshore,
  netresearch.
- **Copy** entry (they **vendor** your SKILL.md/README into their repo) → **static**; any content
  change needs a **new PR**. e.g. sickn33, ComposioHQ, BehiSecc, jqueryscript.

## What `push` vs `tag` updates — the two artifact types

| Endpoint | Skill | MCP server | Updates on |
|---|---|---|---|
| Own marketplace (ckw-skills) | pointer to repo HEAD | pointer to repo HEAD | **push** (install resolves HEAD) |
| Crawlers (topics + manifest) | ✓ | ✓ | **push** (next crawl cycle) |
| Webhook directories | ✓ where offered | ✓ where offered | **push** (instant) |
| Official MCP registry | — (none) | tag → CI publish | **tag** |
| PulseMCP / Glama | crawl | mirror the registry | **push / tag** then their cycle |
| Curated lists — pointer PRs | re-sync | re-sync | **push** (after merge) |
| Curated lists — copy PRs | static | static | **new PR** |

**The punchline:**
- **Skills propagate on `git push`.** No tag, no release, no registry — topics + a manifest +
  the own-marketplace pointer + webhooks do it; `git push` IS the whole update path.
- **MCP servers propagate on `git push` for everything EXCEPT the version-pinned official
  registry, which needs `git tag`.** `scripts/release.sh` makes that tag path one command
  (sync-bump 4 files + commit + push + tag once); the registry then mirrors to PulseMCP/Glama.

## Maximizing "push/tag = update most endpoints" — the setup checklist

1. **Topics** on every repo (the crawl signal) — covers the whole mechanism-1 tier passively.
2. **Valid manifest** in each repo (marketplace.json / plugin.json / server.json) — what crawlers parse.
3. **Own marketplace** (ckw-skills) lists each via a repo pointer → HEAD-tracking.
4. **Webhooks** to any directory that offers one (mechanism 2) → instant push-sync.
5. **MCP only:** the tag→CI→registry pipeline (`publish-mcp.yml` + `release.sh`) → registry + mirrors.
6. **Curated lists:** one-time PRs; prefer **pointer** targets (auto-track push) over **copy** targets.
7. Record every submission in [submissions-log.md](submissions-log.md) so updates hit the same entries.

The irreducible residual that NO mechanism automates: **human-only forms** (hesreallyhim),
**login/account walls** (Smithery, anthropics directory), and **star/maturity gates** (travisvn
≥10★, VoltAgent) — those need the user's hands or organic traction (a crosspost/announce), not
distribution plumbing.

## Source index by mechanism (2026-06-17; `[S]` skill · `[M]` MCP · `[S+M]` both)

### 1. Crawl — topics+manifest, auto on push
- claudemarketplaces.com `[S+M]` · claudepluginhub.com `[S+M]` · quemsah/awesome-claude-plugins `[S]`
- Glama `[M]` · claude-plugins.dev / aitmpl index `[S+M]` · PulseMCP `[M]` (mirrors the registry)
- agentskill.sh 24h "daily sync" `[S]` — ⚠ import returned `failed` on a real SKILL.md; unverified

### 2. Webhook — instant on push
- agentskill.sh `https://agentskill.sh/api/webhooks/github` `[S]` — ⚠ same caveat as above

### 3. Registry publish — MCP-only, on TAG
- **Official MCP Registry** `[M]` → mirrors to PulseMCP + Glama (CI `publish-mcp.yml` / `release.sh`)

### 4. Curated submission — one-time, gated
**4a. PR via `gh`, POINTER (re-syncs on push after merge):**
jeremylongshore/claude-code-plugins-plus-skills (#872 `[S]`, #871 `[M]`) · netresearch/claude-code-marketplace (#71 `[S]`, #70 `[M]`) · majiayu000/claude-skill-registry-core (#220 `[S]`) · GetBindu/awesome-claude-code-and-skills (#70 `[S]`)

**4b. PR via `gh`, COPY (static — new PR to update):**
sickn33/antigravity-awesome-skills (#704 `[S]`, #703 `[M]`) · ComposioHQ/awesome-claude-skills 64.9k★ (#1094 `[S]`) · BehiSecc/awesome-claude-skills 9.5k★ (#374 `[S]`) · jqueryscript/awesome-claude-code (#409 `[S]`) · punkpeye/awesome-mcp-servers (#8199 `[M]`)

**4c. Issue-form, HUMAN-ONLY (not automatable — `gh` = ban):**
hesreallyhim/awesome-claude-code 46.7k★ `[S+M]`

**4d. Web form + login (needs user account/OAuth):**
anthropics official directory `clau.de/plugin-directory-submission` `[S+M]` · Smithery `[M]` · mcp.so `[M]` · mcpservers.org (wong2) `[M]` · claudepluginhub form `[S+M]` (redundant w/ its crawl)

**4e. Star / maturity gated (need traction first):**
travisvn/awesome-claude-skills 13.5k★ (≥10★ gate) `[S]` · VoltAgent/awesome-agent-skills (maturity) `[S]`

**4f. Skipped — content-copy breaks multi-file skills:** davila7/claude-code-templates 28k★ · claude-market `[S]`
**Blocked — PRs+issues disabled:** appcypher/awesome-mcp-servers `[M]`
**Skipped — stale / npm name taken:** mcp-get `[M]`
