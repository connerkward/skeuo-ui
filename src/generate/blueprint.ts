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
function roundRect(x: number, y: number, w: number, h: number, rad: number, fill: string, stroke: string, sw: number): string {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rad}" ry="${rad}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
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

export function regionMaskSvg(regs: Region[], dilate = 28): string {
  const shapes = regs.map((r) => {
    const rc = r.rect;
    const x0 = rc.x * GEN_W, y0 = rc.y * GEN_H, w = rc.w * GEN_W, h = rc.h * GEN_H;
    if (r.kind === "slider-arc" && r.arc) {
      const cx = x0 + w / 2, cy = y0 + h / 2, rr = (w * 0.88) / 2;
      return arcPath(cx, cy, rr, r.arc.start, r.arc.end, 26 + dilate, "white", "none");
    }
    if (r.kind === "knob" || ((r.kind === "button" || r.kind === "display") && r.shape === "ellipse")) {
      return `<ellipse cx="${x0 + w / 2}" cy="${y0 + h / 2}" rx="${w / 2 + dilate}" ry="${h / 2 + dilate}" fill="white"/>`;
    }
    return `<rect x="${x0 - dilate}" y="${y0 - dilate}" width="${w + 2 * dilate}" height="${h + 2 * dilate}" rx="${dilate}" fill="white"/>`;
  }).join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${GEN_W}" height="${GEN_H}" viewBox="0 0 ${GEN_W} ${GEN_H}"><rect width="${GEN_W}" height="${GEN_H}" fill="black"/>${shapes}</svg>`;
}
