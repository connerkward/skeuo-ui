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

// The "wells-only" blueprint (white bg) — fal's ENVELOPE input. Equivalent of
// draw_wells_only(): only the recessed wells/screens drawn, no body fill.
export function wellsOnlySvg(regs: Region[]): string {
  const body = regs.map(regionSvg).join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${GEN_W}" height="${GEN_H}" viewBox="0 0 ${GEN_W} ${GEN_H}"><rect width="${GEN_W}" height="${GEN_H}" fill="white"/>${body}</svg>`;
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
const BP_DARK = "rgb(24,24,28)";      // dark socket / cell outline
const BP_RING = "rgb(255,40,120)";    // bright magenta anchor ring

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
export function combinedBlueprint(regs: Region[]): CombinedBlueprint {
  const stripH = STRIP_H;         // remainder packs the control strip
  const H = COMBINED_H;           // = DEVICE_H + stripH, exactly 9:16
  const devFrac = DEVICE_FRAC;

  // sprite controls = interactive parts only, in stable (region) order.
  const spriteRegs = regs.filter((r) => spriteKindOf(r) !== null);

  const parts: string[] = [];
  parts.push(`<rect width="${GEN_W}" height="${H}" fill="white"/>`);

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

  // --- device sockets: MINIMAL guide (bright magenta keyline only, NO filled shape).
  // Don't draw socket shapes — they override the model's painted control shape. The
  // magenta keyline is just a visual anchor; the model paints inside/around it freely.
  for (const r of regs) {
    const x = r.rect.x * GEN_W, y = r.rect.y * GEN_H;
    const w = r.rect.w * GEN_W, h = r.rect.h * GEN_H;
    const ringW = Math.max(4, Math.round(Math.min(w, h) * 0.08));
    const pad = ringW / 2;
    // magenta outline ONLY — no filled shape to dictate control form
    const round = r.kind === "knob" || ((r.kind === "button" || r.kind === "display") && r.shape === "ellipse");
    if (round) {
      parts.push(ellipse(x - pad, y - pad, w + 2 * pad, h + 2 * pad, "none", BP_RING, ringW));
    } else {
      const rad0 = Math.min(w, h) * 0.3;
      parts.push(roundRect(x - pad, y - pad, w + 2 * pad, h + 2 * pad, rad0 + pad, "none", BP_RING, ringW));
    }
  }

  // --- bottom SPRITE STRIP: minimal guides + labels per control (NO SHAPES).
  // Just grid lines + labels — let the model paint freely. No filled circles/rects
  // to lock control form. detectCellContent will find what the model actually painted.
  const n = spriteRegs.length;
  const cellW = n > 0 ? GEN_W / n : GEN_W;
  const cells: BlueprintCell[] = [];
  spriteRegs.forEach((r, i) => {
    const kind = spriteKindOf(r)!;
    const cx = i * cellW + cellW / 2;
    // light grid line only (no filled shape)
    parts.push(`<line x1="${i * cellW}" y1="${GEN_H}" x2="${i * cellW}" y2="${H}" stroke="${BP_DARK}" stroke-width="1" opacity="0.2"/>`);
    // strip label = the human-readable hint for the model (bind/label), NOT the id
    const label = (r.label || r.bind || r.id).toUpperCase();
    parts.push(
      `<text x="${cx}" y="${GEN_H + stripH * 0.78}" font-family="Arial, sans-serif" font-weight="bold" ` +
      `font-size="26" fill="${BP_DARK}" text-anchor="middle">${escapeXml(label)}</text>`,
    );
    // cell crop box (full combined-image normalized) — detectCellContent finds actual content.
    const cw = cellW * 0.92;
    cells.push({
      bind: bindOf(r), kind,
      cellRect: [(cx - cw / 2) / GEN_W, (GEN_H + stripH * 0.06) / H, cw / GEN_W, (stripH * 0.62) / H],
    });
  });

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${GEN_W}" height="${H}" viewBox="0 0 ${GEN_W} ${H}">${parts.join("")}</svg>`;
  const controls: BlueprintControl[] = spriteRegs.map((r) => ({
    bind: bindOf(r), kind: spriteKindOf(r)!,
    rect: [r.rect.x, r.rect.y, r.rect.w, r.rect.h], // normalized to the DEVICE region (GEN_H)
  }));
  return { svg, layout: { devFrac, controls, cells }, width: GEN_W, height: H };
}

function escapeXml(s: string): string {
  return s.replace(/[<>&]/g, (c) => (c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&amp;"));
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
