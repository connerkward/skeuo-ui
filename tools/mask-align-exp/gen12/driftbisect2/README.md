# driftbisect2 — extraction-commit bisect: paint drift vs detector drift

Follow-through from the drift-clause bisect
([`docs/experiments/2026-07-11-drift-clause-bisect.md`](../../../../docs/experiments/2026-07-11-drift-clause-bisect.md))
fall-through step 1: *"re-run CURRENT extract12 against the ORIGINAL baseline-batch paints
(`794da20e`) — separates 'the paint drifts more now' from 'the detector measures differently
now'."* $0, no new generations (paints already exist; only the extractor was re-run).

## Step 0 — the originally-planned baseline-paint recovery is IMPOSSIBLE (confirmed, not assumed)

The task asked to recover the ORIGINAL `794da20e`-batch `paint.png` for `fallout-pipboy`,
`steam-porthole`, and `fa-pod` from git history or Google Drive. Both are dead ends, confirmed
by direct inspection, not by a single failed grep (per `verify-external-claims-rule`'s
absence-from-a-proxy ≠ absence — this is an exhaustive sweep, not one lookup):

- **`paint.png` was NEVER git-committed at the original seed.** `794da20e` (2026-07-08) committed
  only `orch.json`/`regions.json`/`results.json` for these skins — `paint.png` stayed gitignored
  (working-tree only) until `39d76200` (2026-07-11) first committed pixels. But by then **every
  one of the 6 templated-passing skins had already been rerolled to a NEW seed**:

  | skin | `794da20e` seed | first-committed (`39d76200`) seed |
  |---|---:|---:|
  | fallout-pipboy | 71 | 571 |
  | steam-porthole | 84 | 623 |
  | fa-pod | 173 | 673 |
  | ps1-crunchy | 84 | 623 |
  | wc-goldshield | 110 | 736 |
  | wmp-quicksilver | 84 | 662 (→688 current) |

  Confirmed via `git log --oneline --all -- assets-<skin>/paint.png` (only 2 hits per file, both
  post-reroll) and via `results.json`'s `seed` field diffed across every intermediate commit
  (`794da20e` → `46574f6c` → `12606297` → `39d76200`). `fallout-pipboy`'s reroll happened as
  early as `46574f6c` (2026-07-09) — the original paint was overwritten within a day, matching
  `39d76200`'s own commit message warning ("one was already silently overwritten with no frozen
  copy") — turns out it was **all of them**, not one.
- **Drive (`MEDIA-MANIFEST.md`) only mirrors the CURRENT seeds** (571/623/673/736/688, uploaded
  2026-07-11) — same dead end, not an independent backup.
- **Swept every plausible local cache**: `bproof/gen12ref/assets-steam-porthole/results.json`
  DOES retain the seed-84 metadata (template/palette/keys) but only ships `blueprint.png` (the
  guide scaffold) — no painted pixels. `twoimg/`, `knobticks/`, `abshape/` dirs hold unrelated
  generations at unrelated seeds. `entire`'s local checkpoint git refs
  (`refs/heads/entire/checkpoints/v1`, 1678 commits) store only session **transcripts**
  (`full.jsonl`), never working-tree file snapshots — confirmed structurally (a sample checkpoint
  commit's diff is 3 text files, no images) and by path-filtered `git log` across every
  `entire/*` branch (2 hits total for `assets-fallout-pipboy/paint.png`, both post-reroll,
  same content as the current working tree).

**Verdict: the true baseline paint pixels are gone. No `.env`, permission, or search-effort
issue — the bytes were never preserved anywhere.** Filed as a follow-up in
`docs/DECISIONS.md`-adjacent TODO: freeze-on-first-gate-pass, not on-commit, is the guardrail
gap (a paid Vertex gen currently isn't archived until someone remembers to `git add` it, days
later, by which point the roll loop may have already overwritten it).

## Step 0.5 — the substitute test (holds the SAME evidentiary power)

Instead of "old paint × current extractor" (impossible), this runs the **paint-fixed / extractor-
swapped** twin: hold paint at what's genuinely on disk today (the seed that produced the LIVE
`roster_audit.json` numbers) and run BOTH extractor versions against the exact same
`paint.png`/`mask.png`/`_biref` sprites:

- **(a)** old paint × old extractor — `roster_audit.json`'s `historical_oldest` (already computed
  from `794da20e`'s own committed `regions.json`; needs no paint pixels, since `drift_table()`
  only reads `template` + `regions.<k>.device`, both of which `794da20e` DID commit).
- **(b)** new (current) paint × current extractor — `roster_audit.json`'s `live` (already computed,
  what's actually shipping).
- **(c′)** new (current) paint × OLD extractor (`794da20e`'s `extract12.py`, 433 lines) — **NEW,
  computed here** by copying today's committed `paint.png`/`mask.png`/`results.json` +
  `_biref/*.png` into a scratch dir and running the checked-out `794da20e` version of
  `extract12.py` against it, read-only, via `git show 794da20e:.../extract12.py`.
- **(d)** new paint × current extractor, **re-run from scratch in this harness** as a
  methodology sanity check — must reproduce (b) exactly if the scratch-dir setup is faithful.

Because (c′) and (b) differ ONLY in which `extract12.py` ran — same paint, same mask, same
`_biref` sprites, same template, same `drift_table()` code (imported from
[`twoimg/roster_audit.py`](../twoimg/roster_audit.py), never reimplemented) — any large gap
between them is attributable to the extraction algorithm alone. `extract12.py` churned
substantially over this period (433 → 903 lines; 10 commits since `794da20e`:
`82abe27d f80484b8 453482bf 86f69c75 d2be10f3 8f8c38e5 7b5d0f22 73e5f95b 8a7e081f 2685db4e`),
so "the detector changed" was a live hypothesis worth testing directly, not assuming away.

**Extractor version = origin/main's `extract12.py`** (903 lines; confirmed byte-identical to the
`driftbisect-2026-07-11` branch tip's copy, and 1 commit ahead of the shared checkout's stale
local `HEAD` — the local copy was NOT used to avoid measuring an even-older detector by
accident). Read only via `git show <ref>:extract12.py`; the shared checkout's own
`extract12.py` was never touched by this experiment.

## Method

```
driftbisect2/_extractors/extract12_baseline_794da20e.py   # git show 794da20e:...extract12.py
driftbisect2/_extractors/extract12_current_originmain.py  # git show origin/main:...extract12.py
driftbisect2/_extractors/knob_angle.py                    # unchanged since 794da20e local HEAD == origin/main
driftbisect2/assets-<skin>-old/     (+ -old_biref/)  <- copy of assets-<skin>/{paint,mask,results.json} + _biref/*.png
driftbisect2/assets-<skin>-cur/     (+ -cur_biref/)  <- identical copy, second instance
```
Run each extractor once per skin against its own copy (`python3 _extractors/extract12_*.py
assets-<skin>-{old,cur}`), producing a fresh `regions.json` in each. `compute_drift.py` imports
`twoimg.roster_audit.drift_table` (not reimplemented) and reads `roster_audit.json`'s existing
(a)/(b) rows to complete the table.

**Fallback caveat (found, corrected for):** the OLD extractor missed 2 of 30 controls entirely
(`fallout-pipboy.vol`, `fa-pod.prev`) and fell back to the AUTHORED TEMPLATE position verbatim
(`regions.<k>.fromTemplate: true`) — which trivially reads 0px drift (it's not a real detection,
it's a template pass-through). The CURRENT extractor hit zero such fallbacks on the same paints.
Left uncorrected, these 2 zeros would artificially **deflate** the old extractor's mean and bias
the verdict toward "detector-driven" — so the headline numbers below **exclude fallback
controls from both extractor runs' means** (raw means available in `results.json`).

## Results — the 2×2 (px, mean template-to-detected-device drift; fallback-excluded)

| skin | (a) old paint × old extractor | (c′) **new paint × OLD extractor** | (b) new paint × current extractor | (c′)→(b) swap Δ | (a)→(c′) paint-only Δ |
|---|---:|---:|---:|---:|---:|
| fallout-pipboy | 142.7 | **1016.8** | 950.5 | −66.3 | **+874.1** |
| steam-porthole | 523.2 | **868.6** | 858.3 | −10.3 | **+345.4** |
| fa-pod (control, improver) | 602.0 | **496.5** | 502.9 | +6.4 | **−105.5** |

Methodology check: (d) new-paint × current-extractor, re-run fresh in this harness, reproduced
(b) **exactly** (0.0px delta on all three skins, per-control) — the scratch-dir setup is faithful
to what's actually shipping.

## Verdict: **REAL PAINT DRIFT — not a detector artifact**

Swapping ONLY the extractor version, holding paint fixed at what's on disk today, moves the mean
drift by **−66.3 / −10.3 / +6.4 px** — all three land far inside the drift-clause bisect's own
150px noise floor. Swapping ONLY the paint (holding the extractor fixed at the OLD, 794da20e
version) moves it by **+874 / +345 / −105 px** — the true regressors jump by 3.5–6× the noise
floor, and the control (`fa-pod`, a known IMPROVER) moves the *other* direction, exactly matching
its improver status in the live audit. The detector-swap signal is noise; the paint-swap signal
is the whole effect. Per-control breakdown (in `results.json`) shows the SAME pattern control-by-
control, not just in aggregate — e.g. `fallout-pipboy.album_art` reads 2069px under the OLD
extractor and 2064px under the CURRENT one, on the identical paint.

**This also means the extraction-commit churn (10 commits, 433→903 lines) did not regress
measurement accuracy** — if anything the current extractor is strictly better at NOT falling back
to template (0 fallbacks vs 2 on the same paints).

## Implied follow-up

The drift regression is in the **generations themselves** getting further from their authored
template layout over time, not in how they're measured. Candidate directions (none applied here —
this experiment only isolates WHERE the problem lives, not WHY):
1. The already-completed drift-clause bisect ruled out the BOLD-silhouette clause specifically —
   the driver is some OTHER prompt/serving change across the Jul 8→11 window (Vertex vs fal
   serving switch, seed range, or accumulated unrelated prompt edits are still open suspects).
2. **Guardrail gap, not a drift-cause finding**: paid Vertex generations are gitignored until
   someone remembers to `git add` them — by which point a re-roll may have already overwritten
   the bytes with no way back. Freeze-on-first-gate-pass (commit `paint.png`/`mask.png`
   immediately when `gate.PASS` flips true, before any possible re-roll) would have made this
   bisect a clean git-history diff instead of a recovery investigation.

## Cost

$0 — 6 extractor runs (read-only, local CPU/numpy/scipy, no biref/Vertex calls; existing
`_biref` sprites reused as-is) + 3 lookups against the already-computed `roster_audit.json`.
