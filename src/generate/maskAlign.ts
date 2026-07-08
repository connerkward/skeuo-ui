// ============================================================
// maskAlign — read the model-emitted REGION MASK back out and refine it onto the
// painted skin. TS/canvas port of the mask-align experiment's extract8.py
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
  device?: Box;       // snap-X-refined onto the painted feature (place from THIS)
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
// label 4-connected components of a binary mask, return them sized+bboxed
function components(bin: Uint8Array, W: number, H: number): CC[] {
  const N = W * H;
  const label = new Int32Array(N).fill(-1);
  const queue = new Int32Array(N);
  const out: CC[] = [];
  for (let s = 0; s < N; s++) {
    if (!bin[s] || label[s] !== -1) continue;
    const id = out.length;
    let head = 0, tail = 0, size = 0, minx = W, miny = H, maxx = 0, maxy = 0;
    queue[tail++] = s; label[s] = id;
    while (head < tail) {
      const p = queue[head++]; size++;
      const x = p % W, y = (p / W) | 0;
      if (x < minx) minx = x; if (x > maxx) maxx = x;
      if (y < miny) miny = y; if (y > maxy) maxy = y;
      if (x > 0 && bin[p - 1] && label[p - 1] === -1) { label[p - 1] = id; queue[tail++] = p - 1; }
      if (x < W - 1 && bin[p + 1] && label[p + 1] === -1) { label[p + 1] = id; queue[tail++] = p + 1; }
      if (y > 0 && bin[p - W] && label[p - W] === -1) { label[p - W] = id; queue[tail++] = p - W; }
      if (y < H - 1 && bin[p + W] && label[p + W] === -1) { label[p + W] = id; queue[tail++] = p + W; }
    }
    out.push({ size, minx, miny, maxx, maxy });
  }
  return out;
}
const ccBox = (c: CC, W: number, H: number): Box =>
  [c.minx / W, c.miny / H, (c.maxx - c.minx + 1) / W, (c.maxy - c.miny + 1) / H];

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
      if (n >= minSnap) out.device = [sx / n / W - bw / 2, by, bw, bh];  // X only; keep mask Y
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
          .sort((a, b) => b.size - a.size)
          .slice(0, k.cells.length)
          .sort((a, b) => a.minx - b.minx);
        ccs.forEach((c, i) => { if (k.cells[i]) cells[k.cells[i]] = ccBox(c, W, H); });
      }
    }

    regions[k.id] = out;
  });

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
