---
name: geo-seo
description: Canonical guidance for getting PUBLIC-FACING content SEEN, PICKED UP, AND CITED — the single source of truth for the whole discoverability stack: classic SEO, GEO (Generative Engine Optimization / AI-citation), AND algorithmic distribution (virality, recommendation-feed pickup, engagement-building, tagging/hashtags). Treat "geo", "seo", and "virality" as ONE umbrella — the user uses them interchangeably; any one of them triggers this skill and the full stack applies. Use WHENEVER you publish, announce, syndicate, or cross-post anything public (a blog/portfolio page, README, devlog, project announcement, landing page, docs site, social thread, short-form video, tweet/X thread, Reddit/HN post), or set up structured data, llms.txt, canonical URLs, robots/crawler rules, schema.org JSON-LD, hashtags/tags, a posting/engagement plan, or a shareable chart/diagram/data-viz/infographic meant to be reposted or embedded elsewhere. Trigger even when the user just says "post this", "announce", "share on X/Reddit/HN/TikTok", "write it up", "make this rank", "make it go viral", "get this seen", "blow this up", "get picked up by the algorithm", "build engagement", "get reach", "what hashtags/tags", or "get cited by ChatGPT/Perplexity/AI Overviews" — discoverability and distribution are in scope even when SEO/GEO/virality is never named. Other skills (devlog, crosspost, design, docs) POINT HERE rather than duplicating.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# geo-seo — own-canonical, structured, corroborated, distributed

**"geo", "seo", and "virality" are ONE umbrella here** — the same job of *getting a
thing seen and picked up*, viewed from three angles. The shared lever: **one owned
canonical home per piece, formatted for machine extraction, corroborated across many
crawlable sources that link back to it — then actively pushed into the feeds and
algorithms where humans actually discover it.** The first three angles share the
canonical+corroboration work; the fourth (distribution) is how the spokes earn reach
instead of rotting unseen. Don't treat them as separate efforts.

- **SEO (classic):** rank a URL in search results. Lever: a crawlable, fast,
  well-structured canonical page with real backlinks.
- **GEO (Generative Engine Optimization):** get your entity *named and cited* inside
  AI answers (ChatGPT, Claude, Perplexity, Google AI Overviews/Gemini). Lever: a
  consistently-described entity, anchored to one canonical, corroborated across many
  sources the models crawl.
- **Algorithmic distribution / virality:** get the content *surfaced and spread* by
  recommendation feeds (TikTok/Reels/Shorts FYP, X/Twitter, Reddit, HN, LinkedIn) and
  by humans sharing it. Lever: a hook that earns early-engagement velocity, a built-in
  share trigger, correct tagging, and seeded engagement in the first hour. **§10.**

The first three are won by the four moves below; the fourth is §10.

## Standard — a GEO/SEO pass is the DEFAULT before anything ships to the public internet

**This is not opt-in.** Any artifact going onto the public web gets a GEO/SEO metadata
pass as a standard step of publishing — a blog post, portfolio/landing page, public repo
README, docs site, devlog, a syndicated thread. Treat "ship it" as *incomplete* until the
pass is done, the same way a web UI isn't done until the overflow gate passes.

**The only exception: a private service / internal tool / gated artifact** — something not
meant to be found or cited (an internal dashboard, a localhost studio, a passphrase-gated
page, a private repo). Those skip it (or get only the NDA-safe summary layer). When unsure
whether something is public, assume public and run the pass.

**The minimum pass (scale up per surface):**
- `rel=canonical` to the one owned home (§1); an answer-first lead sentence naming the entity (§3).
- `<title>` + meta description; OpenGraph + Twitter card (+ an OG image).
- schema.org JSON-LD (Person/ProfilePage/SoftwareApplication/BlogPosting/CreativeWork as fits) (§5).
- `llms.txt` / `llms-full.txt` where the site supports it; crawlable + fast (no JS-only content).
- **Claim hygiene** (see below): every factual claim cited or cut, verified independently.
- For repos: GEO topics + README H1 = entity + one-line definition (see `publish-skill`).

Where a pipeline already bakes this (e.g. the portfolio's `build-seo.py`, `publish-skill`
for repos), the standard is satisfied by running that pipeline — don't hand-roll a second.
The point is it *always happens*, automatically, before public.

## 1. POSSE + canonical-first (publish the hub before the spokes)

**POSSE** = Publish (on your) Own Site, Syndicate Elsewhere. Every piece has exactly
ONE owned canonical home:

- **Writing / project / portfolio process** → own-domain blog or portfolio page.
- **Code** → the GitHub repo (its README is the canonical).
- Never let a silo (Twitter, Medium, LinkedIn, a Reddit post) be the only home — you
  don't own it, it isn't durably crawlable as *yours*, and it can't carry your
  structured data.

**Order is load-bearing:** publish the canonical FIRST, get a live URL, THEN
syndicate. Every spoke (HN, Reddit, tweet, Discord, registry) links back to that live
canonical. A spoke that links to a 404 or a "coming soon" wastes the corroboration.

**Mirrors must self-demote:** any full-text copy on a silo that supports it sets
`<link rel="canonical" href="…the owned URL">` (Medium "import", canonical plugins).
This tells search engines the owned page is the original and prevents the mirror from
outranking it.

## 2. Entity consistency — the core GEO lever

AI engines cite **entities that are described the same way across many independent,
crawlable sources, all anchored to one canonical.** This is *why* disciplined
cross-posting is itself a GEO strategy, not just reach.

Across EVERY syndicated post, use:

- the **SAME entity name** (exact string — `mcp-apple-notes`, not "the Apple Notes
  MCP" in one place and "my notes tool" in another), and
- the **SAME one-line definition** in the canonical "**X is a Y that does Z**" shape
  — e.g. *"mcp-apple-notes is an MCP server that exports Apple Notes to Markdown."*

Vary the *surrounding* phrasing per platform (tone, length, hook) — but keep the
name + definition string identical so the corroboration is unambiguous. Models
resolve and trust an entity when its definition is consistent and repeated; they get
confused (and don't cite) when each source describes it differently.

→ Concrete per-platform example in
[references/entity-consistency.md](references/entity-consistency.md).

## 3. Page formatting for citation

Structure the canonical page so a model can lift the answer cleanly:

- **H1 = the entity name** (the exact string from §2).
- **One-sentence definition immediately under the H1** — the "X is a Y that does Z"
  line, before any preamble. This is the sentence most likely to be quoted.
- **A TLDR / FAQ section** near the top, in plain question→answer form.

Implement the TLDR/FAQ **twice, both legitimately visible-or-machine channels**:

1. **`FAQPage` JSON-LD** (machine-readable, in `<head>` or inline) — see §5.
2. **A genuinely visible section** on the page. A collapsible `<details>`/`<summary>`
   block is fine (collapsed-but-present is visible — the user can open it). The Q&A
   must exist in the rendered DOM for a human.

## 4. ANTI-CLOAKING — never hide text from humans to feed crawlers

**Cloaking = showing content to crawlers/AI that a human visitor cannot see.** It is
a search-penalty trigger (de-indexing, ranking demotion) and burns trust. Do NOT:

- put "AI-only" / keyword text behind `display:none`, `visibility:hidden`,
  `opacity:0`, `height:0`, off-screen positioning, or `hidden` attributes intending
  it to be read by crawlers but not humans;
- serve different content based on the user-agent being a bot.

`<details>` collapsed is **NOT** cloaking — it's in the DOM and the human can expand
it. The line: *if a human can reveal it through normal interaction, it's visible; if
it's engineered to be unreachable by a human yet present for a crawler, it's
cloaking.*

The two **legitimate** "rich for machines, light for humans" channels:

1. **JSON-LD structured data** — metadata that's *meant* to be machine-only and isn't
   pretending to be page copy. Not cloaking.
2. **Visible / collapsible sections** (`<details>`, tabs, accordions) — present for
   humans, just compact.

Use those. Never the hidden-text trick.

## 5. schema.org JSON-LD — pick the type that matches the thing

Embed as `<script type="application/ld+json">`. One block per entity; combine via
`@graph` when a page describes several. Which type:

| Type | Use for |
|------|---------|
| `Person` | An author/creator bio page or the author of an article (your identity entity). |
| `Article` / `BlogPosting` | A written post / devlog / essay (`BlogPosting` for blog-style). |
| `CreativeWork` | A generic creative artifact (a render, design, video, mixed media) with no more specific type. |
| `SoftwareApplication` / `SoftwareSourceCode` | A tool/app/library; pair with the GitHub repo. |
| `FAQPage` | The TLDR/FAQ Q&A (§3) — `mainEntity` is an array of `Question`→`acceptedAnswer`. |
| `BreadcrumbList` | Site hierarchy/navigation trail — helps engines understand structure. |

Copy-paste-ready JSON-LD for each →
[references/json-ld-snippets.md](references/json-ld-snippets.md).

## 6. llms.txt — the AI-reader's site map

`llms.txt` (Jeremy Howard / Answer.AI proposal, Sept 2024) is a Markdown file at the
site root (`https://yourdomain.com/llms.txt`) that gives LLMs a curated, low-noise
map of the site — the docs/pages worth reading, as links with one-line descriptions,
so a model isn't forced to crawl rendered HTML/nav/JS.

Format (Markdown, ordered):

```markdown
# Site / Project Name

> One-sentence summary of what this site/entity is (the §2 definition).

## Docs
- [Getting started](https://…/start.md): how to install and run X.
- [API reference](https://…/api.md): full endpoint list.

## Optional
- [Background](https://…/about.md): longer context, skippable.
```

`## Optional` marks links a model can skip under a tight context budget. Pair with
per-page `.md` "clean" versions when feasible. It lives at `/llms.txt`; a fuller
`/llms-full.md` can inline everything for one-shot ingestion.

## 7. Robots / crawler access — allow AI bots when you WANT ingestion

To be cited, the AI crawlers must be *allowed* to fetch the canonical. In
`robots.txt`, explicitly allow the ones you want:

```
User-agent: GPTBot         # OpenAI (ChatGPT training + browsing)
Allow: /
User-agent: ClaudeBot      # Anthropic
Allow: /
User-agent: PerplexityBot  # Perplexity
Allow: /
User-agent: Google-Extended # Gemini / Vertex (separate from Googlebot SEO crawl)
Allow: /
```

Notes: `Google-Extended` gates AI training/grounding **without** affecting classic
Googlebot SEO indexing — they're independent. Only *block* these if you explicitly
do not want ingestion; the default for public-facing content you want cited is
**allow**. (Don't confuse "allowed to crawl" with "ranks well" — access is necessary,
not sufficient.)

## 8. AI-cited-source insight — Reddit, GitHub, YouTube punch above their reach

LLM answer engines disproportionately cite a few source types, so these have **GEO
value beyond their human audience**:

- **Reddit** — Google's 2024 content-licensing deal with Reddit + LLMs' heavy use of
  Reddit threads as training/grounding data make a well-written Reddit post a
  frequently-cited source. A genuine, on-topic Reddit answer that names the entity
  (§2) is a GEO asset, not just traffic.
- **GitHub** — README content is heavily ingested. A clean, well-structured README
  (entity name as H1, one-line definition under it, clear sections) is one of the
  highest-leverage GEO assets for any code project — it's *both* the canonical and a
  corroborating crawled source.
- **YouTube** — transcripts (auto-captions) are indexed and cited. A video with a
  clean spoken/typed transcript that states the entity definition is a GEO asset; add
  a real description + transcript, don't rely on the video pixels.

So route code → GitHub README, and lean into Reddit + YouTube transcripts when the
entity warrants — their citation weight exceeds their click-through.

## 9. Content-type → canonical → spokes (routing guidance)

A map for *where the canonical lives* and *where to syndicate*. This is **guidance**;
the actual routing call is left to the calling agent (and the user's review gate in
`devlog`). Full table →
[references/routing-map.md](references/routing-map.md). Quick version:

| Content type | Canonical home | Typical spokes |
|---|---|---|
| Dev / code | GitHub repo README | HN (Show HN), Reddit (relevant sub), registries, Twitter, Discord |
| Visual stills | Own portfolio page | Twitter/IG, relevant subs, Are.na/Cosmos |
| Motion / video | YouTube (w/ transcript) + own page | Twitter, Reddit, IG/TikTok (vertical) |
| Writing / essay | Own-domain blog | HN, Reddit, Medium-mirror (`rel=canonical`), Twitter |
| Portfolio / process | Own portfolio page | Twitter thread, relevant subs, Cosmos |
| Product / launch | Own landing page | Product Hunt, HN, Reddit, registries, Twitter |

## 10. Distribution — algorithmic pickup, virality, engagement, tagging

SEO/GEO make a thing *findable when someone looks*; distribution makes it *surface to
people who weren't looking*. Recommendation feeds (TikTok/Reels/Shorts FYP, X, Reddit,
HN, LinkedIn, YouTube) are the dominant discovery path now, and they reward different
signals than crawlers do. The canonical+corroboration work above still applies — this
is how the **spokes** earn reach instead of dying at 40 impressions. Full per-platform
tactics, ratio targets, and frameworks → [references/algorithmic-distribution.md](references/algorithmic-distribution.md).

**The one mechanic every feed shares: early-engagement velocity.** Modern feeds test a
post on a tiny seed audience and *expand* it only if early signal (completion, dwell,
saves, replies, shares) beats a threshold in the first minutes-to-hour. So the first
hour is the whole game — not the first day. Optimize for the seed test, then ride.

- **Hook in the first 1–3 seconds / first line.** Watch-time and dwell are the master
  signals on video and text alike. Front-load the payoff or the tension; never warm up.
  A flat-vs-skeuo *before/after* in frame one beats any intro.
- **Engineer a share/save trigger, not just a view.** Shares and saves are weighted far
  above likes because they signal *value worth redistributing*. Jonah Berger's STEPPS
  (Social currency, Triggers, Emotion, Public, Practical value, Stories — *Contagious*,
  2013) is the checklist: does the post make the sharer look smart, carry a recurring
  trigger, spike high-arousal emotion (awe/anger/delight, not sadness), and hand over
  practical value? If none, it won't spread regardless of reach.
- **Completion > length.** Feeds reward finishing. Shorter that gets watched/read to the
  end out-distributes longer that gets abandoned. Cut to the shortest that lands.
- **Seed the first hour deliberately.** Reply to every early comment fast (replies are
  engagement and signal a live thread), post when *your* audience is active, drop it in
  the Discord/group chat / DM a few people who'll genuinely engage at launch. Don't
  post-and-leave — the algorithm reads your own early replies as velocity.
- **Tagging is routing, not decoration.** Tags/hashtags tell the feed *who to test it
  on*. Use a few specific, real-community tags over broad generic ones (`#skeuomorphism`
  / `#uidesign` over `#design`); `@`-mention people/projects you genuinely reference (a
  tagged account may reshare → instant new audience); fill platform topic fields, video
  alt text, and YouTube tags+description (also doubles as GEO/SEO §8). Over-tagging or
  irrelevant tags get throttled as spam — relevance over volume.
- **Native-first, link-second.** Every feed demotes posts that send users off-platform
  (external links suppress reach). Put the substance *in* the post (native video, image,
  full text, a thread) and the link in a reply / second slot / bio. POSSE §1 still holds
  — the canonical exists — but the spoke must stand alone natively to get distributed.
- **Hook-loop-payoff for threads/carousels.** Each unit should pull to the next (open
  loops, "but here's the catch"). Completion of a thread/carousel is a strong signal.
- **Consistency compounds; one viral hit rarely does.** Feeds favor accounts that post
  reliably and hold audiences (return/retention signals). A steady cadence of decent
  posts out-distributes one polished drop, because the algorithm learns your account is
  a reliable hold. This is the engagement-*building* half: it's an account property, not
  a per-post one.
- **Don't fake it.** Engagement-bait ("comment X to get Y"), follow-loops, pods, and
  bought engagement get pattern-detected and reach-throttled on every major platform,
  and the off-signal (high views, no genuine saves) tanks the *next* post's seed test.
  Earn the early engagement; don't simulate it.

This composes with [[crosspost]] (posting mechanics) and [[devlog]] (the human
review gate) — those handle *how/when to post*; §10 is *what makes the post spread once
posted*. Distribution tactics never override Claim hygiene (below) or anti-cloaking §4.

## 11. Shareable visual assets — charts/diagrams ship as RASTER, baked from a vector source, branded for citation

A chart, diagram, or data-viz you want *shared around* (reposted to X/LinkedIn/Reddit,
embedded in other blogs, pasted into Discord/Slack) is a distribution artifact, and its
format decides whether it can travel at all. The rule: **author the source in code
(SVG / a declarative spec), then bake a high-res raster PNG — and that PNG is what goes
on the page and into the world.** Source-as-code keeps it editable and re-bakeable;
raster is the only thing that actually propagates.

**Why raster, not the on-page SVG/CSS** — what each on-page form can and can't do:

| On-page form | Google Images indexes | right-click → save | reshareable file? | usable as og:image |
|---|---|---|---|---|
| inline `<svg>` / CSS-rendered | ❌ no | ❌ no (it's DOM) | — | ❌ |
| `<img src="chart.svg">` | ✅ yes | ✅ (saves `.svg`) | ❌ socials reject SVG | ❌ |
| **`<img src="chart.png">` @2×** | ✅ yes | ✅ (saves a PNG) | ✅ pastes everywhere | ✅ |

Inline SVG is invisible to image search and can't be grabbed; `<img src=svg>` *is*
indexable and grabbable but saves a file nobody can post (X, LinkedIn, Reddit, Facebook,
og:image, and Twitter cards all reject SVG). Only the **2× PNG `<img>`** does every job
at once — indexed, right-click-saved into a *pasteable* file, valid og:image, universally
reshareable. So ship the PNG on the page; the SVG stays the build source only. (Sources:
[Google Image SEO](https://developers.google.com/search/docs/appearance/google-images),
[fransdejonge](https://fransdejonge.com/2018/03/twitter-and-facebook-dont-support-svg-yet/).)

**The GEO move — a brand/source bar baked into every asset.** Title + one-line source +
your domain (`connerkward.dev`), baked *into the pixels*. When the image propagates with
the link stripped (the normal case on social), the bar **is** the citation — it's why
Datawrapper (Gregor Aisch) and the Economist/FT/NYT graphics desks stay recognizable and
attributed after reshare. A naked chart that goes viral is a lost citation. This is the
visual-asset corollary of §2 entity-consistency: the asset carries its own attribution.

**Make the chart worth resharing, not just acceptable** (the claim is the viral unit, not
the chart): the **title is a provocative, debatable takeaway** with the punch phrase in the
accent colour; **annotate the punchline ON the chart** (callout on the key datapoint, so it
survives a context-stripped reshare); **focus-colour** — gray everything except the one
element carrying the argument; one insight per chart; lead with the dramatic shape; round
sticky numbers. Full virality levers + production defaults → [references/shareable-visuals.md](references/shareable-visuals.md).

**The non-negotiable specs** (full per-platform dimensions + bake recipe + brand-bar
template + a11y → [references/shareable-visuals.md](references/shareable-visuals.md)):

- **PNG, not JPEG** — JPEG smears text and thin chart lines; PNG keeps them crisp.
- **Optimal resolution is platform-NATIVE, not "as big as possible"** — bake to ~2× the
  on-page display width for the blog `<img>` (retina), but for native feed uploads match the
  platform's own processing width (`1080` for IG) — going past it just inflates bytes and
  gets downscaled anyway, and over-large files trip recompression. Landscape charts at
  **~2400px wide** are the sweet spot: retina-grade, well under X's `8192`px / 5 MB caps, no
  waste. (X keeps PNG for text/graphics but recompresses oversized uploads — stay modest.)
- **sRGB, solid background** — transparent PNGs box out black/white on some feeds and in
  dark/light-mode mismatches.
- **Aspect ratio is optimized per destination — pick the ratio, don't accept the default.**
  Feed real-estate / scroll-stop optimum is **4:5 portrait** (`1080×1350`) — Meta recommends
  it over square (~⅓ more mobile screen, better reach; square gets grid-cropped). No-crop
  optimum on X is **16:9** (`1600×900`) — X center-crops anything else in the timeline. Link
  unfurl is fixed **1.91:1** (`1200×630`). So the *feed-share* variant defaults to **4:5**
  when the chart re-flows into portrait legibly, else 16:9.
- **Author center-safe so it survives auto-crop.** Every feed center-crops (X → 16:9 in
  timeline, IG → 4:5/1:1 in grid). Keep title + data + brand bar inside the center zone so
  nothing critical is trimmed whichever crop a platform applies to the one asset.
- **Bake N crops from one source** — blog-inline (~2400px wide), OG `1200×630`, feed `1080×1350`
  (4:5) or `1600×900` (16:9), story `1080×1920`. Same data; re-flow (don't squeeze) per ratio.
- **Legible at feed-thumbnail size** — one idea per chart, big type, few data points.
- **On-page share affordance** — the chart figure exposes a **hover-revealed (desktop) /
  tap-revealed (touch)** share UI: *download the branded PNG*, *copy-image-to-clipboard*
  (`navigator.clipboard.write` of the PNG blob → paste straight into a post/DM), and
  *copy-permalink* to the chart's anchor (+ optional X/LinkedIn share-intent). This collapses
  the gap from "I like this chart" to "it's in my post" — the highest-leverage distribution
  lever for a chart. Hover-only is invisible on mobile, so always pair with a tap target.
- **a11y** — strong `alt` + `<figcaption>` + optional `<details>` data table (raster has
  no selectable text, so the numbers must exist in the DOM another way).

This is the **default treatment for any chart/diagram on a public page**, not opt-in —
same standing as the minimum pass above. Where a repo already bakes share assets (the
portfolio's `make-og-cards.py` / `build-seo.py` pattern), extend that pipeline rather than
hand-rolling. Composes with §10 (native-first: the baked asset is the native artifact the
feed distributes) and Claim hygiene below (a chart's numbers are factual claims — source them).

## Claim hygiene — every factual claim cites a source, or it's flagged

Public, AI-citable content is exactly where a hallucinated stat or misattributed quote
does lasting damage — engines propagate it, and it's *your* entity that gets the wrong
fact attached. Before publishing anything with factual claims (numbers, dates,
"first/largest/only", quotes, third-party capabilities):

- **Each non-obvious factual claim carries a source** — inline link, footnote, or named
  primary reference. A claim you can't source gets cut or softened to what you can stand
  behind, not shipped on vibes.
- **Verify with an INDEPENDENT pass, not the writing pass.** The drafter is biased toward
  its own prose; do a separate read whose only job is "list every factual claim, mark each
  cited / uncited / unverifiable." The uncited ones are the flag list. (Mirrors
  `verify-outputs-rule` — the check must be independent of what produced the claim — and
  the Vercel `vercel-optimize` pattern of stripping any recommendation that cites nothing
  in an allowed source set.)
- **Pin the source version** — the commit / dated snapshot / version you actually checked,
  not "the docs." A claim sourced to a moving target isn't reproducible.
- **First-party claims** (what you built, when, the result) are sourced by the canonical
  page itself — the point of POSSE §1: *be* the primary source.
- Composes with §2: a *consistent* description that's *wrong* gets the error cited
  everywhere. Consistency without verification is amplified error.

## Relationship to other skills/rules

- **[[devlog]]** owns the draft → human-review-gate → post pipeline. It applies the
  entity-consistency (§2) discipline when drafting per platform.
- **[[crosspost]]** owns the per-platform posting mechanics (auth, APIs, formats); §10
  here owns what makes those posts get *picked up* once sent.
- **[[design]]** / **[[docs]]** — when building a public page or README, apply §3
  (H1=entity, definition line, FAQ) and §5 (JSON-LD).
- **`web-dev-rule`** — page must be crawlable/fast for any of this to matter.
