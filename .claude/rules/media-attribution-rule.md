---
name: "media-attribution-rule"
id: "media-attr-01"
description: "When presenting generated media for review, always state which model produced it (and key params) so the user can direct the next iteration."
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

# Always annotate the model when presenting generated media for review

When you generate media — image, video, audio, music, 3D, voice — and put it in front
of the user to review/pick/iterate on, **always state which model produced it** (and
ideally the key params). The user is choosing and refining; they can't direct the next
iteration if they don't know what made the current one.

**Why:** "regenerate that but more X" depends on knowing the engine. A FLUX image, a
Midjourney image, and a Stable-Diffusion image respond to prompt changes differently;
swapping models is often the actual fix (e.g. photoreal FLUX can't hit a retro-render
look no matter the prompt — a different model can). Unlabeled media hides the most
important lever. This rule exists because a contact sheet of fal portraits was handed
over with no model noted, and the user couldn't tell why the style was off.

**How to apply** — put the model where the user sees it, not buried in a log:
- **Contact sheets / preview pages:** a header or per-image caption with the model id
  (e.g. `fal-ai/flux/dev`), and per-image seed/prompt when they differ.
- **Single artifact:** say it in the message that delivers it ("generated with
  `fal-ai/elevenlabs/sound-effects/v2`"), and/or bake it into the filename
  (`portrait_flux-dev_seed1488.jpg`) or a sidecar `.txt/.json`.
- **Iterating across models:** label each candidate with its model so comparisons are
  meaningful ("A: flux-dev · B: recraft-v3 · C: midjourney").
- Include the **full endpoint/version**, not just "flux" — `flux/dev` vs `flux/schnell`
  vs `flux-pro` matter.

This complements [[verify-outputs-rule]] (look at the real artifact) — here, also record
*what tool made the artifact* so the review is actionable. Applies to all media work,
and especially in `lookdev`/contact-sheet review flows.
