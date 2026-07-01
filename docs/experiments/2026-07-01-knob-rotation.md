# Knob rotation technique — how a rotary knob should show its value — 2026-07-01

**Question:** On Y2K / WMP / Winamp skins, how should a rotary knob render its
value? Which technique reads as *tactile* — a static cap with a CSS-drawn pointer,
or a physically-rotating cap under a fixed light?

**Method:** Themed knobs painted with **nano-banana-2** (`fal-ai/gemini-3.1-flash-image-preview/edit`)
from a UI blueprint, aspect **1:1** (matches the blueprint — see the aspect-drift
ADR, 2026-06-23). Caps cut with **rembg / BiRefNet**. Compared live in an interactive
studio (drag any knob; `value→angle = −135° + value·270°`). Two experiments:

- **(a) PACKED** — isolated socket+knob patches across **6 materials** (glossy
  chrome, black glass, brushed aluminium, matte gunmetal, Bondi-blue plastic,
  pearlescent white). Scratch: `/tmp/knobexp`.
- **(b) WHOLE SKIN** — complete generated devices (full media-player skins), knob
  caps cut **in-place** from the finished paint at their authored center & radius,
  across a **glossy** and a **matte** device. Scratch: `/tmp/knobskin`.

**Candidates / conditions:**

| # | Technique | Notes |
|---|-----------|-------|
| ① | Static cap + **CSS-rotated pointer line** | the shipped approach |
| ② | **Rotate the cap** + a **PINNED** (non-rotating) radial specular overlay | cheap modern equivalent of Winamp's pre-lit rotation frames |
| ③ | Static cap, no indicator | reference / control |

**Verdict (human-reviewed — Conner, 2026-07-01): adopt ② (rotate cap + pinned
specular) as the knob technique.**

- ② is clearly **more tactile on glossy / reflective caps** (chrome, black-glass,
  translucent): the metal visibly *turns* under a fixed highlight, so the knurl /
  notch reads as real rotation.
- On **matte** it's a near-tie (no strong specular to pin), but ② was still chosen
  for **consistency** — one technique across all materials.

**Requirements this surfaced (for the pipeline):**
1. Knob caps must be authored with a **neutral / symmetric baked specular**, so the
   pinned overlay is the *sole* light source — otherwise a baked-in highlight rotates
   with the cap and fights the fixed one.
2. A **`gloss` signal from the Director material pass** should drive **specular
   intensity** of the pinned overlay (strong on chrome/glass, near-zero on matte).

**Seating fix (whole-skin, incidental win):** cutting the cap **in-place** at its
known center + radius and rotating it about *that exact center* keeps it **seated at
every angle** — no packed-patch drift. Verified at **0° / ±135°** (see the two
whole-skin shots).

**Known flaws of the PACKED version** (fixed by the whole-skin approach + a neutral
cutout background — a follow-up experiment):
- **BiRefNet white-on-white miscut** of the pearlescent-white knob (cap silhouette
  lost against a light background).
- **Packed-patch misalignment** — patches reassembled off their sockets; the
  in-place whole-skin cut eliminates this.

**Candidate model:** all skins/knobs painted with **nano-banana-2**
(`fal-ai/gemini-3.1-flash-image-preview/edit`), 1:1.

## Artifacts

- **Whole-skin comparison, knob at +135°** (①=CSS indicator vs ②=rotate+pinned
  specular; glossy + matte devices) —
  [`assets/2026-07-01-knob-wholeskin-pos135.png`](./assets/2026-07-01-knob-wholeskin-pos135.png)
- **Whole-skin comparison, knob at −135°** (proves seated at the opposite extreme) —
  [`assets/2026-07-01-knob-wholeskin-neg135.png`](./assets/2026-07-01-knob-wholeskin-neg135.png)
- **Packed 6-material sheet** (isolated socket+knob patches; shows the BiRefNet
  miscut + packed misalignment flaws) —
  [`assets/2026-07-01-knob-packed-6materials.png`](./assets/2026-07-01-knob-packed-6materials.png)

Re-run inputs (prompts, per-knob centers/radii, sprite maps): `/tmp/knobskin/meta.json`,
`/tmp/knobskin/gen_fal.py`, `/tmp/knobexp/`.
