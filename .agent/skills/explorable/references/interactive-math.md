# Teaching math in an explorable — build intuition, don't display notation

Load this whenever an explorable touches real math (a transform, a fit, a loss, a
probability, an optimization). The failure to avoid: **printing the equation and
annotating its terms is NOT teaching it.** A labelled formula is a *spec*; intuition
comes from making the math a thing the reader can *move*.

> Worked counter-example, in this very skill: the auto-balance explainer's §7 showed the
> ridge equation `w = (XᵀX + λI)⁻¹Xᵀy` and labelled the symbols — correct, but inert. The
> reader still can't *feel* what a "linear map" does or why λ stabilizes it. This file is
> how to fix exactly that.

The lineage: **Grant Sanderson / 3Blue1Brown** ("Essence of Linear Algebra" — *what does
this operation do to space?*), **Bret Victor** ("Kill Math", "Scrubbing Calculator" —
every number is a draggable handle), **Kalid Azad / BetterExplained** (the ADEPT order),
and the **multiple-representations** tradition (Richard Lesh's translation model; NCTM) —
symbolic ↔ graphical ↔ numeric ↔ verbal, all linked and live.

---

## The four rules of interactive math

1. **Intuition before formalism — the ADEPT order** (Azad). Present in this sequence,
   technical definition *last*: **A**nalogy → **D**iagram → **E**xample (concrete numbers)
   → **P**lain-English → **T**echnical. Most explanations run it backwards and lose everyone
   at symbol one.

2. **Show the object the math acts on.** Math is always *doing something to something*.
   Linear algebra acts on space (a grid, vectors). Regression acts on data points. A loss
   acts on a guess. Draw that object first; the equation is the *description* of the motion,
   not the lesson.

3. **Make every symbol a handle.** Each variable/coefficient in the formula should be a
   slider or a draggable point, and the picture must respond *in the same frame*. The reader
   learns what `λ` *is* by dragging `λ` and watching. (Victor: a number you can't scrub is a
   number you don't understand.)

4. **Link the representations.** When the reader drags a point, update the graph, the number,
   AND the symbolic form together. Seeing a coefficient in the equation change as the line
   tilts is what fuses notation to meaning (Lesh translation model).

Plus the build-up move: **assemble the formula term by term.** Start with the simplest true
version, add one term at a time with a toggle, each time showing what that term *does to the
picture*. `y = ax` → add `+b` (watch it lift off the origin) → add the `+λ‖w‖²` penalty
(watch the line resist steepening). Never reveal the whole expression at once.

---

## Recipe A — a *linear map* (the §7 weakness, done right)

A "linear map" / matrix is not a grid of numbers; it's **a transformation of space**, and a
matrix's columns are simply *where the basis vectors land*. The canonical 3B1B widget:

- Draw a coordinate grid with the unit basis vectors **î** (1,0) and **ĵ** (0,1) as arrows.
- The 2×2 matrix `[[a, c], [b, d]]` IS the new positions: column 1 = where **î** goes
  `(a,b)`, column 2 = where **ĵ** goes `(c,d)`.
- **Make î and ĵ draggable** (or four sliders a,b,c,d). As the reader moves them, transform
  the whole grid and a sample shape (a letter, a unit square) live: every point `(x,y)` maps
  to `x·î' + y·ĵ'`.
- Show the **determinant as the area** of the transformed unit square — a live number — so
  "det = 0" becomes *visibly* "space collapsed to a line." Negative det = the grid flipped.
- Now the reader *sees* matrix-multiply = "follow the basis vectors," and the symbolic
  `M·v` is just bookkeeping for the motion they just performed.

This same picture demystifies the auto-balancer's "features → δ" map: it's a (1×n) linear
map — a **weighted sum** — which deserves its own simpler widget:

## Recipe B — a *weighted sum / dot product* (`w · features`)

The honest name for "linear model" in most ML contexts. Don't show `w·x`; build it:

- A row of feature sliders `f₁ … fₙ` (the inputs).
- For each, a weight `wᵢ` (a second slider or a draggable bar).
- Draw each **contribution** `wᵢ·fᵢ` as a signed bar; stack them; the **sum** is the
  prediction, shown as the running total.
- The reader nudges one feature and watches *its* bar grow and the total move. Now `Σ wᵢfᵢ`
  is obvious, and a "linear layer" is just "many of these."

## Recipe C — *least-squares regression* (feel the fit)

- Plot draggable data points.
- Draw the best-fit line; recompute it live as points move (closed form: slope =
  cov(x,y)/var(x), intercept = ȳ − slope·x̄).
- **Draw the residuals as vertical sticks** from each point to the line — the thing being
  minimized — and show **Σ residual²** as a live number (optionally as literal squares whose
  *areas* sum, so "least squares" is visual).
- Add a draggable **"your guess" line** alongside the optimal one: the reader tries to beat
  least-squares by hand, watches their SSE vs the minimum, and *feels* why the formula wins
  (productive failure → the reveal).

## Recipe D — *ridge regression & the bias–variance trade-off* (why λ exists)

Build on C; this is the intuition §7 skipped:

- Add a **λ slider**. Show the weight(s) as bars that **shrink toward zero** as λ grows, and
  the line **flatten toward the no-correction baseline**. λ is a *force pulling the fit toward
  "do nothing."*
- Make the **instability visible**: place two points at nearly the same x with different y
  (the real degeneracy that blew the scalar fit's slope to ~32). At λ=0 the line whips around
  wildly as you nudge a point; crank λ and it barely moves. The reader *sees* "λ trades a
  little fit for a lot of stability" — bias–variance, felt, not stated.
- Only now show the closed form, term by term: ordinary `w = (XᵀX)⁻¹Xᵀy`, then *add* the
  `+ λI` and connect it to the flattening they just watched. The `λI` is the picture.

Minimal solver to embed (2×2 ridge normal equations, no library):
```js
// fit y = a·x + b with ridge penalty λ on [a,b]
function ridge(pts, lam){
  let Sxx=0,Sx=0,Sxy=0,Sy=0,n=pts.length;
  for(const p of pts){Sxx+=p.x*p.x;Sx+=p.x;Sxy+=p.x*p.y;Sy+=p.y;}
  const A=[[Sxx+lam,Sx],[Sx,n+lam]], B=[Sxy,Sy];          // (XᵀX + λI)
  const det=A[0][0]*A[1][1]-A[0][1]*A[1][0] || 1e-9;
  return { a:(B[0]*A[1][1]-A[0][1]*B[1])/det,             // (·)⁻¹ Xᵀy
           b:(A[0][0]*B[1]-B[0]*A[1][0])/det };
}
```

---

## Typesetting the symbols (once you've earned them)

Intuition first — but when you *do* show the formula, set it properly:
- **Styled HTML + Unicode is enough and works offline**: `Σ ∫ √ ‖·‖ ≈ ≤ ∇² σ λ` plus
  `<sub>/<sup>`, a serif-math or mono block set off from prose. Prefer this — no dependency.
- Reach for **KaTeX/MathJax only** when expressions genuinely need stacked fractions,
  matrices, or big operators that Unicode can't fake. (CDN dependency — note it; the skill's
  default is dependency-free.)
- **Annotate every symbol** in one line each directly below (this part §7 *did* do right) —
  but the annotation is the *floor*, the interactive picture is the lesson.

## The one-line test

Before shipping a math explainer: *can the reader change a symbol and watch the meaning
move?* If the math is read-only — even if it's beautifully typeset and fully annotated —
you displayed notation, you didn't teach the idea. Go make a symbol draggable.
