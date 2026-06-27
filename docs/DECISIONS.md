# Decisions (ADR log)

Architecture Decision Records for skeuo-ui — the curated record of *why*. Newest on top,
**append-only** (supersede a past entry with a new dated one; never edit it), **real tradeoffs
only** (no fork in the road → no entry). Format + discipline: central `docs` skill.

## 2026-06-23 — SAM box-prompted align is the load-bearing control placement, not a heuristic detector
Context: a homegrown dark-blob + nearest-neighbor control detector (`src/generate/cutoutClient.ts`) was rebuilt over many rounds and still failed on low-contrast/radial skins.
Decision: use the existing documented `generation/sam_snap.py` "Align" pass (SAM 3.1 box-prompted by each control's template rect → snap/warp) as the deterministic placement step; any VLM is *optional polish within tight bounds*, never load-bearing and never resizing a control.
Consequence/supersedes: replaces the heuristic detector. A clean procedural baseline that's "always fine" beats a smart step that's "great then broken."

## 2026-06-23 — Blueprint and baked coords must match the EXACT aspect requested from the image model
Context: a combined blueprint was 0.513 but paint was requested at 2:3 (0.667); the edit model reshapes output to the requested aspect, so it squished the content and every normalized coord landed on the wrong row → sprites cut "way off" (chased as a cut bug for ~a day).
Decision: build the blueprint + bake its 0..1 coords at the same aspect requested from the model; assert blueprint aspect before the call, parse the returned image's real dims after. Repack content to fit the target aspect rather than ship a mismatched canvas.
Consequence: eliminates aspect-drift cut errors; the canvas you send and the coords you bake are one aspect, verified both ends.
