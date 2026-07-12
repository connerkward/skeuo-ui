# User-loved generation — wc-goldshield jsonspec CONTROL-121 (2026-07-11)

Human-labeled gold: the user singled out this paint as an aesthetic favorite — a gold
shield with a sculpted LION-HEAD crest on the upper-left edge and a silver/steel
GAUNTLET CLAW gripping the right side of the screen, rune-engraved borders with blue
gems, and a bottom sprite strip (knob cap + rune cylinder + two cross/clasp toggle
states). Identified by visually sweeping every wc-goldshield `paint.png` on disk
(prod, abshape a/b, twoimg neutral/control/treat, jsonspec control/treat, driftbisect
a/b/c) — only one has the lion head + claw combo.

## Where it lives

- **File**: [`assets-jsonspec-wc-goldshield-control-121/paint.png`](assets-jsonspec-wc-goldshield-control-121/paint.png)
- **SHA-256**: `5609f54d4e1449991732d93650be9f571c33dd3a1cad3882f4d20179242b31d5`
- **Desktop copy + provenance sidecar**: `~/Desktop/cc-skeuo/2026-07-11-loved-goldshield-control-121.png` (+ `.txt`)

## Provenance

| Field | Value |
|---|---|
| Experiment | `jsonspec` — "does a fenced-JSON blueprint spec help PAINT generation?" |
| Arm | **CONTROL** — verbatim production prose prompt (imported `genskin.py`'s own `main()`, prompt content byte-identical to production; `PROMPT_JSON_SPEC` is `False` in both) |
| Seed | 121 |
| Model | `fal-ai/gemini-3-pro-image-preview/edit` |
| Mode | templated |
| Blueprint config | `blueprint_arm="solid"` (forced), `blueprint_conditioning="solid"`, `blueprint_twoimg=false` — the [abshape-verdict](../abshape/verdict.json) winning guide style, also `genskin.py`'s current default majority arm (0.75 solid / 0.25 outline) |
| Dims | 4608×3712 |
| Generated | 2026-07-11 ~16:00 |
| Automated gate | **FAIL** (`gate_pass=false`, reason `emptiness`; queue-button guide-colour bleed ring 14.45% — see [`scores.json`](scores.json)) — flagging this for honesty: the human-loved read and the automated defect gate disagree here |

## Why it's different from the shipped production asset

Shipped `assets-wc-goldshield/paint.png` is **seed 736** (`../assets-wc-goldshield/orch.json`:
rolls 710 → 723 → 736, same model, same templated mode, same prose prompt content —
`PROMPT_JSON_SPEC=False` in both). Since the loved gen is the jsonspec **CONTROL** arm,
prompt *content* is not the differentiator — this is the exact production prompt.

Two real deltas vs. the seed-736 shipped asset:

1. **Seed 121 vs 736.** Per-seed variance is large even within one arm (see
   [`scores.json`](scores.json) bleed/drift swings seed-to-seed) — 121 rolled a far more
   elaborate, figural interpretation (literal lion-head statue + gauntlet claw) than 736's
   roll (dragon-wing filigree, no figural elements).
2. **`blueprint_arm` forced "solid".** The abshape-verdict winning guide style (cleaner
   cavity emptiness, no stray guide-colour ring). Production's seed-736 `orch.json`/
   `results.json` predate the `blueprint_arm` field, so whether that run also drew
   "solid" is unconfirmed — likely (current default favors it 75%) but not verified.

**Conclusion: primarily seed variance on an otherwise-unchanged production prompt, not a
prompt-engineering win.** For "more like this," re-roll more seeds through the current
production path (optionally forcing `blueprint_arm="solid"`) rather than changing the
prompt.

Related: [`verdict.json`](verdict.json), [`genskin_jsonspec.py`](genskin_jsonspec.py),
[`../abshape/verdict.json`](../abshape/verdict.json), `docs/experiments/2026-07-11-jsonspec-paint.md`.
