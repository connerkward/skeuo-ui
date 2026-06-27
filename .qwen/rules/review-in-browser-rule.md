---
name: "review-in-browser-rule"
id: "review-in-browser-01"
description: "For human review in chat, show the live served browser page and hand over the URL — not a generated PNG contact sheet or montage. PNG only for archival/devlog or the listed exceptions."
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

# Human review → the browser, not a generated PNG

When the artifact is for the **user to review right now in chat** — a comparison, a
detection overlay, a set of variants, a "does this look right?" check — **show it
live in the browser and hand over the inline link**, don't render a static PNG and
`SendUserFile` it. Serving a page (or refreshing the `claude-in-chrome` tab) and
giving the clickable URL is **faster** (no render-encode-send round trip) and the
result is **interactive** — the user can flip detectors, drag a slider, zoom, scrub
— which a flat image can't do. This is the default. Reach for a PNG only when
there's a real reason (below).

**Why:** the review loop is the bottleneck in iterative work. A PNG is a dead end
the moment the user wants to see the next state — you regenerate and resend. A
served page updates in place and the user explores it themselves. The user called
this out directly (skeuo-ui, 2026-06): "for human review with those inline links in
chat, always use browser… it's faster."

## The split

- **Human review (live, in-chat) → browser.** Build the review as an HTML page
  (a lookdev studio, a comparison grid, an overlay viewer), serve it on a free port
  (`~/dev/central/scripts/serve <dir> --bg`), open/refresh the
  `claude-in-chrome` tab for the user's real browser, and give the clickable
  `http://localhost:<port>/…` link in the message. Per
  [[dev-server-chrome-tab-rule]] and [[terminal-file-links-rule]].
- **Documentation / portfolio / devlog → PNG (and other static artifacts).**
  Anything meant to be *archived* rather than *reacted to right now* — a devlog
  entry, a case-study figure, a portfolio shot, a design-doc diagram, a README
  image, a proactive "here's the finished thing" while the user is away — render
  the PNG and put it in `~/Desktop/cc-<project>/` per [[file-output-rule]]. Bias
  toward **producing these freely** as you work (they're cheap now, expensive to
  recreate later) — just don't make them the *review* medium.

## Contact sheets / spreads / grids → ALWAYS a web page, NEVER a montage PNG

A **contact sheet** (a grid/spread of many variants, crops, mockups, candidates for
the user to scan and compare) is the single worst thing to ship as a flat PNG, and the
user has said so directly: *"i don't want to see png contact sheets anymore, unless they
are an output from the web contact sheet / preview."* So, as a hard rule:

- **Build every contact sheet / spread / variant-grid / mockup-comparison as a served
  HTML page** — labeled cells, clickable to full-res, responsive — and hand over the live
  `http://localhost:<port>/…` link. Never assemble a montage/`magick montage`/screenshot-
  stitched PNG grid as the review artifact.
- **Do NOT reflexively screenshot the web sheet and paste the PNG back into chat.** Lead
  with the link; the user reviews in the browser. A screenshot of your own served sheet is
  not a substitute for the link — it's the exact habit being called out.
- **PNGs are allowed ONLY as an *output* of the web sheet**, never as the sheet itself.
  Legitimate PNG outputs: (a) the individual baked **deliverable assets** the sheet
  displays (e.g. the actual share-ready chart PNGs), filed to `~/Desktop/cc-<project>/`;
  (b) an export the **user explicitly triggers** from the page ("download this view"); (c)
  the documentation/archival snapshot covered in "The split" above, for a finished thing
  meant to be archived — not reviewed-right-now. If a PNG is standing in for "here, scan
  these options," it's wrong; serve the page.
- Embed mockups/device-frames/in-context views **inside that same web sheet** (CSS frames),
  so "show it at real size / in context" is a section of the live page, not a separate PNG.

This composes with `verify-outputs-rule` §6 (a thumbnail grid is an index, not inspection —
open individual full-res items): the web sheet *is* that index, and its cells link to the
full-res artifacts, satisfying both rules at once.

## "Almost always" — the good-reason exceptions (PNG for review is fine when)

- **No page exists and standing one up costs more than a screenshot** — a one-off
  glance where building/serving an HTML viewer is overkill for a single static frame.
- **A frozen, exact comparison** the user needs to mark up or keep side-by-side — a
  precise pixel diff, a before/after they'll annotate, an A/B they want pinned.
- **The state is transient / hard to reproduce live** — a captured moment, a crash
  frame, a render that took minutes to produce.
- **The user is away from the machine** — a proactive push where a phone-visible
  image chip beats a localhost link they can't open (see `SendUserFile` `proactive`).
- **The thing isn't web-renderable** — a native-app screenshot, a 3D viewport grab.

When you do send a PNG for review, still give the clickable `file://` link
([[terminal-file-links-rule]]).

## The reflex

Before you `SendUserFile` a freshly-rendered PNG for the user to react to, ask:
*could this be a served page they'd explore instead?* If yes and there's no
good-reason exception — serve it, open the tab, link it. Default to the browser.
