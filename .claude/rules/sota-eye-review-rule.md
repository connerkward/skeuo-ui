# Skin review requires a SOTA eye — sub-Opus agents must call one via API

Project rule (user directive 2026-07-10). Companion to [[skin-observation-rule]]: that rule
says a skin is done only when directly observed; THIS rule says **who** is qualified to do
the observing.

**The requirement:** the visual judgment on any finished skin (base player, PBR player, any
variant — the screenshot + per-control crops pass) must be made by a **SOTA-class model**:

- If the executing agent IS SOTA-class (**Opus / Fable** tier) → its own eyes qualify.
- If the executing agent is below that (**Sonnet, Haiku, or any smaller model**) → it MUST
  route the review through an API call to a SOTA vision model and act on that verdict:
  **Gemini SOTA** (via fal `openrouter/router/vision` ~$0.01–0.03/call, or Vertex direct)
  or **Claude Opus/Fable** via the Anthropic API. Its own weaker look does not qualify as
  the final observation — 2026-07-10 shipped two visibly broken PBR players (blown-white
  glass, unloaded sprites, misplaced switch) past a sub-SOTA agent's "looks fine".

**How:**
- Send the full screenshot AND the per-control close-up crops with a targeted per-control
  prompt ("for each named control: SEATED-CORRECTLY or BROKEN, with what's wrong; note
  exposure blowouts, missing sprites, misplacement; end VERDICT: PASS/FAIL"). State designed
  asymmetries so they aren't false-flagged.
- **Adjudicate per [[verify-outputs-rule]]**: the VLM is a witness, not a judge, on ±px
  geometry — cross-check precise-placement claims against deterministic measurement. But its
  PASS/FAIL on whole-part errors (missing cap, blown screen, wrong-place switch) is the
  load-bearing review for a sub-SOTA agent.
- **Record which eye reviewed it** (model id) alongside the verdict, per
  [[media-attribution-rule]]'s spirit — an unattributed "verified" is unauditable.

Orchestrators: when spawning sub-SOTA agents to finish/verify skins, put this requirement in
the agent's prompt explicitly.

## Crop discipline

A tight crop is only evidence of what it actually contains. Anchor it wrong and the VLM
confidently judges empty space or the wrong control — it has no way to know the crop missed.
Every VLM review call in this pipeline (observe12.py, and any future eye/judge script) must:

- **(a) Always attach the FULL FRAME.** Every call sends the whole rendered screenshot(s)
  (before + after interaction) alongside any crops — never crops-only. The full frame is the
  ground truth the VLM can fall back on when a crop is wrong; crops are a supplement for
  precision, never the sole evidence for a control.
- **(b) Anchor crops on DETECTED positions, never template-expected ones.** Crop boxes come
  from measured output (`regions.json` device rects post-extraction/alignment), not from the
  authored template's expected layout. Whenever layout drift is possible — which is always,
  post-generation — a template-anchored crop can miss the control entirely while a
  detection-anchored crop degrades gracefully (still centered near where the thing actually is).
- **(c) Pad wide — ≥2x the control's own extent.** A tight crop makes mis-anchoring invisible
  (the VLM sees only the wrong content, filling the frame, and judges it as if it were right).
  A wide pad makes mis-anchoring visible: if the control drifted, the padded crop still shows
  it nearby, or shows enough surrounding context for the VLM to notice something's off.
- **(d) The prompt must license CROP-MISS.** Every VLM prompt sending crops must instruct: "if
  a crop does not clearly contain the named control, say CROP-MISS for that control — do not
  judge what isn't there." Without this instruction the model defaults to judging whatever is
  in the frame, confidently, as if it were the named thing.
- **(e) A returned CROP-MISS is UNMEASURED, not FAIL.** A crop miss is a harness failure (bad
  anchor), not evidence the control is broken — don't let it silently count against the skin.
  Surface it distinctly so a human (or a re-anchored retry) can resolve it.

**Failure anchors (dated 2026-07-11):**
- `knobticks/` batch, skin `steam-porthole-ticks01-402`: the knob was displaced from its
  template socket by layout drift (template crop location contained the button row instead);
  the VLM was sent a template-anchored crop, judged the buttons as if they were the knob, and
  returned RELIABLE — while its own per-field answer ("pointer-notch visible?") was already
  "no." Adjudication caught it only because a human re-cropped from the real paint and looked.
- knob-angle detector: measured spurious noise as the "indicator mark" on 4 of 7 generations
  because the detection window was sized/anchored off the template's expected cap geometry
  rather than the sprite's actual detected extent, picking up unrelated texture instead of
  the real pointer.
