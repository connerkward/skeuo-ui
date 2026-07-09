# "Fix the skin" ALWAYS means a generalizable pipeline fix — never a per-skin patch

When the user asks to **fix a skin** — or fix any generated output of the skin-generation loop
(a bad slider throw, a misaligned switch, a missing button, wrong icons, residue, a socket that
isn't empty, a mask that doesn't align, a part rendered side-view instead of top-down, etc.) —
the fix must be made **in the shared, parameterized pipeline so it improves EVERY skin and every
future generation**, not hand-patched into one skin's assets.

This is the skin-loop instance of [[placement-invariants-rule]]'s "compute, don't hand-author"
and of `discover-before-building` / `restraint` (don't ship a worse one-off): a manual tweak to
`assets-<id>/regions.json` or a one-skin asset edit is the anti-pattern — it fixes the symptom on
one skin while the next generation reproduces the bug.

## Where a fix belongs (the shared pipeline in `tools/mask-align-exp/gen12/`)

- **Generation defect** (residue, non-empty socket, kept guide ring, baked text, side-view strip
  part, model rearranged/rescaled the layout, wrong/duplicate icon) → strengthen the **prompt
  clauses in `genskin.py`** (they are shared by all themes). Verify the clause helps across seeds,
  not just one roll.
- **Detection/alignment defect** (knob centre off, slider travel over/undershoots the groove,
  switch states jump, region missed, mask blob flooded) → fix the **algorithm in `extract12.py`**
  (or `biref12.py`) so it's material-agnostic and correct for the whole roster. Examples already
  in-tree: matte-hole-centroid seat centring, coverage-span travel with a groove-bbox clamp,
  silhouette-IoU state registration, template-fallback for an omitted control.
- **Rendering/interaction defect** (part seats wrong, toggle misapplies its transform, missing
  control) → fix **`build_player.py`** (the one template all skins render through).
- A control the model omitted in **templated** mode → recover it from the authored template
  (fallback), don't paint it in by hand.

## The test before you call a skin fixed

"Did I change the shared pipeline (prompt/algorithm/player), so re-running it — and every OTHER
skin — gets this fix for free? Or did I patch one skin's output?" If it's a per-skin patch, it's
not done. Regenerate the affected skin(s) through the fixed pipeline and verify the fix holds
across seeds/themes, per [[verify-outputs-rule]] (real runtime) and [[verify-external-claims-rule]].

The only legitimate per-skin action is **choosing a seed** or **re-rolling a failed generation** —
that's selection, not a hand-fix. Everything else generalizes.
