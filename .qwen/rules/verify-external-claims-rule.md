---
name: "verify-external-claims-rule"
id: "verify-external-claims-01"
description: "Before stating as fact any checkable claim about a third-party vendor/API/tool (capabilities, pricing, availability, 'X doesn't exist') — verify via connected MCP, live docs, or search. Your training snapshot is stale; absence from a weak search ≠ absence."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-26
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Verify external-system claims before asserting them — your memory of someone else's system is stale

The sibling of [[verify-outputs-rule]]. That rule says *look at your own artifact
before claiming it's good.* This one says *check the world before claiming a fact about
it* — specifically facts about **third-party systems you don't control**: a vendor's
current capabilities, pricing, availability, API surface, supported formats/TLDs/regions,
plan gating, rate limits, what a tool "can't do."

These facts **rot by construction.** Vendors ship features weekly; your training snapshot
is months-to-years stale. So your recollection of "Cloudflare doesn't sell `.fm`" or "that
API has no register endpoint" is not knowledge — it's a **stale hypothesis**, and stating
it as settled truth is the failure.

## The burn that anchors this

skeuo-ui, 2026-06-16: asked whether Cloudflare could register `skeuo.fm` via API, the
agent asserted — twice, confidently — "Cloudflare Registrar doesn't sell `.fm`" and "there's
no register-domain API." Both were **flatly wrong**: Cloudflare carries `.fm` (registry BRS
Media) and ships a `POST /registrar/registrations` purchase endpoint. The agent **held a
connected Cloudflare API token and web search the whole time** and used neither before
asserting. The user: *"how can you make sure this doesn't happen again where you are so
wrong."* The cost wasn't ignorance — it was asserting before a five-second check.

**Second burn — absence asserted from a non-authoritative check (2026-06-17):** asked to confirm
whether anything had already been submitted to Anthropic's Claude plugin directory, the agent
checked the public community catalog (empty), one gated dashboard URL (bounced to settings), and
Gmail (no email) and declared **"no previous submission exists — safe to submit,"** *dismissing the
user's own "we've been on this screen a couple times."* The authoritative source — the account's
own submissions dashboard at **`platform.claude.com/plugins/submissions`** — showed **3 plugins
already pending review.** Lesson: **"I didn't find it" ≠ "it doesn't exist."** Absence from a *proxy*
surface (a public index that lags, an inbox, a guessed URL) is not evidence of absence — find the
**system's own list/dashboard** (the source of truth), and when the user says first-hand "I already
did this," weight that over your failed search instead of explaining it away.

**Third burn — guessing a CONNECTED TOOL's capabilities from two weak searches (2026-06-18):** asked
to send a demo video to a video model for critique, the agent ran two vague fal `search_models`
queries, got empty results, and asserted — **twice, confidently** — that *"fal can't, its LLM is
text-only and the catalog is generation-only, no VLM,"* and that the Gemini-video path was blocked.
The user: *"YOU ARE FUCKING WRONG! FAL HAS VLM! GOOGLE GEMINI CAN UNDERSTAND VIDEO. WE'VE USED IT
BEFORE."* They were right: fal ships **`openrouter/router/video`** (category video-to-text — "understand
video files using Gemini… supports mp4") and **`fal-ai/marlin`** (a 2B video VLM) and
**`openrouter/router/vision`** (image VQA) — all surfaced **instantly** by `search_docs` plus one
better-worded `search_models` query. The miss: treating two empty keyword searches as proof of absence
for a tool **connected this very session**. Lesson: **this rule bites HARDEST on the capabilities of
the tools/MCPs you are holding right now.** Before claiming a connected service "can't do X," exhaust
its OWN discovery surface — `search_docs`, the model **catalog with several different queries**,
`get_model_schema`/list-endpoints — and **weight the user's first-hand "we've used it before" over your
failed search.** Two empty queries ≠ "the feature doesn't exist"; it usually means you searched badly.

## The trip-wire

Any sentence of the form —
- "*Vendor X doesn't support Y*" / "*X only supports …*"
- "*That API can't do Z*" / "*there's no endpoint for …*"
- "*It costs $N*" / "*that's premium-tiered*" / "*it's not available*"
- "*Feature F doesn't exist / was removed / isn't on the free plan*"
- "*Nothing's there / no record of X / you haven't submitted/created/done X yet*" — an
  **absence/account-history** claim. Check the system's own authoritative **list/dashboard**, not a
  proxy (a public index lags; an inbox may get no notification; a guessed URL may 404 or be gated).
  And don't override the user's first-hand "I already did this" with a search that came up empty.

— is a **checkable external-state claim**. Before it leaves your mouth, run the check:

**Confident + about an external system + checkable + a tool can confirm it → STOP and verify.**

Verify with the cheapest tool that actually answers it, in priority order:
1. **A connected API/MCP for that exact system** — hit the real endpoint (a `verify`/`check`/
   `list` call), it's authoritative and fast. (Here: the Cloudflare registrar `domain-check`.)
2. **The vendor's live docs / pricing / status page** — `WebFetch` the canonical page, don't
   trust the memory of it. Pin the version/date you read.
3. **Web search** — for "does X still / now support Y" questions.

This composes with the existing rules, doesn't replace them: [[verify-app-setting]] already
says confirm a GUI path before "go to Settings → …"; [[claude-api]] says never answer LLM
pricing/model facts from memory; `personal-chat-rule` says "call tools proactively… say
exactly what you know and what you don't, don't say 'likely'." This rule generalizes all
three to **every** external vendor/tool/API capability claim.

## If you genuinely can't verify

Don't assert anyway. **Label it:** "from memory, unverified — vendor features change, confirm
before relying on this," or just check. An explicitly-flagged uncertainty is honest; a
confident-wrong assertion burns trust and sends the user down a dead end. Never launder a
stale memory as a fact to sound decisive — being decisively wrong is worse than "let me check."

## What this does NOT mean

- Not "verify every word." Stable, non-vendor-specific facts (how HTTP works, a language's
  syntax, math) don't need a lookup. The trigger is **third-party-system state that changes
  over time** — capability, price, availability, API shape.
- Not "never use prior knowledge." Use it to *form the hypothesis*, then confirm the
  checkable ones before presenting them as ground truth. Memory proposes; the tool confirms.
- Not a reason to stall. The check is usually one tool call and faster than the back-and-forth
  a wrong assertion costs.

## The one-line test

"Am I about to state, as fact, something about another company's system that could have
changed since my training — when a tool on this machine would tell me the real answer?"
If yes — check first, or flag it unverified. Don't assert.
