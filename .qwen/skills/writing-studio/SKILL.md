---
name: writing-studio
description: Review and iterate written DRAFTS in an interactive in-browser studio — render one or many drafts into a readable page, highlight-to-comment, leave a per-piece note, then export a feedback JSON the author pastes back to drive revisions. The prose sibling of lookdev / visual-eval-loop (there the eye or a VLM judges; here the HUMAN judges, and JSON is the round-trip). Use WHENEVER presenting drafts for human review/markup, collecting structured feedback on writing, ghostwriting that needs an author sign-off gate, or running a draft→feedback→revise loop.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# writing-studio

A studio for **judging prose with a human in the loop** — the writing analogue of `lookdev`
(tune a visual param by eye) and `visual-eval-loop` (render variants, judge by rubric). Here
the artifact is text, the judge is the author, and the round-trip is a **feedback JSON** —
the same copy-the-JSON-and-paste-it-back move `lookdev` uses for settings.

Use it so feedback is **located and actionable** ("this sentence → tighten") instead of a
vague "make it better," and so nothing ships without an explicit human gate.

## The loop

1. **Draft** — produce one or more drafts (e.g. via `writing-as-conner`, or any prose task).
2. **Render into the studio** — populate `assets/drafts-review.html` (a template per draft).
3. **Author marks up** — select text → highlight or attach a comment; per-piece overall note.
4. **Export** — hit **copy feedback JSON**; author pastes it back to you.
5. **Revise** from the JSON (each item is a quote + a note, scoped to a draft).
6. **Repeat** until sign-off, then ship (e.g. to the blog) — only after approval.

## The studio (`assets/drafts-review.html`)

Self-contained, zero-build HTML (one CDN font). What it gives the reader:
- **Tabs** — one per draft; reads in a clean editorial register (close to the live blog).
- **Optional hero** per draft (`data-hero`; pull via `web-media`, CC/PD only, record credits).
- **Highlight-to-comment** — select any text → a popover; save a comment or just highlight.
  Uses the **CSS Custom Highlight API** (no DOM surgery; survives across element boundaries).
- **Per-piece "overall note"** textarea.
- **Comment rail** listing marks (click to scroll back; delete).
- **`localStorage`** persistence, so a reload doesn't lose markup.
- **copy feedback JSON** → clipboard.

**Populate it:** copy `assets/drafts-review.html` to a working dir and add one
`<template data-art="unique-id" data-title="Title" data-hero="optional.jpg">` per draft. The
body is semantic HTML the engine renders automatically:
`<p class="lead">` (dek) · `<p>` · `<h2>` · `<blockquote>…<span class="by">— Name</span></blockquote>` ·
`<em>` · one `<p class="pull">`. No code changes needed — the engine reads the templates.

**Feedback JSON schema** (what the author pastes back):
```json
{ "drafts": [
  { "title": "…", "overall": "…",
    "comments": [ { "quote": "the highlighted text", "note": "the comment (may be empty)" } ] }
] }
```
The `quote` locates the passage; act on the `note`. Empty note = a plain highlight (attention).

## Deliver it the way the author can actually use it

- **Serve, don't `file://`** — Playwright/automation blocks `file:`. Serve the dir
  (`~/dev/central/scripts/serve <dir> --bg`) and open the `http://localhost:…` URL in the
  **author's real browser** (`claude-in-chrome`) so they can interact (this is the rare case
  where claude-in-chrome is right — the human IS the judge).
- **Verify before handing over** (per `verify-outputs-rule`): with headless Playwright, drive
  a select→comment→copy round-trip and confirm the stored comment + exported JSON actually
  populate. A studio whose controls don't fire is a vacuous green.

## Why a studio, not just "paste the draft in chat"

Chat feedback is unlocated and lossy; the author can't easily say "this clause, here." The
studio turns reading into structured, quote-anchored markup, and the JSON makes the revise
step mechanical. Same reason `lookdev` beats "describe the color you want" — put the judgment
on the artifact, round-trip a machine-readable result.

## Related

- `lookdev` / `visual-eval-loop` — sibling studios (visual params, judged by eye/VLM). This
  one judges **prose**, by a **human**.
- `writing-as-conner` — a consumer: it owns the voice/content; this owns the review UX.
- `design-system` — the editorial type register (Iowan) the studio reads in.
- `web-media` — hero images (record CC/PD credits).
