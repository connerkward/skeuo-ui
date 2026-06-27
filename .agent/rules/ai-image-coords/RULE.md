---
name: "ai-image-coords-rule"
id: "ai-image-coords-01"
description: "AI image pipelines with normalized coordinates: match blueprint aspect to requested model aspect (verify both ends), and don't make noisy VLM bboxes load-bearing when a clean procedural baseline exists."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: false
priority: "high"
human-reviewed-at: 2026-06-26
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# AI image geometry — match aspect, and don't make a noisy model load-bearing

Two reusable gotchas behind the skeuo-ui skin-generation goose chase (2026-06-23). Both
bite any pipeline that **overlays normalized coordinates on an AI-generated image** —
blueprints/control-maps painted by an image model, then cut/placed by code.

## 1. An image-EDIT model reshapes its output to the REQUESTED aspect, not the input's

When you send an image model a "blueprint" to restyle and you ask for an `aspect_ratio` /
`image_size`, the output comes back at **that** aspect — it does NOT preserve the input's
shape. So if your blueprint is a different aspect than what you requested, the model
**squishes/stretches** the content, and every **normalized (0..1) coordinate you baked into
the blueprint now lands in the wrong place** on the output.

The burn: a combined blueprint was 0.513 (tall) but the paint was requested at 2:3 (0.667).
The model squished it → the bottom "control strip" cells mapped to the wrong rows → sprites
cut "way off" for ~a day, chased as a cut-geometry bug when the real cause was aspect drift.

**Rule:** the thing you send + the coords you bake into it **must be the SAME aspect you
request from the model.** Build the blueprint/control-map to a supported aspect, request that
exact aspect, and **check both ends**: assert the blueprint aspect before the call (cheap,
fail loud), and parse the returned image's real dims after (warn if the model didn't honor
it). If the content can't fit the target aspect, **repack** it to fit — don't ship a
mismatched canvas. (This is the geometry sibling of [[verify-outputs-rule]]: verify the real
pixels, not the metric you assumed.)

## 2. Don't make a noisy VLM load-bearing for precise geometry

Asking a VLM (gpt-4o vision et al.) to return precise bounding boxes for controls/objects is
**unreliable** — it returns inconsistent, often thin/squashed boxes. Gating + refining +
de-overlapping that noisy signal is whack-a-mole: it'll pass on the easy case and collapse
controls to slivers on the rest (worked on 1 of 6 skins in the burn).

**Rule:** when a **clean procedural baseline exists** (a repacked template with known,
non-overlapping, correctly-sized positions), **trust it** and make the VLM *optional polish*
that only nudges within tight bounds — never the load-bearing placement step, and never let
it *resize* a control. Stacking heuristics on a noisy model signal is the goose chase; a
deterministic baseline that's "always fine" beats a smart step that's "great then broken."

Related: [[verify-outputs-rule]] (§2 circular validation, §7 real-runtime), [[restraint-rule]]
(don't keep patching a broken foundation).
