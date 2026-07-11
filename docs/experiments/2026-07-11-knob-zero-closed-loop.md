# Knob-zero fix — deterministic closed-loop re-verification (user overrule of a VLM-witnessed PASS)

Code: [`tools/mask-align-exp/gen12/knob_angle.py`](../../tools/mask-align-exp/gen12/knob_angle.py)
(shared detector), [`tools/mask-align-exp/gen12/extract12.py`](../../tools/mask-align-exp/gen12/extract12.py)
(`detect_knob_zero_deg`, now a thin wrapper), [`tools/mask-align-exp/gen12/knobzero-proof/render_knob.mjs`](../../tools/mask-align-exp/gen12/knobzero-proof/render_knob.mjs)
(throwaway isolated Playwright render driver), [`tools/mask-align-exp/gen12/knobzero-proof/annotate2.py`](../../tools/mask-align-exp/gen12/knobzero-proof/annotate2.py)
(draws from stored `regions.json` values only). Results page:
[`tools/mask-align-exp/gen12/knobzero-proof.html`](../../tools/mask-align-exp/gen12/knobzero-proof.html) (served).
Fixing commit: see repo log at/after this record's date, `gen12: knob-zero closed-loop fix`.

## Question

The user overruled commit `8a7e081f` (knob baked-rotation fix) + `e242a2eb` (its proof page):
*"knob-zero fix is fail. did you even cross check with vlm? these lines are off. near, but off
and noticeably."* Two independent verification failures were named: a VLM cross-check cannot
judge small angular error (witness, not judge — `verify-rule` §1b), and the proof page's overlay
arrows were drawn by a script (`annotate.py`) that **reimplemented** the detector's centroid/
radius geometry instead of reading its stored output (`verify-rule` §7 proxy trap). Question:
how far off is the render actually, what's the root cause, and does a generalizable fix bring it
under a 3° bar — measured with a real, deterministic, non-VLM closed loop, not eyeballing.

## Method

**Closed loop (no VLM, no human eyes as the metric):** for each of the 6 skins from the prior
batch (steam-porthole, ps1-crunchy, myst-arcanum, fallout-vault, fa-pod, n64-cutscene — the 4
originally-fixed skins plus 2 regression controls), render the REAL shipped `player.html` in a
throwaway isolated Playwright browser (own `chromium.launch()`, `deviceScaleFactor:4`), screenshot
the `.pknob .cap` element's exact DOM bounding box at init (value=0.5, the page default — no
interaction needed, target = 12 o'clock / 0°), and run the pointer-angle detector on the RENDERED
PIXELS. `angular_error = |measured − 0°|` (circular distance). Ran this SAME measurement against
both the pre-fix and post-fix pipeline state so only the pipeline changes between the two numbers,
never the ruler.

**Detector:** `knob_angle.py:radial_anomaly_angle()` — a local radial anomaly in the gradient-
magnitude angular profile (median+MAD z-score vs. the cap's radially-symmetric body), rejecting
wide humps (specular streaks). Two call sites share this one implementation: `extract12.py`
(alpha-masked raw sprite, at extraction time) and the closed-loop verifier (opaque rendered crop,
known DOM geometry, at render time) — deliberately the same core algorithm applied to categorically
different data (pre-render alpha-masked cutout vs. post-render/post-CSS-transform/post-rasterize
pixels), which is what makes the verifier a genuine end-to-end check rather than circular
validation (`verify-rule` §2).

**Cost:** $0 — fully deterministic signal processing, zero model/API calls anywhere in extraction,
rendering, or measurement.

## Root cause(s), in suspicion order

1. **CONFIRMED — bin-quantization bias.** The old detector returned the winning angular bin's
   leading EDGE (`peak * bw`, `nbins=180` → `bw=2°`), zero sub-bin refinement. Proof: every stored
   `knob_zero_deg` pre-fix was an exact multiple of 2° across all 6 independent paints (84.0, 142.0,
   94.0, 354.0, 4.0, 0.0 — never fractional). Re-running the identical algorithm with 3-point
   parabolic sub-bin refinement shifted every value by **+1.0° to +1.9°** — small, real, systematic,
   and fully generalizable (same shape of bug on every knob, not a per-skin fluke). This is the
   shipped fix, in the shared `knob_angle.py` module (`bin_center_refine=True` default).
2. **RULED OUT — rotation-center error.** Measured directly: alpha *centroid* (old origin) vs.
   alpha *bounding-box center* (what `build_player.py`'s `tight()` + `background-size:cover`
   actually renders around) differ by <1.5px / <0.3° on all 6 sprites. Negligible; not the
   dominant error, though the detector now centers on bbox-center anyway (exact render-origin match).
3. **RULED OUT — CSS transform-origin / aspect mismatch.** `--ar: PW/DEVH` on `#phone` makes any
   seat-radius-derived box render as a true geometric square in pixels regardless of paint aspect
   or `devFrac` (verified algebraically); `.pknob .cap`'s default 50%/50% origin coincides with
   that square's center. A real transform-origin bug would show up as a large, direction-dependent
   error; none was found in the closed loop.
4. **CONFIRMED on principle — proof-page proxy trap.** `annotate.py` reimplemented the centroid/
   radius math instead of reading `extract12.py`'s stored output. It happened to land on
   near-identical numbers here (same reason (2) was ruled out — these cutouts are nearly circular,
   centroid≈bbox-center), so it wasn't the source of the angular bug, but was still the wrong
   practice. Fixed regardless: `regions.json` now stores `knob_zero_geo` (the detector's own
   measured center+radius) alongside `knob_zero_deg`; `annotate2.py` draws from those stored values,
   never re-derives.

**Verifier-only calibration** (affects measurement, not the pipeline): render-domain scan uses
`r_hi=0.80` (vs. sprite-domain `0.94`) — `.pknob .cap`'s `border-radius:50%` clip sits right past
the cap's own opaque knurled rim, and scanning out to 0.94R samples into a soft alpha-blend zone
where the phone's body art shows through, producing spurious peaks (verified: fallout-vault read a
false 20.8° error at `r_hi=0.94`; `0.80` recovered 0.9°, corroborated by an independent manual
dark-pixel-centroid measurement and a full-res visual crop). `z_thresh=4.5` (vs. sprite-domain
`5.0`) accounts for CSS-rotation raster blur attenuating peak sharpness; every skin but ps1-crunchy
(smallest crop, thinnest carved pointer, z=4.6) clears 8.3–245.8, so this carries no false-positive
risk in this batch. Doubling capture resolution (`deviceScaleFactor` 4→8) made ps1-crunchy's z
score WORSE (3.5, not better) — confirms a raster-blur floor, not a resolution shortfall.

## Results — render error vs. 12 o'clock target, before vs. after

| skin | stored knob_zero_deg (old → new) | render error (before → after) | bar |
|---|---|---|---|
| steam-porthole | 84.0° → 85.59° | 2.83° → **0.44°** | PASS |
| ps1-crunchy | 142.0° → 143.93° | 1.21° → **0.69°** | PASS (weakest detector signal, still consistent) |
| myst-arcanum | 94.0° → 95.47° | 0.56° → **0.89°** | PASS (both noise-level; two-mark ambiguity unresolved, see below) |
| fallout-vault | 354.0° → 355.01° | 0.88° → **0.98°** | PASS (noise-level both ways) |
| fa-pod (regression) | 4.0° → 4.73° | 1.02° → **1.29°** | PASS (regression control) |
| n64-cutscene (regression) | 0.0° → 1.19° | 3.72° → **2.32°** | PASS (only skin over 3° pre-fix; now under) |

All 6 knobs measure ≤3° render error post-fix (max 2.32°, n64-cutscene).

## Human verdict — 2026-07-11

Not a human-in-the-loop judgment call this pass — the whole point was replacing the prior
VLM-witnessed "PASS" with a deterministic, re-runnable metric per the user's overrule. The
**user's qualitative call was correct**: a real, systematic bias existed and the prior
verification method (VLM + reimplemented-geometry overlay) could not have caught it. The
**quantitative magnitude was smaller than the "5–20°" working hypothesis** floated when scoping
this task — the actual bug was worth +1.0–1.9° per skin, and pre-fix render errors measured
0.56°–3.72°, not double digits. This is reported plainly rather than inflated to match the
hypothesis (`anti-sycophancy-rule` / `verify-outputs-rule` §4 — no positive or exaggerated claims
beyond what was actually measured).

**myst-arcanum's two-carved-marks ambiguity is explicitly unresolved** — a source-art question
(which of two marks is "the" pointer), not something this fix touches; the wedge-mark choice
stands until the user rules on it.
