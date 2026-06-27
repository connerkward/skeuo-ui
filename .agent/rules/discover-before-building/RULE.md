---
name: "discover-before-building-rule"
id: "discover-before-building-01"
description: "Before building any non-trivial feature or solving a non-trivial problem, run a repo-WIDE discovery sweep (not just src/) and read the project's own docs/process pages for an existing implementation, prototype, or spec. Do not reinvent what already exists."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-23
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---
# Discover before building — search the WHOLE repo for what already exists

Before you build a non-trivial feature or solve a non-trivial problem, **assume a
better version already exists in this repo and go find it first.** The default is
not "write it" — it's "search the whole repo and read its docs, then port/wire what's
there." Reinventing a thing the repo already has is the most expensive kind of waste:
you ship a *worse* implementation while the documented good one sits unused.

## The burn that anchors this

skeuo-ui, 2026-06-23: the runtime "generate a skin" pipeline
(`src/generate/cutoutClient.ts`) grew a homegrown **heuristic** control-detector —
dark-blob detection + nearest-neighbor matching — rebuilt from scratch over many
rounds. But a **better, documented** implementation already existed in the repo:
`generation/sam_snap.py`, the "Align" pass (SAM 3.1 box-prompted by each control's
template rect → snap/warp). It was even written up on the project's own process page
(`site/index.html`, the "Align — VLM mask + snap/warp" step). When the user asked
*"do we have an LLM pass that draws where slots are,"* the agent `grep`-ed only
`src/`, found nothing, and answered **"no"** — while `generation/sam_snap.py` was
right there. The agent never searched outside `src/` and the conversation summary.
The user: *"how to make sure this 'missing part of codebase' never happens again."*
The cost wasn't difficulty — it was never looking past the obvious directory.

## The discovery sweep — do this BEFORE writing a detector/parser/pipeline/algorithm

1. **`grep -ri` the WHOLE repo** for the concept's keywords *and* likely filenames —
   not just `src/`. From the repo root, no path filter. Search synonyms (detector,
   snap, align, mask, segment, warp, match…), not just your one chosen word.
2. **List the adjacent non-`src/` dirs and read their contents.** Existing
   implementations and prototypes hide in `generation/`, `scripts/`, `tools/`,
   `prototypes/`, `notebooks/`, `experiments/`, and standalone `*.py` / `*.sh` /
   `*.ipynb` at the repo root — exactly the places a `src/`-only grep never reaches.
3. **Read the project's own docs and process/design pages.** `docs/`, `README*`, and
   especially a `site/` / landing / process page that *documents the intended
   pipeline* (the skeuo "Align" step lived there). The design page is often the
   fastest map to what already exists and what the system is *supposed* to do.
4. **Prefer porting/wiring the existing prototype over a fresh build.** If you find
   one, the job is to connect/port it, not to author a parallel worse version. Only
   build new after the sweep confirms nothing usable exists.

## "Don't we already have X?" → near-certain proof X exists

When the user implies the thing already exists — *"don't we already have…", "didn't
we build…", "isn't there a pass that…"* — **treat that as near-certain evidence it
does.** Their first-hand memory of their own repo outweighs your search. Before you
answer "no" or start building: grep the **entire** repo and read the design docs. A
failed grep of **one** directory is **not** "it doesn't exist" — that's
[[verify-external-claims-rule]]'s *absence-from-a-proxy ≠ absence* applied to your own
codebase. Answer "no" only after a repo-wide sweep + the docs both come up empty.

## Relation to other rules

This is the **"search the codebase first"** sibling of:
- [[restraint-rule]] — best part is no part; don't build what already exists.
- [[software-engineering-rule]] — use existing tools, don't reinvent; produce less.
- [[verify-outputs-rule]] — verify in the real shipping system, not a reimplementation.
- [[verify-external-claims-rule]] — absence from a proxy (one dir, one search) ≠ absence.

## The one-line test before you build

"Have I `grep`-ed the **whole** repo (not just `src/`), listed the non-src dirs, and
read the project's docs/process page for an existing implementation — or am I about to
reinvent something that's already here?" If you haven't swept, sweep first.
