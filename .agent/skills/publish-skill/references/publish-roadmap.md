# Publish roadmap & strategy (living doc)

Order: **ship the blocks first, work upward.** Foundational skills now; orchestrators later.
Nothing public until the per-repo sanitization diff is human-approved (Aa).

## The two narratives we're selling

Everything ladders up to two positioning stories — this is the cross-market spine:
1. **Human-in-the-loop** — a human steers/judges generative output, vs fire-and-forget AI.
   → **`lookdev`**, **`screenstudio-alt`**, **`writing-studio`** (prose sibling — human judges
   drafts, JSON round-trip).
2. **Determinism beats AI randomness** — render and *measure*, don't trust the model's eye.
   → **`deterministic-design`**.

**Flagships: `lookdev`, `deterministic-design`, `screenstudio-alt`.** The rest are
secondary. `lookdev-auto` is the *foil* (model-judged, stochastic) — frame it honestly as the
automated counterpart, never as a flagship.

## Framing principle (every README)

State honestly which one this is — never blur:
- **Improving an existing Claude Code behavior** — name what it extends; don't claim to reinvent.
- **A new paradigm / capability** — say that, and why it's new.

(Audited honestly: `lookdev` = new interaction; `deterministic-design` = improves + adds a real
new deterministic check; `lookdev-auto` = *structures* an existing ability, not new; tools =
new capabilities, some explicitly "alternatives.")

## Publish queue — now (the blocks)

| internal | repo | lib | frame |
|---|---|---|---|
| `lookdev` | `lookdev-studio-skill` | `lookdev` | **New interaction** — human-in-the-loop web visual editor for generative output |
| `deterministic-design` | `deterministic-design-skill` | `deterministic-design` | **Improves + new check** — deterministic layout audit + vision-judged UX the default lacks |
| `screenstudio-alt` | `screenstudio-alternative-skill` | `screenstudio-alt` | **New capability (alternative)** — open-source Screen Studio alternative |
| `ckw-design` | `ckw-design-skill` | `ckw-design` | **Personal take / portfolio** — direction, system, philosophy; `ckw-` = attribution |
| `web-media` | `web-media-getter-skill` | `web-media-getter` | **New capability** — one query across free media APIs; OSS + PRs |
| `macos-screen-recorder` | `macos-screen-recorder-system-audio` | — | **New tool, narrow** — CLI screen record + system audio, no driver. Not "better," just the gap |
| `lookdev-auto` | `lookdev-auto-skill` | `lookdev-auto` | **Structures existing behavior** — automated vision-judge loop; secondary |

## Round 2 — queued (not yet published)

| internal | repo | lib | frame |
|---|---|---|---|
| `writing-studio` | `writing-studio-skill` | `writing-studio` | **Human-in-the-loop (new interaction)** — interactive studio to review/iterate written drafts: highlight-to-comment + feedback-JSON round-trip. The prose sibling of `lookdev`. Artifact: markdown + self-contained `assets/drafts-review.html` (one CDN font; sanitize any personal paths; works on clone). |

- **`writing-as-conner` stays PRIVATE** — it embeds the author's personal voice corpus + notes; not for public release. Only its generic review UX (`writing-studio`) publishes.

## Later (TODO)
- **dailies** — make a publishable form (orchestrator over screencast / screenstudio-alt). After the blocks.
- **agent-radio** — skip for now.
- **crosspost** — stays private (existing public repo left as-is).

## Defaults
- Every repo: **MIT LICENSE** (added at publish; central carries none) + **PR-friendly**
  (CONTRIBUTING, good-first-issue).
- README H1 = lib entity name + a one-line "X is a Y that does Z" + topics
  (`claude-code`, `claude-skill`, `agent-skills`, …) for the crawlers.

## web-media specifics
- **Drop GIPHY** (its API is no longer free) — Klipy is the free GIF source.
- README: "free APIs; respect the per-item `license` field" — don't claim all results are CC0.

## Go-to-market caveat (honest only)
The "ask for Screen Studio alternatives from one account, answer from another" idea is
**astroturfing** — banned by Reddit/HN, detectable, reputation-torching. Honest equivalents:
**Show HN** (disclose authorship) and reply in *existing* alternative-seeking threads as the author.

## PUBLISHED 2026-06-16 (live)

All 7 pushed public + each is its own installable plugin AND its own marketplace; plus a combined catalog. All pass `claude plugin validate`.

| lib | repo | install |
|---|---|---|
| lookdev | [lookdev-studio-skill](https://github.com/connerkward/lookdev-studio-skill) | `/plugin marketplace add connerkward/lookdev-studio-skill` |
| deterministic-design | [deterministic-design-skill](https://github.com/connerkward/deterministic-design-skill) | `…add connerkward/deterministic-design-skill` |
| ckw-design | [ckw-design-skill](https://github.com/connerkward/ckw-design-skill) | `…add connerkward/ckw-design-skill` |
| screenstudio-alt | [screenstudio-alternative-skill](https://github.com/connerkward/screenstudio-alternative-skill) | `…add connerkward/screenstudio-alternative-skill` |
| web-media-getter | [web-media-getter-skill](https://github.com/connerkward/web-media-getter-skill) | `…add connerkward/web-media-getter-skill` |
| macos-screen-recorder | [macos-screen-recorder-system-audio](https://github.com/connerkward/macos-screen-recorder-system-audio) | `…add connerkward/macos-screen-recorder-system-audio` (+ binary in [Releases](https://github.com/connerkward/macos-screen-recorder-system-audio/releases)) |
| lookdev-auto | [lookdev-auto-skill](https://github.com/connerkward/lookdev-auto-skill) | `…add connerkward/lookdev-auto-skill` |

Combined catalog: [connerkward-skills](https://github.com/connerkward/connerkward-skills) — `/plugin marketplace add connerkward/connerkward-skills`.

**Discovery status:** topics set on all (the automated crawlers — claudemarketplaces.com, quemsah, claudepluginhub — index by topic, no action). **Anthropic community registry (platform.claude.com/plugins/submit): PENDING — requires the user's logged-in Claude session; agent cannot authenticate.**

**Follow-ups:** demo gifs in READMEs (force-push dropped old demo media — re-add, also needed for crosspost); curated-list PRs (awesome-claude-* etc.); crosspost announcement (deferred per user).

## TODO — Cowork availability
The 3 flagship registry submissions checked **Claude Code only** (conservative — they're
tested there, and the form asks you to verify each surface before claiming it). **Verify
each skill actually works in Claude Cowork, then enable the Cowork platform** on the
submission (re-submit/edit) so they're available on both surfaces. Most are markdown/CLI
skills that should port cleanly; confirm the studio (lookdev) and ffmpeg-based ones behave
in the Cowork environment before ticking the box.

## Crosspost / publish queue — future (needs cook time or packaging)
Ordered by readiness, after screenstudio-alt ships:
- **generative-ui music player** (the skeuomorphic / generative-UI music-player skins work) —
  strong visual/viral hook; needs packaging into a publishable artifact + demo.
- **deterministic-design** — crosspost candidate (the "anti-AI-slop, measure don't vibe" post);
  ready-ish, good as post #2. Needs a before/after demo asset.
- **agent-radio** — highest pure virality (RTS transmission voice + portrait cards) but **needs
  more cook time** before publish/crosspost; revisit later.
- **muser** — local-first semantic image search (find photos by description, fully offline, no API keys). Clean privacy hook; needs packaging.
- **explorable** — interactive explorable-explanations builder (Bret Victor / Nicky Case lineage). Plays well with the tools-for-thought crowd; needs a flagship example to show.

## Also publish/announce — mcp-apple-notes (already public)
- **[mcp-apple-notes](https://github.com/connerkward/mcp-apple-notes)** — MCP server for Apple Notes (repo already public). This is an **MCP server, not a Claude skill**, so it does NOT go to the Claude plugin marketplace/skill indexes. Its targets are the **MCP registries**: Smithery, mcp.so, Glama, PulseMCP (the `crosspost` skill already lists these). To do: GEO/README pass (entity name + one-line definition + a demo gif), register on the MCP registries, then crosspost/announce. Pairs conceptually with the `apple-notes-export` skill.
- **ji-blur-site** — crosspost target **X/Twitter** (and maybe Reddit); **not** HN-worthy (too small a piece). Just an announce/share, not a full launch.
