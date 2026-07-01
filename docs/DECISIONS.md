# Decisions (ADR log)

Architecture Decision Records for skeuo-ui — the curated record of *why*. Newest on top,
**append-only** (supersede a past entry with a new dated one; never edit it), **real tradeoffs
only** (no fork in the road → no entry). Format + discipline: central `docs` skill.

## 2026-07-01 — Knob value = rotate the cap under a pinned specular (not a static cap + CSS pointer)
Context: rotary-knob value rendering on Y2K/WMP/Winamp skins was a static cut cap with a CSS-drawn pointer line; unclear whether physically rotating the cap reads as more tactile. Two experiments (packed 6-material patches + whole generated skins), human-reviewed live.
Decision: adopt technique ② — CSS-rotate the cut cap about its known center while a PINNED (non-rotating) radial specular overlay stays fixed as the light source. Clearly more tactile on glossy/reflective caps (chrome/glass/translucent); near-tie on matte but chosen for consistency. Requires: knob caps authored with a NEUTRAL/symmetric baked specular; a `gloss` signal from the Director material pass drives specular intensity. Whole-skin in-place cut (cap cut + rotated about its own center) also fixes packed-patch alignment — seated at 0°/±135°.
Consequence: supersedes the static-cap + CSS-pointer approach for knobs. Evidence → [experiments/2026-07-01-knob-rotation.md](./experiments/2026-07-01-knob-rotation.md).

## 2026-07-01 — Layout template is authored as DATA, not a rendered-then-segmented image; hotspots enriched to organic shapes
Context: decide whether the layout template should be DATA (LLM emits coords) or a RENDERED template image (paint, then segment to recover hotspots). Segmentation bake-off on 16 controls, human-reviewed.
Decision: DATA-authored wins the hotspot axis outright — 100% exact, free, zero false positives (classical CV on a clean template only matches it at cost and degrades on the paint; SAM ~100× slower; gpt-4o VLM 7/16 with 10 FP, unusable). Rendered-template + segmentation is ruled out as the hotspot source. Adopt the HYBRID: enrich `deriveLayout` to author ORGANIC (bezel-hugging, non-rect) layouts as DATA — free/exact hotspots AND the WMP look. Caveat: segmentation numbers were on EASY synthetic shapes; a follow-up stress-tests hard/wild shapes.
Consequence: keeps placement deterministic (consistent with the 2026-06-27 rejection of detection-snapping); no segmentation dependency. Evidence → [experiments/2026-07-01-template-authoring.md](./experiments/2026-07-01-template-authoring.md).

## 2026-06-27 — Detection-snapping is rejected for control alignment; the generation system needs a ground-up rebuild
Context: overlay boxes (knobs/sliders/seek/visualizer) don't land on the painted controls because the painter drifts them off the fixed blueprint sockets. Every detection fix — CV well-detect, gpt-4o boxes, SAM-3.1 (the 2026-06-23 entry below), and TWO Gemini 2.5 Pro passes this session — made alignment WORSE (0oyq 29→0; a SAM-snapped render scored 1/10). A noisy VLM/SAM cannot precisely re-locate AI-painted controls (ai-image-coords-rule).
Decision: SUPERSEDES the 2026-06-23 "SAM is load-bearing" entry — SAM snap was wired in and reverted (f1db039). Blueprint coords stay the only placement; a Gemini-gated paint RE-ROLL (3-run consensus, cfd7fe5/5d7ed05) re-rolls until the baked button bank is clean — but that fixes bank *evenness* only, NOT overlay-to-paint alignment of the sprite/CSS controls, which remains UNSOLVED after ~6 attempts.
Consequence: the root cause is architectural (painter drift vs fixed overlays); patching detection is a confirmed dead end. The generation system is slated for a ground-up revamp (see TODO #1) rather than more detection patches.

## 2026-06-23 — SAM box-prompted align is the load-bearing control placement, not a heuristic detector
Context: a homegrown dark-blob + nearest-neighbor control detector (`src/generate/cutoutClient.ts`) was rebuilt over many rounds and still failed on low-contrast/radial skins.
Decision: use the existing documented `generation/sam_snap.py` "Align" pass (SAM 3.1 box-prompted by each control's template rect → snap/warp) as the deterministic placement step; any VLM is *optional polish within tight bounds*, never load-bearing and never resizing a control.
Consequence/supersedes: replaces the heuristic detector. A clean procedural baseline that's "always fine" beats a smart step that's "great then broken."

## 2026-06-23 — Blueprint and baked coords must match the EXACT aspect requested from the image model
Context: a combined blueprint was 0.513 but paint was requested at 2:3 (0.667); the edit model reshapes output to the requested aspect, so it squished the content and every normalized coord landed on the wrong row → sprites cut "way off" (chased as a cut bug for ~a day).
Decision: build the blueprint + bake its 0..1 coords at the same aspect requested from the model; assert blueprint aspect before the call, parse the returned image's real dims after. Repack content to fit the target aspect rather than ship a mismatched canvas.
Consequence: eliminates aspect-drift cut errors; the canvas you send and the coords you bake are one aspect, verified both ends.
