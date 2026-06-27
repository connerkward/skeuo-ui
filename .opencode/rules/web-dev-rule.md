---
name: "web-dev-rule"
id: "web-rule-01"
description: "Multi-window web dev isolation: each Claude window runs its own git worktree, dev server, and Playwright browser profile."
globs: ["**/*.tsx", "**/*.jsx", "**/*.ts", "**/*.js", "**/*.css", "**/*.scss", "**/*.html", "**/vite.config.*", "**/next.config.*", "**/package.json"]
applyTo: ["**/*"]
alwaysApply: false
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---
# Multi-window web dev isolation

When more than one Claude window is working on the same web project at the same time, each window must operate in an isolated environment. Sharing causes file stomps, HMR thrash, and "Browser is already in use" Chrome lock errors.

## The three things to isolate

**1. Worktree.** Each Claude window gets its own git worktree on its own branch — see [[git-worktree-rule]] for the mechanics (`git worktree add ../<repo>-<topic> -b <topic-branch>`, work + commit + push from there, `git worktree remove` when done). The web-specific reason it's non-negotiable: even on *different files*, two windows in the same checkout share one dev server, so HMR fires on both windows' edits and stale reads overwrite each other. `node_modules` is per-worktree, so `npm install` once in each.

**2. Dev server / static preview.** Each worktree runs its own server, and **no two sessions may hardcode the same port.** This is the most common collision: two Claude windows both `python3 -m http.server 4848` (or any fixed port). Whoever binds the socket wins, so the human loads the URL and gets a coin-flip of which session's content — and a blanket `pkill -f http.server` from one window kills the *other* window's server.

- **Framework dev servers (Vite etc.):** fine as-is — Vite with default `strictPort: false` auto-falls-through to the next free port (5173 → 5174 → 5175). If a project pins `strictPort: true` (some Astro/Next templates), pass `--port` explicitly per worktree.
- **Static / ad-hoc servers (`python3 -m http.server`, lookdev studios, preview pages): never pick a fixed port.** Use the shared helper, which binds port 0 so the OS hands back a guaranteed-free port and writes the chosen URL to `<dir>/.serve-url`:

  ```bash
  ~/dev/central/scripts/serve <dir> --bg     # prints the chosen URL (free port, no collision)
  ~/dev/central/scripts/serve --stop <dir>   # kills ONLY this server, never a sibling session's
  ~/dev/central/scripts/serve --list         # show servers this tool started
  ```

- **Never `pkill -f http.server` (or any broad name match).** It reaches across sessions. Kill only your own server — by the pid/port you started, or via `serve --stop <dir>`. The same applies to any shared process name: scope kills to a pid or a port you own, never a substring that matches siblings.

**3. Playwright browser profile.** The Playwright MCP defaults to a shared Chrome `--user-data-dir`. A second Claude window trying to launch Playwright while another holds it will fail with "Browser is already in use." Two fixes:

- Global, no persistence: add `"--isolated"` to the playwright args in `~/.claude.json` (each session gets a temp profile).
- Per-project, persistent: drop a `.mcp.json` in the repo with `--user-data-dir <unique-path>`; project-scoped servers override the user-level one. Useful when you want logged-in state to persist within a project.

## Why this matters

The failure modes are silent until they aren't. Two windows on the same branch will look fine for a while, then one window's screenshot will reflect code the other window already overwrote. The Playwright collision is louder (immediate error) but the file-stomp case is the dangerous one — it produces wrong test results that look right.

## When this rule does *not* apply

Single Claude window: ignore everything above, work normally in the main checkout. The rule only triggers when there's a second window touching the same repo concurrently.

## Public-facing pages — make them discoverable

For any page meant to be found/cited (landing, blog, portfolio, docs), apply
[[geo-seo]]: owned canonical first, entity name + one-line definition under the H1,
schema.org JSON-LD, `llms.txt`, AI-crawler allow rules. Crawlable + fast (the
isolation/port discipline above) is the precondition; geo-seo is the rest.
