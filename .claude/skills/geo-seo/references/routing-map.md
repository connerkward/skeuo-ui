# Content-type → canonical → spokes — routing map

**This is guidance, not a mandate.** The actual routing decision (which spokes, which
subs, which accounts) is left to the calling agent and the user's review gate in
`devlog`. Use this to default sensibly, not to auto-blast everywhere.

Two rules underpin every row (SKILL.md §1–2):
1. The **canonical** is published FIRST and is the link every spoke points to.
2. The **entity name + one-line definition** are identical across all spokes.

| Content type | Canonical home (own/durable) | Typical spokes | GEO notes |
|---|---|---|---|
| **Dev / code** | GitHub repo README | HN (Show HN), relevant subreddit, MCP/tool registries (glama, mcp.so, smithery), Twitter, Discord | README is BOTH canonical and a heavily-cited crawled source — make its H1 the entity name with the definition line under it. Reddit answers cite well. |
| **Visual stills** (renders, design, photography) | Own portfolio page | Twitter/X, Instagram, relevant subs (r/design etc.), Are.na / Cosmos | Add `CreativeWork`/`ImageObject` JSON-LD + alt text. Pages, not just image silos — silos aren't crawlable as yours. |
| **Motion / video** | YouTube (with real transcript) + own embed page | Twitter, Reddit, IG Reels / TikTok (vertical 9:16) | YouTube transcript is the GEO asset — write/clean it. `VideoObject` JSON-LD with `transcript`. Vertical cut for phone-first spokes (see `screenstudio-alt`). |
| **Writing / essay** | Own-domain blog post | HN, relevant subreddit, Medium/Substack mirror with `rel=canonical`, Twitter thread | `BlogPosting` JSON-LD; definition sentence under H1; FAQ block. Mirrors MUST set canonical to the owned URL. |
| **Portfolio / process** (case study, build log) | Own portfolio page | Twitter thread, relevant subs, Cosmos / Are.na | Process narratives get cited when the entity+definition is stated up front, not buried in story. |
| **Product / launch** | Own landing page | Product Hunt, HN, relevant subs, registries, Twitter | `SoftwareApplication` or `Product` JSON-LD; landing H1 = product name + definition; FAQ for objections. |

## Where discovery actually originates (engine vs amplifier)

Within a bucket's spokes, one or two are the *discovery engine* (algorithmic /
non-follower reach); the rest amplify to people who already follow you. Lead with
the engine, then amplify.

- **Dev** → HN, Reddit, Lobsters (community/search discovery). Twitter, Discord amplify.
- **Visual stills** → Instagram, Pinterest (visual search). Twitter/X amplifies.
- **Motion / video** → Reels / TikTok / YouTube Shorts (algorithmic, non-follower) —
  the **single highest-reach surface for non-dev work**; vertical 9:16 is the format
  (see `screenstudio-alt`). YouTube long-form + X amplify.
- **Writing** → HN + Reddit for discovery; X thread amplifies.
- **Feed posts** (Instagram feed, LinkedIn) mostly reach *existing* followers — they
  are amplifiers, not engines. Don't mistake a feed post for discovery.

## The disproportionately-cited spokes (SKILL.md §8)

Regardless of content type, these three carry GEO weight beyond their click-through —
prioritize a *genuine, on-topic, entity-naming* presence on them when the piece
warrants it:

- **Reddit** — Google content deal + heavy LLM grounding. A real answer that names
  the entity and links the canonical.
- **GitHub README** — most-ingested doc surface for code. Clean structure, entity H1.
- **YouTube transcript** — indexed and cited. A clean transcript stating the
  definition turns a video into a text-citable GEO asset.

## Anti-pattern

Auto-syndicating identical full text to every silo with no canonical and no
`rel=canonical` on the mirrors → duplicate-content dilution and no clear original.
Always: one canonical first, spokes link back, mirrors self-demote.
