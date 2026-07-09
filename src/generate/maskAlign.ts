// ============================================================
// maskAlign — read the model-emitted REGION MASK back out and refine it onto the
// painted skin. TS/canvas port of the mask-align experiment's extract8.py, plus the
// extract9/extract10 gradient-fit + gate passes (circle-fit, rrect-fit, global drift,
// leak / emptiness / ring / shape gates, strip-sliver filter)
// (tools/mask-align-exp/README.md is the seam contract; companion record:
// docs/experiments/2026-07-07-dual-output-mask.md).
//
// Inputs are the two halves of a JOINT generation (split at w//2): `paint` = the
// painted device + sprite strip, `mask` = flat colour blobs on black, one identity
// colour per component (componentColors — the shared colour system; see
// blueprint.MaskKey). The learnings baked in, each proven in the experiment:
//   • nearest-colour assignment gated sat>55, max>90, dist<95 — kills bleed/glow.
//   • binary FILL-HOLES before CC labeling — a hollow (ring-drawn) toggle cell
//     still labels as one solid component.
//   • LARGEST connected component per colour — a stray same-hue pixel cluster
//     can't inflate the bbox.
//   • strip cells matched by COLOUR IDENTITY, never left-to-right order across
//     colours (order-based assignment put a toggle where seek belonged); a colour
//     owning N cells (toggle off/on, play/pause) splits its N blobs left→right.
//   • SNAP-X-ONLY: the model paints the mask panel ~+0.5% right of the paint
//     (systematic; 0.2–0.7%). Snap each region's x-centre onto the painted
//     feature (saturated icon for baked buttons, dark well for sockets) and KEEP
//     THE MASK'S Y — the dark-pixel centroid is biased UP (recess shadow hugs the
//     top inner rim under top-light) and was seating knobs too high. Residual
//     after snap ≈0.05%. Both boxes are kept: `maskDevice` (raw) + `device`
//     (snapped — place from THIS).
//   • SEEK TRACK bbox = the painted groove's true dark-CC full extent, not the
//     mask blob (the blob draws ~2% inset of the slot, so flush-to-blob thumb
//     travel still showed slot at the ends).
// ============================================================
import type { MaskKey } from "./blueprint";

// x, y, w, h — normalized to the PAINT PANEL (0..1 of panel width/height) unless
// stated otherwise. The device occupies the top `devFrac` of the panel.
export type Box = [number, number, number, number];

export interface MaskRegionOut {
  maskDevice?: Box;   // raw largest-CC mask blob (where the model drew it)
  device?: Box;       // gradient-fit / drift-refined onto the painted feature (place from THIS)
  seat?: [number, number, number]; // knob socket [cx, cy, r] — cx,r normalized by panel W, cy by H
}
export interface MaskAlignResult {
  devFrac: number;
  regions: Record<string, MaskRegionOut>;   // by region id
  cells: Record<string, Box>;               // by strip-cell bind (colour-identity matched)
}

// extraction gates (per the committed experiment README — the seam contract)
const SAT_MIN = 55;         // pixel saturation (max-min) must exceed this
const VAL_MIN = 90;         // pixel max channel must exceed this
const DIST_MAX2 = 95 * 95;  // nearest-colour distance gate (squared)
const WORK_MAX_W = 1400;    // extraction working width cap (bboxes are normalized; ~0.07% granularity)
// area thresholds, normalized from the experiment's pixel counts at 1200×1920/panel
const MIN_BLOB_FRAC = 5.2e-5;   // ≈120 px — a real blob, not stray pixels
const MIN_SNAP_FRAC = 3.5e-5;   // ≈80 px — enough painted evidence to trust a snap
const MIN_GROOVE_FRAC = 8.7e-5; // ≈200 px — a real seek groove CC

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

// scale a canvas down to ≤maxW wide (returns the input when already small enough)
function workCanvas(src: HTMLCanvasElement, maxW: number): HTMLCanvasElement {
  if (src.width <= maxW) return src;
  const s = maxW / src.width;
  const c = document.createElement("canvas");
  c.width = maxW; c.height = Math.max(1, Math.round(src.height * s));
  c.getContext("2d")!.drawImage(src, 0, 0, c.width, c.height);
  return c;
}
function imageData(c: HTMLCanvasElement): ImageData {
  return c.getContext("2d", { willReadFrequently: true })!.getImageData(0, 0, c.width, c.height);
}

// FILL-HOLES on a binary mask: flood the zeros reachable from the frame border;
// any unreached zero is enclosed → set to 1. (Hollow toggle cells become solid so
// the largest-CC pass sees one component, not a thin ring that fragments.)
function fillHoles(bin: Uint8Array, W: number, H: number): void {
  const N = W * H;
  const outside = new Uint8Array(N);
  const queue = new Int32Array(N);
  let qt = 0;
  const push = (i: number) => { if (!bin[i] && !outside[i]) { outside[i] = 1; queue[qt++] = i; } };
  for (let x = 0; x < W; x++) { push(x); push((H - 1) * W + x); }
  for (let y = 0; y < H; y++) { push(y * W); push(y * W + W - 1); }
  let qh = 0;
  while (qh < qt) {
    const p = queue[qh++]; const x = p % W, y = (p / W) | 0;
    if (x > 0) push(p - 1);
    if (x < W - 1) push(p + 1);
    if (y > 0) push(p - W);
    if (y < H - 1) push(p + W);
  }
  for (let i = 0; i < N; i++) if (!bin[i] && !outside[i]) bin[i] = 1;
}

interface CC { size: number; minx: number; miny: number; maxx: number; maxy: number }
// label 4-connected components of a binary mask (labels[i] = CC index, -1 = background)
function labelComponents(bin: Uint8Array, W: number, H: number): { labels: Int32Array; ccs: CC[] } {
  const N = W * H;
  const labels = new Int32Array(N).fill(-1);
  const queue = new Int32Array(N);
  const ccs: CC[] = [];
  for (let s = 0; s < N; s++) {
    if (!bin[s] || labels[s] !== -1) continue;
    const id = ccs.length;
    let head = 0, tail = 0, size = 0, minx = W, miny = H, maxx = 0, maxy = 0;
    queue[tail++] = s; labels[s] = id;
    while (head < tail) {
      const p = queue[head++]; size++;
      const x = p % W, y = (p / W) | 0;
      if (x < minx) minx = x; if (x > maxx) maxx = x;
      if (y < miny) miny = y; if (y > maxy) maxy = y;
      if (x > 0 && bin[p - 1] && labels[p - 1] === -1) { labels[p - 1] = id; queue[tail++] = p - 1; }
      if (x < W - 1 && bin[p + 1] && labels[p + 1] === -1) { labels[p + 1] = id; queue[tail++] = p + 1; }
      if (y > 0 && bin[p - W] && labels[p - W] === -1) { labels[p - W] = id; queue[tail++] = p - W; }
      if (y < H - 1 && bin[p + W] && labels[p + W] === -1) { labels[p + W] = id; queue[tail++] = p + W; }
    }
    ccs.push({ size, minx, miny, maxx, maxy });
  }
  return { labels, ccs };
}
const components = (bin: Uint8Array, W: number, H: number): CC[] => labelComponents(bin, W, H).ccs;
const ccBox = (c: CC, W: number, H: number): Box =>
  [c.minx / W, c.miny / H, (c.maxx - c.minx + 1) / W, (c.maxy - c.miny + 1) / H];

// ============================================================
// Gradient-fit alignment + extraction gates — numeric port of extract9.py /
// extract10.py (parameterized like extract10: colours/cells passed in, nothing
// hardcoded). All functions operate on raw RGBA arrays (ImageData satisfies Raster
// structurally) so they run in browser AND node tests without canvas.
// Numeric-parity notes (validated against the python originals in maskAlign.test.mjs):
//   • grayscale = PIL convert("L"): (r·19595 + g·38470 + b·7471 + 0x8000) >> 16 (rounds).
//   • gradient = np.gradient: central differences interior, one-sided at edges.
//   • python int()/astype(int) = Math.trunc (toward zero).
//   • np.arange(a,b,s) = a + i·s for i < ceil((b−a)/s).
//   • pixel-count thresholds (ring 250px, shape 800px) are AREA FRACTIONS of the
//     experiment's 2304×3712 panel so they scale with resolution.
// ============================================================

// any RGBA byte buffer + dims (ImageData is one; node tests build these from PNGs)
export interface Raster { data: Uint8ClampedArray | Uint8Array; width: number; height: number }

// PIL-parity luminance (float64 grid for np.gradient-parity math downstream)
export function grayscale(img: Raster): Float64Array {
  const { data, width: W, height: H } = img;
  const out = new Float64Array(W * H);
  for (let i = 0, n = W * H; i < n; i++) {
    out[i] = (data[i * 4] * 19595 + data[i * 4 + 1] * 38470 + data[i * 4 + 2] * 7471 + 0x8000) >> 16;
  }
  return out;
}

// |∇g| — np.gradient (half-pixel central differences) + np.hypot
export function gradientMag(g: Float64Array, W: number, H: number): Float64Array {
  const out = new Float64Array(W * H);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      const gx = x === 0 ? g[i + 1] - g[i] : x === W - 1 ? g[i] - g[i - 1] : (g[i + 1] - g[i - 1]) / 2;
      const gy = y === 0 ? g[i + W] - g[i] : y === H - 1 ? g[i] - g[i - W] : (g[i + W] - g[i - W]) / 2;
      out[i] = Math.hypot(gx, gy);
    }
  }
  return out;
}

// CIRCLE-FIT (extract9:216–229 / extract10:185–197): mini-Hough on gradient magnitude —
// scan centre offsets ±r0/2 (step 3) × radii r0·[0.7, rHi) (step 3), score = mean |∇|
// along 72 ring samples. Material-agnostic (works on dark-on-dark chrome rims).
// rHi: 1.25 = extract9's search band, 1.3 = extract10's (the default).
export function circleFit(
  gm: Float64Array, W: number, H: number, box: Box, rHi = 1.3,
): { score: number; cx: number; cy: number; r: number } {
  const cx0 = (box[0] + box[2] / 2) * W;
  const cy0 = (box[1] + box[3] / 2) * H;
  const r0 = (box[2] * W + box[3] * H) / 4;
  let bs = 0, bx = cx0, by = cy0, br = r0;
  const ca = new Float64Array(72), sa = new Float64Array(72);
  const astep = (2 * Math.PI) / 72;
  for (let i = 0; i < 72; i++) { ca[i] = Math.cos(i * astep); sa[i] = Math.sin(i * astep); }
  const dLim = Math.trunc(r0 * 0.5);
  const rLo = r0 * 0.7;
  const nr = Math.ceil((r0 * rHi - rLo) / 3);
  for (let dy = -dLim; dy <= dLim; dy += 3) {
    for (let dx = -dLim; dx <= dLim; dx += 3) {
      const ccx = cx0 + dx, ccy = cy0 + dy;
      for (let ri = 0; ri < nr; ri++) {
        const r = rLo + ri * 3;
        let n = 0, s = 0;
        for (let i = 0; i < 72; i++) {
          const x = Math.trunc(ccx + r * ca[i]);
          const y = Math.trunc(ccy + r * sa[i]);
          if (x >= 0 && x < W && y >= 0 && y < H) { n++; s += gm[y * W + x]; }
        }
        if (n < 60) continue;
        const sc = s / n;
        if (sc > bs) { bs = sc; bx = ccx; by = ccy; br = r; }
      }
    }
  }
  return { score: bs, cx: bx, cy: by, r: br };
}

// 96 samples along a rounded-rect perimeter, corner radius 0.38·min(w,h)
// (extract10:198–219 — 8 piecewise segments, clockwise from the top edge)
export function rrectPerimeter(cx: number, cy: number, w: number, h: number, n = 96): Float64Array {
  const r = 0.38 * Math.min(w, h);
  const L = 2 * (w - 2 * r) + 2 * (h - 2 * r) + 2 * Math.PI * r;
  const out = new Float64Array(n * 2);
  const step = L / n;
  for (let i = 0; i < n; i++) {
    const s = i * step;
    let x: number, y: number;
    if (s < w - 2 * r) { x = cx - w / 2 + r + s; y = cy - h / 2; }
    else if (s < w - 2 * r + Math.PI * r / 2) {
      const a = (s - (w - 2 * r)) / r;
      x = cx + w / 2 - r + r * Math.sin(a); y = cy - h / 2 + r - r * Math.cos(a);
    } else if (s < w - 2 * r + Math.PI * r / 2 + h - 2 * r) {
      const t = s - (w - 2 * r + Math.PI * r / 2);
      x = cx + w / 2; y = cy - h / 2 + r + t;
    } else if (s < w - 2 * r + Math.PI * r + h - 2 * r) {
      const a = (s - (w - 2 * r + Math.PI * r / 2 + h - 2 * r)) / r;
      x = cx + w / 2 - r + r * Math.cos(a); y = cy + h / 2 - r + r * Math.sin(a);
    } else if (s < 2 * (w - 2 * r) + Math.PI * r + h - 2 * r) {
      const t = s - (w - 2 * r + Math.PI * r + h - 2 * r);
      x = cx + w / 2 - r - t; y = cy + h / 2;
    } else if (s < 2 * (w - 2 * r) + Math.PI * r * 1.5 + h - 2 * r) {
      const a = (s - (2 * (w - 2 * r) + Math.PI * r + h - 2 * r)) / r;
      x = cx - w / 2 + r - r * Math.sin(a); y = cy + h / 2 - r + r * Math.cos(a);
    } else if (s < 2 * (w - 2 * r) + Math.PI * r * 1.5 + 2 * (h - 2 * r)) {
      const t = s - (2 * (w - 2 * r) + Math.PI * r * 1.5 + h - 2 * r);
      x = cx - w / 2; y = cy + h / 2 - r - t;
    } else {
      const a = (s - (2 * (w - 2 * r) + Math.PI * r * 1.5 + 2 * (h - 2 * r))) / r;
      x = cx - w / 2 + r - r * Math.cos(a); y = cy - h / 2 + r - r * Math.sin(a);
    }
    out[i * 2] = x; out[i * 2 + 1] = y;
  }
  return out;
}

// RRECT-FIT (extract10:220–233): same gradient scoring along the rounded-rect
// perimeter — centre offsets ±30% (step 4) × width/height scales 0.85..1.33 (step .08)
export function rrectFit(
  gm: Float64Array, W: number, H: number, box: Box,
): { score: number; cx: number; cy: number; w: number; h: number } {
  const cx0 = (box[0] + box[2] / 2) * W, cy0 = (box[1] + box[3] / 2) * H;
  const w0 = box[2] * W, h0 = box[3] * H;
  let bs = 0, bx = cx0, by = cy0, bw = w0, bh = h0;
  const dyLim = Math.trunc(h0 * 0.3), dxLim = Math.trunc(w0 * 0.3);
  const nsc = Math.ceil((1.35 - 0.85) / 0.08); // np.arange(0.85,1.35,0.08) → 7 scales
  for (let dy = -dyLim; dy <= dyLim; dy += 4) {
    for (let dx = -dxLim; dx <= dxLim; dx += 4) {
      for (let si = 0; si < nsc; si++) {
        const sw = 0.85 + si * 0.08;
        for (let sj = 0; sj < nsc; sj++) {
          const sh = 0.85 + sj * 0.08;
          const pts = rrectPerimeter(cx0 + dx, cy0 + dy, w0 * sw, h0 * sh);
          let n = 0, s = 0;
          for (let i = 0; i < 96; i++) {
            const x = Math.trunc(pts[i * 2]), y = Math.trunc(pts[i * 2 + 1]);
            if (x >= 0 && x < W && y >= 0 && y < H) { n++; s += gm[y * W + x]; }
          }
          if (n < 70) continue;
          const sc = s / n;
          if (sc > bs) { bs = sc; bx = cx0 + dx; by = cy0 + dy; bw = w0 * sw; bh = h0 * sh; }
        }
      }
    }
  }
  return { score: bs, cx: bx, cy: by, w: bw, h: bh };
}

function median(v: number[]): number {
  const s = [...v].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// GLOBAL DRIFT (extract9/10:230–252): median px offset of the knob circle-fits vs their
// mask-blob centres, normalized — applied to every non-fitted region's maskDevice.
export function globalDrift(samples: [number, number][], W: number, H: number): [number, number] {
  return [median(samples.map((s) => s[0])) / W, median(samples.map((s) => s[1])) / H];
}

// numpy-parity linear-interpolation percentile (input must be sorted ascending)
function percentileSorted(sorted: Float64Array, q: number): number {
  const n = sorted.length;
  if (n === 1) return sorted[0];
  const idx = ((n - 1) * q) / 100;
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

// LEAK GATE (run9.py:224–238): count paint-panel pixels still near ANY guide colour
// (sat > 55 AND squared RGB dist < 60²). A pixel can count for multiple keys.
// FAIL when the worst key's fraction exceeds failFrac (0.05%).
export interface LeakGateResult {
  counts: Record<string, number>;
  worst: string;
  worstFrac: number;
  pass: boolean;
}
export function leakGate(
  paint: Raster, keys: { name: string; rgb: [number, number, number] }[], failFrac = 5e-4,
): LeakGateResult {
  const { data, width: W, height: H } = paint;
  const counts: Record<string, number> = {};
  const acc = new Array<number>(keys.length).fill(0);
  for (let i = 0, n = W * H; i < n; i++) {
    const r = data[i * 4], g = data[i * 4 + 1], b = data[i * 4 + 2];
    const mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
    const mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
    if (mx - mn <= 55) continue;
    for (let k = 0; k < keys.length; k++) {
      const dr = r - keys[k].rgb[0], dg = g - keys[k].rgb[1], db = b - keys[k].rgb[2];
      if (dr * dr + dg * dg + db * db < 3600) acc[k]++;
    }
  }
  let worst = "-", worstN = 0;
  keys.forEach((k, i) => {
    counts[k.name] = acc[i];
    if (acc[i] > worstN) { worstN = acc[i]; worst = k.name; }
  });
  const worstFrac = worstN / (W * H);
  return { counts, worst, worstFrac, pass: worstFrac <= failFrac };
}

// RELATIVE EMPTINESS GATE (extract9:283–304): inside the socket rect shrunk by 18%,
// floor = 10th-percentile luminance; FAIL if >10% of pixels sit >55 above the floor
// (a baked part is bright against the recess on ANY material). Returns null when the
// shrunken window is empty.
export interface EmptinessResult { brightFrac: number; floor: number; pass: boolean }
export function emptinessGate(
  paint: Raster, box: Box, opts: { shrink?: number; delta?: number; maxFrac?: number } = {},
): EmptinessResult | null {
  const { shrink = 0.18, delta = 55, maxFrac = 0.10 } = opts;
  const { data, width: W, height: H } = paint;
  const x0 = Math.trunc((box[0] + box[2] * shrink) * W), x1 = Math.trunc((box[0] + box[2] * (1 - shrink)) * W);
  const y0 = Math.trunc((box[1] + box[3] * shrink) * H), y1 = Math.trunc((box[1] + box[3] * (1 - shrink)) * H);
  if (x1 <= x0 || y1 <= y0) return null;
  const lum = new Float64Array((x1 - x0) * (y1 - y0));
  let li = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const i = (y * W + x) * 4;
      lum[li++] = Math.max(data[i], data[i + 1], data[i + 2]);
    }
  }
  const sorted = lum.slice().sort();
  const floor = percentileSorted(sorted, 10);
  let bright = 0;
  for (let i = 0; i < lum.length; i++) if (lum[i] > floor + delta) bright++;
  const brightFrac = bright / lum.length;
  return { brightFrac, floor, pass: brightFrac <= maxFrac };
}

// hue in degrees, numpy-mask-priority order (r, then g-if-not-r, then b-if-neither);
// python % keeps the r-branch non-negative
function rgbHue(r: number, g: number, b: number, mx: number, df: number): number {
  if (df <= 0) return 0;
  if (mx === r) { const h = (60 * ((g - b) / df)) % 360; return h < 0 ? h + 360 : h; }
  if (mx === g) return 60 * ((b - r) / df) + 120;
  return 60 * ((r - g) / df) + 240;
}
// colorsys.rgb_to_hsv parity for the guide-hue targets
function guideHue(rgb: [number, number, number]): number {
  const r = rgb[0] / 255, g = rgb[1] / 255, b = rgb[2] / 255;
  const maxc = Math.max(r, g, b), minc = Math.min(r, g, b);
  if (minc === maxc) return 0;
  const rangec = maxc - minc;
  const rc = (maxc - r) / rangec, gc = (maxc - g) / rangec, bc = (maxc - b) / rangec;
  let h: number;
  if (r === maxc) h = bc - gc;
  else if (g === maxc) h = 2.0 + rc - bc;
  else h = 4.0 + gc - rc;
  h = (h / 6.0) % 1.0;
  if (h < 0) h += 1;
  return h * 360;
}

// strip-cell window shared by the ring + shape gates: full column band below the
// device region, centred on the cell, half-width 9.75% of panel width
function cellWindow(W: number, H: number, devFrac: number, fx: number) {
  const y0 = Math.trunc(H * devFrac);
  const cx = Math.trunc(fx * W), hw = Math.trunc(0.0975 * W);
  return { x0: Math.max(0, cx - hw), x1: Math.min(W, cx + hw), y0, y1: H };
}

// the experiment's gate pixel thresholds, expressed as fractions of its 2304×3712
// panel so they scale with working resolution (Math.round recovers 250/800 exactly
// at reference res — the cross-validation tests depend on that)
const EXP_PANEL_AREA = 2304 * 3712;
const RING_MAX_PX_FRAC = 250 / EXP_PANEL_AREA;
const SHAPE_MIN_CC_FRAC = 800 / EXP_PANEL_AREA;

// PER-CELL RING GATE (extract9:316–354): desaturated guide-colour residue on/around
// each painted strip part. The global leak gate only catches near-exact key colours;
// a baked guide ring often survives DESATURATED — hue survives desaturation, so scan
// each cell window for moderate-sat pixels whose hue sits near ANY strip guide hue.
export interface RingCellResult { leakColour: string; px: number; pass: boolean }
export function ringGate(
  paint: Raster, devFrac: number,
  cells: { name: string; fx: number }[],
  guides: { name: string; rgb: [number, number, number] }[],
  opts: { satMin?: number; valMin?: number; hueTol?: number; maxPxFrac?: number } = {},
): { cells: Record<string, RingCellResult>; pass: boolean } {
  const { satMin = 35, valMin = 70, hueTol = 16.0, maxPxFrac = RING_MAX_PX_FRAC } = opts;
  const { data, width: W, height: H } = paint;
  const maxPx = Math.round(W * H * maxPxFrac);
  const hues = guides.map((g) => guideHue(g.rgb));
  const out: Record<string, RingCellResult> = {};
  let fail = false;
  for (const cell of cells) {
    const { x0, x1, y0, y1 } = cellWindow(W, H, devFrac, cell.fx);
    const counts = new Array<number>(guides.length).fill(0);
    for (let y = y0; y < y1; y++) {
      for (let x = x0; x < x1; x++) {
        const i = (y * W + x) * 4;
        const r = data[i], g = data[i + 1], b = data[i + 2];
        const mx = Math.max(r, g, b), df = mx - Math.min(r, g, b);
        if (df <= satMin || mx <= valMin) continue;
        const hue = rgbHue(r, g, b, mx, df);
        for (let k = 0; k < hues.length; k++) {
          const ad = Math.abs(hue - hues[k]);
          if (Math.min(ad, 360 - ad) < hueTol) counts[k]++;
        }
      }
    }
    let worstName = "-", worstN = 0;
    for (let k = 0; k < guides.length; k++) {
      if (counts[k] > worstN) { worstN = counts[k]; worstName = guides[k].name; }
    }
    const ok = worstN <= maxPx;
    if (!ok) fail = true;
    out[cell.name] = { leakColour: worstName, px: worstN, pass: ok };
  }
  return { cells: out, pass: !fail };
}

// 3×3-cross binary dilation/erosion (scipy default structure, border_value=0 —
// erosion always eats frame-border pixels)
function dilateCross(src: Uint8Array, W: number, H: number, out: Uint8Array): void {
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      out[i] = src[i] ||
        (x > 0 && src[i - 1]) || (x < W - 1 && src[i + 1]) ||
        (y > 0 && src[i - W]) || (y < H - 1 && src[i + W]) ? 1 : 0;
    }
  }
}
function erodeCross(src: Uint8Array, W: number, H: number, out: Uint8Array): void {
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      out[i] = src[i] &&
        x > 0 && src[i - 1] && x < W - 1 && src[i + 1] &&
        y > 0 && src[i - W] && y < H - 1 && src[i + W] ? 1 : 0;
    }
  }
}
// scipy.ndimage.binary_closing(iterations=n): n dilations then n erosions
function binaryClosing(bin: Uint8Array, W: number, H: number, iterations: number): Uint8Array {
  let a = bin, b = new Uint8Array(W * H);
  for (let i = 0; i < iterations; i++) { dilateCross(a, W, H, b); [a, b] = [b, a]; }
  for (let i = 0; i < iterations; i++) { erodeCross(a, W, H, b); [a, b] = [b, a]; }
  return a;
}

// PER-CELL SHAPE GATE (extract9:356–395): each painted strip part's silhouette must
// match its cell's contract geometry (round knob / landscape pill thumb / portrait
// toggle). Catches the seek=toggle SWAP bug. Silhouette = |pixel − backdrop| > 55 on
// any channel; drop CCs touching the window's top row (device body hanging into the
// band); binary-close + fill-holes or pale chrome parts false-fail as rings.
export type ShapeExpect = "round" | "landscape-pill" | "portrait";
export interface ShapeCellResult {
  aspect?: number; fill?: number; expected?: ShapeExpect; pass: boolean; why?: string;
}
export function shapeGate(
  paint: Raster, devFrac: number, backdrop: [number, number, number],
  cells: { name: string; fx: number; expect: ShapeExpect }[],
  opts: { silDelta?: number; minCcFrac?: number } = {},
): { cells: Record<string, ShapeCellResult>; pass: boolean } {
  const { silDelta = 55, minCcFrac = SHAPE_MIN_CC_FRAC } = opts;
  const { data, width: W, height: H } = paint;
  const minCc = Math.round(W * H * minCcFrac);
  const out: Record<string, ShapeCellResult> = {};
  let fail = false;
  for (const cell of cells) {
    const { x0, x1, y0, y1 } = cellWindow(W, H, devFrac, cell.fx);
    const ww = x1 - x0, wh = y1 - y0;
    const sil = new Uint8Array(ww * wh);
    for (let y = 0; y < wh; y++) {
      for (let x = 0; x < ww; x++) {
        const i = ((y0 + y) * W + x0 + x) * 4;
        const d = Math.max(
          Math.abs(data[i] - backdrop[0]),
          Math.abs(data[i + 1] - backdrop[1]),
          Math.abs(data[i + 2] - backdrop[2]),
        );
        if (d > silDelta) sil[y * ww + x] = 1;
      }
    }
    const { labels, ccs } = labelComponents(sil, ww, wh);
    const topIds = new Set<number>();
    for (let x = 0; x < ww; x++) if (labels[x] !== -1) topIds.add(labels[x]);
    let bestId = -1, bestSize = 0;
    ccs.forEach((c, id) => {
      if (topIds.has(id) || c.size <= minCc) return;
      if (c.size > bestSize) { bestSize = c.size; bestId = id; }
    });
    if (bestId === -1) {
      out[cell.name] = { pass: false, why: "no part found" };
      fail = true;
      continue;
    }
    let cm = new Uint8Array(ww * wh);
    for (let i = 0; i < labels.length; i++) if (labels[i] === bestId) cm[i] = 1;
    cm = binaryClosing(cm, ww, wh, 3);
    fillHoles(cm, ww, wh);
    let minx = ww, maxx = -1, miny = wh, maxy = -1, area = 0;
    for (let y = 0; y < wh; y++) {
      for (let x = 0; x < ww; x++) {
        if (!cm[y * ww + x]) continue;
        area++;
        if (x < minx) minx = x; if (x > maxx) maxx = x;
        if (y < miny) miny = y; if (y > maxy) maxy = y;
      }
    }
    const w3 = maxx - minx + 1, h3 = maxy - miny + 1;
    const ar = w3 / h3, fillR = area / (w3 * h3);
    const ok = cell.expect === "round" ? ar >= 0.80 && ar <= 1.25 && fillR >= 0.65
      : cell.expect === "landscape-pill" ? ar >= 1.25
      : ar <= 0.85;
    if (!ok) fail = true;
    out[cell.name] = { aspect: ar, fill: fillR, expected: cell.expect, pass: ok };
  }
  return { cells: out, pass: !fail };
}

// combined strip verdicts — the same structure extract9 persists in regions.json
export interface StripCellSpec { name: string; fx: number; expect: ShapeExpect }
export interface MaskGates {
  ring: Record<string, RingCellResult>;
  shape: Record<string, ShapeCellResult>;
  ringPass: boolean;
  shapePass: boolean;
}
export function runStripGates(
  paint: Raster, devFrac: number, cells: StripCellSpec[],
  guides: { name: string; rgb: [number, number, number] }[],
  backdrop: [number, number, number],
): MaskGates {
  const ring = ringGate(paint, devFrac, cells, guides);
  const shape = shapeGate(paint, devFrac, backdrop, cells);
  return { ring: ring.cells, shape: shape.cells, ringPass: ring.pass, shapePass: shape.pass };
}

// Correlate the mask's colour blobs to controls and refine device placement onto the
// painted skin. `paint` / `mask` are the two (post-split) panels — same source dims.
export function extractMaskRegions(
  paint: HTMLCanvasElement, mask: HTMLCanvasElement, keys: MaskKey[], devFrac: number,
): MaskAlignResult {
  const m = workCanvas(mask, WORK_MAX_W);
  const W = m.width, H = m.height, N = W * H;
  const md = imageData(m).data;
  // paint working canvas at the SAME grid so paint-window coords line up 1:1
  const p = document.createElement("canvas");
  p.width = W; p.height = H;
  p.getContext("2d")!.drawImage(paint, 0, 0, W, H);
  const pd = imageData(p).data;

  const cols = keys.map((k) => hexToRgb(k.color));
  // nearest-colour assignment (sat>55, max>90, dist<95) — everything else unassigned
  const assign = new Int16Array(N).fill(-1);
  for (let i = 0; i < N; i++) {
    const r = md[i * 4], g = md[i * 4 + 1], b = md[i * 4 + 2];
    const mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
    const mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
    if (mx - mn <= SAT_MIN || mx <= VAL_MIN) continue;
    let best = -1, bestD = DIST_MAX2;
    for (let c = 0; c < cols.length; c++) {
      const dr = r - cols[c][0], dg = g - cols[c][1], db = b - cols[c][2];
      const d = dr * dr + dg * dg + db * db;
      if (d < bestD) { bestD = d; best = c; }
    }
    assign[i] = best;
  }

  const devRow = Math.round(devFrac * H);
  const minBlob = N * MIN_BLOB_FRAC, minSnap = N * MIN_SNAP_FRAC, minGroove = N * MIN_GROOVE_FRAC;
  const regions: Record<string, MaskRegionOut> = {};
  const cells: Record<string, Box> = {};
  const snapped = new Set<string>();   // regions whose x came from the painted feature
  const grooved = new Set<string>();   // seek regions measured from the painted groove CC
  const bin = new Uint8Array(N);

  keys.forEach((k, ki) => {
    const out: MaskRegionOut = {};

    // --- DEVICE blob: fill-holes → largest CC → bbox --------------------------------
    bin.fill(0);
    let devCount = 0;
    for (let i = 0; i < devRow * W; i++) if (assign[i] === ki) { bin[i] = 1; devCount++; }
    if (devCount >= minBlob) {
      fillHoles(bin, W, H);
      const ccs = components(bin, W, H).filter((c) => c.size >= minBlob);
      if (ccs.length) {
        const big = ccs.reduce((a, b) => (b.size > a.size ? b : a));
        out.maskDevice = ccBox(big, W, H);
        out.device = out.maskDevice;
      }
    }

    // --- SNAP-X-ONLY onto the painted feature ---------------------------------------
    if (out.device) {
      const [bx, by, bw, bh] = out.device;
      const cx = bx + bw / 2, cy = by + bh / 2;
      const wx0 = Math.max(0, Math.round((cx - bw * 0.6) * W)), wx1 = Math.min(W, Math.round((cx + bw * 0.6) * W));
      const wy0 = Math.max(0, Math.round((cy - bh * 0.6) * H)), wy1 = Math.min(H, Math.round((cy + bh * 0.6) * H));
      let n = 0, sx = 0;
      for (let y = wy0; y < wy1; y++) {
        for (let x = wx0; x < wx1; x++) {
          const i = (y * W + x) * 4;
          const r = pd[i], g = pd[i + 1], b = pd[i + 2];
          const mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
          const mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
          // baked button → its saturated painted icon; empty socket → the dark well
          if (k.baked ? mx - mn > 60 : mx < 70) { n++; sx += x; }
        }
      }
      if (n >= minSnap) { out.device = [sx / n / W - bw / 2, by, bw, bh]; snapped.add(k.id); }  // X only; keep mask Y
    }

    // --- SEEK TRACK = the painted groove's true dark-CC extent -----------------------
    // The mask blob draws ~2% inset of the slot; use the groove's full bbox so thumb
    // travel is genuinely flush to the slot ends.
    if (out.device && k.kind === "slider" && !k.baked) {
      const [bx, by, bw, bh] = out.device;
      const wx0 = Math.max(0, Math.round((bx - bw * 0.15) * W)), wx1 = Math.min(W, Math.round((bx + bw * 1.15) * W));
      const wy0 = Math.max(0, Math.round((by - bh * 2.0) * H)), wy1 = Math.min(H, Math.round((by + bh * 3.0) * H));
      const ww = wx1 - wx0, wh = wy1 - wy0;
      if (ww > 2 && wh > 2) {
        const gb = new Uint8Array(ww * wh);
        for (let y = 0; y < wh; y++) {
          for (let x = 0; x < ww; x++) {
            const i = ((wy0 + y) * W + wx0 + x) * 4;
            const mx = Math.max(pd[i], pd[i + 1], pd[i + 2]);
            if (mx < 70) gb[y * ww + x] = 1;
          }
        }
        const ccs = components(gb, ww, wh).filter((c) => c.size >= minGroove);
        if (ccs.length) {
          const big = ccs.reduce((a, b) => (b.size > a.size ? b : a));
          out.device = [
            (wx0 + big.minx) / W, (wy0 + big.miny) / H,
            (big.maxx - big.minx + 1) / W, (big.maxy - big.miny + 1) / H,
          ];
          grooved.add(k.id);
        }
      }
    }

    // --- fallback: mask omitted the socket → the authored template rect --------------
    // (device-region-normalized → panel space: y and h scale by devFrac)
    if (!out.device && !k.baked) {
      out.device = [k.rect[0], k.rect[1] * devFrac, k.rect[2], k.rect[3] * devFrac];
    }

    // --- STRIP cells by COLOUR IDENTITY ----------------------------------------------
    // A colour owning N cells (toggle off/on, play/pause) contributes its N largest
    // blobs, split left→right — never matched against OTHER colours' positions.
    if (k.cells.length) {
      bin.fill(0);
      let stripCount = 0;
      for (let i = devRow * W; i < N; i++) if (assign[i] === ki) { bin[i] = 1; stripCount++; }
      if (stripCount >= minBlob) {
        fillHoles(bin, W, H);
        const ccs = components(bin, W, H)
          .filter((c) => c.size >= minBlob)
          // degenerate strip-sliver filter (extract9): a real part is at least 1% of
          // the panel in BOTH dimensions — kills 1px-tall colour smears along cell edges
          .filter((c) => c.maxx - c.minx + 1 >= 0.01 * W && c.maxy - c.miny + 1 >= 0.01 * H)
          .sort((a, b) => b.size - a.size)
          .slice(0, k.cells.length)
          .sort((a, b) => a.minx - b.minx);
        ccs.forEach((c, i) => { if (k.cells[i]) cells[k.cells[i]] = ccBox(c, W, H); });
      }
    }

    regions[k.id] = out;
  });

  // --- GRADIENT-FIT refinement (extract9/10) ------------------------------------------
  // Circle-fit every knob socket on |∇| of the paint panel (material-agnostic; <3px
  // residual in the experiment) → knob `seat` + authoritative `device`; the median knob
  // offset becomes the GLOBAL DRIFT. Drift COMPOSES with the extract8 refinements above
  // instead of clobbering them: snap-x keeps its painted x (drift corrects y only),
  // groove-extent seek is already fully paint-measured (no drift), everything else gets
  // the full drift vector. Toggles + non-grooved sliders then get an rrect-fit of their
  // slot perimeter (extract10's treatment). Runs at the work resolution (≤1400w → the
  // 3px search step ≈ 0.21% of panel width; fine for placement).
  const knobKeys = keys.filter((k) => k.kind === "knob" && regions[k.id]?.maskDevice);
  const rrKeys = keys.filter((k) =>
    !k.baked && (k.kind === "toggle" || (k.kind === "slider" && !grooved.has(k.id))) &&
    regions[k.id]?.maskDevice && regions[k.id]?.device);
  if (knobKeys.length || rrKeys.length) {
    const gm = gradientMag(grayscale({ data: pd, width: W, height: H }), W, H);
    if (knobKeys.length) {
      const samples: [number, number][] = [];
      for (const k of knobKeys) {
        const mb = regions[k.id].maskDevice!;
        const f = circleFit(gm, W, H, mb);
        samples.push([f.cx - (mb[0] + mb[2] / 2) * W, f.cy - (mb[1] + mb[3] / 2) * H]);
        regions[k.id].device = [(f.cx - f.r) / W, (f.cy - f.r) / H, (2 * f.r) / W, (2 * f.r) / H];
        regions[k.id].seat = [f.cx / W, f.cy / H, f.r / W];
      }
      const [gdx, gdy] = globalDrift(samples, W, H);
      for (const k of keys) {
        if (k.kind === "knob" || grooved.has(k.id)) continue;
        const r = regions[k.id];
        if (!r?.maskDevice || !r.device) continue;
        const x = snapped.has(k.id) ? r.device[0] : r.maskDevice[0] + gdx;
        r.device = [x, r.maskDevice[1] + gdy, r.maskDevice[2], r.maskDevice[3]];
      }
    }
    for (const k of rrKeys) {
      const r = regions[k.id];
      const f = rrectFit(gm, W, H, r.device!);
      r.device = [(f.cx - f.w / 2) / W, (f.cy - f.h / 2) / H, f.w / W, f.h / H];
    }
  }

  return { devFrac, regions, cells };
}

// ============================================================
// Player-facing payload: panel-space boxes converted to the DEVICE region (the same
// space as template rects), plus baked-button press SILHOUETTES cut from the mask.
// ============================================================
export interface SkinMaskAlign {
  // per-region placement, normalized to the DEVICE region (template-rect space)
  regions: Record<string, MaskRegionOut>;
  // baked-button press ink: white-on-transparent silhouette (data URL) + the rect to
  // place it at — the maskDevice crop TRANSLATED by the snap delta, so mask-size:100%
  // maps silhouette pixels 1:1 onto the painted button (never `contain` — the contain
  // rescale was the oversize bug).
  buttonMasks: Record<string, { url: string; rect: Box }>;
}

const toDev = (b: Box, devFrac: number): Box => [b[0], b[1] / devFrac, b[2], b[3] / devFrac];

// Cut a button's SILHOUETTE from the mask panel: near-colour pixels → opaque white,
// cropped around `box` dilated by `dilate` (the blob draws slightly inset — the
// dilation lets the press ink cover the full button). Returns a data-URL mask image.
function cutMaskSilhouette(
  mask: HTMLCanvasElement, box: Box, rgb: [number, number, number], dilate = 0.12,
): { url: string; crop: Box } | null {
  const MW = mask.width, MH = mask.height;
  const crop: Box = [box[0] - box[2] * dilate / 2, box[1] - box[3] * dilate / 2, box[2] * (1 + dilate), box[3] * (1 + dilate)];
  const x = Math.max(0, Math.round(crop[0] * MW)), y = Math.max(0, Math.round(crop[1] * MH));
  const w = Math.min(MW - x, Math.round(crop[2] * MW)), h = Math.min(MH - y, Math.round(crop[3] * MH));
  if (w < 2 || h < 2) return null;
  const ctx = mask.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  const src = ctx.getImageData(x, y, w, h).data;
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const cc = c.getContext("2d")!;
  const out = cc.createImageData(w, h);
  for (let i = 0; i < w * h; i++) {
    const dr = src[i * 4] - rgb[0], dg = src[i * 4 + 1] - rgb[1], db = src[i * 4 + 2] - rgb[2];
    if (dr * dr + dg * dg + db * db < 7000) {
      out.data[i * 4] = out.data[i * 4 + 1] = out.data[i * 4 + 2] = 255;
      out.data[i * 4 + 3] = 255;
    }
  }
  cc.putImageData(out, 0, 0);
  return { url: c.toDataURL(), crop: [x / MW, y / MH, w / MW, h / MH] };
}

// Convert an extraction result to the player payload. `mask` is the (post-split, full
// resolution) mask panel — silhouettes are cut from it at native res.
export function toSkinMaskAlign(
  res: MaskAlignResult, mask: HTMLCanvasElement, keys: MaskKey[],
): SkinMaskAlign {
  const regions: Record<string, MaskRegionOut> = {};
  const buttonMasks: Record<string, { url: string; rect: Box }> = {};
  for (const k of keys) {
    const r = res.regions[k.id];
    if (!r) continue;
    regions[k.id] = {
      ...(r.maskDevice ? { maskDevice: toDev(r.maskDevice, res.devFrac) } : {}),
      ...(r.device ? { device: toDev(r.device, res.devFrac) } : {}),
      ...(r.seat ? { seat: [r.seat[0], r.seat[1] / res.devFrac, r.seat[2]] as [number, number, number] } : {}),
    };
    // baked buttons: press-darkening silhouette from the RAW mask blob, positioned at
    // the crop rect translated by the snap delta (snapped centre − mask centre).
    if (k.baked && r.maskDevice && r.device) {
      const sil = cutMaskSilhouette(mask, r.maskDevice, hexToRgb(k.color));
      if (sil) {
        const dx = (r.device[0] + r.device[2] / 2) - (r.maskDevice[0] + r.maskDevice[2] / 2);
        const dy = (r.device[1] + r.device[3] / 2) - (r.maskDevice[1] + r.maskDevice[3] / 2);
        const rect: Box = [sil.crop[0] + dx, sil.crop[1] + dy, sil.crop[2], sil.crop[3]];
        buttonMasks[k.id] = { url: sil.url, rect: toDev(rect, res.devFrac) };
      }
    }
  }
  return { regions, buttonMasks };
}
