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
