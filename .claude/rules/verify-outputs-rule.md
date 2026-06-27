---
name: "verify-outputs-rule"
id: "verify-outputs-01"
description: "Before calling any result done/working/fixed, inspect the real artifact against the goal, verify it independently of what you tuned, and compare against the baseline/input."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Verify the actual output — and verify it independently

Before calling any result done / working / fixed / clean / correct, **inspect the
real artifact against the goal**, and make sure the check that convinced you is
**independent** of the thing you were tuning. This is the always-on generalization of
software-engineering-rule's "Make green mean something" — from tests to ALL claimed
results, and especially to visual / generated / media outputs.

This rule exists because of a concrete, expensive failure mode (Muser relief
de-perspective, 2026-06): a "spatial rectifier" was reported as working — "tilt
24°→2°, fixed" — across many iterations, while it was visibly **rotating level
reliefs crooked and skewing frontal ones**. The number was believed; the image was
never opened. Two compounding sins, both covered below.

## 1. Look at the artifact. A metric is not the artifact.

- For an **image / video / render / UI**: open it and look. Does it actually achieve
  the goal? Compare it side-by-side against the **input and against doing nothing**.
- For **code / data**: run it and read the real output, not a log line that says it
  ran. Open the file, print the rows, check the values.
- "A number went down / a test passed / it saved without error" is **not** evidence
  the output is good. The artifact is the evidence. If you didn't look at it, you
  don't know — so don't claim.

## 2. The check must be INDEPENDENT of what you optimized.

A validation that shares the model, assumption, or data of the thing you tuned is
**circular** — it will report success even when the output is wrong.

- Trap (the one that burned a day): rectify an image so a model's estimated tilt
  goes to ~0, then *validate by re-measuring tilt with the same model*. It always
  reads ~0 by construction — it proved nothing while the image got worse.
- Independent checks: a **held-out** signal, a **different method/model**, a
  **physical invariant** (straight lines stay straight, parallel stays parallel,
  known answer is recovered), or **direct visual inspection** against the goal.
- If your only evidence is a metric defined by the same code path you optimized,
  treat it as **no evidence** until corroborated independently.

## 3. Compare against the baseline / input.

"Improved over my previous attempt" ≠ "better than the input." Always confirm the
output beats **doing nothing**. A pipeline that distorts a clean input is worse than
no pipeline — that only shows up when you put input and output next to each other.

## 4. No positive adjectives on unverified output.

Do not write "clean / fixed / works / frontal / correct / done" about anything you
have not directly inspected against the goal. Lead with **what you actually
observed** ("I opened the output: the frame is skewed, the corners are 30% black"),
not what you hoped or what a proxy implied. When you haven't verified, say that
plainly instead of implying success.

## 5. When the fix doesn't hold, say so and stop spinning.

If inspection shows it's still wrong, report that directly and diagnose — don't
re-frame a bad result as partial success, and don't keep shipping adjacent
"improvements" on a broken foundation. Surfacing "this approach is the wrong tool,
here's why" is a successful outcome, not a failure to hide.

## 6. Batches: inspect individuals, and distrust self-fulfilling metrics.

When you evaluate a **set** (N skins, N files, N renders), a thumbnail **contact
sheet is an index, not inspection** — a 300px cell cannot show whether a mask fits a
control or a box lands on the right object. To claim a batch works you must **open
the individual full-res artifacts**, enough of them to span the distribution, and —
critically — **inspect the BEST-scoring and WORST-scoring items, not a comfortable
middle.** The failure usually hides inside the ones the metric calls "passing."

And before you trust an aggregate ("22/30 passed", "90% coverage"), ask: **could
this metric pass on garbage?** If a post-processing step *guarantees* the metric,
the metric is circular and measures the post-processor, not the result. This rule's
section 2 covers "validate with the same model you tuned"; this is its batch cousin:

- Concrete burn (skeuo-ui, 2026-06): a control-detector's output was passed through a
  **shape-fit** that always emits a prior-sized clean rounded-rect, then scored by a
  size/aspect **"plausibility" check**. Of course it passed 22/30 — the shape-fit
  *manufactured* plausible shapes. The agent reported "params GENERALIZE" off the
  count. Opening the individual images showed masks **smeared across a statue's
  torso and a giant ellipse over a dial** — the detector had failed on every
  low-contrast / radial skin. The count proved nothing; the post-process defined it.
- The tell: your "score" is computed downstream of a step whose job is to make
  results look like what the score rewards. Treat that as **no evidence**. Score the
  thing *before* the cosmetic step, or score against an independent signal (does the
  mask sit on the actual painted control?), or just **look at each one**.

## 7. Verify in the REAL runtime — a reimplementation or preview is NOT verification.

The check must exercise the **same code path that ships**. A stand-in that *mimics*
the real thing can pass green while the real thing is broken — and you will believe
the stand-in. This is the proxy trap, and it is the most expensive version of "a
metric is not the artifact": the metric here is *a second implementation you trust
because you wrote it.*

- Concrete burn (skeuo-ui, 2026-06-23, ~10 rounds wasted): a generate→cut→detect→
  render pipeline was "proven" with `/tmp` **Python** scripts that re-did the
  TypeScript cut/composite by hand. The Python previews looked great every round, so
  it was repeatedly called "fixed / repeatable / works." The **actual app render was
  broken the entire time** (square sprites squished into non-square button boxes →
  ovals; a control `<img>` that failed to decode → empty sockets). The Python proxy
  could not see any of it because it wasn't the shipping renderer. Loading the real
  app on round one would have shown it immediately.
- The tell: your evidence is something *you built to stand in for* the real system —
  a hand-port, a mock, a curl that skips the client half, a screenshot of a separate
  harness rather than the product. Treat that as **no evidence** about the real path.
- **Do instead:** run the actual app / the actual shipped function / the real
  end-to-end flow, and inspect *its* output. If the real path is hard to drive
  (needs the browser, a device, a build), drive it anyway — that difficulty is
  exactly why the proxy was tempting and exactly why it lies.
- **No "works / fixed / done / repeatable" until you have shown the SHIPPED artifact
  end-to-end** — not a preview of it, not "the algorithm is proven," not "it's wired
  and should work." Wire it, run the real thing, look, *then* claim. (Reinforces §4:
  no positive adjectives on unverified output — and a proxy leaves it unverified.)

## The one-line test before you hit send

"Did I open the actual output, compare it to the input, and confirm the thing that
convinced me isn't just my own assumption echoed back?" If no — go do that first.
For a **batch**: "Did I open individual full-res items — including the worst — or am
I trusting a thumbnail grid and a count a post-process guaranteed?"
And: **"Is my evidence the REAL shipping artifact, or a reimplementation/preview I
made that only mimics it?"** If it's a proxy, it is not verified — go run the real
path.
