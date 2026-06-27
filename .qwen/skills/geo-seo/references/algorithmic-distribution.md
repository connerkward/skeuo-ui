# Algorithmic distribution — per-platform pickup, virality, engagement, tagging

Detail for SKILL.md §10. SEO/GEO get a thing found *when someone searches*; this is how
the **spokes** get *surfaced to people who weren't looking* by recommendation feeds, and
shared by humans. The universal mechanic: **feeds test on a small seed audience and
expand only if early-engagement velocity beats a threshold.** Win the seed test (first
minutes-to-hour), then the algorithm does the spreading.

## The signal hierarchy (what feeds actually weight)

Roughly high→low, shared across platforms:

1. **Shares / sends / reposts** — redistribution; the strongest signal a thing has value.
2. **Saves / bookmarks** — "I'll come back to this"; near-share weight, esp. IG/TikTok/X.
3. **Completion / watch-time / dwell** — finished the video, read to the end, lingered.
4. **Replies / comments** (esp. ones you reply back to → live thread) — discussion depth.
5. **Likes / reactions** — weakest; cheap, low intent. A like-only post rarely expands.

Design every post to earn the *top* of this list, not the bottom. "Got 200 likes, no
shares" is an algorithmic dead end and poisons the next post's seed test.

## Virality frameworks worth naming

- **Jonah Berger — STEPPS** (*Contagious*, 2013): Social currency (sharer looks
  smart/in-the-know), Triggers (recurring cue that re-surfaces it), Emotion
  (high-arousal — awe, anger, delight; **not** sadness/contentment, which don't drive
  sharing), Public (visible/imitable), Practical value (useful enough to pass on),
  Stories (rides in a narrative). Run a post against all six; if it hits none, it won't
  spread no matter the reach.
- **Nir Eyal — Hooked** (trigger → action → variable reward → investment): for products
  and accounts, the loop that builds *returning* engagement, which feeds read as account
  quality.
- **High-arousal-emotion finding** (Berger & Milkman, 2012, *JMR*, NYT most-emailed
  study): awe and anger drive sharing; sadness suppresses it. Pick the emotion deliberately.

## Per-platform cheat sheet

| Platform | Master signal | Tagging | Notes |
|---|---|---|---|
| **TikTok / Reels / Shorts** | completion rate + rewatch + share | 3–5 specific hashtags, mix niche+broad; trending audio is a ranking input | Hook in 0–2s or they swipe. Native upload only; no visible external link. Vertical, captions baked in. |
| **X / Twitter** | replies + reposts + dwell; reply-engagement in first ~30min | 0–2 hashtags max (more = throttled); `@`-mention people you cite | Links suppress reach — put link in a *reply*, not the main post. Thread for dwell. Post when your audience is on. |
| **Reddit** | upvote velocity in first 1–2h + comment depth | flair + correct subreddit (the "tag" that routes it) | Read the sub's rules; value-first, no naked promo. A genuine post is also a high-weight GEO source (SKILL §8). Title is the whole hook. |
| **Hacker News** | upvotes in first 1–2h on /newest | `Show HN:` / `Ask HN:` prefix is the tag | Title = literal + specific, no hype words. Don't ask for upvotes (auto-penalized). First comment from OP with context helps. |
| **LinkedIn** | dwell + comments + reshares; early-hour engagement | 3–5 professional hashtags | Hook line before the "…more" fold. Native > link (link in comments). |
| **YouTube** | watch-time + click-through-rate on thumbnail/title + session time | tags + keyword-rich description + chapters | Thumbnail+title is the seed test. Transcript/description doubles as GEO/SEO. |
| **Instagram** | saves + sends + reach-from-non-followers | up to ~5 relevant tags; alt text | Carousels for saves; Reels for reach. First frame is the hook. |

## The first-hour playbook (do this every post)

1. **Post at your audience's active time** — not when *you* finish writing it.
2. **Reply to every comment fast** for the first hour — your replies are engagement and
   keep the thread "live"; feeds read this as velocity.
3. **Seed genuine early engagement** — drop it in the relevant Discord/group chat, DM a
   few people who'll actually care. Not a pod, not "like-for-like" — real interested humans.
4. **Watch the first ~30–60min**; if it's moving, a follow-up reply / quote-post can
   re-trigger the expansion. If it's flat, learn and let it go — don't bait.

## Tagging principles (applies everywhere)

- **Tags = routing instructions**, telling the feed which audience to seed-test on.
  Specific real-community tags beat broad generic ones (`#skeuomorphism #uidesign` >
  `#design`). Relevance over volume.
- **`@`-mentions are reach multipliers** — a mentioned account/person may reshare to a
  fresh audience. Only mention what you genuinely reference (false mentions read as spam).
- **Fill every machine field**: video alt text, topic/category dropdowns, YouTube tags,
  image alt — these route *and* feed GEO/SEO (SKILL §8).
- **Over-tagging is throttled** as spam on every platform. A few precise tags, not a wall.

## Anti-patterns (reach-throttled or trust-burning)

- Engagement-bait ("comment YES to get the link", "tag 3 friends") — pattern-detected,
  demoted, and the hollow signal (views without saves) tanks your *next* post.
- Follow-loops / engagement pods / bought engagement — detected; the off-distribution
  (high views, ~0 genuine shares) is itself a negative signal.
- Posting the same link-out with no native substance — feeds demote off-platform sends.
- Reposting identical content cross-platform with no per-platform reshape — see [[crosspost]]
  for the reshape-per-platform discipline (entity name/definition stays constant per
  SKILL §2; hook, length, format, tags change).
- Faking velocity instead of earning it — every shortcut here degrades the account's
  long-run seed-test baseline, which is the asset that actually compounds.
