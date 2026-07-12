# servingbisect — fal-vs-Vertex serving-path drift bisect (2026-07-11)

Final step in the drift-suspect chain
([`docs/experiments/2026-07-11-drift-clause-bisect.md`](../../../../docs/experiments/2026-07-11-drift-clause-bisect.md)):
the extraction-commit bisect (`892bf045`, [`driftbisect2/`](../driftbisect2/README.md)) proved
the drift regression is PAINT-driven; the clause bisect (`218224f7`, [`driftbisect/`](../driftbisect/))
exonerated the BOLD-silhouette clause. Remaining suspects: **(a) the fal→Vertex serving switch**
(`PAINT_VERTEX` flipped ON 2026-07-10, `genskin.py:35` — the baseline batch was fal-served),
(b) seed ranges, (c) accumulated prompt additions in aggregate. This tests **(a)** directly.

## Method

Same **current production prompt** (`../genskin.py` imported read-only via importlib —
`gen_pair.py` drives its real `main()`, runtime-toggling only the module's `PAINT_VERTEX`
attribute per job; genskin.py on disk untouched). Same 2 themes — **fallout-pipboy** +
**steam-porthole**, the roster audit's two true regressors — same 2 seeds each (571/671,
623/723; 571 and 623 are the live production seeds), generated via BOTH paths:

- **vertex** — `gemini-3-pro-image-preview` direct via Vertex AI (project muser-2605300220,
  global), 4K, 5:4, `edit_vertex()` with the 429 retry; **the current post-switch path**.
- **fal** — `fal-ai/gemini-3-pro-image-preview/edit` (fal's wrapper over the same model id),
  4K, 5:4, `edit()`+`upload()`; **the pre-switch path** that served the low-drift baseline batch.

All 8 gens SEQUENTIAL (per the Vertex quota lesson baked into `genskin.py`'s `edit_vertex`
comment); zero 429s occurred. Same seed → same deterministic `pick_blueprint_arm()` draw, so
both paths share the conditioning arm within each pair (571/623/723 drew `solid`, 671 drew
`outline`) — serving path is the only variable within a pair.

Pipeline per gen: extract12 pass1 → local BiRefNet_HR@2048 matte (MPS, $0) → extract12 pass2 →
gates. Scored by `score.py`, which imports `drift_table()` from
[`../twoimg/roster_audit.py`](../twoimg/roster_audit.py) (not reimplemented) — the identical
metric as the live audit and both prior bisects. **Noise floor 150px**, carried forward from
the clause bisect. Fallback (`fromTemplate`) controls excluded from means, same correction as
driftbisect2.

## Results — per-path drift table (mean px, fallback-excluded)

| theme | seed | arm | vertex | fal | Δ (vertex − fal) | read |
|---|---:|---|---:|---:|---:|---|
| fallout-pipboy | 571 | solid | 531.2 | 629.1 | −97.9 | within noise floor |
| fallout-pipboy | 671 | outline | 428.9 | **93.7** | +335.2 | vertex worse |
| steam-porthole | 623 | solid | 529.5 | 718.1 | −188.6 | **fal worse** |
| steam-porthole | 723 | solid | 696.8 | 212.2 | +484.6 | vertex worse |
| **pooled (n=4/path)** | | | **546.6** | **413.3** | **+133.3** | **inside the 150px floor** |

Gates: 1/8 gate-PASS (fallout-pipboy-vertex-671) — normal single-roll rate; the drift metric
doesn't require gate-pass. Per-run per-control tables, gate reasons, fallback lists:
[`results.json`](results.json). Raw gen log: `gen_pair.log`; extraction log: `extract_all.log`.

## Observations

1. **No consistent serving-path effect.** The per-pair deltas point BOTH directions beyond the
   floor (vertex worse at 671/723 by +335/+485; fal worse at 623 by −189; 571 within noise),
   and the pooled Δ (+133px) is inside the 150px floor. A real serving-stack driver would move
   all four pairs the same way; this is the signature of high per-gen variance, not a path effect.
2. **Both paths still drift far above the old 143px baseline.** 7 of 8 fresh gens land at
   212–718px — reverting to fal serving does NOT recover the baseline drift level. (The one
   exception, fal-671 at 93.7px, shows a near-baseline gen is still attainable under the
   current prompt — on either stack, low-drift draws exist in the tail.)
3. **Within-path, cross-seed spread is as large as any cross-path delta** (fal pipboy: 629 vs
   94; fal porthole: 718 vs 212; vertex porthole: 530 vs 697) — seed-to-seed variance dominates.
4. **Same-seed same-path re-roll vs the live production paint differs by 330–420px**
   (vertex-571 fresh 531 vs live 950; vertex-623 fresh 530 vs live 858; paint shas differ).
   Caveat: NOT a clean fixed-seed replication — the live paints were generated 2026-07-10,
   BEFORE the knob-tick clauses shipped (`8679c132`; their results.json carries no `ticks`
   field), so their prompt lacked 2 bullets that mine include. Confounded (prompt delta and/or
   seed non-reproducibility) — but either way, single-gen drift readings swing by 2–3× the
   assumed 150px floor at nominally-fixed config.

## Conclusion (bottom line)

**The fal→Vertex serving switch is NOT the drift driver.** Same seed + same prompt on the two
stacks produces mixed, direction-inconsistent deltas whose pooled mean (+133px, vertex slightly
worse) sits inside the experiment's own noise floor — and critically, the pre-switch fal path
does NOT reproduce the low-drift baseline either (413px pooled vs the 143px-class baseline).
Suspect (a) is exonerated alongside the clause and the extractor.

Remaining suspects narrow to **(b) seed ranges** and **(c) accumulated prompt additions in
aggregate** — plus a candidate this run surfaced: **per-gen variance at fixed config is
≥330–420px** (observation 4), so the original "regression" magnitude itself may partly be
sampling luck on n=1 rolls per skin, and any further bisect needs n≥4 per cell (or a paired
noise-floor re-derivation) before its verdict means anything. Testing (c) directly is one more
cheap arm away: re-run this harness with the tick bullets stripped and the pre-07-10 prompt
reconstructed from git — but per observation 3, spend it at higher n or not at all.

**Honesty note:** n=2 seeds/theme/path, 150px noise floor discipline carried from the clause
bisect — and observation 4 suggests that floor is optimistic for single-gen comparisons.
Directional evidence, not significance.

## Models + spend (dev-facing annotation)

- Paint: `gemini-3-pro-image-preview` — 4 gens Vertex direct ($0.24/img 4K) + 4 gens via
  `fal-ai/gemini-3-pro-image-preview/edit` ($0.30/img 4K) = **$2.16** (zero retries billed).
- Matte: local BiRefNet_HR@2048 (MPS) — $0. Extraction/scoring: local — $0.
