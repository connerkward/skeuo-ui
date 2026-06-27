# Name map — internal (central) / repo (GitHub) / lib (marketplace display)

Three name surfaces, all distinct. Central uses the **internal** name; publish-skill renames
to the **lib** name in the published `SKILL.md` and pushes to the **repo** name. All public
repos under `github.com/connerkward/`. Repo names carry "skill"/"-skill" for discovery; lib
names are clean; tools (not pure skills) skip the suffix.

| internal (central) | repo | lib | artifact strategy |
|---|---|---|---|
| `lookdev` | `lookdev-studio-skill` | `lookdev` | pure markdown; builds studios on the fly. Works on clone. (sanitize the `portfolio-2026` path) |
| `deterministic-design` (subdir of `ckw-design`) | `deterministic-design-skill` | `deterministic-design` | markdown + `layout-audit.js` (node, no deps). Published from the subdir as its own repo. |
| `ckw-design` | `ckw-design-skill` | `ckw-design` | markdown (design-thinking/system/philosophy). Portfolio piece; `ckw-` is intentional (attribution, not spread). |
| `screenstudio-alt` | `screenstudio-alternative-skill` | `screenstudio-alt` | Python (ffmpeg/PIL, `requirements.txt`) + `events-log.swift` build note; functional `click.wav` committed; demo media stays in repo |
| `lookdev-auto` | `lookdev-auto-skill` | `lookdev-auto` | markdown technique skill |
| `web-media` | `web-media-getter-skill` | `web-media-getter` | `webmedia.py` (stdlib + free API keys via env); **drop GIPHY**; per-item `license` note |
| `writing-studio` | `writing-studio-skill` | `writing-studio` | markdown + self-contained `assets/drafts-review.html` (one CDN font, no other deps; works on clone). Sanitize personal paths/sample content. (`writing-as-conner` stays private.) |
| `macos-screen-recorder` | `macos-screen-recorder-system-audio` | — (tool repo) | **GitHub Release** with prebuilt `sck-record` + `.swift` source + `swiftc` fallback + quarantine note |
| `mcp-apple-notes` (own public repo, fork) | `mcp-apple-notes` (unchanged) | `apple-notes` | **triple-duty** — stays an MCP server (→ MCP-server registries, Tier 4), **plus** a `.claude-plugin/plugin.json` declaring the `mcpServers` + a bundled `skills/apple-notes-search/SKILL.md` (→ ckw-skills plugin marketplace + skill scrapers). `server.json` packaging TBD (npm vs `.mcpb`). |

## Structure notes
- **`deterministic-design` lives nested** under `skills/ckw-design/deterministic-design/` in
  central, but **publishes as its own repo** (better for distribution + its own narrative).
  publish-skill extracts the subdir.
- **One central skill ≠ one repo.** `ckw-design` and `deterministic-design` cohabit in central
  but ship as two repos. `screencast` stays central; only its `sck-record` component publishes
  (as `macos-screen-recorder-system-audio`).
- Compiled binaries are never committed to central (gitignored, built by `setup-machine`); on
  publish they ship as **GitHub Release assets** so users clone-and-go without a toolchain.

## Naming principles (validated against top Claude skill repos, June 2026)
- `-skill`/`-skills` suffix on repos is validated (ui-ux-pro-max-skill, taste-skill, …).
- Simple/descriptive > author-prefixed: author prefixes (`ckw-`) only aid spread for *known*
  authors (baoyu, guizang) — use `ckw-` **only** on the portfolio piece where attribution,
  not adoption, is the goal.
- No unverified superlatives ("better-"); name the real differentiator truthfully
  (`macos-screen-recorder-system-audio` — the system-audio is the actual gap).
- Match repo name → README H1 entity name for GEO.

## Marketplace / install naming — "skill" is IMPLIED, drop it everywhere but the repo

The word "skill" appears in **exactly one place: the GitHub repo name** (for discovery).
It is IMPLIED everywhere else — never put it in the marketplace `name`, the plugin `name`,
or the install reference.

- `marketplace.json` `name` = the **lib name** (e.g. `lookdev`), NOT the repo name.
- Install reads `/plugin install <lib>@<lib>` (clean), never `@lookdev-studio-skill` (verbose).
- Only `/plugin marketplace add connerkward/<repo>` uses the repo name — unavoidable, it's the URL.
- Combined catalog: repo `connerkward-skills`, but marketplace `name` = `connerkward` → `<lib>@connerkward`.

> **NOTE — catalog repo `ckw-skills` now carries MCP-server plugins too**, not just skills (e.g.
> `mcp-apple-notes`). The repo name stays **`ckw-skills`** (kept for SEO — "skills" is the search
> term; a brief rename to `ckw-tools` was reverted 2026-06-17). The marketplace **`name` field is
> `connerkward`** — installs are `<lib>@connerkward`.

This was a correction (2026-06-16): marketplace names were initially set to repo names, making
installs needlessly verbose. Don't repeat it.
