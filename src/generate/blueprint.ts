// ============================================================
// SVG blueprint + alpha-mask drawer — a TS port of `_draw_regions`,
// `draw_wells_only` and `region_mask` from generation/wild_sculpt.py.
//
// Produces pure SVG strings (no canvas, no native deps) so the same
// code rasterizes in a Cloudflare Worker (resvg-wasm), in Node
// (resvg-js), or in the browser (an <img> src). The "wells-only"
// blueprint is the FIRST fal image (envelope step); the region mask
// is the alpha (no BiRefNet — the layout IS the body by construction).
// ============================================================
import type { Region } from "../template/schema";
import { GEN_W, GEN_H } from "./layouts";

const WELL = "rgb(20,22,24)";
const EDGE = "rgb(74,78,82)";
const SCREEN = "rgb(12,13,15)";

// one region → its SVG primitive. Mirrors `_draw_regions`: knobs and
// round buttons are filled wells with a rim; displays are dark glass;
// slider-arc is a stroked arc; everything else a rounded rect well.
function regionSvg(r: Region): string {
  const rc = r.rect;
  const x0 = rc.x * GEN_W, y0 = rc.y * GEN_H;
  const w = rc.w * GEN_W, h = rc.h * GEN_H;
  const x1 = x0 + w, y1 = y0 + h;
  if (r.kind === "slider-arc" && r.arc) {
    const i = 0.06 * w;                 // ring radius = 0.88 of half-box (matches live control)
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const rr = (w - 2 * i) / 2;
    return arcPath(cx, cy, rr, r.arc.start, r.arc.end, 18, WELL, "none");
  }
  if (r.kind === "knob" || (r.kind === "button" && r.shape === "ellipse")) {
    return ellipse(x0, y0, w, h, WELL, EDGE, 4);
  }
  if (r.kind === "display") {
    if (r.shape === "ellipse") return ellipse(x0, y0, w, h, SCREEN, EDGE, 6);
    return roundRect(x0, y0, w, h, 12, SCREEN, EDGE, 5);
  }
  return roundRect(x0, y0, w, h, 8, WELL, EDGE, 4);
}

function ellipse(x: number, y: number, w: number, h: number, fill: string, stroke: string, sw: number): string {
  return `<ellipse cx="${x + w / 2}" cy="${y + h / 2}" rx="${w / 2}" ry="${h / 2}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
}
function roundRect(x: number, y: number, w: number, h: number, rad: number, fill: string, stroke: string, sw: number, filterId?: string): string {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rad}" ry="${rad}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"${filterId ? ` filter="url(#${filterId})"` : ""}/>`;
}
// PIL's ImageDraw.arc sweeps clockwise from start→end in screen (y-down) degrees,
// which is exactly SVG's coordinate sense; we emit an explicit A path.
function arcPath(cx: number, cy: number, r: number, a0: number, a1: number, width: number, stroke: string, fill: string): string {
  const p = (a: number) => [cx + r * Math.cos((a * Math.PI) / 180), cy + r * Math.sin((a * Math.PI) / 180)];
  const [sx, sy] = p(a0); const [ex, ey] = p(a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `<path d="M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}" fill="${fill}" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round"/>`;
}

// The "wells-only" blueprint — fal's ENVELOPE input. Equivalent of
// draw_wells_only(): only the recessed wells/screens drawn, no body fill. The
// background is the chosen CUTOUT KEY colour (default white) so the envelope the
// paint grows from already carries the backdrop the cutout will key against.
export function wellsOnlySvg(regs: Region[], bg = "white"): string {
  const body = regs.map(regionSvg).join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${GEN_W}" height="${GEN_H}" viewBox="0 0 ${GEN_W} ${GEN_H}"><rect width="${GEN_W}" height="${GEN_H}" fill="${bg}"/>${body}</svg>`;
}

// The CONSTANT alpha mask — every drawn region, solid white, dilated. Equivalent
// of region_mask(): teeth/jaws the model paints over a screen must not cut holes,
// so the layout is part of the body by construction. We render the union of the
// region footprints (plus a generous stroke that stands in for the iterations=10
// binary dilation) as the silhouette. This is intentionally a LOOSE alpha for v1:
// it guarantees no holes inside the controls, but does NOT trace the wild outline
// the way the Python mask (from the fal-generated envelope image) does. See the
// honest-stub note in functions/api/generate.ts.
// ============================================================
// cutoutAlpha — derive the FINAL alpha from the PAINTED silhouette, not the
// region union. The paint prompt forces "everything outside the silhouette
// stays pure white", so the non-white body IS the real (expanded) outline.
// This replaces the shrink-wrapping regionMaskSvg alpha for the composite.
//
// rgba: tightly-packed RGBA bytes (W*H*4). Returns an 8-bit alpha plane (W*H):
//   1. body = pixel whose R,G,B are NOT all ≥ WHITE_CUTOFF (i.e. non-white).
//   2. keep the LARGEST connected component (4-connectivity) → drops stray
//      JPEG-speckle islands in the "white" margin.
//   3. fill INTERNAL holes: flood the background inward from the image border;
//      any non-body pixel the flood can't reach is enclosed (a dark control
//      well) → mark it opaque so wells don't punch through.
//   4. light 1px erode → kills the pale halo of near-white edge pixels.
// Pure, runtime-agnostic (no PNG codec) so both the Node dev server and the CF
// Worker share one implementation over their own decoded RGBA buffers.
// ============================================================
// ============================================================
// RGB = [r,g,b]. The cutout KEY colour the device was painted against. WHITE is
// the legacy/fallback backdrop (translucent & iridescent skins, whose body would
// be wrongly desaturated by a coloured-key despill — see cutoutColorAware).
export type RGB = [number, number, number];
export const KEY_WHITE: RGB = [255, 255, 255];
const isWhiteKey = (k: RGB) => k[0] >= 250 && k[1] >= 250 && k[2] >= 250;

// ============================================================
// cutoutColorAware — the STANDARD cutout. Paints are rendered on a flat CONTRASTING
// backdrop (a hue outside the device palette); this keys it out cleanly and fixes
// the two white-key failures at the source:
//   • a near-white screen on white bg is indistinguishable from the bg → kept or
//     dropped wrongly. On a coloured bg the screen ≠ bg, so it's unambiguous.
//   • backdrop leaking through thin gaps stays the backdrop colour → cut, not kept.
// Pipeline (per pixel, all pure-JS so dev-server + browser share it):
//   1. body  = pixels NOT within KEY_TOL of the backdrop colour (the colour key).
//   2. keep the LARGEST connected component (drops speckle islands).
//   3. COLOUR-AWARE FILL: flood the outside; an enclosed pixel becomes opaque ONLY
//      if it is NOT backdrop-coloured → dark screens/wells filled, backdrop that
//      leaked into an interior gap stays transparent (the colour-aware CUT).
//   4. 1px erode → drop the anti-aliased rim.
//   5. DESPILL: subtract the backdrop hue's chroma from every kept pixel so no
//      coloured fringe remains (skipped for a white key — no hue to suppress).
// MUTATES rgba in place: writes despilled RGB + the computed alpha. Returns rgba.
// For a WHITE key it reproduces the legacy cutoutAlpha exactly (fill ALL holes, no
// despill) so translucent/iridescent fallbacks are unchanged.
const KEY_TOL = 70;          // colour-key radius (Euclidean RGB) — a pixel within this of the key IS backdrop
const KEY_TOL2 = KEY_TOL * KEY_TOL;
export function cutoutColorAware(rgba: Uint8Array, W: number, H: number, key: RGB = KEY_WHITE): Uint8Array {
  if (isWhiteKey(key)) {                       // legacy path: identical to cutoutAlpha
    const alpha = cutoutAlpha(rgba, W, H);
    for (let i = 0; i < W * H; i++) rgba[i * 4 + 3] = alpha[i];
    return rgba;
  }
  const N = W * H;
  const [kr, kg, kb] = key;
  const dist2 = (i: number) => {
    const dr = rgba[i * 4] - kr, dg = rgba[i * 4 + 1] - kg, db = rgba[i * 4 + 2] - kb;
    return dr * dr + dg * dg + db * db;
  };
  // 1. body = NOT backdrop-coloured.
  const body = new Uint8Array(N);
  for (let i = 0; i < N; i++) if (dist2(i) > KEY_TOL2) body[i] = 1;

  // 2. largest connected component (4-connectivity BFS) — drops stray speckles.
  const label = new Int32Array(N).fill(-1);
  const queue = new Int32Array(N);
  let best = -1, bestSize = 0, cur = 0;
  for (let s = 0; s < N; s++) {
    if (!body[s] || label[s] !== -1) continue;
    let head = 0, tail = 0, size = 0;
    queue[tail++] = s; label[s] = cur;
    while (head < tail) {
      const p = queue[head++]; size++;
      const x = p % W, y = (p / W) | 0;
      if (x > 0 && body[p - 1] && label[p - 1] === -1) { label[p - 1] = cur; queue[tail++] = p - 1; }
      if (x < W - 1 && body[p + 1] && label[p + 1] === -1) { label[p + 1] = cur; queue[tail++] = p + 1; }
      if (y > 0 && body[p - W] && label[p - W] === -1) { label[p - W] = cur; queue[tail++] = p - W; }
      if (y < H - 1 && body[p + W] && label[p + W] === -1) { label[p + W] = cur; queue[tail++] = p + W; }
    }
    if (size > bestSize) { bestSize = size; best = cur; }
    cur++;
  }
  const mask = new Uint8Array(N);
  if (best >= 0) for (let i = 0; i < N; i++) if (label[i] === best) mask[i] = 1;

  // 3. colour-aware fill: flood the outside from the border; an enclosed pixel
  //    becomes opaque ONLY if it is NOT backdrop-coloured.
  const outside = new Uint8Array(N);
  let qh = 0, qt = 0;
  const push = (i: number) => { if (!mask[i] && !outside[i]) { outside[i] = 1; queue[qt++] = i; } };
  for (let x = 0; x < W; x++) { push(x); push((H - 1) * W + x); }
  for (let y = 0; y < H; y++) { push(y * W); push(y * W + W - 1); }
  while (qh < qt) {
    const p = queue[qh++];
    const x = p % W, y = (p / W) | 0;
    if (x > 0) push(p - 1);
    if (x < W - 1) push(p + 1);
    if (y > 0) push(p - W);
    if (y < H - 1) push(p + W);
  }
  for (let i = 0; i < N; i++) if (!outside[i] && dist2(i) > KEY_TOL2) mask[i] = 1; // enclosed & non-bg ⇒ opaque

  // 4. 1px erode → alpha.
  const alpha = new Uint8Array(N);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (!mask[i]) continue;
      const edge =
        (x > 0 && !mask[i - 1]) || (x < W - 1 && !mask[i + 1]) ||
        (y > 0 && !mask[i - W]) || (y < H - 1 && !mask[i + W]);
      alpha[i] = edge ? 0 : 255;
    }
  }

  // 5. despill: subtract the positive projection of each kept pixel's chroma onto
  //    the key's chroma direction — kills any backdrop-coloured fringe while leaving
  //    neutral and opposite-hue surfaces untouched.
  const km = (kr + kg + kb) / 3;
  let dxr = kr - km, dxg = kg - km, dxb = kb - km;
  const dn = Math.hypot(dxr, dxg, dxb) || 1;
  dxr /= dn; dxg /= dn; dxb /= dn;
  for (let i = 0; i < N; i++) {
    rgba[i * 4 + 3] = alpha[i];
    if (!alpha[i]) continue;
    const r = rgba[i * 4], g = rgba[i * 4 + 1], b = rgba[i * 4 + 2];
    const m = (r + g + b) / 3;
    const proj = (r - m) * dxr + (g - m) * dxg + (b - m) * dxb;
    if (proj > 0) {
      rgba[i * 4] = Math.max(0, Math.min(255, r - proj * dxr));
      rgba[i * 4 + 1] = Math.max(0, Math.min(255, g - proj * dxg));
      rgba[i * 4 + 2] = Math.max(0, Math.min(255, b - proj * dxb));
    }
  }
  return rgba;
}

const WHITE_CUTOFF = 244; // R,G,B all ≥ this ⇒ background (pure white)
export function cutoutAlpha(rgba: Uint8Array, W: number, H: number): Uint8Array {
  const N = W * H;
  // 1. body mask: non-white pixels.
  const body = new Uint8Array(N);
  for (let i = 0; i < N; i++) {
    const r = rgba[i * 4], g = rgba[i * 4 + 1], b = rgba[i * 4 + 2];
    if (!(r >= WHITE_CUTOFF && g >= WHITE_CUTOFF && b >= WHITE_CUTOFF)) body[i] = 1;
  }

  // 2. largest connected component of body (4-connectivity, iterative BFS).
  const label = new Int32Array(N).fill(-1);
  const queue = new Int32Array(N);
  let best = -1, bestSize = 0, cur = 0;
  for (let s = 0; s < N; s++) {
    if (!body[s] || label[s] !== -1) continue;
    let head = 0, tail = 0, size = 0;
    queue[tail++] = s; label[s] = cur;
    while (head < tail) {
      const p = queue[head++]; size++;
      const x = p % W, y = (p / W) | 0;
      if (x > 0 && body[p - 1] && label[p - 1] === -1) { label[p - 1] = cur; queue[tail++] = p - 1; }
      if (x < W - 1 && body[p + 1] && label[p + 1] === -1) { label[p + 1] = cur; queue[tail++] = p + 1; }
      if (y > 0 && body[p - W] && label[p - W] === -1) { label[p - W] = cur; queue[tail++] = p - W; }
      if (y < H - 1 && body[p + W] && label[p + W] === -1) { label[p + W] = cur; queue[tail++] = p + W; }
    }
    if (size > bestSize) { bestSize = size; best = cur; }
    cur++;
  }
  const mask = new Uint8Array(N); // 1 = inside the chosen body component
  if (best >= 0) for (let i = 0; i < N; i++) if (label[i] === best) mask[i] = 1;

  // 3. fill internal holes: flood the OUTSIDE (non-mask) from the border; any
  //    non-mask pixel not reached is enclosed → make it part of the body.
  const outside = new Uint8Array(N);
  let qh = 0, qt = 0;
  const push = (i: number) => { if (!mask[i] && !outside[i]) { outside[i] = 1; queue[qt++] = i; } };
  for (let x = 0; x < W; x++) { push(x); push((H - 1) * W + x); }
  for (let y = 0; y < H; y++) { push(y * W); push(y * W + W - 1); }
  while (qh < qt) {
    const p = queue[qh++];
    const x = p % W, y = (p / W) | 0;
    if (x > 0) push(p - 1);
    if (x < W - 1) push(p + 1);
    if (y > 0) push(p - W);
    if (y < H - 1) push(p + W);
  }
  for (let i = 0; i < N; i++) if (!outside[i]) mask[i] = 1; // enclosed ⇒ opaque

  // 4. light 1px erode → drop the pale near-white halo at the silhouette edge.
  const alpha = new Uint8Array(N);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (!mask[i]) continue;
      const edge =
        (x > 0 && !mask[i - 1]) || (x < W - 1 && !mask[i + 1]) ||
        (y > 0 && !mask[i - W]) || (y < H - 1 && !mask[i + W]);
      alpha[i] = edge ? 0 : 255;
    }
  }
  return alpha;
}

// ============================================================
// COMBINED BLUEPRINT (single-pass sprite-sheet pipeline) — a TS port of
// /tmp/A_blueprint.py. ONE image carries both a DEVICE BODY (top) and a
// SPRITE STRIP (bottom):
//   • a faint gray rounded BODY silhouette behind the wells (the model
//     RESTYLES an existing shape instead of inventing+growing one → less drift);
//   • each control well drawn as a dark socket, ringed by a bright MAGENTA
//     ANCHOR RING so it reads as a fixed, non-negotiable anchor;
//   • a bottom strip of labeled placeholder cells — one per sprite control —
//     where the model paints the BARE finished control parts.
// The single paint pass (see pipeline.ts) restyles the whole thing in one shot;
// there is NO separate envelope pass. The returned `layout` tells the browser
// (cutoutClient.ts) where to cut the device region and each control sprite.
// ============================================================

// kinds the SPRITE STRIP carries (interactive parts that get cut + re-seated).
// displays/screens are device-only (painted in place, never cut as a sprite).
export type SpriteKind = "button" | "knob" | "toggle" | "slider";

// one control as the browser needs it. rect is normalized to the DEVICE region
// (0..1 of GEN_W × GEN_H), matching the on-device socket the app re-seats into.
export interface BlueprintControl {
  bind: string;
  kind: SpriteKind;
  rect: [number, number, number, number];
}
// one sprite-strip cell. cellRect is normalized to the FULL combined image
// (0..1 of GEN_W × (GEN_H+STRIP_H)) — the box the browser crops + masks to get
// the bare control sprite.
export interface BlueprintCell {
  bind: string;
  kind: SpriteKind;
  cellRect: [number, number, number, number];
}
export interface BlueprintLayout {
  // device region = the TOP `devFrac` of the combined image height.
  devFrac: number;
  controls: BlueprintControl[];
  cells: BlueprintCell[];
}

export interface CombinedBlueprint {
  svg: string;
  layout: BlueprintLayout;
  width: number;
  height: number;
  stripDesc: string;   // enumerated control list for the paint prompt (no text drawn in-image)
  bakeLegend: string;  // full colour→identity→role→icon legend for EVERY device control
  colors: Map<string, CompColor>;  // id → its identity hex, shared across every pipeline stage
}

// The FACE ICON for a transport button, in WORDS only — NO literal glyph characters
// (the model paints literal ◀▶■ as a separate floating glyph that gets cut into the
// sprite). Returns "" when the bind carries no prescribed icon. Shared by the strip
// description (controlDesc) AND the baked-button colour legend so the two never drift.
function faceIconWords(b: string): string {
  b = b.toLowerCase();
  if (b.includes("prev") || b.includes("rew")) return "a rewind icon (two left-pointing triangles)";
  if (b.includes("play")) return "a play icon (one right-pointing triangle)";
  if (b.includes("next") || b.includes("fwd") || b.includes("forward")) return "a fast-forward icon (two right-pointing triangles)";
  if (b.includes("stop")) return "a stop icon (a filled square)";
  if (b.includes("pause")) return "a pause icon (two vertical bars)";
  if (b.includes("power") || b.includes("eject") || b.includes("open")) return "a power/eject icon embossed subtly";
  return "";
}

// Human description of a control for the paint prompt (so we can convey identity
// WITHOUT drawing any text/labels into the strip).
function controlDesc(r: Region, kind: SpriteKind): string {
  const b = (r.bind || r.id || "").toLowerCase();
  if (kind === "button") {
    // describe the face icon in WORDS only — NO literal glyph characters (the model
    // paints literal ◀▶■ as a separate floating glyph that gets cut into the sprite).
    // SHAPE IS THE MODEL'S CHOICE: do not force "round". The cut keeps whatever
    // silhouette is painted (BiRefNet matte + connected components), so a button may
    // be round, pill, square, rounded-rectangle, a car-console key, a Walkman bar —
    // whatever suits the device. Only the FACE ICON is prescribed.
    // Push toward ORGANIC, era-correct silhouettes — the model defaults to a safe
    // rounded-square unless steered away. The cut keeps whatever is painted, so the
    // only job here is to discourage the generic box and invite the reference shapes.
    const sh = "a tactile push-button whose SILHOUETTE matches REAL hardware of this device era — prefer an ORGANIC, NON-rectangular shape: a half-oval / D-shape, a kidney/lozenge, a curved trapezoid, or a WEDGE / arc-segment like a Walkman jog cluster or a car-console key. AVOID a plain square or plain circle unless the device truly demands it. The button need NOT fill its slot — give it its own distinct sculpted outline";
    const icon = faceIconWords(b);
    return icon ? `${sh} with ${icon} embossed ON ITS FACE` : sh;
  }
  if (kind === "knob") return `a round rotary knob cap, smooth or knurled, with NO painted pointer/notch/indicator line — a plain symmetric cap (the app draws the rotating indicator on top)${r.label ? ` (${r.label})` : ""}`;
  if (kind === "slider") return `a small slider THUMB/grip — JUST the compact movable handle that rides along a track (a knurled cap / grip button), matching the device's material and era; NOT the whole track, NOT the groove — only the little part the finger drags`;
  return "a control part";
}

// REPACK to the paint aspect. The combined image (device + strip) MUST be the exact
// aspect we request from the paint model (9:16) — if it isn't, the model reshapes the
// output and the normalized strip cells + device sockets land in the wrong place
// (mis-cut sprites). So we derive the canvas FROM the aspect: combined height =
// GEN_W / (9/16); the device takes a clean 2:3 (GEN_H) at the top and the strip packs
// into the remainder. If GEN_H wouldn't leave room for the strip, the device shrinks
// so the strip always fits (repack). This guarantees the blueprint is 9:16 by build.
export const PAINT_ASPECT = 9 / 16;                          // width / height of the paint
const COMBINED_H = Math.round(GEN_W / PAINT_ASPECT);         // 1024 / 0.5625 ≈ 1821
const MIN_STRIP_H = Math.round(COMBINED_H * 0.14);           // strip always gets ≥14%
const DEVICE_H = Math.min(GEN_H, COMBINED_H - MIN_STRIP_H);  // device 2:3 if it fits, else shrunk
const STRIP_H = COMBINED_H - DEVICE_H;
// device region = the TOP fraction of the combined image (the rest is the sprite
// strip). Exported so the browser can crop the device even without a layout object.
export const DEVICE_FRAC = DEVICE_H / COMBINED_H;

const BP_BODY = "rgb(218,218,224)";   // faint gray body silhouette
export const BP_RING = "rgb(0,190,90)";      // bright GREEN anchor ring (empty well → sprite overlay). Green,
                                      // not magenta: magenta was physically transmitted into translucent
                                      // bodies + bled as pink frames (2026-07-01). Green reads as a clearly
                                      // foreign guide on any neutral backdrop and removes cleanly.

// PER-BUTTON identity hues for BAKED device buttons. The baked buttons are molded
// into the body and are NOT in the ordered strip, so — unlike the strip — they carry
// NO left-to-right position cue; without a per-button tag the model can't tell WHICH
// scattered ring is play vs stop and embosses icons arbitrarily. Each unique baked
// button gets its OWN hue + a prose legend maps hue→control→face-icon (reusing the
// glyph-free faceIconWords vocabulary). Hues kept MODERATE (removed guide rings, but
// strong chroma can still tint the painted control — the magenta-bleed lesson).
// PER-COMPONENT IDENTITY COLOUR — the ONE hex each component wears across the ENTIRE pipeline
// (studio panels, blueprint anchors, prompt legend, output mask), so every stage identifies a
// component by its exact colour. Deterministic per component id (FNV hash → palette slot) and
// UNIQUE within a template (linear-probe on collision; HSL fallback past the palette). Curated,
// high-contrast, NAMEABLE hues so the paint model can match a mark to the {legend} by name.
export interface CompColor { hex: string; name: string }
const PALETTE: CompColor[] = [
  { hex: "#E23B3B", name: "RED" },     { hex: "#2E74F0", name: "BLUE" },
  { hex: "#23BE55", name: "GREEN" },   { hex: "#F5B414", name: "AMBER" },
  { hex: "#AA46EB", name: "VIOLET" },  { hex: "#14C3B4", name: "TEAL" },
  { hex: "#F5781A", name: "ORANGE" },  { hex: "#F05FAF", name: "PINK" },
  { hex: "#8CD72D", name: "LIME" },    { hex: "#23C3E6", name: "CYAN" },
  { hex: "#E137CD", name: "MAGENTA" }, { hex: "#5F55E6", name: "INDIGO" },
  { hex: "#B4823C", name: "BROWN" },   { hex: "#F0DC3C", name: "YELLOW" },
  { hex: "#4FB4F5", name: "SKY" },     { hex: "#F0506E", name: "ROSE" },
  { hex: "#78D796", name: "MINT" },    { hex: "#8C4FA0", name: "PLUM" },
  { hex: "#F56E50", name: "CORAL" },   { hex: "#6E32B4", name: "GRAPE" },
  { hex: "#96A03C", name: "OLIVE" },   { hex: "#3CD7C8", name: "AQUA" },
  { hex: "#C86EF0", name: "ORCHID" },  { hex: "#A0A7B4", name: "SLATE" },
];
function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function hslHex(hue: number): CompColor {
  const sat = 0.62, l = 0.56, c = (1 - Math.abs(2 * l - 1)) * sat, hp = hue / 60;
  const x = c * (1 - Math.abs((hp % 2) - 1)); let r = 0, g = 0, b = 0;
  if (hp < 1) { r = c; g = x; } else if (hp < 2) { r = x; g = c; }
  else if (hp < 3) { g = c; b = x; } else if (hp < 4) { g = x; b = c; }
  else if (hp < 5) { r = x; b = c; } else { r = c; b = x; }
  const m = l - c / 2, to = (v: number) => Math.round((v + m) * 255).toString(16).padStart(2, "0");
  return { hex: `#${to(r)}${to(g)}${to(b)}`.toUpperCase(), name: `HUE${Math.round(hue)}` };
}
// id → stable, unique-within-template CompColor. Every stage calls THIS with the SAME regs
// and gets the SAME hex per component — the shared identity key across the whole pipeline.
export function componentColors(regs: Region[]): Map<string, CompColor> {
  const m = new Map<string, CompColor>(); const used = new Set<number>();
  for (const r of regs) {
    let idx = hashStr(r.id) % PALETTE.length, t = 0;
    while (used.has(idx) && t < PALETTE.length) { idx = (idx + 1) % PALETTE.length; t++; }
    if (t >= PALETTE.length) { m.set(r.id, hslHex(hashStr(r.id) % 360)); continue; }
    used.add(idx); m.set(r.id, PALETTE[idx]);
  }
  return m;
}

// map a template Region kind → the sprite kind we cut, or null for non-sprite
// (displays/decorations stay on the device and are never cut to the strip).
function spriteKindOf(r: Region): SpriteKind | null {
  if (r.kind === "knob") return "knob";
  if (r.kind === "toggle") return "toggle";
  if (r.kind === "button") return "button";
  if (r.kind === "slider-h" || r.kind === "slider-v" || r.kind === "slider-arc" || r.kind === "slider-path")
    return "slider";
  return null; // display / flourish / segmented / xy — device-only
}
// The per-sprite KEY = the region id. It is GUARANTEED unique within a template
// (bind is NOT — e.g. all six EQ bands share bind:"eqBand"), so it is the only safe
// token for skins/<id>/sprites/<key>.png (write-once would otherwise collide) and is
// what the render team resolves back to a template region to size the sprite. For the
// common transport controls id===bind, so existing lookups keep working.
const bindOf = (r: Region): string => r.id;

// Build the COMBINED blueprint SVG + its layout, REPACKED to the paint aspect (9:16)
// so the model reproduces it ~1:1. Device region is GEN_W×DEVICE_H (2:3), strip is
// GEN_W×STRIP_H below it; together they equal GEN_W×COMBINED_H = 9:16 by construction.
// deviceBg = the DEVICE-region backdrop colour (the cutout key colour). The STRIP
// stays flat white so connected-component sprite cutting is unambiguous. Default
// white = legacy behaviour (no colour key).
// Shape-AGNOSTIC control anchor (blueprint "option B"). Instead of a ring / rounded-rect
// that implies a silhouette (and then a prompt fighting to say "ignore that shape"), mark
// each control with a crisp CENTROID CROSSHAIR (exact position) + a SOFT SIZE DISC (roughly
// how big) — the silhouette is left entirely to the paint model. There is NO hard edge, so
// nothing dictates the painted control's form. DIFFUSENESS is encoded honestly: diff 0 = a
// tight, bright, firm anchor ("control is HERE"); diff 1 = a large, soft, blurry disc + a
// faded crosshair ("somewhere around here — nudge freely").
function anchorMark(cx: number, cy: number, w: number, h: number, col: string, diff: number, corner: number, key: string, defs: string[]): string {
  const s = Math.min(w, h);
  const blur = s * 0.10 + diff * s * 0.55;                 // always soft; diffuseness → spread
  const fid = `a_${key}`;
  defs.push(`<filter id="${fid}" x="-90%" y="-90%" width="280%" height="280%"><feGaussianBlur stdDeviation="${blur.toFixed(1)}"/></filter>`);
  // soft SHAPE: a rounded-rect whose corner radius morphs it between a RECTANGLE (corner 0)
  // and an OVAL (corner 1) — the "anchor + shape" the studio drags with live corner handles.
  const rw = w * 0.88, rh = h * 0.88, rx0 = cx - rw / 2, ry0 = cy - rh / 2;
  const rr = (Math.min(rw, rh) / 2) * Math.max(0, Math.min(1, corner));
  const disc = `<rect x="${rx0.toFixed(1)}" y="${ry0.toFixed(1)}" width="${rw.toFixed(1)}" height="${rh.toFixed(1)}" rx="${rr.toFixed(1)}" ry="${rr.toFixed(1)}" fill="${col}" fill-opacity="0.36" filter="url(#${fid})"/>`;
  const arm = s * 0.27, lw = Math.max(2.5, s * 0.03), dot = Math.max(3, s * 0.05);
  const op = (0.95 - diff * 0.45).toFixed(2);              // crosshair fades as the position gets diffuse
  const ch =
    `<g stroke="${col}" stroke-width="${lw.toFixed(1)}" stroke-linecap="round" opacity="${op}">` +
    `<line x1="${(cx - arm).toFixed(1)}" y1="${cy.toFixed(1)}" x2="${(cx + arm).toFixed(1)}" y2="${cy.toFixed(1)}"/>` +
    `<line x1="${cx.toFixed(1)}" y1="${(cy - arm).toFixed(1)}" x2="${cx.toFixed(1)}" y2="${(cy + arm).toFixed(1)}"/></g>` +
    `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${dot.toFixed(1)}" fill="${col}" opacity="${op}"/>`;
  return disc + ch;                                        // disc behind, crosshair on top
}

export function combinedBlueprint(regs: Region[], deviceBg = "white"): CombinedBlueprint {
  const stripH = STRIP_H;         // remainder packs the control strip
  const H = COMBINED_H;           // = DEVICE_H + stripH, exactly 9:16
  const devFrac = DEVICE_FRAC;

  // sprite controls = interactive parts only, in stable (region) order. BAKED controls
  // are EXCLUDED — they're painted cohesively into the device body, not cut to the strip.
  const spriteRegs = regs.filter((r) => spriteKindOf(r) !== null && !r.baked);

  const parts: string[] = [];
  // base = white (the STRIP must be white for clean cutting). The DEVICE region (top
  // DEVICE_H) gets the key-colour backdrop so the device cuts out cleanly; the strip
  // below stays white.
  // whole blueprint on ONE neutral backdrop — device region AND control strip share it.
  // BiRefNet (object-based) cuts both, and a neutral grey/white/black never tints a
  // translucent body or eats a white knob the way the old white/magenta keys did.
  parts.push(`<rect width="${GEN_W}" height="${H}" fill="${deviceBg}"/>`);

  // --- faint gray BODY silhouette: rounded envelope around all DEVICE wells. ---
  // (mirrors A_blueprint.py: bbox of every well + generous margin, big radius.)
  let bx0 = GEN_W, by0 = GEN_H, bx1 = 0, by1 = 0;
  for (const r of regs) {
    const x0 = r.rect.x * GEN_W, y0 = r.rect.y * GEN_H;
    const x1 = x0 + r.rect.w * GEN_W, y1 = y0 + r.rect.h * GEN_H;
    if (x0 < bx0) bx0 = x0; if (y0 < by0) by0 = y0;
    if (x1 > bx1) bx1 = x1; if (y1 > by1) by1 = y1;
  }
  if (regs.length) {
    const mx = GEN_W * 0.06, my = GEN_H * 0.05;
    bx0 = Math.max(0, bx0 - mx); by0 = Math.max(0, by0 - my);
    bx1 = Math.min(GEN_W, bx1 + mx); by1 = Math.min(GEN_H, by1 + my * 1.6);
    parts.push(roundRect(bx0, by0, bx1 - bx0, by1 - by0, GEN_W * 0.10, BP_BODY, "none", 0));
  }

  // --- device sockets: MINIMAL guide (bright guide keyline only, NO filled shape).
  // Don't draw socket shapes — they override the model's painted control shape.
  // Guides are blurred by diffuseness (0=crisp, 1=soft); BAKED controls stay crisp.
  //
  // GEOMETRY INVARIANTS (fix for "oval buttons" + "overlapping rings"):
  //   • ROUND controls (knob / ellipse button) render as a TRUE CIRCLE — diameter =
  //     min(w_px, h_px) centered in the rect — so a non-pixel-square rect (0.13×0.13
  //     normalized is 133×200px) can never come out an oval.
  //   • The ring is stroked INSET (centered on the rect edge, i.e. the stroke's OUTER
  //     edge sits at the rect boundary) instead of padded OUTWARD by `pad`. Padding the
  //     ring outward made adjacent, non-overlapping rects produce visibly overlapping
  //     rings. With an inset ring the painted outline never exceeds the (separated) rect,
  //     so resolveOverlaps' min-gap guarantees the rings clear each other.
  // PER-BUTTON identity: assign each BAKED button its own hue (stable region order) and
  // build a colour→identity→icon legend for the paint prompt. So the model knows which
  // scattered ring is which control + what to emboss, with no ambiguity and no drawn text.
  // ONE identity hex per component, shared across every pipeline stage (panels, blueprint,
  // this legend, output mask). Built once here from the region set.
  const colors = componentColors(regs);
  // FULL colour→identity legend for EVERY device-body control (not just baked buttons): the
  // model matches each distinctly-coloured mark to exactly one control by colour + role.
  const roleOf = (r: Region): string =>
    r.kind === "display" ? "a recessed SCREEN — leave it blank dark glass"
    : (r.kind === "button" && r.baked) ? "a real MOLDED BUTTON on the body"
    : "an EMPTY recessed socket (a cut control part sits here)";
  const bakeLegend = regs.map((r) => {
    const cc = colors.get(r.id)!;
    const who = (r.bind || r.id).toUpperCase();
    const icon = r.kind === "button" ? faceIconWords((r.bind || r.id).toLowerCase()) : "";
    return `${cc.name} (${cc.hex}) = ${who}, ${roleOf(r)}${icon ? `: emboss ${icon}` : ""}`;
  }).join("; ");

  // SHAPE-AGNOSTIC anchors (no ring / rounded-rect — those implied a silhouette the prompt
  // then had to un-say). Each socket = a crisp centroid crosshair + a soft size disc; the
  // painted control's shape is entirely the model's. GREEN = empty well (player overlays a cut
  // sprite); a BAKED button gets its OWN identity HUE so the model can tell which molded button
  // is which. DIFFUSENESS spreads the disc + fades the crosshair; BAKED anchors stay crisp.
  const defs: string[] = [];
  for (const r of regs) {
    const x = r.rect.x * GEN_W, y = r.rect.y * GEN_H;
    const w = r.rect.w * GEN_W, h = r.rect.h * GEN_H;
    const col = colors.get(r.id)!.hex;   // this component's identity hex (same everywhere)
    const diff = !r.baked && typeof (r as any).diff === "number" ? (r as any).diff : 0;
    const scx = x + w / 2, scy = y + h / 2, ss = Math.min(w, h), stw = Math.max(4, ss * 0.06);
    // SLIDERS draw their track (straight line / partial-circle arc); every other control is a
    // diffuse rounded-rect anchor whose `corner` morphs it between rectangle and oval.
    if (r.kind === "slider-h") parts.push(`<line x1="${x + w * 0.12}" y1="${scy}" x2="${x + w * 0.88}" y2="${scy}" stroke="${col}" stroke-width="${stw}" stroke-linecap="round"/>`);
    else if (r.kind === "slider-v") parts.push(`<line x1="${scx}" y1="${y + h * 0.12}" x2="${scx}" y2="${y + h * 0.88}" stroke="${col}" stroke-width="${stw}" stroke-linecap="round"/>`);
    else if (r.kind === "slider-arc") { const a = r.arc ?? { start: 200, end: 340 }; parts.push(arcPath(scx, scy, (ss / 2) * 0.86, a.start, a.end, stw, col, "none")); }
    else parts.push(anchorMark(scx, scy, w, h, col, diff, (r as any).corner ?? 0.5, r.id, defs));
  }

  // --- bottom SPRITE STRIP: each slot gets a faint MAGENTA KEYLINE anchor (outline only,
  // NO fill, NO text) — the SAME guide mechanism as the device sockets. It makes the slot
  // COUNT and POSITION deterministic: the painter fills exactly one finished control per
  // visible anchor and removes the magenta (guides only), so the model can't drop, merge, or
  // miscount a control (the sx7a "painted 3 of 4 transport buttons" failure). The keyline is
  // an OUTLINE, not a filled tile, so it does not dictate the control's painted form, and it
  // is removed in the output, so nothing extra is cut into the sprite. Round anchor for
  // buttons/knobs, rounded-rect for toggles — matching the on-device socket shape so the cut
  // sprite fits its socket. TOGGLES collapse to a shared OFF/ON pair keyed switch-off/on.
  interface StripItem { bind: string; kind: SpriteKind; desc: string; color: string }
  const items: StripItem[] = [];
  for (const r of spriteRegs) {
    const kind = spriteKindOf(r)!;
    if (kind === "toggle") continue;  // toggles handled as an off/on pair below
    // Horizontal sliders (seek / volume / balance) get a CUT THUMB sprite (Winamp model:
    // painted track in the device + a movable thumb sprite). slider-v (EQ) / arc / path
    // keep CSS for now. The cut sprite is named by r.id → SliderH reads spriteUrl(skinId, r.id).
    if (kind === "slider" && r.kind !== "slider-h") continue;
    const bind = bindOf(r);
    items.push({ bind, kind, desc: controlDesc(r, kind), color: colors.get(r.id)?.hex ?? "#888888" });
    // PLAY/PAUSE is a two-state control (like the toggle off/on pair): emit a paired
    // PAUSE face — the SAME button body, only the icon differs — cut to <id>__pause and
    // swapped live by the player on play state. (id===bind for transport controls.)
    const isPlay = kind === "button" && /(^|_)play(_|$)/.test(bind) && !bind.includes("playlist");
    if (isPlay) items.push({
      bind: `${bind}__pause`, kind, color: colors.get(r.id)?.hex ?? "#888888",
      desc: "the SAME push-button as the previous slot — IDENTICAL body, shape, size and material — but shown with a PAUSE icon (two vertical bars) embossed on its face instead of the play triangle",
    });
  }
  const firstToggle = spriteRegs.find((r) => spriteKindOf(r) === "toggle");
  if (firstToggle) {
    const tc = colors.get(firstToggle.id)?.hex ?? "#888888";
    items.push({ bind: "switch-off", kind: "toggle", color: tc, desc: "a toggle switch shown in its OFF position (lever/rocker down)" });
    items.push({ bind: "switch-on", kind: "toggle", color: tc, desc: "the SAME toggle switch shown in its ON position (lever/rocker up)" });
  }
  const n = items.length;
  const cellW = n > 0 ? GEN_W / n : GEN_W;
  const cells: BlueprintCell[] = [];
  items.forEach((it, i) => {
    const cx = i * cellW + cellW / 2;
    const cw = cellW * 0.92;
    const sx0 = cx - cw / 2;
    const sy0 = GEN_H + stripH * 0.02;
    const shh = stripH * 0.66;
    // shape-agnostic anchor: crosshair + soft green disc centered in the slot (crisp — strip
    // positions are deterministic). Same honest marker as the device sockets; the painter
    // fills one control per anchor and removes the mark.
    parts.push(anchorMark(sx0 + cw / 2, sy0 + shh / 2, cw, shh, it.color, 0, 0.5, `strip_${i}`, defs));
    cells.push({
      bind: it.bind, kind: it.kind,
      cellRect: [sx0 / GEN_W, sy0 / H, cw / GEN_W, shh / H],
    });
  });
  const stripDesc = items.map((it, i) => `slot ${i + 1}: ${it.desc}`).join("; ");

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${GEN_W}" height="${H}" viewBox="0 0 ${GEN_W} ${H}"><defs>${defs.join("")}</defs>${parts.join("")}</svg>`;
  const controls: BlueprintControl[] = spriteRegs.map((r) => ({
    bind: bindOf(r), kind: spriteKindOf(r)!,
    rect: [r.rect.x, r.rect.y, r.rect.w, r.rect.h], // normalized to the DEVICE region (GEN_H)
  }));
  return { svg, layout: { devFrac, controls, cells }, width: GEN_W, height: H, stripDesc, bakeLegend, colors };
}


// Per-component LABEL mask: each region filled with its identity hex (componentColors) on a
// black field — so a downstream stage can key each control's pixels by its exact colour. Same
// colour a component wears in the panels / blueprint, so the mask is consistent with them.
export function regionMaskSvg(regs: Region[], dilate = 28): string {
  const colors = componentColors(regs);
  const shapes = regs.map((r) => {
    const fill = colors.get(r.id)?.hex ?? "#FFFFFF";
    const rc = r.rect;
    const x0 = rc.x * GEN_W, y0 = rc.y * GEN_H, w = rc.w * GEN_W, h = rc.h * GEN_H;
    if (r.kind === "slider-arc" && r.arc) {
      const cx = x0 + w / 2, cy = y0 + h / 2, rr = (w * 0.88) / 2;
      return arcPath(cx, cy, rr, r.arc.start, r.arc.end, 26 + dilate, fill, "none");
    }
    if (r.kind === "knob" || ((r.kind === "button" || r.kind === "display") && r.shape === "ellipse")) {
      return `<ellipse cx="${x0 + w / 2}" cy="${y0 + h / 2}" rx="${w / 2 + dilate}" ry="${h / 2 + dilate}" fill="${fill}"/>`;
    }
    return `<rect x="${x0 - dilate}" y="${y0 - dilate}" width="${w + 2 * dilate}" height="${h + 2 * dilate}" rx="${dilate}" fill="${fill}"/>`;
  }).join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${GEN_W}" height="${GEN_H}" viewBox="0 0 ${GEN_W} ${GEN_H}"><rect width="${GEN_W}" height="${GEN_H}" fill="black"/>${shapes}</svg>`;
}
