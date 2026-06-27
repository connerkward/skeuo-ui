# Learning science for explorables — the empirical + theoretical basis

Load this when you want an explorable to actually *teach*, not just look interactive.
Every move in the main SKILL.md traces to a finding below. Cite the principle when you
use it (the explorable itself can name it in a margin note — readers trust a method that
shows its sources, and naming the principle is itself a retrieval cue).

The throughline: **understanding is built, not transmitted** (constructivism — Jean
Piaget; Seymour Papert's *Mindstorms*, 1980, "constructionism": you learn most when you
build a public artifact you can manipulate). An explorable is a constructionist object.

---

## The principles (finding → the explorable move it licenses)

| Principle | Core finding & source | What it buys you in an explorable |
|---|---|---|
| **Generation effect** | Self-generated answers are retained far better than read ones (Slamecka & Graf, 1978). | The reader *drives* the variable and produces the outcome — don't autoplay it for them. |
| **Retrieval / testing effect** | Retrieving beats re-studying for long-term retention (Roediger & Karpicke, 2006, *Test-enhanced learning*). | A **predict-before-reveal** prompt before each key result. The act of guessing is the learning. |
| **Predict–Observe–Explain (POE)** | Eliciting a commitment, then confronting it with the real result, drives conceptual change (White & Gunstone, *Probing Understanding*, 1992). | "Predict what happens when you raise λ" → they move it → "reconcile what you saw." |
| **Productive failure** | Letting learners struggle on a problem *before* instruction improves conceptual transfer vs. instruction-first (Manu Kapur, 2008). | Let them *try to balance the layout by hand* before you reveal the rule. The flailing primes the lesson. |
| **Concreteness fading** | Concrete → iconic → symbolic, *in that order*, beats concrete-only or abstract-only (Bruner, 1966; Goldstone & Son, 2005; Fyfe, McNeil, Son & Goldstone, 2014, review). | See-saw you drag → centroid dots → the Σ equation. Never open on the equation. |
| **Variation theory** | You discern a feature only by experiencing it *vary while everything else is held constant* (Ference Marton, *Necessary Conditions of Learning*, 2015). | One-variable widgets: freeze the geometry, vary *only* ink-density. The contrast is the concept. |
| **Cognitive load theory** | Working memory is tiny; manage intrinsic load, cut extraneous load, free capacity for schema-building (John Sweller, 1988; Sweller, van Merriënboer & Paas, 1998/2019). | Segment into one idea per widget. Kill decorative motion. Don't make them hold 5 variables at once. |
| **Worked-example effect** | Novices learn more from studying worked steps than from unguided problem-solving (Sweller & Cooper, 1985). | Show the fully-worked case first; *then* hand over the controls (faded guidance). |
| **Multimedia principles** | 12 evidence-based principles for words+pictures (Richard Mayer, *Multimedia Learning*, 2009/2021). The load-bearing ones here: **signaling**, **segmenting**, **pre-training**, **spatial contiguity**, **coherence**. | Pre-teach the key term before the widget; put labels *on* the moving thing (contiguity); cut anything not serving the idea (coherence). |
| **Dual coding** | Verbal and visual channels are separate and additive (Allan Paivio, 1971/1986). | Prose *and* a manipulable picture, carrying the same idea two ways — not prose alone, not a wordless animation. |
| **Self-explanation effect** | Learners who explain steps to themselves learn more, even without feedback (Chi, Bassok, Lewis, Reimann & Glaser, 1989). | Prompts that ask *why*, not just *what*: "why does the heavy element need the shorter lever?" |
| **Conceptual change** | A sticky misconception only yields when the learner feels it *fail* (Posner, Strike, Hewson & Gertzog, 1982). | Make the wrong intuition visibly break — the "50% looks centered" dot that reads as *low* against the optical line. |
| **Desirable difficulties** | Conditions that slow acquisition but improve retention & transfer: spacing, interleaving, testing, generation, variation (Robert & Elizabeth Bjork, 2011). | Don't smooth every bump. A small guess-and-check loop sticks better than a frictionless reveal. |
| **ZPD & scaffolding** | Teach just beyond independent reach, with support that *fades* (Lev Vygotsky, 1978; Wood, Bruner & Ross, 1976). | Layer toggles: start with support (the blueprint overlay), let the reader peel it away as they gain footing. |
| **Information-gap curiosity** | Curiosity spikes when a gap opens between what you know and want to know (George Loewenstein, 1994). | Open each section with the *question*, not the answer. Create the gap, then let them close it. |
| **Embodied / direct manipulation** | Reasoning is faster and deeper when the abstraction is a thing you physically move (Bret Victor, "Kill Math" & "Media for Thinking the Unthinkable", 2011–13). | Make the variable a *handle you drag*, not a number you type. The body is part of the thinking. |

---

## Assembling a whole explorable (the sequence, not just the parts)

A good explorable is these principles *in order*, not a pile of widgets:

1. **Open the gap** (curiosity). One sentence that poses the question and makes the reader
   want the answer. Not "This page explains centroids." → "When does a lopsided page still
   *feel* balanced?"
2. **Pre-train the term** (Mayer: pre-training). Name and define the one new word before the
   widget that uses it, so working memory isn't split between vocabulary and mechanism.
3. **Concrete widget first** (concreteness fading, productive failure). The graspable object.
   Let them fail at it by hand before the rule appears.
4. **Predict → reveal** (retrieval, POE). Ask for a commitment; then the widget or a reveal
   shows the truth; then reconcile.
5. **Isolate one variable** (variation theory, cognitive load). Each widget moves *one* thing.
   Multi-variable only after the singles are solid.
6. **Fade to the symbol** (concreteness fading). Now the equation — and make *it* manipulable
   too (see `interactive-math.md`), so the notation inherits the intuition.
7. **Reach the wrong state** (conceptual change, desirable difficulty). Let them break it; the
   failure mode is where the understanding consolidates.
8. **Recombine** (segmenting → synthesis). Only at the end do the isolated parts run together
   as the whole system.
9. **Name the payoff and the method.** Close with the transferable idea, and (optionally) a
   margin note citing the pedagogy used — transparency is itself a retrieval cue and earns
   trust.

---

## Anti-patterns (the ways explorables fail to teach)

- **The screensaver.** It autoplays and loops; the reader watches, hands in lap. No
  generation, no retrieval. Fix: take away the play button, give them the slider.
- **The cockpit.** Twelve sliders at once. Extraneous load swamps the signal. Fix: segment;
  one variable per widget; reveal complexity in layers.
- **Tell-don't-show.** A paragraph of explanation with a static diagram that *illustrates*
  rather than *responds*. If moving the input doesn't move the picture, it's a screenshot.
- **The equation cold-open.** Leading with the symbolic form. Violates concreteness fading;
  loses everyone without the schema already. Earn the equation; don't open on it.
- **Frictionless reveal.** Every answer one click away with no prediction asked. Removes the
  desirable difficulty that makes it stick. Always ask for a guess first.
- **Unfalsifiable success.** Claiming "this teaches X" without watching a control actually
  drive the consequence. Mirror of `verify-outputs-rule`: drive it, see the effect, or you
  don't know it teaches.
