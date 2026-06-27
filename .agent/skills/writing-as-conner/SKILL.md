---
name: writing-as-conner
description: Draft blog posts, essays, devlogs, and public writing in Conner Ward's own voice — ghostwriting from his notes. Use WHENEVER turning his notes/theses into a post, drafting "in my voice", writing a blog entry for connerkward.dev/writing, or continuing/expanding his essays. Grounds every draft in his actual notes (no fabricated facts/quotes), matches his documented voice, optionally injects a hook, and routes drafts through a highlight-and-comment review app for human approval before anything ships.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# writing-as-conner

Ghostwrite in Conner's voice — not a generic "good essay," *his* essay. The job is to
turn a thesis from his notes into a finished draft that reads like he wrote it, grounded in
his own arguments and references, then gate it through his review before it ships.

**The non-negotiables:** ground in his notes (never invent his opinions), no fabricated
stats/quotes, match the voice profile, and **never auto-publish** — drafts go through the
review app for his highlight/comment pass first.

## The corpus (where his thinking lives)

`~/Desktop/jun162026notesexport/ACTIVES/BLOG/` — his blog notes. Key files:
- `⭐️ THESES.md` — the master list of throughlines (aesthetics, AI/UX, industrialization,
  geopolitics, personal).
- `HIGHEST ROI BLOG POSTS.md` — his own ranked queue with sources, reference scaffolds, and
  effort/"hiring-signal" notes. **Start here when picking what to write.**
- `POSTS/` — per-post drafts/fragments (most posts have a source note).
- `HOOKS/` — collected quotes, idioms, foreign words, anecdotes to open/spice/close a post
  (curated into [`references/hooks-library.md`](references/hooks-library.md)).

The published voice exemplar (his actual finished register):
`~/dev/portfolio-2026/writing-app/content/things-that-love-to-exist.mdx`.

## The process

1. **Pick the thesis** from `HIGHEST ROI BLOG POSTS.md` / `⭐️ THESES.md` (or take his ask).
   Confirm the pick before writing a full essay — it's his identity on the page.
2. **Ground it in his notes.** Read the source note(s) for that post. Use *his* argument,
   analogies, and named references. **Do not invent his positions.** For outside facts, cite
   real named sources (author + work + year); use a statistic only if it's in his notes or
   you can attribute it — otherwise hedge or cut. No fabricated quotes, ever.
3. **Match the voice** — load [`references/voice-profile.md`](references/voice-profile.md)
   (full profile + 35 verbatim sample passages) and write to it. Cheat-sheet below.
4. **Optionally inject a hook** from [`references/hooks-library.md`](references/hooks-library.md)
   as an opener, aside, section preface, or closing turn — only where it earns its place.
5. **Present for review, don't publish — via `writing-studio`.** The review UX (the
   drafts studio: highlight-to-comment, per-piece note, copy-feedback-JSON) lives in the
   **`writing-studio`** skill — load it and use its `assets/drafts-review.html` template.
   Populate one `<template>` per draft, add a hero (pull via `web-media`, CC/PD, record
   credits), serve it, and open it in his real browser so he marks it up.
6. **Revise from the feedback JSON** (quotes + notes per piece; schema in `writing-studio`).
   Iterate until he signs off.
7. **Ship** to the `/writing` blog as MDX in the Iowan register (see the portfolio's CLAUDE.md
   for the blog pipeline) — only after his sign-off. Apply `geo-seo` claim-hygiene to any
   factual claims before publishing.

## Voice cheat-sheet (full profile in references/voice-profile.md)

- **High-register vocab collided with blunt vernacular** — *simulacrum / rent-seeking /
  appropriability* sitting next to *"we are fucked," "literally colonial type shit."* The
  collision IS the voice; don't sand either pole off.
- **Crude self-puncturing asides** — real and characteristic: *"made me shit my pants a
  little," "shoutout to Jared Diamond for sponsoring this episode," "Maybe I'm just a serious
  guy."* Use sparingly, never forced.
- **Analogy-driven "X as Y" reasoning** is the engine — reason by lens, not assertion (a Lays
  chip *as* epoxy-filled delignified wood; the training run *as* a clinical trial).
- **Names specific scholars/works/places as load-bearing evidence**, never decoration
  (Mullaney, Gibson, Heidegger, Kapferer, Carlota Perez — the real ones, correctly).
- **"X was right" / contrarian thesis openers**; **opens on a concrete anecdote**; **ends on
  a TURN, not a summary** (the last line reframes, it doesn't recap).
- **Coins and christens terms** ("Jeffersonian Genocide," "hypographs," "Luxury Software").
- **Hard rhythm swings** — long dash-stacked periodic sentences broken by staccato fragments
  (*"Bland. Empty. Soulless."*); heavy em-dashes.
- **Confessional + contrarian honesty** — admits the trap is one he's felt; hedges his own
  theories ("I don't put much faith in that, but…"); stakes heterodox positions unsoftened.
- **Avoid:** LinkedIn uplift, hedge-everything corporate neutrality, summary endings,
  decorative citations, em-dash-free smoothness, and praise-the-reader filler.

## Piece structure (house template)

Every piece follows the same spine:
- **Open on a concrete anecdote/image**, then **end the opening with an isolated one-line
  thesis** set apart for emphasis (its own line — in the studio that's `<p class="thesisline">`).
  The hook lands, then a single crystallized sentence states what the piece argues.
- **Body** develops it via "X as Y" analogy, named scholars, section `<h2>`s, one mid `<p class="pull">`.
- **Close with a short punch:** a 2–4-word thesis heading (`<h2 class="conc">`) + one tight
  paragraph that nails the argument — a deliberate sign-off that *turns*, never a recap.

So the skeleton is: lead/dek → opening para → **isolated thesis line** → body → … → **punch
heading + paragraph**. Hold this for every draft.

## Provenance caution

Some notes (`LUXURY SOFTWARE POST V0.md`, parts of the NYC essay) are partly AI-assisted or
pasted. Treat those as *raw material for his points*, not as voice samples — the voice must
come from `references/voice-profile.md` and the verified-his passages, not from AI-written
blocks already in the corpus.

## Related

- `writing-studio` — the review/markup UX (drafts studio, highlight→comment, feedback-JSON
  round-trip). This skill owns the **voice/content**; that one owns the **review loop**.
- `geo-seo` — claim hygiene + discoverability before publishing public writing.
- `design` / `design-system` — the Iowan editorial register the blog ships in.
- `web-media` — pull CC/archival hero images (record credits).
- portfolio-2026 `CLAUDE.md` — the `/writing` blog build/deploy pipeline.

## Status (forming)

Bootstrapped from a session that drafted 5 posts (hypographs / affordance / beyond-apps /
pharma / luxury-software) against this method. The review UX has been factored out into
`writing-studio`. Still to harden: add a couple of his *sign-off-quality* finished posts as
gold-standard few-shot exemplars once they ship.
