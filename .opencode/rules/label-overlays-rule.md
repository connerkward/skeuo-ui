---
name: "label-overlays-rule"
id: "label-overlays-01"
description: "Any box/mask/overlay drawn over an image for human review must carry a legible per-shape label (identity, score, state) and a color legend — an unlabeled box is unverifiable."
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

# Always label boxes, masks, and overlays meant for human review

Any time you draw a **bounding box, mask, region, keypoint, arrow, or any
annotation over an image** for a human to inspect — detection output, alignment
proof, before/after overlay, a crop sheet, a lookdev studio — **every drawn shape
must carry a legible label that says what it is**. An unlabeled box is unverifiable:
the human cannot tell whether box #3 is the "play button" or the "volume knob," so
they cannot tell you it landed on the wrong thing. The label is what turns a picture
into a check.

This is the visual corollary of [[verify-outputs-rule]] and
[[media-attribution-rule]]: looking at the artifact only helps if the artifact is
*legible*. It fired on a concrete failure (skeuo-ui, 2026-06): detection overlays
were handed over as bare colored rectangles, and the review was impossible —
"the bboxes look kinda wrong" with no way to say *which* box or *what it should be*.

## What a labeled overlay must have

1. **A per-shape identity label.** Each box/mask gets text naming the thing it
   bounds — the control's `bind`/id, the class name, the track id. Place it on or
   beside the shape (small text with a dark backing pill so it stays readable over
   any art), not only in a far-off legend the eye has to re-pair.
2. **A confidence / score when one exists.** Detection and model outputs carry a
   score — show it (`play 0.88`). The human is often judging exactly the
   low-confidence ones; hiding the score hides the thing worth looking at.
3. **A color legend when color encodes meaning.** If green = snapped, red = prior,
   amber = refit (or class A/B/C), state the mapping somewhere on the frame. Color
   alone is not a label — colors are not self-describing and fail for
   color-blind viewers.
4. **State, where relevant.** kept / moved / rejected / on / off — whatever
   distinction the review is *about* should be readable per shape, not inferred.

## Don'ts

- Don't hand over bare rectangles and expect the human to map them back to controls.
- Don't bury identity in a corner legend when there are more than ~3 shapes — pair
  the label to the shape.
- Don't let labels overlap into illegibility; when boxes are dense, stagger the
  labels, lead with a short id, draw a tick from label to box, or zoom/crop so each
  is readable. A label you can't read is the same as no label.
- Don't omit the score because "it cluttered the image" — make it small, keep it.

## The one-line test before you send an annotated image

"Could the user point at any single box and tell me what it's supposed to be and
how confident the model was — without asking me?" If no, label it before sending.
