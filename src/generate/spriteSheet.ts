// spriteSheet.ts — sprite-sheet alignment for skeuomorphic skin generation.
//
// A single image generation produces, in ONE image:
//   - a DEVICE (top region, height DEV_H) with empty dark control "sockets"
//   - a SPRITE STRIP (bottom region) with one finished control per labeled cell.
// We cut each control sprite from its KNOWN cell (deterministic geometry) and
// overlay it onto the device's matching socket. The device sockets DRIFT during
// paint/expansion, so sockets are DETECTED in the device and each template
// control-slot is MATCHED to its nearest detected socket (template positions as
// priors, greedy nearest-neighbour, one socket per slot) — not blind-classified.
//
// Pure TypeScript, browser-safe: operates on RGBA pixel buffers (the kind you get
// from canvas getImageData). No Node-only imports, no npm deps. Connected-components
// is implemented here via an explicit-stack flood fill.

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A flat RGBA image: `data` is row-major, 4 bytes/pixel (r,g,b,a), 0..255. */
export interface RGBAImage {
  data: Uint8ClampedArray;
  width: number;
  height: number;
}

export type ControlKind = "screen" | "slider" | "button" | "knob";

/** A control as defined in the blueprint/layout. `rect` is normalized to the
 *  DEVICE region: [x, y, w, h] in 0..1 of (W x DEV_H). */
export interface LayoutControl {
  id: string;
  kind: ControlKind;
  rect: [number, number, number, number];
}

/** The layout.json shape produced by the blueprint builder. */
export interface Layout {
  W: number;
  H: number;
  DEV_H: number;
  controls: LayoutControl[];
  /** ids of controls that have a generated sprite in the strip, IN STRIP ORDER. */
  sprite_controls: string[];
}

/** A cut sprite: an isolated RGBA tile (already alpha-masked to its shape). */
export interface Sprite {
  rgba: Uint8ClampedArray;
  w: number;
  h: number;
}

/** A detected dark socket (connected component) in DEVICE pixel coordinates. */
export interface Socket {
  cx: number;
  cy: number;
  /** nominal radius = (bboxW + bboxH) / 4 */
  r: number;
  area: number;
  /** bbox aspect ratio = bboxW / bboxH */
  aspect: number;
  bboxW: number;
  bboxH: number;
}

// ---------------------------------------------------------------------------
// Small RGBA helpers
// ---------------------------------------------------------------------------

const idx = (x: number, y: number, w: number) => (y * w + x) * 4;

/** sRGB-ish luminance, 0..255. */
function luma(r: number, g: number, b: number): number {
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function makeRGBA(w: number, h: number): RGBAImage {
  return { data: new Uint8ClampedArray(w * h * 4), width: w, height: h };
}

/** Nearest-neighbour resample of an RGBA tile to (nw, nh). Cheap, dependency-free,
 *  and adequate for seating already-small sprites onto sockets. */
function resizeNearest(
  src: Uint8ClampedArray,
  sw: number,
  sh: number,
  nw: number,
  nh: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(nw * nh * 4);
  for (let y = 0; y < nh; y++) {
    const sy = Math.min(sh - 1, Math.floor((y * sh) / nh));
    for (let x = 0; x < nw; x++) {
      const sx = Math.min(sw - 1, Math.floor((x * sw) / nw));
      const si = (sy * sw + sx) * 4;
      const di = (y * nw + x) * 4;
      out[di] = src[si];
      out[di + 1] = src[si + 1];
      out[di + 2] = src[si + 2];
      out[di + 3] = src[si + 3];
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Geometry masks (mirror the blueprint builder's cut shapes)
// ---------------------------------------------------------------------------

/** Coverage 0..1 of pixel (x,y) inside an ellipse inscribed in [0,w)x[0,h). */
function ellipseAlpha(x: number, y: number, w: number, h: number): number {
  const rx = w / 2,
    ry = h / 2;
  const nx = (x + 0.5 - rx) / rx;
  const ny = (y + 0.5 - ry) / ry;
  return nx * nx + ny * ny <= 1 ? 1 : 0;
}

/** Coverage 0..1 for a rounded rect inscribed in [0,w)x[0,h) with corner radius r. */
function rrectAlpha(x: number, y: number, w: number, h: number, r: number): number {
  const px = x + 0.5,
    py = y + 0.5;
  const rr = Math.max(0, Math.min(r, Math.min(w, h) / 2));
  // inside the straight edges (inset by rr) -> fully covered
  const inX = px >= rr && px <= w - rr;
  const inY = py >= rr && py <= h - rr;
  if (inX || inY) {
    return px >= 0 && px <= w && py >= 0 && py <= h ? 1 : 0;
  }
  // corner regions -> distance to nearest corner centre
  const cxp = px < rr ? rr : w - rr;
  const cyp = py < rr ? rr : h - rr;
  const dx = px - cxp,
    dy = py - cyp;
  return dx * dx + dy * dy <= rr * rr ? 1 : 0;
}

// ---------------------------------------------------------------------------
// cutSprites — cut each sprite-control from its known strip cell.
// ---------------------------------------------------------------------------

/**
 * Cut each sprite-control from its known cell in the combined image, using a
 * geometric alpha mask (circle for button/knob, rounded-rect for slider).
 *
 * Cell geometry mirrors the blueprint builder exactly:
 *   cell_w = W / sprite_controls.length
 *   cx = i*cell_w + cell_w/2           (i = index within sprite_controls)
 *   cy = DEV_H + STRIP_H*0.42
 *   size: slider = cell_w*0.5 x cell_w*0.28 ; button/knob = cell_w*0.42 (circle)
 *
 * The combined image may be at a different resolution than the blueprint, so cell
 * coordinates are scaled by (W_img/W_bp, H_img/H_bp).
 */
export function cutSprites(
  combined: RGBAImage,
  layout: Layout,
): Record<string, Sprite> {
  const { W: BW, H: BH, DEV_H } = layout;
  const STRIP_H = BH - DEV_H;
  const sc = layout.sprite_controls;
  const cellW = BW / sc.length;
  const byId = new Map(layout.controls.map((c) => [c.id, c]));

  const sxScale = combined.width / BW;
  const syScale = combined.height / BH;

  const out: Record<string, Sprite> = {};
  for (let i = 0; i < sc.length; i++) {
    const id = sc[i];
    const ctrl = byId.get(id);
    if (!ctrl) continue;
    const kind = ctrl.kind;

    const cxBp = i * cellW + cellW / 2;
    const cyBp = DEV_H + STRIP_H * 0.42;
    const wBp = kind === "slider" ? cellW * 0.5 : cellW * 0.42;
    const hBp = kind === "slider" ? cellW * 0.28 : cellW * 0.42;

    const x0 = Math.round((cxBp - wBp / 2) * sxScale);
    const y0 = Math.round((cyBp - hBp / 2) * syScale);
    const x1 = Math.round((cxBp + wBp / 2) * sxScale);
    const y1 = Math.round((cyBp + hBp / 2) * syScale);
    const cw = Math.max(1, x1 - x0);
    const ch = Math.max(1, y1 - y0);

    const tile = new Uint8ClampedArray(cw * ch * 4);
    for (let yy = 0; yy < ch; yy++) {
      const sy = y0 + yy;
      for (let xx = 0; xx < cw; xx++) {
        const sx = x0 + xx;
        const di = (yy * cw + xx) * 4;
        let cov = 0;
        if (kind === "slider") cov = rrectAlpha(xx, yy, cw, ch, ch * 0.45);
        else cov = ellipseAlpha(xx, yy, cw, ch);
        if (cov <= 0) {
          tile[di + 3] = 0;
          continue;
        }
        if (sx < 0 || sx >= combined.width || sy < 0 || sy >= combined.height) {
          tile[di + 3] = 0;
          continue;
        }
        const si = idx(sx, sy, combined.width);
        tile[di] = combined.data[si];
        tile[di + 1] = combined.data[si + 1];
        tile[di + 2] = combined.data[si + 2];
        tile[di + 3] = Math.round(cov * 255);
      }
    }
    out[id] = { rgba: tile, w: cw, h: ch };
  }
  return out;
}

// ---------------------------------------------------------------------------
// detectSockets — connected components of DARK pixels inside the body.
// ---------------------------------------------------------------------------

/**
 * Find dark control sockets in the device image: connected components of pixels
 * that are inside the body (alpha > 128) AND dark (luma < darkThreshold).
 * Screens (very large blobs, or wide-aspect blobs) are filtered out.
 *
 * Connected-components via explicit-stack flood fill (4-connectivity). No deps.
 */
export function detectSockets(
  device: RGBAImage,
  opts: { darkThreshold?: number; minAreaFrac?: number } = {},
): Socket[] {
  const { width: W, height: H, data } = device;
  const darkT = opts.darkThreshold ?? 80;
  const minArea = (opts.minAreaFrac ?? 0.0008) * W * H;

  // dark-mask
  const mask = new Uint8Array(W * H);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = idx(x, y, W);
      const a = data[i + 3];
      if (a <= 128) continue;
      if (luma(data[i], data[i + 1], data[i + 2]) < darkT) mask[y * W + x] = 1;
    }
  }

  const seen = new Uint8Array(W * H);
  const stack: number[] = [];
  const sockets: Socket[] = [];

  for (let p0 = 0; p0 < W * H; p0++) {
    if (mask[p0] === 0 || seen[p0]) continue;
    // flood fill this component
    stack.length = 0;
    stack.push(p0);
    seen[p0] = 1;
    let area = 0;
    let sumX = 0,
      sumY = 0;
    let minX = W,
      minY = H,
      maxX = 0,
      maxY = 0;
    while (stack.length) {
      const p = stack.pop() as number;
      const x = p % W;
      const y = (p - x) / W;
      area++;
      sumX += x;
      sumY += y;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      // 4-neighbours
      if (x > 0 && mask[p - 1] && !seen[p - 1]) {
        seen[p - 1] = 1;
        stack.push(p - 1);
      }
      if (x < W - 1 && mask[p + 1] && !seen[p + 1]) {
        seen[p + 1] = 1;
        stack.push(p + 1);
      }
      if (y > 0 && mask[p - W] && !seen[p - W]) {
        seen[p - W] = 1;
        stack.push(p - W);
      }
      if (y < H - 1 && mask[p + W] && !seen[p + W]) {
        seen[p + W] = 1;
        stack.push(p + W);
      }
    }
    if (area < minArea) continue;
    const bw = maxX - minX + 1;
    const bh = maxY - minY + 1;
    const aspect = bw / Math.max(1, bh);
    sockets.push({
      cx: sumX / area,
      cy: sumY / area,
      r: (bw + bh) / 4,
      area,
      aspect,
      bboxW: bw,
      bboxH: bh,
    });
  }

  // Filter out only the genuinely huge screen blobs (the visualizer); keep
  // everything else as a candidate. We deliberately do NOT drop wide-aspect
  // blobs: a slider socket is legitimately wide and looks identical to a marquee
  // readout — the difference is which template SLOT has a prior over it. The
  // template-prior nearest-neighbour matcher resolves that; unmatched candidates
  // (marquee, spare screens) are simply never seated. This keeps the slider
  // socket alive instead of throwing it away with the marquee.
  const devArea = W * H;
  const screenAreaFrac = 0.06;
  return sockets.filter((s) => s.area <= screenAreaFrac * devArea);
}

// ---------------------------------------------------------------------------
// matchSlots — greedy nearest-neighbour, template positions as priors.
// ---------------------------------------------------------------------------

/**
 * Match each template control slot to its nearest UNUSED detected socket, using
 * the slot's template position (scaled to device px) as the prior. Greedy:
 * pairs are assigned in increasing distance order so the most-confident matches
 * win their socket first; each socket is used at most once.
 *
 * @param controls       the control slots to seat (the sprite_controls' controls)
 * @param sockets        detected sockets (device px coords)
 * @param deviceW/deviceH device pixel dimensions (the rect is normalized to these)
 */
export function matchSlots(
  controls: LayoutControl[],
  sockets: Socket[],
  deviceW: number,
  deviceH: number,
): Record<string, Socket> {
  // prior centre for each slot, in device px
  const priors = controls.map((c) => {
    const [x, y, w, h] = c.rect;
    return { id: c.id, cx: (x + w / 2) * deviceW, cy: (y + h / 2) * deviceH };
  });

  // all (slot, socket) pairs by distance
  type Pair = { si: number; ki: number; d: number };
  const pairs: Pair[] = [];
  for (let si = 0; si < priors.length; si++) {
    for (let ki = 0; ki < sockets.length; ki++) {
      const dx = priors[si].cx - sockets[ki].cx;
      const dy = priors[si].cy - sockets[ki].cy;
      pairs.push({ si, ki, d: Math.hypot(dx, dy) });
    }
  }
  pairs.sort((a, b) => a.d - b.d);

  const slotUsed = new Array(priors.length).fill(false);
  const sockUsed = new Array(sockets.length).fill(false);
  const out: Record<string, Socket> = {};
  for (const p of pairs) {
    if (slotUsed[p.si] || sockUsed[p.ki]) continue;
    slotUsed[p.si] = true;
    sockUsed[p.ki] = true;
    out[priors[p.si].id] = sockets[p.ki];
  }
  return out;
}

// ---------------------------------------------------------------------------
// composeSkin — alpha-composite each sprite onto its matched socket.
// ---------------------------------------------------------------------------

/**
 * Composite each matched sprite onto the device, scaled to cover its socket
 * (~`scale`× the socket diameter, preserving sprite aspect) and centred on the
 * socket centre. Returns a fresh RGBA frame (the device is copied first).
 */
export function composeSkin(
  device: RGBAImage,
  sprites: Record<string, Sprite>,
  matches: Record<string, Socket>,
  scale = 1.15,
): RGBAImage {
  const { width: W, height: H } = device;
  const out = makeRGBA(W, H);
  out.data.set(device.data);

  for (const [id, sock] of Object.entries(matches)) {
    const sp = sprites[id];
    if (!sp) continue;
    // Scale the sprite to cover the socket's bounding box (preserving sprite
    // aspect), times `scale` for a small overhang. For a round socket
    // bboxW≈bboxH≈2r so this matches a diameter fit; for a WIDE slider socket it
    // fits the width without over-inflating the (slim) handle vertically.
    const k = scale * Math.min(sock.bboxW / sp.w, sock.bboxH / sp.h);
    const nw = Math.max(1, Math.round(sp.w * k));
    const nh = Math.max(1, Math.round(sp.h * k));
    const tile = resizeNearest(sp.rgba, sp.w, sp.h, nw, nh);

    const ox = Math.round(sock.cx - nw / 2);
    const oy = Math.round(sock.cy - nh / 2);
    alphaComposite(out, tile, nw, nh, ox, oy);
  }
  return out;
}

/** Source-over composite of an RGBA tile onto `dst` at (ox, oy). */
function alphaComposite(
  dst: RGBAImage,
  tile: Uint8ClampedArray,
  tw: number,
  th: number,
  ox: number,
  oy: number,
): void {
  const { width: W, height: H, data } = dst;
  for (let y = 0; y < th; y++) {
    const dy = oy + y;
    if (dy < 0 || dy >= H) continue;
    for (let x = 0; x < tw; x++) {
      const dx = ox + x;
      if (dx < 0 || dx >= W) continue;
      const si = (y * tw + x) * 4;
      const sa = tile[si + 3] / 255;
      if (sa <= 0) continue;
      const di = idx(dx, dy, W);
      const da = data[di + 3] / 255;
      const oa = sa + da * (1 - sa);
      if (oa <= 0) continue;
      data[di] = (tile[si] * sa + data[di] * da * (1 - sa)) / oa;
      data[di + 1] = (tile[si + 1] * sa + data[di + 1] * da * (1 - sa)) / oa;
      data[di + 2] = (tile[si + 2] * sa + data[di + 2] * da * (1 - sa)) / oa;
      data[di + 3] = Math.round(oa * 255);
    }
  }
}

// ---------------------------------------------------------------------------
// Convenience: crop the device region out of a body-masked combined image.
// ---------------------------------------------------------------------------

/**
 * The device frame is the TOP region (height DEV_H/H of the image) of a
 * body-masked image (alpha = transparent outside the device). Returns that crop.
 */
export function cropDeviceRegion(masked: RGBAImage, layout: Layout): RGBAImage {
  const devBottom = Math.round((layout.DEV_H / layout.H) * masked.height);
  const W = masked.width;
  const out = makeRGBA(W, devBottom);
  out.data.set(masked.data.subarray(0, W * devBottom * 4));
  return out;
}

/**
 * Full pipeline: cut sprites from `combined`, detect sockets in the device crop
 * of `masked`, match template slots to sockets, and compose. Returns the final
 * frame plus the intermediate matches/sockets for inspection.
 */
export function alignSpriteSheet(
  combined: RGBAImage,
  masked: RGBAImage,
  layout: Layout,
): {
  frame: RGBAImage;
  device: RGBAImage;
  sprites: Record<string, Sprite>;
  sockets: Socket[];
  matches: Record<string, Socket>;
} {
  const device = cropDeviceRegion(masked, layout);
  const sprites = cutSprites(combined, layout);
  const sockets = detectSockets(device);
  const spriteControls = layout.controls.filter((c) =>
    layout.sprite_controls.includes(c.id),
  );
  const matches = matchSlots(spriteControls, sockets, device.width, device.height);
  const frame = composeSkin(device, sprites, matches);
  return { frame, device, sprites, sockets, matches };
}
