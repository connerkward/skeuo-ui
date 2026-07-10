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
