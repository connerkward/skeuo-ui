# A skin is not "done" until you have OBSERVED it directly

Project rule (user directive 2026-07-10). Before declaring any skin — base player, PBR
player, any variant — done / verified / linked from the dashboard, you MUST open the real
served page and **look at the rendered result with your eyes**: a full screenshot AND
per-control close-up crops (knob, seek + thumb, switch both states, buttons pressed,
screens/visualizer), viewed and judged against the paint.

**What does NOT count as observation** (each of these passed while shipped players were
visibly broken on 2026-07-10 — blown-white screens, missing knob caps, misplaced switches,
emissive splatter):
- "zero console errors" / "no failed requests" — a page can render garbage with a clean console;
- "canvas is not blank" / "render exists";
- an emissive-coverage or any other metric;
- the base player looking fine (each variant is its own artifact).

**The check**: for every control, can you see the correct sprite, at the correct place, at
sane exposure, and does it respond to its interaction (drag the knob/thumb, click the
switch)? If you didn't look at the crop, you didn't verify it. Broken → fix or withhold the
link; never ship a card link to a player you haven't watched work.

This is the skin-pipeline sharpening of [[verify-outputs-rule]] §1/§7 and the two-stage
close-up discipline in [[placement-invariants-rule]] §2 — those already demanded this;
this rule exists because a "live verification" that skipped the *looking* still slipped
through. Related: [[label-overlays-rule]], [[fix-generalizable-rule]] (the fix, once
observed, still lands in the shared pipeline).
