# skeuo-ui — TODO

## Generation pipeline
- [ ] **Remove the expansion (envelope) step.** The `ENVELOPE_PROMPT` pass grows a
  flat silhouette around the wells before the paint pass. Cut it — paint directly
  from the wells-only blueprint (halves the fal cost per skin, removes a pass).
- [ ] **Fix masking — stop relying on the white-key cutout.** The current
  `cutoutAlpha` keys near-white → transparent + largest-connected-component +
  fill-holes + erode. It's error-prone: keys out light/white parts of the device,
  leaves holes and ragged edges (visible broken spots in the egg/grape proofs).
  Prefer the model emitting transparency directly; fall back to a real segmentation
  model (BiRefNet / bria rembg) if the generators can't. Chroma-key is a last resort.

## Sprite-sheet controls (prototype proven 2026-06-22)
- [ ] In-pass button generation: paint emits a labeled sprite strip below the device
  in the same pass (cost-neutral), client cuts it into per-control sprites, generated
  skins render their own material-matched sprites instead of generic donor sprites.
  Add "circular buttons matching the round slots" to the prompt (fixes nano-banana-2).

## App
- [ ] Delete-skin button (removes from localStorage + R2; needs a global-delete gate).
- [ ] Native rebuilds (macOS widget + iOS TestFlight) to ship this session's fixes.
