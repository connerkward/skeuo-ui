---
name: explorable
description: Build an interactive, highly-visual web page that TEACHES a concept by letting the reader manipulate it — an "explorable explanation" (Bret Victor / Nicky Case / Bartosz Ciechanowski / 3Blue1Brown lineage), not a static diagram or slide deck. Use WHENEVER the user wants to understand, learn, see, or "get" how something works in a visual/interactive way; says "help me understand", "show me visually", "build me an interactive page/site to learn X", "make a visualization/explainer/simulation of X", "I want to play with it"; or when you're explaining a system/algorithm/pipeline/tradeoff in chat and a draggable, manipulable page would land it better than prose. Default output is a self-contained single .html file (zero build, opens by double-click). Reach for this skill proactively when understanding is the goal and the subject has moving parts, parameters, or cause→effect worth feeling firsthand.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Explorable

Build a page that lets someone **understand a thing by doing**, not by reading about it.
The reader drags a slider, toggles a layer, scrubs a value — and *sees* the consequence.
That firsthand cause→effect is the whole point; a paragraph and a screenshot can't replace it.

This is the tradition of **Bret Victor** ("Explorable Explanations", "Up and Down the Ladder
of Abstraction", the Tangle reactive-document library), **Nicky Case** (explorabl.es,
"Parable of the Polygons" with Vi Hart), **Bartosz Ciechanowski** (ciechanow.ski —
interactive articles on gears, light, GPS), **Mike Bostock** (D3, Observable), and
**Grant Sanderson / 3Blue1Brown** (manim — visual-first math). Borrow their move: take the
abstract thing you're explaining and make it a concrete object the reader can grab.

**Two deeper references — load them when the task warrants:**
- [`references/learning-science.md`](references/learning-science.md) — the empirically-proven + theoretical
  basis (generation effect, retrieval practice, concreteness fading, variation theory,
  cognitive load, conceptual change, productive failure, …), each tied to the explorable
  move it licenses, plus the *sequence* for assembling a whole explorable. **Read it for any
  non-trivial explainer** — it is what makes the thing teach rather than merely wiggle.
- [`references/interactive-math.md`](references/interactive-math.md) — **load whenever the
  subject involves real math** (a transform, a fit, a loss, a probability). Printing an
  equation and labelling its terms is *not* teaching it; this file is how to make the math
  manipulable (draggable basis vectors for a linear map, residual sticks + a λ force for
  regression, the ADEPT order). The intuition-first methods of 3Blue1Brown / Victor / Azad.

## When to build one

Reach for an explorable when **understanding is the deliverable** and the subject has parts
that move, parameters that trade off, or a cause→effect worth feeling:
- The user says "help me understand / show me / let me see / I want to play with X."
- You're explaining a pipeline, algorithm, system, or tradeoff in chat and prose is losing.
- A decision hinges on intuition the user doesn't have yet (why does this drift? what does
  this parameter actually do?).

Don't build one for a fact lookup, a yes/no, or something a single sentence settles. The
machinery has to earn its keep (see `restraint-rule`) — if there's nothing to manipulate,
write the sentence instead.

## The stack decision

- **Standalone concept explainer → one self-contained `.html` file.** Vanilla JS + inline
  `<svg>` or `<canvas>`, all CSS in a `<style>` block, no build, no dependencies, no CDN if
  avoidable. It opens by double-click, archives forever, and the user can keep/share it.
  This is the default — pick it unless there's a reason not to.
- **Embedding into an existing app → that app's framework.** If the explainer lives inside
  a React/Vue/Svelte project, build it as a component in the repo's stack so it composes.
- Don't reach for D3/Three/a framework for a standalone unless the subject genuinely needs
  it (force-directed graphs, 3D, large data). A few hundred lines of vanilla SVG/canvas
  covers most explainers and stays readable.

Start from `assets/explainer-template.html` — a working skeleton (state → render → controls
loop, layer toggles, a slider, a reset). Copy it, gut the demo, build your thing.

**Default theme — the warm "paper" editorial palette** (baked into the template):
`--paper:#ebe8df` background, `--ink:#1a1712` text, one hot color `--accent:#b4543f`
(terracotta) reserved for live handles/values, `--good/--warn/--blue` for state, a serif
body (`Iowan Old Style`→Palatino fallback) with `--mono` for controls/readouts/labels. Use
this for **all** explainers by default — it reads as considered and editorial, not dashboard.
**Only theme otherwise if the user asks to match a specific repo** (then pull that repo's CSS
variables / fonts). For heavy-particle or 3D canvas work a dark stage can read better — swap
`--paper`/`--ink`, keep the structure.

## What makes it actually teach (the substance)

A pretty animation that loops on its own is a screensaver, not an explainer. The difference
is these moves — apply the ones the concept needs:

1. **Reify the abstraction.** Map the invisible concept to a concrete visual object that
   moves. "Paint drift" is abstract; a painted box sliding away from a template box while a
   misalignment counter climbs is *grabbable*. Find the one picture that IS the idea.

2. **Hand the reader the controls.** The reader, not an autoplay timer, drives the key
   variable. A slider/drag/toggle they push and watch is worth ten seconds of passive
   animation. Direct manipulation > play button. (Bret Victor's core thesis.)

3. **Show cause→effect live, with a number.** When they move the input, the output AND a
   readout update in the same frame. Name the consequence numerically ("misalignment: 12px",
   "drift: 0") so the abstract relationship becomes a concrete, watchable quantity.

4. **Compare against the baseline / "do nothing."** The insight is usually in the *contrast*
   — before vs after, with-fix vs without, this-pipeline vs that. Put them side by side or on
   a toggle so the difference is visible, not asserted. (This mirrors `verify-outputs-rule`:
   show it beating the baseline, don't claim it.)

5. **Layer it — concrete first, then peel.** Start with the simplest true picture; let the
   reader toggle on additional layers (the blueprint, the math, the edge cases) as they build
   intuition. Don't dump the full system at once. Toggleable layers > one busy diagram.

6. **Annotate the live state.** Labels, arrows, and values that update *with* the simulation
   — not a static legend. The reader should never have to map a number in a corner back onto
   the picture; put the label on the moving thing.

7. **Make wrong states reachable.** Let the reader push it until it breaks — that's where the
   understanding is. The failure mode you can *drive to* teaches more than the one you read
   about.

8. **Wiki-link the major concepts.** The first time a *named, established* concept appears
   (centroid, ridge regression, optical center, cognitive load, a theorem, a named law),
   link it out — Wikipedia, or the canonical source (a paper, a 3Blue1Brown video, the
   original author's page). Mark it with a dotted underline (`a.wiki` in the template) so the
   reader knows it's a rabbit-hole, not a navigation link. This respects the reader who wants
   to go deeper without bloating the page, and signals "this is a real, looked-up thing, not
   hand-waving." Don't link every term — only the load-bearing concepts and proper nouns.

9. **If there's math, make it manipulable — don't just typeset it.** A labelled equation is a
   spec, not a lesson. Build intuition first (concrete → symbolic), and make the symbols
   themselves into handles the reader drags. This is its own discipline →
   [`references/interactive-math.md`](references/interactive-math.md). (The bundled
   `example-auto-balance.html` is honest about getting this *wrong* in its §7 — read the math
   reference to see the fix.)

Apply the right *pedagogy*, not just the right widgets — sequence matters (open the curiosity
gap → pre-train the term → concrete widget → predict-then-reveal → isolate one variable →
fade to the symbol → reach the wrong state → recombine). The evidence and the full sequence
are in [`references/learning-science.md`](references/learning-science.md).

## Build recipe (single-file)

The reliable shape, all in one `.html`:

```
<style>  …all CSS; the warm-paper default theme, readable controls…  </style>

<div class="stage"> <svg> or <canvas> </svg> </div>     ← the visual
<div class="controls"> sliders / toggles / reset </div>  ← the reader's grip
<div class="readout"> live numbers </div>                 ← the consequence

<script>
  const state = { … };                 // single source of truth
  function render() { …draw from state… }   // pure: state → pixels
  // every control mutates state then calls render() (or rAF if animated)
  input.oninput = e => { state.x = +e.target.value; render(); };
  render();                            // first paint
</script>
```

Principles that keep it clean:
- **One `state` object, one `render()`.** Controls mutate state and re-render. No scattered
  DOM mutation. This is the React mental model without React.
- **SVG for crisp boxes/labels/arrows that need DOM**; **canvas for many particles, pixels,
  or per-frame redraw**. Mixing is fine (canvas stage, HTML labels over it).
- **`requestAnimationFrame` only if something animates on its own.** A slider-driven
  explainer often needs no loop at all — render on input. Don't add a loop you don't need.
- **Responsive via `viewBox`** (SVG) or a resize handler (canvas). Use a `<style>` `clamp()`
  layout so it's legible on a laptop and a phone.
- **No reduced-motion suppression** in personal projects (see `motion-preference-rule`).

## Verify it before delivering

Per `verify-outputs-rule`, open the actual artifact and confirm it *teaches*, don't assume:
1. **Serve it, don't `file://` it.** Playwright MCP **blocks the `file:` protocol** — navigating
   to a `file://` path errors out. Serve the folder on a free port first
   (`~/dev/central/scripts/serve <dir> --bg` prints a `http://localhost:<port>/` URL), then
   `mcp__playwright__browser_navigate` to `…/<file>.html` → `browser_take_screenshot`. Look:
   does the visual read? Are labels legible? Stop the server when done (`serve --stop <dir>`).
2. **Drive the controls** and confirm the cause→effect actually fires — move the slider /
   click the toggle via `browser_evaluate` (read back the readout's text) or `browser_drag`,
   screenshot again, and verify the picture AND the number changed the way the concept says
   they should. A control that doesn't move the picture is the explainer's version of a
   vacuous green test. (Check each widget's readout updates — independent of the rendering.)
3. Check the baseline/contrast is visible, not just asserted.
4. Then deliver: it's a static file, so a `file://` **link** opens it directly for the *user*
   (the `file:` block is Playwright-only, not the OS). Give the clickable `file://` link (see
   `terminal-file-links-rule`); optionally open it in the user's browser so they can play
   immediately.

Showcase artifact, not a repo doc → it goes to `~/Desktop/cc-<project>/` (see
`file-output-rule`), unless it's embedded in a repo.

## Worked examples

- `assets/example-slot-alignment.html` — explains why a generated-art pipeline's HTML control
  overlays drift off the painted hardware. Moves 1–7: a draggable "paint drift" slider,
  blueprint/art/overlay layer toggles, a live misalignment readout, a pipeline selector, and a
  "masked-inpaint fix" toggle that forces drift to zero. Clean end-to-end clone target.
- `assets/example-auto-balance.html` — a 10-section explainer of a visual-balance auto-balancer
  (see-saw → optical center → centroid → ink-density → box-vs-pixel → discrepancy → ridge
  regression → trust dial → hill-climb). Shows the warm-paper default theme, predict-then-reveal
  prompts, wiki-style structure, and per-section pedagogy margin notes. **It also demonstrates
  the math anti-pattern on purpose:** its §7 typesets the ridge equation but leaves it inert —
  exactly what `references/interactive-math.md` exists to fix. Study it for the moves and the
  theme; study the math reference for what §7 should have been.

## Related

- `design` — make it *look* good once it works (typography, color, spacing). Its
  **design-spatial §6** ("Balance is measurable") is the quantitative balance method an
  explorable about layout would teach — centroid, optical center, pixel oracle.
- `lookdev` / `lookdev-auto` — for *tuning a parameter by eye*, a different job (those
  judge an output; this teaches a concept).
- `render-tool-rule` — prefer web/WebGL over Blender for visuals.
- `web-dev-rule` — if it grows into a served app, port/worktree discipline.
