---
name: "end-with-web-preview-rule"
id: "end-with-web-preview-01"
description: "When a task produced or changed anything viewable in a browser, the operation is NOT finished until you stand up (or refresh) a live web preview, open it in the user's Chrome tab, and hand over clickable URL(s) at the bottom — every turn, including follow-ups."
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

# Always END a web operation with a live web-based preview

When a task produced or changed anything **viewable in a browser** — a web app/page,
a component, a studio, a lookdev, a chart, a served artifact — the operation is **not
finished until you stand up (or refresh) a live web preview and hand over its clickable
URL.** Don't end on a bare "done," a static screenshot, or only a code summary. The
human reviews in the browser; closing the loop there is part of the deliverable, not an
optional follow-up.

This is the always-on default the user asked for directly (skeuo-ui, 2026-06): *"should
always end operation with web based preview."* It generalizes the existing review rules
from "prefer the browser" to "**finish there, every time.**"

## What "end with a preview" means

- **Serve it and open it in the user's real Chrome tab.** Start/confirm the dev server
  (or `~/dev/central/scripts/serve <dir> --bg` for static), open the reachable URL in
  its dedicated `claude-in-chrome` tab so the user sees the running result live — per
  [[dev-server-chrome-tab-rule]]. One tab per server; refresh it on follow-ups.
- **Give the clickable link(s) at the bottom of the message** — the live
  `http://localhost:<port>/…` URL, plus the device-reachable `.local` / tailnet URLs
  when the user might view on a phone ([[dev-server-network-rule]]). This is the
  `Review:` section [[review-links-rule]] already requires; the live preview link is
  the headline of it.
- **Prefer the live page over a PNG.** A served page is faster and interactive; reach
  for a static image only for the good-reason exceptions in [[review-in-browser-rule]]
  (frozen A/B, transient state, user away from the machine, non-web-renderable).

## The reflex before you end the turn

*Did this turn change something a browser can show? → Is it served, open in the Chrome
tab, and linked at the bottom right now?* If not, do that before sending. **Re-surface
the preview link on EVERY turn that touches the artifact**, even iterative follow-ups
where the URL didn't change — "I linked it earlier" is not an exception
([[review-links-rule]]).

## When this does NOT apply

Pure-conversation answers, questions, non-web work (a CLI tool, a data file, a native
app), or a turn that produced nothing openable. The trigger is **a web-previewable
result existing** — then finishing in the browser is mandatory, not a nicety.

Related mechanics (this rule sets the *default*; those own the *how*):
[[dev-server-chrome-tab-rule]], [[review-in-browser-rule]], [[review-links-rule]],
[[dev-server-network-rule]], [[terminal-file-links-rule]].
