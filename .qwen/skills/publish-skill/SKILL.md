---
name: publish-skill
description: Take a skill from private central and publish it as a public, working, discoverable open-source artifact — sanitize personal data/secrets, ship needed compiled artifacts (LFS or GitHub release) so it works on clone, generate README + GEO/SEO discoverability metadata, push to its public GitHub repo, get it into the big Claude Code marketplaces/skill indexes, and trigger a crosspost announcement. Use when the user wants to publish, open-source, share, or release a skill publicly, or republish/update an already-public one. Human-gated preview-first — nothing leaves the machine until the sanitization diff is approved.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# publish-skill — central (private) → public, working, discoverable

Central is the **private source of truth**. This skill turns one central skill into a
**public, self-working, AI-citable** open-source repo. The public repo is a *derived,
sanitized artifact* — never the source; central → public is one-way.

This reverses the old external-repo pattern (see [[skill-authoring-rule]]): skills live in
central; publishing is an explicit, human-gated, outbound step.

## Hard gates (never skip)

1. **Sanitize, then human-approve the diff before anything leaves the machine.** Run
   `scripts/sanitize.py`; show the human the private→scrubbed diff and the residual-leak
   report. Publishing is **blocked** until the leak scan is clean AND the human approves.
   (security-rule is the floor; this operationalizes it.)
2. **It must actually work on clone.** A cloned/installed skill that needs hidden setup is
   a failed publish — see "Working artifacts" below.
3. **A real publish/major update triggers a crosspost.** After pushing, hand off to
   [[crosspost]] to announce (human-gated preview there too).

## Flow

```
select skill → sanitize (scrub + leak-scan) → preview diff (HUMAN GATE) →
build/attach working artifacts → write README + discoverability metadata →
push to public repo → register in marketplaces/indexes → crosspost announce
```

The "discoverability metadata" step is the **`geo-seo` standard pass** (mandatory for anything
public — see `geo-seo` → "Standard: a GEO/SEO pass is the DEFAULT before anything ships to the
public internet"): README H1 = entity + one-line definition, GEO/SEO topics, claim hygiene. Not
optional.

## How propagation works (read this to reason about push vs tag)

For the mental model of **how a `git push` / `git tag` reaches every endpoint** — for skills AND
MCP servers — see [references/distribution-mechanics.md](references/distribution-mechanics.md).
The four mechanisms in one line: **(1) crawl** (topics+manifest → auto on push), **(2) webhook**
(instant on push), **(3) registry publish** (MCP-only, on tag → mirrors), **(4) curated PR/form**
(one-time; pointer-entries track push, copy-entries need a re-PR). **Skills propagate on push;
MCP servers propagate on push except the version-pinned registry, which needs a tag** (one
command: `scripts/release.sh` in the repo).

For the **right way to STRUCTURE a repo** as a skill, an MCP server, or both (triple-duty) — the
exact layouts the tooling loads, verified against docs — see
[references/repo-structure.md](references/repo-structure.md). Key distinction it nails: **`/plugin`
(Claude Code marketplaces) ≠ the official MCP Registry** — the former is Claude-Code's install layer
for skills + MCP-as-plugin; the latter is a central cross-client directory of MCP *servers* only.

## 1. Sanitize (safety-critical)

`python3 scripts/sanitize.py <central-skill-dir> --out /tmp/publish-<name>` copies the skill
to a staging dir, scrubs personal data, and prints a diff + residual-leak report. It strips
the patterns in [references/sanitization.md](references/sanitization.md): absolute user
paths, the user's email/internal handle, machine + network names (LAN IPs, `.local`,
tailnet), private project/repo names, `[[links]]` to private rules/skills, `.env` paths and
secret var names. Public GitHub identity (`connerkward`) is intentionally **kept**.

The script **exits non-zero if any residual private pattern survives** — that failure blocks
publish. Show the human the diff; they approve or annotate. Never push the un-staged central
copy directly.

## 2. Working artifacts (clone-and-go)

The user's bar: someone who clones the repo — or installs it via a skill library / Claude's
official mechanism — gets a **working** skill without dev rework or installing new things,
within reason. Per skill type:

- **Pure markdown/script skills** (most): just work on clone. Ensure scripts use
  repo-relative or `~`-relative paths, not central absolutes (the scrubber enforces this).
- **Compiled tools** (Swift `sck-record`, `say-notify-overlayd`, etc.): do **not** rely on
  the user having a toolchain. Ship a **GitHub Release** with the prebuilt binary
  (`gh release create`) AND keep the `.swift` source + a one-line build fallback in the repo.
  A `postinstall`/setup note points at the release. (Downloaded binaries get macOS-quarantined
  — document the `xattr -d com.apple.quarantine` one-liner, or prefer build-from-source when
  the toolchain is ubiquitous.)
- **Python skills with deps**: include `requirements.txt`/`pyproject` and a one-command
  setup; pin versions. Prefer stdlib where reasonable.
- **Functional media assets** (overlay portraits, click sounds): commit to the public repo
  (these make it work out of the box). **Demo/archival media stays in the public repo only**
  and is never pulled back into central.

Decide artifact strategy per skill; record it in [references/name-map.md](references/name-map.md).

### Triple-duty: one repo as MCP server + plugin + skill

A single canonical repo can be **all three at once** — an MCP server, a Claude Code plugin,
and a skill — and get indexed by **both** ecosystems (MCP-server registries AND skill
scrapers) from that one repo. The mechanism: ship a `.claude-plugin/plugin.json` that carries
an `mcpServers` block **and** a bundled `skills/<name>/SKILL.md`. Installing the plugin then
registers the server and surfaces the skill; the MCP registries crawl the same repo via its
`mcp` topics (see [references/targets.md](references/targets.md) Tier 4); the skill scrapers
crawl it via the `claude-skill` topics (Tier 0/1). One repo, two discovery surfaces, no
duplicate canonical.

**The catch (current Claude Code docs):** a plugin install bundles the code, registers the
server, and auto-starts it — but it does **NOT** install the runtime (bun/node/python) and does
**NOT** grant OS permissions (e.g. macOS Full Disk Access for an Apple Notes / FDA server). The
bundled `SKILL.md` must guide that manual setup (install the runtime, grant FDA), or the
auto-started server fails on first use. Treat runtime + permissions as the "working on clone"
gate (§2) for MCP-server plugins.

`ckw-skills` is the marketplace that now distributes **both** plain skills and MCP-server
plugins; `mcp-apple-notes` is the first triple-duty entry (see name-map).

## 3. README + discoverability (GEO/SEO)

**The README is for HUMANS, not agents.** Lead with value — hook, demo gif, why-it-matters,
what it does. Install is ONE agent-first line ("tell your coding agent to add it" + a single
`marketplace add`); push CLI/manual setup and internals to `docs/`. The agent's *operating*
instructions live in `SKILL.md`, never the README. No pip/CLI walkthroughs up top — that reads
like machine docs and buries the pitch. Keep the repo root lean too (code in a subdir, fixtures
in `test/`) so the README shows high on the GitHub landing page. (Learned 2026-06-16 on
screenstudio-alt.)

Apply [[geo-seo]] to every published repo — this is how the automated indexes find it:
- **README H1 = the skill's entity name**, immediately followed by a one-line
  "**X** is a **Y** that does **Z**" definition, then a TL;DR, usage, and an FAQ.
- `LICENSE` (added at publish — central does **not** carry one), `llms.txt`, schema.org
  JSON-LD where the repo has a page.
- **GitHub topics** so the crawlers index it: `claude-code`, `claude-skill`, `agent-skills`,
  `claude-code-skill`, `anthropic`, plus skill-specific tags.
- A `.claude-plugin`/marketplace manifest if distributing as an installable plugin.

## 4. Register in marketplaces / indexes

See [references/targets.md](references/targets.md) for the current largest surfaces and how
each ingests. Most are **automated GitHub crawlers** (a well-tagged public repo is picked up
with no action); a few are **curated lists you PR into**. Verify each target's current
submission mechanics at publish time — this ecosystem moves fast (don't trust a stale step).

## 5. Crosspost

A genuine publish or major update **necessitates a crosspost**. Load [[crosspost]], draft the
announcement (lead with the hook, tag `@claudeai` etc., attach a real demo gif/screenshot),
preview, human-approves, post. [[devlog]] can draft the writeup first.

## Name map

Central skill names are internal; public repo names are chosen for GEO/SEO (often different).
The mapping + per-skill artifact strategy lives in
[references/name-map.md](references/name-map.md). New public repo names get a short GEO/SEO
ideation pass before first publish.
