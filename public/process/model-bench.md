# Model template-adherence benchmark (frog skin)

How well do image-EDIT models keep painted controls on the blueprint's KNOWN template
coordinates? Lower mean deviation = better adherence. `wells painted-over` = sockets the
model destroyed (no recessed dark well survives → undetectable); this is the worst failure
mode and is reported alongside the deviation metric.

Ground truth: the frog `template.json` rects (16 controls measured: buttons, knobs, EQ
sliders, seek, toggles). 6 models x 3 wildly different themes = 18 paint jobs.
Detection: re-apply frog alpha, then within each control's prior window find the recessed
dark well (local-adaptive: blob darker than its local body ring + plausible fill + near
the prior), centroid offset from the template rect center. Contact sheet: `model-bench.png`.

Ranked by MEAN template deviation across the 3 themes:

| rank | model | mean dev px | mean dev %diag | worst single px | wells painted-over /48 | per-theme mean dev (vic/ramen/olmec) | per-theme painted-over |
|---|---|---|---|---|---|---|---|
| 1 | gpt-image-2 | 1.9 | 0.10% | 6 | 1 | 1.0 / 1.3 / 3.4 | 0 / 0 / 1 |
| 2 | nano-banana-1 | 4.1 | 0.22% | 38 | 2 | 1.0 / 3.8 / 7.6 | 0 / 1 / 1 |
| 3 | nano-banana-pro | 4.3 | 0.23% | 80 | 0 | 1.4 / 6.3 / 5.1 | 0 / 0 / 0 |
| 4 | nano-banana-2 | 6.3 | 0.34% | 35 | 0 | 3.1 / 9.7 / 6.2 | 0 / 0 / 0 |
| 5 | seedream4 | 8.8 | 0.48% | 30 | 5 | 7.6 / 15.5 / 3.4 | 1 / 4 / 0 |
| 6 | qwen-edit | 22.9 | 1.24% | 94 | 0 | 22.0 / 20.4 / 26.4 | 0 / 0 / 0 |
Canvas diagonal = 1846 px (1024x1536). "worst single px" = the single most-displaced
detected well across that model's 3 themes.

## Verdict

- **gpt-image-2/edit — best adherence.** 1.9 px mean (0.10% of diagonal); controls land
  essentially dead-center on the template rects across all three themes. Its one "painted-
  over" count is the thin `seek` groove on olmec, which is borderline-present. Strongest at
  keeping controls where the blueprint put them.
- **nano-banana-pro (gemini-3-pro/edit, the reference) and nano-banana-1 (nano-banana/edit)**
  are the next tier: 4.1-4.3 px mean, near-pixel layout fidelity. nano-banana-pro destroyed
  zero wells across all 18 controls-per-theme; its 80 px "worst single" is one drifted switch
  on the neon ramen theme, not a structural failure.
- **nano-banana-2 (gemini-3.1-flash/edit):** 6.3 px, all wells kept — good, slightly looser
  than pro/1.
- **seedream-v4/edit — destroys wells.** 5 of 48 sockets painted over, concentrated on the
  ramen theme where it reinterpreted the playlist+seek region as a literal ramen bowl,
  deleting the lower controls (visible as red-X in the contact sheet). When it keeps a well
  it places it decently (olmec 3.4 px), but it is the model most willing to redesign the
  layout to fit the theme.
- **qwen-image-edit — worst registration.** 22.9 px mean (1.24% of diagonal), consistent
  global up-left offset of the whole control cluster on every theme. It keeps all the wells
  (0 painted over) but registers them poorly against the template.

Bottom line: gpt-image-2/edit best keeps controls on the blueprint coordinates across wildly
different themes; nano-banana-pro/1 are close behind with zero/near-zero destruction.
seedream-v4 is the one that DESTROYS wells (reshapes the layout to the theme); qwen keeps
wells but mis-registers them by ~20 px.
