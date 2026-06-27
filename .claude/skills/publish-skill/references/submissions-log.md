# Submissions log — where each published artifact was pushed, and how to update it

One section per published artifact. When you change the artifact, re-run the **Update**
procedure and re-do any **manual** surfaces. Auto surfaces re-ingest on their own.

Status legend: ✅ live · 🕓 auto-crawl pending · 📝 PR open · 🔒 needs interactive login · ⛔ blocked.

## Where to check submission status / history (CHECK THESE FIRST — the sources of truth)

A distribution job: before submitting anything, look here to see what's already been submitted and
its status. Each surface's authoritative status lives in ITS OWN dashboard/API — NOT in a public
index (those lag and only show *approved* items) or in email (most send no confirmation). "I didn't
find it in the catalog" ≠ "it wasn't submitted." See [[verify-external-claims-rule]].

| Surface | Where to see your submissions + status | Notes |
|---|---|---|
| **Official Claude plugin directory** (`claude-community`) | **`platform.claude.com/plugins/submissions`** (Console dashboard — works on individual/Max plans) | The ONLY truth source. Pending items do NOT appear in the public `anthropics/claude-plugins-community` catalog until approved, and no email is sent. (The `claude.ai/admin-settings/directory/...` path is Team/Enterprise-gated — ignore on individual plans.) |
| **Official MCP Registry** | `curl "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.<user>/<name>"` → check `status` + `isLatest` | Instant publish (no review queue); authoritative via API. |
| **ckw-skills marketplace** | the repo's `.claude-plugin/marketplace.json` | Lists every plugin; install resolves repo HEAD. |
| **Curated-list PRs** | the PR URLs recorded per-artifact below | Status = open / merged on the PR. |
| **Crawler directories** (Glama, claudemarketplaces, etc.) | search the directory site for the repo name | Lags a crawl cycle; appearance ≠ "submitted" (it's pull-based). |

**Current official-directory submissions (pending review, 2026-06-17):** `apple-notes`, `lookdev`,
`screenstudio-alt`, `deterministic-design`. Not yet submitted: `ckw-design`, `web-media-getter`,
`macos-screen-recorder`, `lookdev-auto`, `muser`. (Re-check the dashboard for live status.)

---

## mcp-apple-notes  (repo `connerkward/mcp-apple-notes`, lib `apple-notes`)

Triple-duty: MCP server + Claude Code plugin + bundled skill. Current version **1.0.2**.

### Update procedure (ship a new version)
1. Edit code/files. Bump version in **all four**: `server.json` (`version` **and** the
   `packages[0].identifier` release-asset URL `…/vX.Y.Z/…`), `.claude-plugin/plugin.json`,
   `manifest.json`, `package.json`.
2. `git commit` → `git push origin main`.
3. `git tag vX.Y.Z && git push origin vX.Y.Z` — the `publish-mcp.yml` Action builds the
   `.mcpb`, attaches it to the GitHub Release, and republishes `server.json` to the official
   registry via GitHub OIDC.
4. **Push the tag exactly ONCE.** Re-tagging (delete+repush) spawns a second CI run that
   rebuilds a different `.mcpb` (zip mtimes differ) → the registry's `fileSha256` ends up
   pointing at one bundle while the Release asset is the other. If that happens, don't re-tag —
   cut the next patch version cleanly (one tag, one run). Verify after: registry `fileSha256`
   == `shasum -a 256` of the downloaded asset.
5. Marketplace plugin + the pointer-PR lists track repo HEAD automatically; the copy-in lists
   (sickn33) and any blocked targets need a manual re-PR.

### Surfaces
| Surface | Type | Updates how | Link / id |
|---|---|---|---|
| **Official MCP Registry** | MCP | ✅ auto on `git tag` (CI OIDC publish) | `io.github.connerkward/mcp-apple-notes` · `registry.modelcontextprotocol.io/v0/servers?search=io.github.connerkward/mcp-apple-notes` |
| **GitHub Release `.mcpb`** | MCP | ✅ auto on tag (CI) | `github.com/connerkward/mcp-apple-notes/releases` |
| **ckw-skills marketplace** | plugin | ✅ auto — entry points at repo HEAD | `github.com/connerkward/ckw-skills` |
| **GitHub topics** | both | manual: `gh api -X PUT repos/connerkward/mcp-apple-notes/topics` | mcp, mcp-server, model-context-protocol, claude-code, agent-skills, apple-notes… |
| **Glama** (glama.ai) | MCP | 🕓 auto-crawl (repo has `glama.json` + topics); **ownership claim** needs browser GitHub login | `glama.ai/mcp/servers` |
| **PulseMCP** | MCP | 🕓 auto-mirrors the official registry | `pulsemcp.com/servers` |
| **punkpeye/awesome-mcp-servers** | MCP | 📝 PR #8199 (Knowledge & Memory section); update = new PR | `github.com/punkpeye/awesome-mcp-servers/pull/8199` |
| **jeremylongshore/claude-code-plugins-plus-skills** | both | 📝 PR #871 (pointer in `sources.yaml`, weekly sync vendors files); update = edit that entry | `github.com/jeremylongshore/claude-code-plugins-plus-skills/pull/871` |
| **sickn33/antigravity-awesome-skills** | skill | 📝 PR #703 (**copies** SKILL.md in); update = new PR editing their copy | `github.com/sickn33/antigravity-awesome-skills/pull/703` |
| **netresearch/claude-code-marketplace** | plugin | 📝 PR #70 (pointer; may be declined — internal catalog); update = edit their marketplace.json | `github.com/netresearch/claude-code-marketplace/pull/70` |
| **appcypher/awesome-mcp-servers** | MCP | ⛔ PRs+issues disabled on the repo; fork `connerkward/awesome-mcp-servers-1` branch ready if re-enabled | — |
| **mcp.so** | MCP | 🔒 web form + GitHub login | `mcp.so/submit` |
| **Smithery** | MCP | 🔒 `smithery login` (browser) + API key, then `smithery mcp publish ./*.mcpb -n connerkward/mcp-apple-notes`; repo has `smithery.yaml` | `smithery.ai/new` |
| **mcpservers.org** (wong2) | MCP | 🔒 web form only ("we do not accept PRs") | `mcpservers.org/submit` |
| **mcp-get** | MCP | ⛔ skipped — stale (last add 2025) + npm name `mcp-apple-notes` owned by another author | — |

### Auto-crawler discovery aggregators (no submission — they crawl topics/manifests)
claudemarketplaces.com, claudepluginhub.com, quemsah/awesome-claude-plugins — pick up the repo
+ ckw-skills `marketplace.json` from the topics set above; verify appearance after a crawl cycle.

---

## The 7 ckw-skills (lookdev, deterministic-design, ckw-design, screenstudio-alt, web-media-getter, macos-screen-recorder, lookdev-auto)

Distribution pass 2026-06-17 for all skills in `ckw-skills` **except** apple-notes + muser. These
are pure skills (no `.mcpb`/registry release), so **`git push` to a skill repo is the whole update
path** — there's no tag/version step. Each skill repo carries the topic set:
`claude-code, claude-code-plugin, claude-code-skill, claude-skill, agent-skills, anthropic, ai-tools` + per-skill tags.

| Surface | Updates how on `git push` | Status |
|---|---|---|
| **ckw-skills marketplace** | ✅ auto — entries point at each repo; install resolves HEAD | live |
| **GitHub topics → claudemarketplaces / claudepluginhub / quemsah / Glama** | ✅ auto-crawl by topic | topics set; verify after crawl cycle |
| **jeremylongshore/claude-code-plugins-plus-skills** | ✅ pointer in `sources.yaml`, weekly sync re-vendors | PR [#872](https://github.com/jeremylongshore/claude-code-plugins-plus-skills/pull/872) (7 entries) |
| **netresearch/claude-code-marketplace** | ✅ pointer entries | PR [#71](https://github.com/netresearch/claude-code-marketplace/pull/71) (7 plugins) |
| **sickn33/antigravity-awesome-skills** | ❌ copies SKILL.md in → re-PR on content change | PR [#704](https://github.com/sickn33/antigravity-awesome-skills/pull/704) (7, mergeable) |
| **ComposioHQ/awesome-claude-skills** (64.9k★) | ❌ static README entry → re-PR if pitch changes | PR [#1094](https://github.com/ComposioHQ/awesome-claude-skills/pull/1094) (7 entries) |
| **hesreallyhim/awesome-claude-code** (46.7k★) | — | ⛔ issue-form only, PRs forbidden; needs traction first |
| **travisvn/awesome-claude-skills** (13.5k★) | — | ⛔ hard 10-star auto-close gate; repos at 0★ |

All 7 repos verified MIT (fixed `screenstudio-alternative-skill` LICENSE — was truncated, GitHub
read it as NOASSERTION).

### Additional directories — 2026-06-17 sweep (more PRs)
| Directory | Stars | Action |
|---|---|---|
| majiayu000/claude-skill-registry-core | — | PR [#220](https://github.com/majiayu000/claude-skill-registry-core/pull/220) (7 skills) |
| BehiSecc/awesome-claude-skills | 9.5k★ | PR [#374](https://github.com/BehiSecc/awesome-claude-skills/pull/374) (7 skills) |
| GetBindu/awesome-claude-code-and-skills | — | PR [#70](https://github.com/GetBindu/awesome-claude-code-and-skills/pull/70) (ckw-skills marketplace) |
| jqueryscript/awesome-claude-code | 426★ | PR [#409](https://github.com/jqueryscript/awesome-claude-code/pull/409) (7 skills) |

### Gated — need the USER (auth / human form / organic stars); NOT automatable
| Target | Wall |
|---|---|
| hesreallyhim/awesome-claude-code (46.7k★) | human web issue-form ONLY; `gh` = CoC violation + ban risk. Submit at `issues/new?template=recommend-resource.yml` — focused single skills (not the marketplace; they reject marketplaces), fill License + validate-claims from each repo's README. |
| anthropics official plugin directory | web form + review: `clau.de/plugin-directory-submission` |
| Smithery (skills) | needs account + API key |
| travisvn/awesome-claude-skills (13.5k★) | auto-closes <10★ (ckw-skills at 0★) |
| VoltAgent/awesome-agent-skills | rejects brand-new/unadopted skills (maturity gate) |
| agentskill.sh / ClaudePluginHub form | web submit + login |
| davila7/claude-code-templates, claude-market | content-COPY marketplaces — multi-file skills would ship broken; skip |

**The one lever for the star-gated lists (travisvn, VoltAgent, hesreallyhim's bar): organic ≥10★.**
A crosspost/announce drives that — but publishing public content is human-gated, so it waits for approval.

---

## Open TODOs (Tier-1 GEO — the high-value remainder)

1. **Muser → official MCP Registry.** Drafts ready (uncommitted) in `connerkward/Muser`: `server.json`
   (`io.github.connerkward/muser`, mcpb path), `manifest.json` (MCPB 0.3, `server.type: uv`),
   `.github/workflows/publish-mcp.yml`, `.mcpbignore`. **BLOCKED on verification** — Muser's MCP server
   is a thin client of a heavy `muser serve` FastAPI+SigLIP service (multi-GB first run); the uv-Python
   bundle is unproven. Do NOT blind-tag. Next: install `@anthropic-ai/mcpb`, `mcpb validate`+`pack`,
   launch-test. If it won't bundle cleanly, SKIP the registry (Muser keeps crawl+marketplace coverage).
2. **Launch.** Show HN + r/ClaudeAI + Product Hunt + devlog for the skills + apple-notes. Highest-value
   Tier-1 backlink/citation event (HN is extreme-DA + heavily LLM-scraped); the stars it earns unlock
   the gated lists. Human-gated (public, under the user's name) → route via `devlog`/`crosspost`,
   preview-first; lead with each project's consistent entity one-liner.
3. **Official Claude plugin directory** (`claude-community`) — submit via the **Console** form
   `platform.claude.com/plugins/submit`; **your submissions list is `platform.claude.com/plugins/submissions`**
   (the dashboard — check it FIRST to avoid duplicates; the claude.ai admin path is Team/Enterprise-gated
   and won't work on a Max/individual plan). Run `claude plugin validate ./<plugin>` before submitting.
   Per-plugin form: link, name, description, example use cases, supported platform (Claude Code vs Cowork),
   license, contact email. Consent checkbox (legal Terms) + the final "Submit for review" are the USER's
   clicks; the agent fills the rest. Submitting ≠ guaranteed inclusion (Anthropic review + safety screen;
   approved → `anthropics/claude-plugins-community`, nightly sync). **Pending review as of 2026-06-17:**
   `apple-notes`, `lookdev`, `screenstudio-alt`, `deterministic-design`. **Not yet submitted:** `ckw-design`,
   `web-media-getter`, `macos-screen-recorder`, `lookdev-auto`, `muser`. Note: nothing here shows in the
   public community catalog until APPROVED, and there's no email confirmation — the dashboard is the only
   source of truth.
4. **Verify the auto-crawlers actually ingested** (don't assume — [[verify-external-claims-rule]]). After a
   crawl cycle, confirm the repos now appear: Glama (`glama.ai/mcp/servers` search), claudemarketplaces.com,
   claudepluginhub.com, agentskill.sh (its earlier import returned `failed` — re-check or treat as not-covered).
   Topics were set 2026-06-17; if a directory still doesn't show the repo after ~2 cycles, its crawl trigger
   differs from topics — investigate or submit manually.
5. **Submit the remaining 5 to the official Claude plugin directory** (see TODO 3): `ckw-design`,
   `web-media-getter`, `macos-screen-recorder`, `lookdev-auto`, `muser`. Agent fills the form; user does
   consent + final submit per plugin.
