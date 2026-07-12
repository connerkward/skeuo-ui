# Verification recalibration — the human review round as an eval set

## Question

The human review round (`tools/mask-align-exp/gen12/review-2026-07-11-round1.json`) failed
0/15 skins the automated verification stack — `observe12.py` (SOTA-eye pass, fal
`openrouter/router/vision`, google/gemini-2.5-pro) and `director_review.py` (DIRECTOR pass,
Vertex `gemini-3.1-pro-preview`) — had mostly PASSed. The user's own words on
`n64-prerender-character`: *"what the fuck is this orientation? how did this get past the vlm
gate?"* That skin's `observe12` run HAD already returned FAIL — but for a completely different
reason (a baked "ON" text label), never once mentioning orientation. Is this systematic
miscalibration, or noise? And after rewriting the prompts to explicitly interrogate the defect
classes the human actually flagged, how much of the gap closes?

## Method

1. **Coded the human's free-text notes into a fixed defect taxonomy** (10 classes: baked-thumb,
   sprite-slot-mismatch, css-misalignment, silhouette-mismatch, orientation, dead-control,
   duplicate-control, phantom-control, placement-wrong, aesthetic) — one manual pass over all
   15 notes, stored in `tools/mask-align-exp/gen12/human_defects.json`. 35 human-flagged defect
   instances total across 15 skins (avg 2.3/skin).
2. **Baseline**: filled every missing `observe.json`/`director-review.json` on disk using the
   UNMODIFIED (pre-recalibration) scripts (8 missing observe runs, 9 missing director runs, one
   `AttributeError` crash fixed defensively — a `null` region entry on
   `n64-prerender-character`'s `repeat` control that neither script guarded against). Scored all
   15 with `score_verification.py` — a keyword-heuristic recall scorer (generous synonym sets
   per class, since baseline prose never uses canonical tag names).
3. **Recalibrated** both scripts' prompts/schemas to explicitly interrogate each taxonomy class
   per control (observe12: a fixed checklist + a forced `<key>: DEFECT[tag1,tag2] - detail` /
   `DEVICE: [tags] - detail` output line format; director_review: added `defects` (per-control)
   and `device_defects`/`orientation_ok` fields to the existing Vertex `responseSchema`, plus a
   hard verdict-gate rule — "a visible geometry defect FAILs the render even with a good
   aesthetic score" — enforced both in the prompt AND server-side as a belt-and-suspenders
   check against verdict/tag disagreement). Re-ran BOTH passes fresh on all 15 skins, overwriting
   the baseline outputs. Scored again with the same scorer, which now gets exact tag matches
   (the canonical taxonomy string appears verbatim in recalibrated output) in addition to the
   keyword fallback.
4. Cost: ~27 observe12 calls (fal, ~$0.01-0.03 each) + ~25 director_review calls (Vertex,
   ~$0.02-0.05 each) ≈ **~$1.3-1.5 total**, a bit over the ~$0.05/skin + ~$0.75 plan — a few
   extra calls came from (a) a caught race condition: editing `observe12.py` while its own
   background baseline-fill loop was still running caused 2 in-flight subprocess calls
   (`steam-porthole`, `wc-goldshield`) to pick up the NEW prompt mid-run; both were detected
   (by checking whether the output contained the new `DEFECT[`/`DEVICE:` markers) and redone
   against a git-restored copy of the original script before being counted as baseline, and
   (b) 3 calls spent smoke-testing the recalibrated prompt on `diablo-gothic` before committing
   to the full 15-skin batch. No baseline or recalibrated SCORE was computed from a
   cross-contaminated run.

## Baseline (pre-recalibration) — confusion made explicit

| defect class | human N | observe12 recall | director recall | either recall |
|---|---|---|---|---|
| baked-thumb | 6 | 3/6 (50%) | 3/6 (50%) | 3/6 (50%) |
| sprite-slot-mismatch | 8 | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) |
| css-misalignment | 6 | 0/6 (0%) | 3/6 (50%) | 3/6 (50%) |
| silhouette-mismatch | 5 | 0/5 (0%) | 0/5 (0%) | 0/5 (0%) |
| orientation | 1 | 0/1 (0%) | 0/1 (0%) | 0/1 (0%) |
| dead-control | 2 | 0/2 (0%) | 1/2 (50%) | 1/2 (50%) |
| duplicate-control | 1 | 0/1 (0%) | 0/1 (0%) | 0/1 (0%) |
| phantom-control | 1 | 0/1 (0%) | 0/1 (0%) | 0/1 (0%) |
| placement-wrong | 2 | 0/2 (0%) | 0/2 (0%) | 0/2 (0%) |
| aesthetic | 3 | 0/3 (0%) | 2/3 (67%) | 2/3 (67%) |
| **OVERALL** | **35** | **3/35 (8.6%)** | **9/35 (25.7%)** | **9/35 (25.7%)** |

**The smoking gun**: `n64-prerender-character`'s baseline `observe12` verdict was already
FAIL — but scored 0/1 on the ONE defect class the human actually named (orientation). Verdict
agreement (FAIL=FAIL) massively overstates how useful the check was; per-defect recall is the
honest number, and it shows the old prompts caught almost nothing that mattered:
**sprite-slot-mismatch (the single most-flagged class, 8 instances) and silhouette-mismatch
(5 instances) both sat at literal 0% recall** because the old prompt only ever asked
"SEATED-CORRECTLY or BROKEN" — never "does it FIT its slot," never "does the depression shape
match the button."

## Recalibrated — after-table

| defect class | human N | observe12 recall | director recall | either recall | Δ (either) |
|---|---|---|---|---|---|
| baked-thumb | 6 | 5/6 (83%) | 6/6 (100%) | 6/6 (100%) | +50pp |
| sprite-slot-mismatch | 8 | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | +0pp |
| css-misalignment | 6 | 2/6 (33%) | 5/6 (83%) | 5/6 (83%) | +33pp |
| silhouette-mismatch | 5 | 0/5 (0%) | 0/5 (0%) | 0/5 (0%) | +0pp |
| orientation | 1 | 0/1 (0%) | 1/1 (100%) | 1/1 (100%) | +100pp |
| dead-control | 2 | 0/2 (0%) | 1/2 (50%) | 1/2 (50%) | +0pp |
| duplicate-control | 1 | 0/1 (0%) | 0/1 (0%) | 0/1 (0%) | +0pp |
| phantom-control | 1 | 0/1 (0%) | 1/1 (100%) | 1/1 (100%) | +100pp |
| placement-wrong | 2 | 1/2 (50%) | 1/2 (50%) | 2/2 (100%) | +100pp |
| aesthetic | 3 | 2/3 (67%) | 3/3 (100%) | 3/3 (100%) | +33pp |
| **OVERALL** | **35** | **10/35 (28.6%)** | **18/35 (51.4%)** | **19/35 (54.3%)** | **+28.6pp** |

`n64-prerender-character` — the skin that triggered this whole pass ("what the fuck is this
orientation?") — now correctly flags `orientation` on BOTH passes (director's `orientation_ok`
came back `false` with a note describing the device rendered on its side; observe12's DEVICE
line tagged `orientation`). That specific miss is closed.

Raw JSON: `tools/mask-align-exp/gen12/human_defects.json` (taxonomy), baseline scores snapshot
copied out at generation time (`/tmp/gen12-baseline-scores.json`, not repo-tracked — regenerate
via `score_verification.py` against a restored pre-recalibration script pair if needed),
recalibrated scores in the repo-relative reproduce command below.

## What generalized vs. what's still a gap

**Generalized well** — classes where the fix was "the prompt never asked, now it does":
baked-thumb (explicit before/after thumb-position + static-art-duplication check),
css-misalignment (explicit track/fill/groove alignment check), orientation (explicit
device-level upright check — new in the recalibrated prompt, didn't exist at all before),
phantom-control and placement-wrong (both went from a class the prompt never mentioned to
100% on the one instance each — note the small N, see below), aesthetic (broadened checklist
catches more of what used to fall through as "nothing to say here").

**Did NOT generalize — stuck at 0% despite explicit interrogation**: sprite-slot-mismatch (8
instances, the single most common human complaint) and silhouette-mismatch (5 instances).
Inspected directly rather than trusting the recall number alone (per `verify-outputs-rule`):

- `assets-fa-pod/observe/crop-shuffle.png` — the human's complaint was "switch isnt scaled to
  slot, too small." The crop clearly shows it: the switch's inner track sits with a visible
  ring of dead space inside the outer silver pill outline. The recalibrated prompt explicitly
  asks "does the sprite match its socket's SIZE and SHAPE" — and the model still answered
  `shuffle: OK`. This is a genuine VLM judgment miss, not a harness/crop-anchoring failure (the
  evidence was in the image sent to the model). Proportional smallness within a similar overall
  shape is exactly the kind of fine geometric judgment vision-language models are weak at —
  consistent with this repo's own established finding in `ai-image-coords-rule` #2 ("don't make
  a noisy VLM load-bearing for precise geometry... it'll pass on the easy case and collapse on
  the rest"). No amount of prompt wording fixed it here either.
- `assets-wmp-quicksilver/observe/observe.json` — 3 of 10 controls (`playpause`, `prev`,
  `repeat`) came back `CROP-MISS`, meaning the harness's own crop didn't contain usable content
  for those buttons and the model had to fall back to judging them from the full frame — where
  a depression-silhouette mismatch is much harder to see at native scale. This is a distinct,
  partially-addressable contributing cause (a harness/crop-anchoring gap, not a pure model
  weakness) sitting alongside the proportion-judgment weakness above.

**duplicate-control and dead-control** stayed low too, but N=1 and N=2 respectively — too small
to separate "didn't generalize" from "didn't get lucky." dead-control did catch 1/2 via the
explicit before/after crop-pair comparison instruction (confirmed working live during
recalibration testing on `diablo-gothic`'s dead `shuffle` toggle, see commit); the miss was
`ps1-crunchy`'s "visualizer not working" — a canvas/rAF-driven element where two static
screenshots may legitimately look identical whether or not the animation loop is actually
running, which is exactly the class of defect flagged below as needing a deterministic probe
instead of vision.

## Methodological caveat: concurrent regeneration (shared checkout)

This repo is a shared checkout — other agents were actively re-rolling generations (new
`paint.png`/`regions.json`/`player.html`, via `extract12.py`/`build_player.py`/`genskin.py`,
none of which this pass touched) for several skins WHILE this pass ran. Checked directly rather
than assumed (per `verify-outputs-rule`): compared each skin's CURRENT `paint.png` sha256 prefix
against the `paint_sha` the human actually reviewed
(`review-2026-07-11-round1.json`). **7 of 15 skins no longer match**: `diablo-gothic`,
`fallout-pipboy`, `fallout-vault`, `n64-cutscene`, `steam-porthole`, `wc-goldshield`,
`wmp-quicksilver`. For those 7, this pass's verification ran against a DIFFERENT render than
the one the human's notes describe — a genuine confound, not something to silently fold into
the headline number. (The old byte-exact `paint.png` wasn't recoverable from git history for a
quick re-check — the tracked copies at the two commits touching `diablo-gothic/paint.png`
both hash to the empty-file sha, consistent with LFS-pointer mechanics; chasing that down is
outside this pass's scope.)

**Robustness check**: recomputed recall restricted to the 8 skins with a CONFIRMED-matching
`paint_sha` (claymation, fa-pod, fa-sky, myst-arcanum, n64-prerender-character, ps1-crunchy,
ps1-wild, wmp-vario — 16 human-flagged defect instances):

| subset | baseline either-recall | recalibrated either-recall |
|---|---|---|
| all 15 skins (35 instances) | 9/35 (25.7%) | 19/35 (54.3%) |
| paint_sha-confirmed 8 skins (16 instances) | 2/16 (12.0%) | 9/16 (56.0%) |

The confound-free subset shows the SAME direction and a comparable magnitude of improvement
(+44pp vs. +28.6pp on the full set) — the recalibration effect is not an artifact of the
concurrent regeneration. The 7 mismatched skins' numbers should be read as "recall against
whatever the render happens to be right now," not as a claim about the exact skins the human
graded.

## Residual gaps and specced follow-ups (not built here)

- **Dead-control detection is fundamentally a vision-on-two-screenshots problem being asked to
  do an interaction-testing job.** The recalibration adds an explicit before/after crop
  comparison instruction, which helped (diablo-gothic's dead `shuffle` toggle now correctly
  caught by both passes in ad-hoc testing during recalibration). But a VLM comparing two static
  images will always be weaker than actually checking whether the control's own DOM/JS state
  changed. **Follow-up spec (not built):** a small scripted interaction probe in
  `observe_drive.mjs` (or a sibling script) that reads the actual JS state before/after each
  interaction — e.g. for a toggle, read the class list or a data-attribute the player sets on
  toggle; for a slider, read the computed CSS `left`/`transform` of the thumb element; for the
  visualizer (the `ps1-crunchy` "visualizer not working" complaint), check whether its canvas
  actually mutates pixels or a driving rAF loop is running — and gate on that directly instead
  of asking a VLM to eyeball pixel-identical crops. This is a **deterministic** check (no VLM
  cost, no ambiguity) and should live alongside `observe_drive.mjs`, not replace the vision pass
  (the vision pass still needs to say whether the *visual result* of a working interaction looks
  right — deterministic state-read only proves the interaction fired).
- **Human notes with low specificity** (`ps1-wild`: "absolute failure") were coded to a single
  catch-all `placement-wrong` tag for lack of anything more precise — this skin's recall number
  is low-confidence in both directions and shouldn't be read as strongly as the others. A
  follow-up human-review pass that asks for at least one concrete defect per skin (even
  "everything is wrong, starting with X") would make future eval rounds scoreable.
- **The taxonomy itself was hand-coded from 15 free-text notes** — a reasonable N for a
  calibration pass, small for validating recall percentages precisely (e.g. "0/1" and "1/1" for
  singleton classes like orientation/duplicate-control/phantom-control swing 100 percentage
  points on one skin). Treat the per-class recall numbers above as directional, not
  statistically tight; the overall trend (near-zero baseline recall on structural fit/shape
  classes, material recovery after explicit interrogation) is the load-bearing finding.
- **Not addressed here**: WHY the generation pipeline produces these defects in the first place
  (baked thumbs, mis-scaled switches) — that's `genskin.py`/`extract12.py`/`build_player.py`
  territory, explicitly out of scope for this pass (owned by other agents per the task
  boundary). This pass only recalibrates the verification prompts so future gate runs actually
  catch what the human catches; it does not fix the generator.

## Reproduce

```bash
cd tools/mask-align-exp/gen12
python3 score_verification.py --out=/tmp/recal-scores.json   # scores whatever's currently on disk
# to regenerate the recalibrated outputs from scratch for one skin:
python3 observe12.py assets-<id> --vlm
python3 director_review.py assets-<id>
```
