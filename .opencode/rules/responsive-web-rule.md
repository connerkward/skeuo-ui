---
name: "responsive-web-rule"
id: "responsive-web-01"
description: "Every web page, studio, lookdev, dashboard, or component must reflow correctly across viewport widths from the first version — fixed-width overflow is a bug, not a draft. No exceptions, including throwaway tools."
globs: ["**/*.tsx", "**/*.jsx", "**/*.ts", "**/*.js", "**/*.css", "**/*.scss", "**/*.html", "**/vite.config.*"]
applyTo: ["**/*"]
alwaysApply: false
priority: "high"
human-reviewed-at: 2026-06-26
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Web UIs are ALWAYS responsive to viewport width — no exceptions

Every web page, app, studio, lookdev, dashboard, preview, or component you build
**must reflow correctly across viewport widths** — phone to wide desktop — from the
first version. This is not a polish step or a "later"; a fixed-width layout that
overflows, clips, or ignores the window is a **bug**, not a draft. There is no case
where shipping a non-responsive web UI is acceptable.

**Why this is absolute:** the user resizes windows, splits screens, and views on
phones constantly. A layout that only works at the width you happened to test is
broken for them immediately. It fired on a concrete miss (skeuo-ui, 2026-06): a CAD
studio was built at a fixed canvas/panel width and didn't respond to the window —
"why is it not responsive to window width. that should ALWAYS apply. never not."

## The defaults that make it responsive by construction

- **Fluid containers, not fixed pixels.** Top-level layout uses `flex`/`grid` with
  `flex-wrap`, and sizes in `%` / `min()` / `max()` / `clamp()` / `fr`, not hard
  `width: 1200px`. Panels and sidebars `flex: 1 1 <basis>` so they shrink and wrap
  under the main content on narrow screens instead of overflowing.
- **Canvas / SVG scale to their container.** A `<canvas>` keeps its intrinsic
  resolution for drawing but is displayed with `style="width:100%; height:auto; max-width:<n>px"`
  so it shrinks with the viewport. SVG uses `viewBox` + `width:100%`. Never leave a
  canvas at a fixed CSS width that can exceed the window.
- **Two-pane tools reflow to one column.** A `studio | controls` side-by-side layout
  must stack (controls below or above the stage) when the width can't hold both —
  `flex-wrap: wrap` on the container + a sensible `flex-basis` on each pane does it
  for free.
- **No horizontal scroll from layout.** Content fits the width; only intentionally
  scrollable regions scroll. `max-width: 100%` on media and wrappers.
- **Readable line length** via `max-width` in `ch`/`rem` on text columns, centered —
  responsive ≠ "text spans 3000px on a wide monitor."

## The check before you hand over any web UI

Resize it narrow (or screenshot at ~390px and ~1400px). If anything overflows the
window, clips, or fails to reflow — it's not done. This applies to throwaway studios
and scratch tools too: "it's just a lookdev" is not an exemption.

Related: `web-dev-rule` (serving/isolation), `design-spatial` (composition). This
rule is narrower and non-negotiable: **fluid width, always.**
