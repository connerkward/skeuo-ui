---
name: "name-ideation-rule"
id: "name-ideation-01"
description: "When the user asks to ideate/brainstorm names, mass-generate 30–60+ varied candidates in prose — never funnel into AskUserQuestion or a 2–4-option selection dialog."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: false
priority: "medium"
human-reviewed-at: 2026-06-26
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Name ideation = mass-generate in prose, NOT a selection dialog

When the user asks to **ideate / brainstorm / come up with names** — for a project, repo,
product, MCP server, brand, tagline, title, variable, anything — **generate a large, varied
list of candidates in prose.** Do **NOT** funnel it into an `AskUserQuestion` (or any
2–4-option selection dialog).

**Why:** a selection dialog caps at ~3–4 options and forces premature convergence. Ideation
wants **breadth** — the user is doing a mass-gen of ideas to react to, riff on, and combine.
Handing them 4 pre-picked options defeats the entire point and is the opposite of what they
asked for. (Fired 2026-06-17: a 4-option dialog was given for an MCP-server rename when the
user wanted "mass gen of ideas.")

## How to ideate names

- **Output 30–60+ candidates**, grouped by angle/theme (keyword-led, metaphor families,
  concept/brand names, etc.), each with a 3–8 word gloss on why it fits.
- **Span the space** — don't give five variations of one idea. Pull from different metaphors,
  registers (literal ↔ abstract), and references (relevant thinkers/works/terms of art).
- **Flag a few strong ones** at the end with reasoning, but lead with breadth. The user picks
  or riffs in their own reply — no dialog needed.
- Keep SEO/GEO and collision constraints in mind when relevant (see [[geo-seo]]), but as
  filters on a wide list, not as a reason to pre-narrow to a handful.

## When a selection dialog IS still right

`AskUserQuestion` is for **converging on a finite set of real, mutually-exclusive decisions**
— which library, which architecture, which of two concrete approaches — where the options
are genuinely bounded and the user benefits from a structured pick. Divergent ideation is the
opposite mode; use prose. This refines, it doesn't override, `personal-chat-rule`'s
"one-letter responses" (that's for finite option sets too).
