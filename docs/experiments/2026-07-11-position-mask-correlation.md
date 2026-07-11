# 2026-07-11 — Position-mask correlation (pure-control, non-skin)

## Question

`docs/experiments/2026-07-10-twoimg-conditioning.md`'s NEUTRAL arm found guide-colour bleed
survives even a **colourless** reference image, because the mask spec must still NAME each
colour in the TEXT PROMPT ("ROSE PINK region filled 255,0,128; …") — the bleed pathway ranks
**canvas-pixel < reference-image < text-prompt**, and no image-conditioning topology removes
the text one while a colour-keyed mask column exists. This experiment asks the prior question:
if colour is dropped from the mask-column convention entirely, can `gemini-3-pro-image-preview`
still correlate an output mask CELL to its template REGION by **position alone** — with zero
colour and zero number anywhere in the prompt — reliably enough to be a viable replacement? And
if not, does an explicit NUMBER-tag convention (still colourless) do better?

Deliberately **pure-control and non-skin**: abstract shapes on a plain panel, not a music-player
control footprint, so the result isolates the correlation mechanism from every skin-specific
confound (theme prompting, icon fidelity, material rendering).

## Method

- Self-contained harness in `tools/mask-align-exp/gen12/poscorr/`, reusing the proven Vertex
  call (`edit_vertex_multi`, imported not re-derived) from `twoimg/genskin_twoimg.py`.
- **Template** (`template.py`): one 2400×1920 (5:4) canvas, LEFT column = a plain grey panel
  with 8 abstract regions (circle small/large, oval, small/large rounded-rect, a groove, a
  diamond, a vertical pill) at fixed grid positions (4 rows × 2 cols, hand-jittered, reading
  order unambiguous). RIGHT column = pure black, split into 8 equal-height stacked bands
  (fixed vertical order) by thin divider lines. Geometry is IDENTICAL across all three arms —
  only the correlation SIGNAL varies:
  - **position** — no marks at all. Prompt states the rule in words only: "the k-th region in
    reading order (top-to-bottom by row, left-to-right within a row) is assigned to band k."
  - **numbered** — each region and its assigned band carry a matching printed digit tag (1–8),
    removed from the prompt's expected final output (drafting-mark framing, same pattern as
    twoimg's NEUTRAL arm).
  - **color** — each region is filled a solid guide colour; its band carries a matching colour
    swatch chip. This ports today's actual production mechanism into the synthetic harness as
    the anchor/baseline arm.
- Matrix: 3 arms × 3 seeds (11, 22, 33) = 9 generations. Model: `gemini-3-pro-image-preview`
  via Vertex AI (project `muser-2605300220`, global), 4K, 5:4.
- **Scoring** (`score_poscorr.py`, $0, deterministic, independent of any model call per
  verify-outputs-rule §2):
  1. **Per-cell IoU (stack)** — output band k's painted silhouette vs the expected shape for
     the region canonically assigned to band k, both rendered in the same fixed geometry. The
     literal, most demanding test of the requested convention. PRIMARY metric.
  2. **Per-cell IoU (mirror)** — same shape, but at the region's OWN panel position mirrored
     1:1 into the right column instead of its band. Tests the ALTERNATE convention the model
     may default to when it ignores the requested stack.
  3. **cells_filled** — occupancy completeness (of 8 bands, how many contain any painted
     blob). Two shape-identity classifiers (area+aspect nearest-neighbour; argmax-IoU-against-
     all-candidates) were tried and dropped as unreliable — see "Scoring notes" below.
  4. **contamination** — colour fraction of painted pixels (should be pure white silhouettes)
     and residual digit-tag/swatch-chip leakage in the band's known drafting-mark position.
  - A real scoring bug was caught and fixed mid-run (see "Scoring notes"): the model does not
    reliably render its own black mask panel edge-to-edge within its half of the crop (it adds
    its own margin), so a naive 50/50 crop assumption silently counted background margin as
    "painted foreground" and wrecked every IoU. Fixed by detecting the actual black-panel
    bounding box per generation before scoring bands.
- Budget: 9 gens × ~$0.24/4K image ≈ **$2.16** generation, $0 scoring. Under the $2.5 cap.

## Scoring notes (methodology, not results)

- **Bbox-detection bug**: the model's own black mask panel doesn't always fill its crop half
  edge-to-edge — it sometimes adds a card-style margin (observed: `numbered` arm) and sometimes
  doesn't (observed: `position`/`color` arms). Fixed via `find_black_panel_bbox()` — a global
  bbox of pixels below a dark threshold, robust to a single stray bright seam pixel that broke
  an earlier row/col-mean contiguity approach.
- **Shape-identity classification was tried twice and dropped.** An area+aspect nearest-
  neighbour classifier failed because the model does not preserve source SIZE faithfully
  (observed: ovals/circles rendered up to ~2x linear scale, and the inflation factor varies by
  shape, not just by generation — no simple per-generation rescaling fixed it). A follow-up
  argmax-IoU-against-all-8-candidates classifier also failed: several of the 8 abstract shapes
  are genuinely silhouette-similar at the sizes the model actually renders (e.g. an oversized
  small circle can out-IoU its own ground truth against a same-sized rounded-rect candidate).
  Both are informative in their own right — the model's shape+size fidelity is looser than the
  position/assignment question this experiment is actually about — but neither survived as a
  scored metric; `cells_filled` (blunt occupancy) replaced them, and the primary per-cell IoU
  metric already captures position+shape+size jointly.
- Tag/swatch leak-check initially scanned the wrong location (a hardcoded top-left corner) —
  the template actually places tags/swatches at the band's VERTICAL CENTER, left edge. Fixed to
  match the template's own geometry before trusting any `tag_leak` count.

## Results

Full artifacts (templates, paints, masks, per-cell IoU tables): served results page,
`tools/mask-align-exp/gen12/poscorr/results.html`. 9/9 generations completed, $2.16 spend.

| arm | seed | IoU (stack) | IoU (mirror) | topology | cells passing IoU&ge;0.5 |
|---|---|---|---|---|---|
| position | 11 | 0.000 | 0.093 | mirror | 0/8 |
| position | 22 | 0.000 | 0.098 | mirror | 0/8 |
| position | 33 | 0.000 | 0.054 | mirror | 0/8 |
| numbered | 11 | 0.426 | 0.006 | stack | 4/8 |
| numbered | 22 | 0.914 | 0.002 | stack | 8/8 |
| numbered | 33 | 0.046 | 0.009 | stack | 0/8 |
| color | 11 | 0.000 | 0.096 | mirror | 0/8 |
| color | 22 | 0.896 | 0.002 | stack | 8/8 |
| color | 33 | 0.000 | 0.012 | mirror | 0/8 |

- **position: 3/3 seeds ignored the requested stack convention, every time.** Mean stack IoU
  is exactly 0.000 across all three seeds (0/24 cells ever pass IoU&ge;0.5 against the requested
  band). The model instead consistently defaulted to MIRRORING the panel's own 2-column×4-row
  spatial layout straight into the mask column (topology=mirror all 3/3) — visually confirmed
  in `results.html`: `position-11/22/33`'s output masks are a 4-row×2-col grid, not an 8-row
  stack, at every seed. Mirror-topology IoU (0.05–0.10) is itself modest, held down by the same
  shape-size drift seen everywhere in this experiment, but the STACK/MIRROR gap (0.000 vs
  0.05–0.10) is the finding: reading-order convention as WORDED IN THE PROMPT, with zero visual
  anchor, was never followed once in 3 tries.
- **numbered: 3/3 seeds correctly adopted the stack topology, but reliability within that
  topology was highly variable.** All three gens scored higher on stack IoU than mirror IoU
  (topology=stack 3/3) — the digit-tag convention DOES get communicated and generally followed.
  But quality varied hugely: seed 22 was near-perfect (0.914 mean IoU, 8/8 cells passing —
  visually confirmed near-exact match to ground truth), seed 11 was middling (0.426, 4/8), and
  seed 33 largely failed the STRICT 8-equal-band format even though it kept the right shapes in
  roughly the right relative order — visual inspection shows seed 33 collapsed some rows into a
  hybrid stack (two shapes sharing a taller band, e.g. circle+diamond, pill+rrect) rather than 8
  strictly equal bands, so per-band scoring against the exact requested geometry cratered to
  0.046 even though the underlying region-to-band correspondence was still directionally
  sane. This is a genuine format-compliance reliability gap, not a correlation failure.
- **color: inconsistent — 1/3 seeds followed the stack convention (and followed it
  excellently: 0.896, 8/8), 2/3 defaulted to the same panel-mirroring fallback position saw.**
  No seed showed partial/garbled compliance the way numbered-33 did — color's outcomes were
  cleanly bimodal (either near-perfect stack compliance or complete mirror fallback), suggesting
  the colour-swatch key is read as an authoritative instruction only some of the time, with no
  middle ground once it's ignored.
- **Contamination: clean across the board.** Colour leakage into the (supposed to be pure-white)
  silhouettes was ~0% in every gen (color-22's 0.10% is noise-level). Tag/swatch-chip residue
  (`tag_leak`) was 0/8 in every single gen — once the corner-check was fixed to match the
  template's actual tag position (see Scoring notes), no digit or swatch leaked into any output.
  Cells were 8/8 "filled" (some blob painted) in every gen regardless of arm or topology — the
  model never left a cell empty, it just didn't always put content in the requested cell.
- **Ranking by reliable compliance with the EXACT requested format:** numbered (3/3 topology-
  correct, but 1/3 format-degraded) > color (1/3 clean pass, 2/3 clean fail, 0/3 degraded) >
  position (0/3 ever compliant). Position-only correlation, with literally zero colour/number
  signal, was not reliable even once across 3 seeds for this 8-region, format-fixed convention.

## Conclusion

**Position-only correlation is unreliable for a fixed-vertical-stack mask-column convention at
N=8 — it failed 3/3 seeds, every time reverting to spatial mirroring of the panel layout
instead of the requested reading-order stack.** This rules out the simplest de-colouring path
(drop colour, rely purely on prose position language) as a drop-in replacement for gen12's
mask column.

**Numbered tags are the most promising colourless alternative** — they got the model to adopt
the correct topology in 3/3 seeds (vs 1/3 for color) — but are NOT yet reliable enough to ship
as-is: 1/3 seeds badly degraded the strict per-cell format (numbered-33's row-collapsing), and
even the successful seeds show larger variance (0.05–0.91 IoU) than would be acceptable for a
production pipeline stage other stages depend on. Numbered tags trade the twoimg NEUTRAL arm's
proven digit-contamination risk (which this experiment's `tag_leak=0/9` result suggests is
LOWER than twoimg previously found, likely because prompt framing improved here) for a new
format-compliance risk.

**Colour keying (today's mechanism) is not obviously more reliable than numbered tags at this
task** — it was the ONLY arm to show a clean total failure mode (2/3 seeds) alongside a clean
total success (1/3), with no partial-credit middle ground. That said, colour is still the
current production default because it's the one arm proven (in `twoimg`) to reliably communicate
LAYOUT even when it also causes bleed — this experiment did not re-test bleed, only correlation.

**Recommendation for gen12:** do NOT de-colour the mask column based on this result alone.
Position-only is out. If pursuing numbered tags further, the next experiment should isolate WHY
numbered-33 degraded (was it seed-specific noise, or does N=8 exceed some reliable-format
ceiling that a smaller N or a stronger per-cell divider treatment would fix) before considering
it for the real pipeline — n=3/arm is directional, not conclusive, and this was a pure abstract-
shape control, not a validation against real skin control footprints.

## Human verdict

**PENDING** — awaiting human review of `results.html`. No human has judged this experiment yet;
the automated IoU/occupancy/contamination metrics above are evidence, not the verdict.
