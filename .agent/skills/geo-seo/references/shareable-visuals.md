# Shareable visual assets — full spec, dimensions, bake recipe

Detail for geo-seo §11. The principle: **SVG (or declarative) source → bake a high-res
raster PNG; the PNG is what ships on the page and travels.** This file is the *how*.

## Make the CHART itself spread — heuristics for a good / viral chart

The format rules below get a chart *accepted* by feeds; these make it *worth resharing*.
**Honest hierarchy first: the chart is not the viral unit — the claim is.** What spreads is a
surprising, debatable take with the chart as proof; most of the leverage is the insight +
headline, not chart chrome. Don't over-polish; sharpen the take. Sources: Berger,
*Contagious*/STEPPS + the Wharton high-arousal-emotion list (awe, excitement, amusement,
anger, anxiety, **surprise** — surprise/expectation-violation is the strongest); Tufte
(data-ink / chart-junk); Knaflic, *Storytelling with Data* (focus via colour); Cairo, *How
Charts Lie*; the NYT/FT/Economist annotation house style; MIT 2025 ("readers judge a chart's
trustworthiness from its **design** — palette, arrangement — before they read the data").

### A. The message
1. **One insight per chart — grokkable in 3 seconds.** Viewers decide to engage within ~3s.
   Cut secondary series, dual axes, anything that isn't the single comparison. Complexity
   kills shares.
2. **The title IS the takeaway — a provocative, debatable claim, not a description.** "Agents
   kill the middlemen first", not "Exposure by layer". Arguable claims drive comments/
   quote-tweets = early-engagement velocity (geo-seo §10). The title carries the "so what";
   no separate kicker line.
3. **Surprise / violate an expectation.** The most-shared charts contradict conventional
   wisdom or confirm a tribe's worldview. If the data isn't surprising, the framing must be.
4. **Lead with the shape.** Viral charts have a memorable silhouette — a cliff, crossover,
   hockey stick, collapse. Frame/scale so the dramatic shape reads first.
5. **Round, sticky numbers** — "25×", "96%", "18×→6×". Quotable; precise decimals aren't.
6. **The visual must MATCH the claim.** If the title says "two kinds survive", exactly TWO
   elements read as the highlighted class — a title that disagrees with the chart (says two,
   shows three) reads as confusing and untrustworthy. Count and logic in the picture = the
   words. (This is why a 2×2 titled "two survive" must have two survive-coloured cells and
   two dead, not three tinted.)

### B. Direct attention (colour + annotation)

**Colour must MEAN something — encode a variable, or be reserved for emphasis. Never a
decorative gradient.** This is the load-bearing one. A colour ramp that merely mirrors what
the bars *already* encode (their height/length = the value) adds zero information — it's
chart-junk — and can actively fight the message: a value-honest ramp (dark=big→light=small)
makes the *lowest* bar the faintest, which buries the punchline when the punchline IS the low
bar (e.g. "cost collapsed to almost nothing"). So decide deliberately:
- **Is there a real second variable?** Let colour encode it. Exposure/threat → a red→green
  heat ramp (most-exposed red, safe green); category → distinct hues that match the labels;
  survival → survive vs selected-against; era/region → its own palette. Now colour *teaches*.
- **No second variable (height already carries the data)?** Then colour's job is *emphasis
  only*: one muted context tone + the focal element accented. Don't gradate to "look colourful".
The test: if you removed the colour, would the chart lose information? If no, the colour was
decoration — collapse it to emphasis.
6. **Accent-colour the punch phrase in the title** (bold), rest in ink — "Shipping an app got
   **~25× cheaper**". (Portfolio baker: `*phrase*` markup → accent run.)
7. **Focus the eye — emphasise ONE element, de-emphasise the rest. But de-emphasise with
   COLOUR, not dead gray.** Knaflic's rule, with the nuance that bit us repeatedly:
   - **Categorical series (colour identifies the category):** keep each category's own hue so
     the colour↔label correlation holds — *mute* the non-focal ones (a soft, desaturated tint
     of their own colour), and make the focal one full-vivid/accent. Do NOT flatten categories
     to gray; that destroys the encoding and reads as "hiding data."
   - **Ordinal / sequential series:** use a **gradation** (e.g. orange→yellow) across the
     non-focal bars and the full accent on the focal/most-severe one (often the last/extreme).
   - **A single excluded "loser":** true **gray** is right for the one element being called out
     as out (e.g. the dead quadrant), against the still-coloured survivors.
8. **Annotate the punchline ON the chart** — a callout on the key datapoint so the insight
   survives a context-stripped reshare. **Annotate with the number/fact, not a forced phrase:**
   "↓96%", "6× (was 18×)" land; preachy captions ("first to go") read as on-the-nose — let the
   colour + title carry the editorial. Thin leader/arrow, key number in the accent.

### C. Craft (trust + legibility)
9. **Kill chart-junk (Tufte data-ink).** No decorative frames/borders, no heavy gridlines, no
   redundant labels, no 3-D. Every mark earns its place; the data is the hero.
10. **Design signals trust before the data is read (MIT 2025).** A consistent, restrained
    palette + clean arrangement makes a chart *feel* credible — which decides whether it's
    screenshot-worthy. Sloppy/garish = distrusted regardless of the data.
11. **Legible at a phone thumbnail.** Big type, few datapoints, high contrast; most reshares
    are viewed small on mobile.
12. **House style = recognition across reshares.** A consistent ground/type/accent (the FT/
    Economist effect) makes charts identifiable as they propagate — GEO entity-consistency
    (§2) applied to visuals.

### Production defaults (portfolio)
Off-white ground = the page's own paper colour (charts read as native light figures, not boxed
cards); **no frame**; dark ink; ONE accent (terracotta) for the title punch phrase + the focal
element + the brand-bar domain; source bar always baked; categorical colours muted-not-grayed
for de-emphasis, ordinal series as a gradation, gray reserved for an excluded element. For the
highest-distribution surfaces also consider an **animated reveal** (2–4 s MP4/GIF of the bars/
line drawing — video feeds reward dwell/completion) and the **tweet-screenshot container**
(chart + hook claim posted natively), which is the actual viral unit.

## Why raster is mandatory for sharing (the constraint, not a preference)

No major social platform accepts SVG as an upload or a link-preview image. Verified:

- **og:image / Twitter (X) cards reject SVG** — must be PNG/JPEG/WebP. X card image:
  `1200×675` (2:1), min `300×157`, max `4096×4096`, under 5 MB.
  ([SEO Framework](https://kb.theseoframework.com/kb/twitter-cards-and-x-sharing/))
- **Facebook / LinkedIn / Reddit / Instagram** all rasterize or reject SVG uploads.
- **Google Images** *does* index SVG — but **only** via `<img src="x.svg">`; inline
  `<svg>` in the HTML is not indexed and can't be hot-linked or right-click-saved.
  ([Google Image SEO](https://developers.google.com/search/docs/appearance/google-images))

Net: the only on-page form that is indexed **and** right-click-saved into a *pasteable*
file **and** valid as og:image is a raster `<img src="*.png">`. Ship that. Keep SVG as
the build source.

## Format specs

- **PNG** for charts/diagrams (sharp text + thin lines). JPEG only for photographic
  assets — it artifacts on text and vector edges.
- **WebP** is smaller and accepted by most platforms now, but PNG is the safest universal
  upload; bake PNG as the canonical, optionally WebP as a `<picture>` on-page source.
- **2× pixel density** — design at logical size, render at 2× (a 1200-wide design → a
  2400px PNG). Retina displays + platform recompression both eat detail; 2× survives it.
- **sRGB**, **solid background** (not transparent — transparent PNGs render on a
  black/white box on some feeds and in dark/light mode mismatches).
- Keep each file **under ~2 MB** (well under platform caps; faster crawl + load).

## Per-platform crop targets (bake these from one source)

| Variant | Bake to (px) | Ratio | Use |
|---|---|---|---|
| Blog-inline | **~2400 wide** (2× of 1200 display), natural height | content | on the canonical page `<img>` |
| Link preview / OG | `1200×630` | 1.91:1 | `og:image` / `twitter:image` (large card) |
| **Feed (default)** | **`1080×1350`** | **4:5** | **IG / LinkedIn / FB feed — max real estate, scroll-stop** |
| X / Twitter in-stream | `1600×900` | 16:9 | X timeline (shows full, no crop) |
| Square (fallback) | `1080×1080` | 1:1 | Discord, older feeds, when 4:5 would crop badly |
| Story / Reel / Short | `1080×1920` | 9:16 | IG/TikTok story, vertical |

**Optimal resolution = platform-native, not maximal.** The instinct to "render huge" is
wrong on two counts: (1) feed uploads are downscaled to the platform's own processing width
(IG `1080`), so anything above it is discarded bytes; (2) oversized files trip harder
recompression. Targets:

- **Blog `<img>`:** 2× the CSS display width. Full-bleed ~1200 display → bake `2400` wide.
- **OG/link:** `1200×630` is already the retina standard — don't inflate it.
- **X in-stream:** `1600×900` — above the ~1200 desktop display width (so retina is crisp)
  but modest enough to dodge aggressive recompression. X **keeps PNG** for text/graphics
  (its JPEG pass artifacts hard edges), so PNG is right here. Hard limits: min `440×220`,
  max `8192×8192`, under **5 MB** ([soona](https://soona.co/image-resizer/twitter-spec-guide)).
- **IG square/portrait/story:** bake at native `1080`-width — do **not** upscale past it.

Don't crop blindly — re-lay-out (re-flow) the chart per ratio when needed; a wide chart
squeezed into 9:16 is unreadable. One source *file*, but the bake step re-flows for tall crops.

## Aspect ratio — optimized per destination (pick it, don't accept the default)

There is no single best ratio, but each surface has a clear optimum, and "whatever shape the
chart happened to be" is the wrong default:

- **Feed image post (the actual share): 4:5 portrait (`1080×1350`) is the optimum.** Meta
  *officially recommends* 4:5 over square — it occupies ~⅓ more mobile screen, stops the
  scroll better, and consistently outperforms 1:1 in reach/engagement; square posts also get
  grid-cropped. This is the default `feed` variant whenever the chart re-flows into portrait
  legibly. ([Buffer](https://buffer.com/resources/instagram-image-size/),
  [SocialBee](https://socialbee.com/blog/instagram-aspect-ratio-and-image-size/))
- **X timeline: 16:9 (`1600×900`) shows full, no crop.** X center-crops anything non-16:9 in
  the timeline (top/bottom trimmed). Use 16:9 for X landscape charts, or a 4:5 with all
  critical content center-safe. ([aspectratiocalculator](https://aspectratiocalculator.com/twitter-aspect-ratios/))
- **Link unfurl: 1.91:1 (`1200×630`)** — fixed OG spec, not negotiable.
- **Story/Reel/vertical: 9:16 (`1080×1920`)**.
- **Square 1:1** is now a *fallback*, not a default — use it for Discord/older surfaces or
  when 4:5 would crop badly, not as the go-to.

### Author center-safe so ONE asset survives every crop
Because every feed center-crops to its own ratio, lay the chart out so the **title + the data
+ the brand bar all sit inside the center zone** — the region that survives both X's 16:9
timeline crop and IG's 4:5/1:1 grid crop. Then a single baked asset doesn't lose its title or
attribution when a platform trims it. Keep margins generous; don't push critical content to
the top or bottom edge where it's the first thing cropped.

## On-page share affordance (hover/tap-revealed share UI)

The branded PNG is useless if the reader can't easily grab it. Every chart figure on a
public page should expose a **share UI revealed on hover (desktop) and via a persistent tap
target (touch)** — this is the single highest-leverage distribution lever for a chart,
because it collapses "I like this" → "it's in my post" to one click.

What the affordance offers, in priority order:

1. **Copy image to clipboard** — `navigator.clipboard.write([new ClipboardItem({'image/png': blob})])`
   on the branded PNG. The reader pastes it straight into a tweet/DM/Slack. Lowest friction.
2. **Download PNG** — `<a href="chart.png" download>`; gives them the branded high-res file.
3. **Copy permalink** — copy a URL with the chart's anchor (`…/post#chart-slug`) so a link
   points at *that* chart, not just the page. (Give each `<figure>` an `id`.)
4. **Share-intent links** (optional) — X / LinkedIn / Reddit web-intent URLs pre-filled with
   the chart title + permalink. e.g. `https://twitter.com/intent/tweet?text=…&url=…`.

Implementation notes:
- **Hover-only is invisible on mobile** (no hover state). Always pair the hover reveal with
  an always-visible-or-tappable control on touch (a small share glyph in the figure corner).
- Keep it out of the baked pixels — this is *page* UI (HTML/CSS/JS over the `<figure>`), not
  part of the PNG. The PNG carries the brand bar; the page carries the share buttons.
- It's a `<figure>`-level component: corner toolbar, `opacity:0 → 1` on
  `figure:hover`/`:focus-within`, buttons wired to the clipboard/download/intent actions.
- Don't block right-click — native "save image as" still works and should; the toolbar is
  the *faster* path, not a replacement.

This composes with §10 (the affordance is how the on-page asset becomes a native social
upload) and the brand bar above (whatever they copy/download already carries the citation).

## The brand/source bar (the citation that survives reshare)

Bake into every variant, as pixels, not page chrome:

```
┌──────────────────────────────────────────────┐
│  [Chart title — one line, large]             │
│                                              │
│         …the chart / diagram…                │
│                                              │
│  Source: <primary source>   ·  connerkward.dev│  ← brand bar
└──────────────────────────────────────────────┘
```

- **Title** top-left, large enough to read as a feed thumbnail.
- **Source line** = where the data came from (so the chart is self-verifying and
  Claim-hygiene-compliant) **+ your domain** (so a stripped-link reshare still cites you).
- Keep it one thin strip; don't let it crowd the data. Datawrapper/Economist/FT model.

## Bake recipe (SVG source → raster)

Two reliable headless paths; both deterministic, scriptable, no GUI:

1. **Playwright screenshot** (best when the source is HTML+inline SVG, e.g. an existing
   studio chart) — load the page/SVG at a fixed viewport, `deviceScaleFactor: 2`,
   screenshot the chart element to PNG. Reuses the exact on-page rendering (fonts, CSS).
2. **resvg / `rsvg-convert` / sharp** (best when the source is a standalone `.svg`) —
   `rsvg-convert -z 2 chart.svg -o chart.png`, or `sharp(svgBuf).resize(2400).png()`.
   Faster, no browser, but needs fonts available to the renderer.

In this fleet, **extend the portfolio pattern** rather than inventing a new one:
`scripts/make-og-cards.py` already bakes `1200×630` PNGs; `build-seo.py` wires
`og:image`/`twitter:image` to baked PNGs when present. A chart baker is the same shape —
add a `make-chart.py` (or extend `make-og-cards.py`) that takes the SVG source + a
settings JSON and emits the variant PNGs with the brand bar, then point the page `<img>`
and `og:image` at them.

## Accessibility (raster has no selectable text)

Because the numbers aren't in the DOM as text once it's a PNG:

- **`alt`** — describe the chart's *finding*, not just "a bar chart" (e.g. *"Bar chart:
  app-creation cost fell ~90% from 2020 to 2025"*).
- **`<figcaption>`** — the human-visible caption + source.
- **`<details>` data table** (optional but ideal) — the underlying numbers as a real HTML
  `<table>` so screen readers and crawlers get the data. Doubles as GEO (extractable text).

## When inline SVG on-page IS right (the exception)

If a visual is genuinely **interactive** (the reader drags/toggles it — see the
`explorable` skill) or you specifically want **dark-mode re-theming** of the on-page
render, keep inline SVG for the on-page experience **and** *also* bake a static PNG for
og:image + sharing + image-search. Two artifacts, not one. For a static chart, that's
overkill — ship the one PNG.
