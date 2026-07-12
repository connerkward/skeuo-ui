# 2026-07-11 — KNOB_POINTER_UP: paint the pointer AT the convention, not detect-and-correct

Code: [`tools/mask-align-exp/gen12/genskin.py`](../../tools/mask-align-exp/gen12/genskin.py)
(`KNOB_POINTER_UP` flag + `_POINTER_UP_CLAUSE`), [`tools/mask-align-exp/gen12/knobup/run_experiment.py`](../../tools/mask-align-exp/gen12/knobup/run_experiment.py)
(harness), [`tools/mask-align-exp/gen12/knob_angle.py`](../../tools/mask-align-exp/gen12/knob_angle.py)
(the shared, independent verifier — unmodified). Results page:
`tools/mask-align-exp/gen12/knobup/index.html` (served).

## Question

The whole `knob_angle.py` detect-and-counter-rotate machinery exists because the paint model
bakes the volume-cap's pointer notch at an unpredictable angle, so the player has to measure it
post-hoc and CSS-counter-rotate the cap. The user's insight (verbatim): "maybe instead of all
this bullshit [detect-and-counter-rotate] you can just specify in prompt that the tick on knob
face should point upwards 0 degrees?" — invert the architecture: paint the pointer AT the
zero-degree convention instead of detecting and correcting after. Does a light prompt clause
actually make the model comply, measured independently?

## Method

- **Clause** (`genskin.py`, both prompt paths — prose and `PROMPT_JSON_SPEC`): one clause added
  to the existing CAMERA bullet's knob-cap sentence, flag-gated `KNOB_POINTER_UP` (default OFF):
  `"...a knurled outer rim and a small pointer notch, its pointer notch aiming straight up..."`.
  Deliberately no position-label word (MIN/MAX/CENTER) and no angle number/clock-position digit —
  the `knobticks/` tick-provisioning experiment (2026-07-11, same day) found that vocabulary bakes
  in as literal engraved TEXT; "straight up" is a direction, not a label.
- **Themes:** steam-porthole (templated, single dominant mark) + myst-arcanum (templateless, the
  MULTI-mark ambiguity case — its carved stone-and-brass arcane engraving gives the radial-anomaly
  detector more than one candidate radial feature to lock onto).
- **4 seeds each, clause ON for all 8** — no control arm run here; compared against the historical
  (clause OFF) distribution supplied directly: the 6 mainline templated skins' pre-fix
  `knob_zero_deg` (85.6°, 144°, 95°, 355°, 4°, 359°) — see
  [`2026-07-11-knob-zero-closed-loop.md`](./2026-07-11-knob-zero-closed-loop.md) for that number's
  provenance (the run-centroid-refined detector's stored values across the original 6-skin batch).
- **Pipeline per gen:** the same chain `orchestrate12.py` runs for one roll — `genskin.py` →
  `extract12.py` (pass1) → `biref12.py` (local BiRefNet cut, $0) → `extract12.py` (pass2, reads the
  matte + writes `regions[vol].knob_zero_deg` via `knob_angle.detect_from_sprite`). Isolated into
  `knobup/assets-knobup-<theme>-<seed>/` via an in-memory `genskin.HERE` monkeypatch (same pattern
  as `jsonspec/genskin_jsonspec.py`) — the live production roster (`assets-steam-porthole/`,
  `assets-myst-arcanum/`) is never touched.
- **Compliance metric:** fraction of the 8 detected `knob_zero_deg` values within ±10° of 0 (up),
  via `knob_angle.angular_error` — the SAME shared detector the mainline pipeline already writes
  to every skin's `regions.json`, for a different purpose, with no knowledge this experiment
  exists (an independent check, not one tuned to validate its own clause — verify-outputs-rule §2).

## Results

Raw table: [`knobup/results.json`](../../tools/mask-align-exp/gen12/knobup/results.json);
per-gen annotated crops + distributions: `knobup/index.html` (served).

| gen | knob_zero_deg (stored) | err from up | ±10° | visual adjudication (full-res crop) |
|---|---|---|---|---|
| steam-porthole s101 | 0.51° (recovered cut) | 0.5° | **PASS** | pointer up; mainline biref missed the cut (model painted a parts-tray card), recovered via cell-crop + local BiRefNet |
| steam-porthole s202 | 92.23° | 92.2° | FAIL | pointer at ~3 o'clock — disobeyed |
| steam-porthole s303 | None (recovered cut; detector abstained, z=4.3) | — | FAIL | pointer visually ~100° — non-compliant either way |
| steam-porthole s404 | 0.10° | 0.1° | **PASS** | pointer up — clean |
| myst-arcanum s101 | 63.0° | 63.0° | FAIL | pointer ~90–105° (cap painted with a 3/4-perspective CAMERA violation, skews the exact read) |
| myst-arcanum s202 | None (recovered cut; detector abstained, z=4.2) | — | FAIL | pointer **visually UP** but embossed too low-contrast for the z-bar — visually compliant, unmeasured |
| myst-arcanum s303 | 106.19° (recovered cut) | 106.2° | FAIL | keyway notch ~100° — disobeyed |
| myst-arcanum s404 | 162.42° | 162.4° | FAIL | wedge notch points DOWN — disobeyed |

**Compliance: 2/8 detector-measured within ±10° of up; 3/8 by best adjudication** (adding
myst-202's visually-up-but-unmeasurable cap). Threshold for flipping the architecture was 6/8.

**The historical baseline was NOT "effectively random."** The supplied pre-fix values (85.6°,
144°, 95°, 355°, 4°, 359°) are **bimodal**: 3/6 already within ±10° of up (errors 5°, 4°, 1°),
3/6 in a right-side cluster (~85–145°). Clause-ON (25–38%) shows **no improvement over
clause-OFF (50%)** at these sample sizes; the model's competing right-side-pointer prior
(4/8 gens here at ~60–110°, plus one at ~162°) is not overridden by one light sentence.

**Measurement collateral found and fixed en route ($0, no new gens):** biref12's mask-cell
island matching failed to isolate the vol cap on 4/8 gens (parts-tray card and strip layout
drift in the paint) — recovered deterministically by
[`knobup/recover_caps.py`](../../tools/mask-align-exp/gen12/knobup/recover_caps.py) (circular
strip-island pick off the existing global matte, with a cell-crop + local-BiRefNet fallback;
recovery changes only sprite ISOLATION, never the angle measurement). Two of its own picker
bugs were caught by opening the recovered sprites (a gear-lever passing a 0.55 circularity bar;
a square-ish toggle button that OVERFILLS its circumscribed circle) — both fixed with tighter
geometry gates (0.80 floor, 1.02 overfill ceiling), each verified visually after.

**Unattributed observation:** 3/4 steam-porthole gens failed the emptiness gate (a knob baked
into the socket). Whether the pointer clause increases baked-knob rate can't be attributed
without a same-seed control arm — emptiness failure is also a known baseline mode. Flagged only.

## Verdict

**Detect-and-counter-rotate stays PRIMARY. `KNOB_POINTER_UP` stays default OFF.** The clause is
not demonstrably harmful, but it is not demonstrably a useful prior either (2–3/8 vs a 3/6
baseline), and prompt bulk is not free (bproof lesson). No `build_player.py` change specced —
demoting the counter-rotation to fallback-only is moot at this compliance level. The flag +
clause stay in `genskin.py` (flag-gated, one line) so a future stronger-conditioning variant
(e.g. drawing the pointer INTO the blueprint guide, rather than describing it) can re-test
cheaply without re-plumbing.

## Spend

8 Vertex 4K gens (`gemini-3-pro-image-preview` via Vertex direct, PAINT_VERTEX) ≈ **$1.92–2.40**;
extraction/matte/recovery all local ($0). Within the ~$2 budget.

## Changed as a result

- `genskin.py`: `KNOB_POINTER_UP` flag (default **OFF**) + `_POINTER_UP_CLAUSE`, wired into both
  prompt paths (prose + `PROMPT_JSON_SPEC`) — kept for cheap future re-tests, not enabled.
- `knobup/` experiment dir: harness (`run_experiment.py`), recovery cutter (`recover_caps.py`),
  results page (`build_results_page.py` → `index.html`), raw table (`results.json`).
- No mainline pipeline behaviour change: the shipped counter-rotation path
  (`extract12.py` → `regions[vol].knob_zero_deg` → `build_player.py`) is unchanged and remains
  the load-bearing mechanism.

## Human verdict addendum (2026-07-12)

User, reviewing the results page: **"myst-arcanum · seed 202 knob is fine"** — confirms the
adjudicated call (visually straight-up; detector abstained at z=4.2 < 5 rather than guessing).
The 3/8 best-adjudication compliance figure stands as the correct read; the detector's
abstention behavior on low-contrast embossed pointers is working as designed (abstain > guess).
