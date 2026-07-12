# 2026-07-11 — toggle sprite sizing: COVER-fit vs CONTAIN-fit

## Question

Review round `review-2026-07-11-round1.json` flagged multiple skins with an undersized
shuffle/toggle switch ("switch isnt scaled to slot, too small" — fa-pod; "switch doesnt
match slot" — several others). Is this a paint-side (genskin/extract) mismatch, or a
`build_player.py` render-side sizing bug?

## Method

`build_player.py`'s `.ptog` (toggle) sizing forced the box to the **slot's own aspect
ratio** (`r.device[2]*1.06, r.device[3]*1.06`) and relied on CSS `background-size:contain`
to fit the OFF/ON cut inside it. `contain` scales by the *smaller* of the two per-axis
factors — so whenever the cut's own aspect ratio diverges from the slot's, the sprite
renders visibly smaller than the slot on whichever axis doesn't bind.

Measured `cut_aspect / slot_aspect` across the roster (cut = `shuffle_off.png` natural
w/h, slot = the toggle's `device` bbox w/h):

| skin | ratio | before |
|---|---|---|
| fa-pod | 0.13 | badly undersized (portrait cut in a wide slot) |
| fallout-vault | 0.20 | badly undersized |
| claymation | 0.37 | undersized |
| n64-cutscene | 0.49 | undersized |
| wc-goldshield | 1.09 | ~fine already |
| wmp-vario | 1.08 | ~fine already |

Fix: size the box to the cut's **own** aspect ratio, scaled to **COVER** the slot ×1.06
in both axes (`Math.max` of the two per-axis factors instead of `Math.min`) — same pattern
the seek-thumb already uses correctly. Same ×1.5-natural upscale cap retained. Gated behind
`SPRITE_COVER_FIT_ENABLED` in `build_player.py` (off = exact prior contain-fit behavior).

## Verification

- **fa-pod** (ratio 0.13, worst case): before — a small disc floating in the left third of
  the oval slot, most of the housing empty. After — the switch fills the housing.
  Screenshots: `/tmp/skeuo-verify/fapod-before.png`, `fapod-after.png` (not committed —
  local verification captures).
- **wc-goldshield** (ratio 1.09, near-parity control): no visible change before/after —
  confirms the flag is a no-op when cut and slot aspect already agree.
- **ps1-crunchy** (`stateAlign.dx=-12`): clicked OFF→ON, both states render correctly
  seated in their housing with the lever visibly sliding from bottom slot to top slot;
  the `offS` (displayed-scale) used to convert the extractor's px `dx/dy` into on-screen
  offset is now computed directly (`offS = s`, the exact COVER scale) instead of
  re-derived — confirmed the ON-state offset still lands correctly (no drift introduced).

## Decision

Shipped `SPRITE_COVER_FIT_ENABLED = True` (default on) in `build_player.py` — verified
improvement on badly-mismatched skins, verified no regression on already-good skins, and
verified the stateAlign ON/OFF offset math still holds. Root cause for the *worst* cases
(fa-pod, fallout-vault) is still a very extreme cut/slot aspect mismatch — worth a look on
the genskin/extract side too (a switch cut that's 3-5x more portrait than its slot expects
is unusual), but the render-side COVER fix makes the shipped result correct regardless.
