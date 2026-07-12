# gen12 human review round — protocol

This round is **Milestone 1's gate** (`skeuov1-pipeline`, see
[`docs/SKEUO-V1.md`](../../../docs/SKEUO-V1.md)). Milestone 2 (roster parity / generation
port) does not start until every skin below has a persisted PASS/FAIL verdict from this round.

## One link, when re-rolls land

```
http://localhost:61171/dashboard12.html
```

(port also recorded in [`.review-url`](.review-url) — `review_server.py` may pick a new port on
restart, so re-check that file if this link goes dead). The server is left running; refresh the
page after any re-roll lands to see current renders.

## What to judge, per skin

For each of the 15 roster skins, drive the embedded **live player** (drag knobs, drag the seek
thumb to both extremes, click buttons, flip the toggle) and set **PASS** or **FAIL** with a note
on what's wrong. The gate criteria (the pipeline's definition of "controls seated correctly"):

1. **Controls seated** — every knob/slider/button/toggle sits on its painted socket, not
   floating or overlapping a neighbor.
2. **No leftover guide rings** — no visible alignment-guide ring / halo baked into the paint
   around any control.
3. **No baked text** — no literal "ON"/"OFF" (or any control label) painted into the sprite;
   state must read from the art, not text.
4. **Toggle reads as two distinct states** — flipping it is visually obvious (not just a text
   swap), and it's aligned to its slot.
5. **Slider/seek throw** — the thumb's travel covers the full groove at both extremes, not
   stopping short or overshooting onto the body.
6. **Knob ticks** (where the theme calls for them) — match the director-specified tick vocabulary
   for that theme, not a generic mismatched set.
7. **Knob zero position** — the rotation knob's rest angle reads at its true zero (see
   `knobzero-proof.html` / `knob_angle.py` for the closed-loop measurement this claims to fix).
8. **Overall aesthetic** — does it read as a cohesive, intentional skin for its theme, not a
   template-color fallback or a mismatched part.

A skin that mostly works but has one of the above wrong is a **FAIL** — this round is checking
whether the CURRENT pipeline state (post knob-zero fix, post crop-discipline protocol) actually
produces a clean roster, not partial credit.

## How verdicts persist

The dashboard keeps live edits in the browser's `localStorage` (key `gen12-review`) and, on every
toggle/note change, debounce-POSTs the full set to `/save` (400ms after the last edit), which
`review_server.py` writes atomically to [`review.json`](review.json) in this directory. That file
is what the agent reads back to know the round is done — **the JSON on disk is the record**, not
the browser tab.

- **Fresh round = fresh browser origin.** Because state lives in `localStorage` keyed by page
  origin, a new server port (a restart) gives every skin a blank "— unset —" automatically. If
  reusing the same tab/port, hit the page's `reset` button (clears `localStorage` and reloads) to
  start clean.
- `review.json` was reset to `{}` for this round on 2026-07-11. Prior rounds are preserved,
  never deleted, per this repo's human-labeled-data-rule: [`review-2026-07-09.json`](review-2026-07-09.json)
  and [`review-2026-07-09-archived.json`](review-2026-07-09-archived.json) are the two prior
  snapshots (both stale — predate the knob-zero fix and the current 15-skin roster; kept for
  history only, not to be read back into a live round).

## Definition of done

Every one of the 15 roster skins listed in the dashboard's table has a `gate` of `"pass"` or
`"fail"` (not `"unset"`) in `review.json`, with a `notes` string on every FAIL explaining what's
wrong. When that's true, Milestone 1's checklist item 6 is complete and Milestone 2 unblocks.

---

## Publish gate contract

This is the **written contract** the future `skeuov1` skin-registry manifest (`docs/SKEUO-V1.md`
Milestone 2 item 1) consumes to decide which of the 15 roster skins ship. It formalizes this
review round as the roster's one and only publish gate — see Milestone 2 item 9. Spec only: no
manifest generator exists yet, and nothing here builds one.

### 1. Definition — when is a skin PUBLISHABLE

A skin `id` is **PUBLISHABLE** iff **both**:

**(a) Auto-gate PASS in its live `regions.json`** — `assets-<id>/regions.json`'s `gate.PASS ===
true` at the moment the manifest is generated. This is `extract12.py`'s deterministic checklist
(controls found, sockets empty, seek coverage, no guide-ring residue, no baked text, no
degenerate regions, drift under threshold — see `gate.reasons` for the live list of checks).
"Live" matters: `regions.json` is re-written on every extraction, so this is always the CURRENT
state of the directory, never a cached snapshot (`orch.json`'s `"passed"` is roll-history, not
the live gate — `build_dashboard.py` already treats `regions.json` as authoritative over `orch.json`
for this exact reason, see its "LIVE gate vs CACHED gate" comment).

**(b) Human verdict PASS in `review.json` for the EXACT generation reviewed.** Not just "a PASS
exists for this `id`" — the PASS must be bound to the specific `seed` + `paint.png` the human
actually looked at when they clicked PASS. A verdict is **stale** (and the skin is NOT
publishable on that verdict alone) when the roster directory's current generation identity no
longer matches what's recorded in the verdict.

**(a) AND (b) both hold, checked independently** — an auto-PASS with a stale/missing human
verdict is not publishable (nobody has looked at this exact generation); a human PASS on a
generation that no longer auto-gates (e.g. a later drift-gate addition catches something the
human's round predated) is also not publishable. Neither side overrides the other.

### 1a. Binding a verdict to a generation identity

**Current state (verified by reading `review_server.py` + `build_dashboard.py` before writing
this contract):** `review_server.py` just writes whatever JSON blob the dashboard POSTs to
`/save` — it does not itself define or enforce a schema. The dashboard's `fbJSON()` was, until
this pass, building `{id: {gate, notes}}` per skin — **no generation identity was recorded**, so
a verdict couldn't be told apart from a stale one after a re-roll.

**This was a ≤10-line change, made as part of this pass** (small enough to fall inside the
carve-out in this task's brief — not deferred to a future round): `build_dashboard.py` now
stamps each skin's current `seed` (from `orch.json`/`results.json`) and a truncated sha256 of its
`paint.png` (`paint_sha`, 12 hex chars — collision-safe at this roster's scale) as
`data-seed`/`data-paint-sha` attributes on that skin's toggle button at page-build time, and
`fbJSON()` now includes both in every saved entry:

```json
{
  "fallout-vault": {
    "gate": "pass",
    "notes": "",
    "seed": 649,
    "paint_sha": "f37d3326e7c7"
  }
}
```

**Staleness check** (what the future manifest generator — or any consumer of `review.json` —
must do before trusting a PASS): for each `id` with `gate: "pass"`, recompute the CURRENT
`paint_sha` from `assets-<id>/paint.png` and compare. Mismatch → the paint was re-rolled after
the human judged it → **that verdict is invalid for the current generation**, full stop, no
matter how recently it was saved. `seed` is carried alongside `paint_sha` as a human-readable
cross-check (visible in the dashboard's own `runid` line) but `paint_sha` is the binding key —
two different seeds can theoretically hash-collide-free but only `paint_sha` is a direct hash of
the actual pixels the human looked at.

**This round's verdicts (started 2026-07-11, `review.json` reset to `{}`) already carry this
binding** — they are captured durably from the first save, not retrofitted later.

### 2. Output — the publish-set artifact the manifest will read

Spec only — shape, not implementation. A future `roster-v<N>.json` (or equivalently-shaped data
the manifest generator emits), derived as **`review.json` ∩ live auto-gate**, one entry per
PUBLISHABLE skin (§1):

```json
{
  "version": "v1",
  "date": "2026-07-11",
  "skins": [
    {
      "id": "fallout-vault",
      "seed": 649,
      "paint_sha": "f37d3326e7c7",
      "verdict_ref": "review.json#fallout-vault"
    }
  ]
}
```

- `version` — a monotonically increasing publish-set identifier (see §3 lifecycle); NOT the
  same axis as gen12's internal `gen12`/roll numbering.
- `date` — the date the publish set was generated (not the date any individual skin was judged;
  that's recoverable via `verdict_ref`).
- `skins[]` — exactly the PUBLISHABLE set per §1, nothing else. A skin that FAILed, is unset, or
  whose verdict is stale is simply absent — not included with a `false` flag. Absence is failure.
- `seed` / `paint_sha` — copied from the bound verdict (§1a), so the manifest itself carries
  enough to re-verify a publish decision without re-reading `review.json`.
- `verdict_ref` — a pointer back to the source-of-truth record (`review.json`'s per-skin entry),
  so "why is this skin in/out of the roster" is always traceable to a human judgment, per
  human-labeled-data-rule.

The manifest generator that PRODUCES this file is Milestone 2 item 1's job, not this pass's.

### 3. Lifecycle

- **A new roster drop = a new review round = a new `version`.** Adding/regenerating skins means
  re-running the gate (§1) against the new generations, which means a new review round
  (fresh `review.json` state or targeted re-review of only the changed skins) before a new
  `roster-v<N>.json` can be cut.
- **Partial rounds are allowed.** The publish set is simply whatever subset of the roster
  currently satisfies §1 — a round doesn't need every skin PASSed to produce a valid (smaller)
  publish set. This round's own `Definition of done` (all 15 with a verdict) is this round's bar
  for calling gen12 pipeline validation complete — it is stricter than what §3 requires for
  cutting a manifest at all.
- **Re-rolls always re-enter through the same gate.** There is no fast path that lets a re-rolled
  skin skip human review — a new `paint_sha` means no bound verdict exists for it (§1a), so it is
  automatically excluded from the publish set until a human looks at it again and a fresh PASS is
  saved against the new hash.

Related: [`docs/SKEUO-V1.md`](../../../docs/SKEUO-V1.md) Milestone 2 items 1 (manifest, consumes
this contract) and 9 (this contract). [`human-labeled-data-rule`](../../../.claude/rules/human-labeled-data-rule.md)
(why `review.json` is never silently regenerated or lost). [`verify-outputs-rule`](../../../.claude/rules/verify-outputs-rule.md)
§7 (the manifest must read the LIVE `regions.json`/`paint.png`, never a cached snapshot).
