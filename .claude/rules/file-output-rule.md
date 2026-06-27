---
name: "file-output-rule"
id: "file-output-01"
description: "Where agent-created files go: /tmp for scratch, ~/Desktop/cc-<project>/ for review deliverables, the repo's docs/ for reference docs; every Desktop agent folder wears a cc- prefix."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# File output locations

Where the agent puts files it creates. Default to keeping the user's workspace clean,
and make every agent-created file structurally distinguishable from the user's own.

## The `cc-` rule (the one that matters)

**Agent output on `~/Desktop` goes in one folder per project: `~/Desktop/cc-<project>/`.**
`cc-` = the agent made this. This is the load-bearing convention: it is the only thing
that separates "the agent's output" from "the user's own files" on a Desktop where the
two are otherwise indistinguishable (a 96 GB Google Takeout sitting next to a generated
demo). With the prefix, `~/Desktop/cc-*` is the agent's review/inbox material and
*everything without the prefix is the user's, never to be touched, moved, or swept.*

- **One folder per project**, stable and reused: `~/Desktop/cc-skeuo/`, `~/Desktop/cc-feedsieve/`.
  Don't spawn a new dated folder per task — the project folder accumulates.
- **Flat inside.** No nested subfolders. Files sit directly in `cc-<project>/`.
- **Name files so they sort by task** — task- or date-prefixed
  (`2026-06-13-ig-demo.gif`, `ig-demo.gif`, `feed-health.md`), so the flat folder stays
  scannable as it grows.
- Never a loose `cc-` file at the Desktop top level — everything lives inside its
  `cc-<project>/` folder.

## Three destinations, by intent

| What | Where | Why |
|------|-------|-----|
| **Transient — agent-only scratch the user never sees.** Intermediate downloads, base64 buffers, polled job responses, logs you tail once, verification screenshots ("did it render?"), WIP files you'll consolidate before reporting. | `/tmp/<descriptive-name>` | Cleared by the OS on reboot. Out of sight. No prefix needed — never surfaced. |
| **A showcase artifact / deliverable the user reviews.** Contact sheets, demo gifs, generated images/video, side-by-side comparisons, exports, a report they asked to "just see". | `~/Desktop/cc-<project>/<task-named-file>` (see the `cc-` rule above) | Desktop is the user's **inbox**: they scroll it, then manually graduate keepers to `ideas-syncthing/proj-dailies` (their durable, Syncthing-replicated corpus). The agent does NOT graduate or expire anything — that's a human call. |
| **A durable artifact that belongs to a project.** | the project repo, or `ideas-syncthing` | See "Showcase vs reference docs" below. Not the Desktop. |

## Showcase vs reference docs

Two registers of "documentation"; they go to different places:

- **Reference docs** — textual, audience is a *future builder* who needs to use/maintain
  the thing (READMEs, API notes, design docs, how-it-works writeups). → the project repo's
  `docs/`, version-controlled with project context.
- **Showcase artifacts** — visual/portfolio, audience is a *viewer* who needs to see or
  evaluate the work (gifs, renders, contact sheets, the eventual written "case study").
  → `~/Desktop/cc-<project>/` as inbox; the user graduates keepers to `ideas-syncthing/proj-dailies`.

Showcase artifacts are **never** `docs/`, and reference docs are never dropped on the
Desktop. Bias toward **producing more** showcase artifacts, not fewer — they are cheap to
make now (assets and context are already loaded) and expensive-to-impossible to recreate
later. Volume is not the problem; an un-prefixed, un-replicated heap is.

## Rules of hygiene

1. **Only surface final deliverables.** If you generated 12 files to produce one contact
   sheet, all 11 intermediates are `/tmp/` material; only the contact sheet goes to
   `~/Desktop/cc-<project>/`.
2. **Never write to the `~/Desktop` top level.** All agent output lives inside a
   `cc-<project>/` folder — the `cc-` prefix is what makes agent output safe to identify
   and the user's files safe from cleanup. A loose or un-prefixed agent file on the
   Desktop is a bug.
3. **Never write to `~/Desktop` for a file the user didn't ask for.** Don't auto-screenshot
   every verification step there — those are `/tmp`. Desktop is for deliverables.
4. **Clean up `/tmp` aggressively** between tasks (`rm /tmp/cap-*.jpg /tmp/openai-*.json`).
5. **`.scratch/` in repo roots is deprecated** — use `/tmp` for the agent's own loop,
   `~/Desktop/cc-…` to surface to the user. Only use `.scratch/` if the user explicitly
   asks for a repo-relative path, in one dated subfolder, cleaned up when done.
6. **`~/Downloads` is off-limits** for agent-generated files — the user's browser-download
   space.

## The decision in one sentence

Agent-only scratch → `/tmp`; something the user should review → `~/Desktop/cc-<project>/`
(flat, files named by task; their inbox); reference docs → the repo's `docs/`. Every
agent folder on the Desktop wears a `cc-` prefix; everything without one is the user's.

## Exception

If the user explicitly names a path (including `Downloads` or `.scratch/`), follow their
instruction. This rule only governs the default when no location is specified.
