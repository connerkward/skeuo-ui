---
name: devlog
description: Auto-document recent work into platform-ready announcement drafts and get explicit human approval BEFORE cross-posting. Use when the user wants to share/announce/post about what was built ("announce this", "post about this", "share on twitter/reddit/discord", "write it up"), or offer it proactively right after a ship-worthy milestone (public repo published, release cut, demo recorded). Drafting and review live here; posting mechanics live in crosspost.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Devlog — document work, review, then crosspost

Pipeline: **gather → draft → human review gate → post → log**. The review gate is
the point of this skill: NOTHING is posted without explicit per-platform approval.

## 1. Gather evidence

Collect what actually shipped — don't write from memory:

- `git log` since the last announcement (or since branch/tag) in the relevant repo(s)
- Public repo README(s) if the work was published — reuse their framing/value prop
- Media: check `~/ideas-syncthing/proj-dailies/` for matching-slug captures (dailies
  skill), repo `docs/` screenshots/demos. Announcements with media outperform text.
  **Judge candidates before attaching**: open each candidate (or a frame strip) and
  pick the sharp/complete/representative one — never attach the most recent blindly.
  For social platforms prefer the `-vertical.mp4` (9:16) variant when one exists;
  `screencast.sh --demo` produces both (see `screenstudio-alt`).
- The session itself: what was the user-visible outcome, in one sentence?

## 2. Draft per platform

Load the `crosspost` skill and its `platforms/<platform>.md`
docs — each platform has its own tone/format/length rules. Draft per platform, not
one blob: an HN "Show HN" is not a tweet is not a Discord drop. Lead with the
problem solved, not the tech. Include links + attached media per platform norms.

**Voice — kill the LLM tells.** Auto-drafted copy (and any blog/write-up the agent
generates) reads like a machine by default; rewrite it to sound like a person *before*
the review gate. Cut: bold-fragment listicles, emoji bullets (✓ / 🚫 / 🎯), the
rule-of-three on every sentence, scaffolding phrases ("Here's the thing", "It turns
out", "Let's dive in"), the parenthetical "(lol)" wink, and em-dash overuse. Replace
with: first person, **varied sentence length** (some short; some longer and winding),
and **concrete specifics over tidy parallelism** — the actual username, the exact
error text, the real number, the embarrassing detail. A reader can smell generated
prose; rhythm and specificity are what it can't fake. (This is the publishing-voice
companion to [[anti-sycophancy-rule]], which governs the agent's *own* chat tone — a
different surface: chat is terse-machine, a blog post is a human narrator.)

**Apply [[geo-seo]] while drafting:** publish the owned canonical FIRST (repo
README / blog page) so every spoke links to a live URL, and keep the SAME entity
name + one-line "X is a Y that does Z" definition across all drafts — consistent
cross-posting is itself the GEO/AI-citation lever, not just reach.

## 3. Review gate (mandatory, no exceptions)

Present every draft VERBATIM — full text, target account/subreddit/channel, and the
exact media files (clickable `file://` links) — then ask for approval **per platform**
(A/B/C letters). Silence, ambiguity, or "looks good" without platform selection is
NOT approval to post everywhere; re-ask. Apply edits and re-show changed drafts.
Never post a draft the user hasn't seen in its final form.

## 4. Post + report + log

Post approved drafts via crosspost mechanics. **Platforms without safe API posting
(LinkedIn, Instagram, TikTok) get STAGED instead**: write each approved draft to
`~/Desktop/<date>-devlog-staged/<platform>/` as `caption.txt` + the final media in
the right aspect (vertical for phone-first platforms), ready to drag into the app.
Staging counts as "posted" for the log. Report each live URL. Append a line to
the repo's `ANNOUNCEMENTS.md` (create if missing): date, platforms, URLs, one-line
summary — this is what "since the last announcement" in step 1 reads, and it prevents
double-announcing the same work.
