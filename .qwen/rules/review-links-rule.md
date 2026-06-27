---
name: "review-links-rule"
id: "review-links-01"
description: "Every working response that produced or changed something openable must end with a Review: section of clickable links (files, served pages, deliverables, commits) — re-give the link every turn you touch the artifact, no exceptions."
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

# End every working response with a Review section of clickable links

Whenever a response involved **producing or changing something the user might want to
open** — edited/created files, a served page, a generated image/video, a committed
change, a deliverable in `~/Desktop/cc-<project>/` — **finish the message with a short
`Review:` section at the bottom that lists clickable links to each of those things.**
The user asked for this directly (skeuo-ui, 2026-06): "always provide links at bottom to
what you worked on so i can review."

This is a **consolidated index for review**, distinct from links you drop inline while
explaining. Even if a path appears in the prose above, repeat it in the bottom section so
there is one obvious place to click and review everything the turn touched.

> **BINDING — NO EXCEPTIONS, EVERY TURN.** If the turn produced or changed *anything
> openable* — most especially a **served page / lookdev studio / dev server** — the
> message is INCOMPLETE until it ends with a clickable link to it. Before you send, re-read
> your draft and confirm the link is there; a turn without it is a FAILURE, not a stylistic
> miss. This has been violated repeatedly and the user is angry about it.
>
> **This applies on EVERY turn, including iterative follow-ups on the SAME artifact.** "I
> gave the link two turns ago" is NOT an excuse — the user is reviewing *now*, scrolled to
> *this* message, and must be able to click from here. Re-give the served-page/studio URL
> at the bottom of **every** turn you touch it, even if nothing about the URL changed.
> Updating a studio's contents and not re-surfacing its link is the exact, repeated failure.

## What goes in the section

- **Files you created or edited** → `file://` links (absolute path). For a set, link the
  containing folder.
- **A running dev server / served page** → its reachable `http://localhost:<port>/…` (or
  `.local`/`.ts.net`) URL — the live thing to look at, not a screenshot of it.
- **Deliverables / generated media** → the `file://` to the artifact in
  `~/Desktop/cc-<project>/` (these are the user's review inbox).
- **Commits / PRs** → the short SHA (and message) or the PR URL, when work was committed.

Keep it tight — a few labeled links, not every file mechanically. Link the things worth
*reviewing*, grouped if many (e.g. "3 edited components → repo folder").

## Mechanics & when to skip

- Clickability rules (absolute `file:///`, URL-encoding, `file://` to open vs agent-run
  `open -R` to reveal, and the binding rule that every `SendUserFile` is paired with a
  link) live in [[terminal-file-links-rule]] — this rule says *always surface the review
  index at the bottom*; that rule says *how to make each link work*.
- **Skip only when there is genuinely nothing to review** — a pure-conversation answer, a
  question, a quick status with no artifact. The moment the turn changed a file, served a
  page, generated media, or committed, the bottom `Review:` section is expected.
- For **human review of a live/interactive result**, prefer the served-page link over a
  static PNG ([[review-in-browser-rule]]); the bottom section is where that link goes.
