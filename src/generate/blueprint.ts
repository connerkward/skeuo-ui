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
  stripDesc: string;   // enumerated control list for the paint prompt (no text drawn in-image)
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
    if (b.includes("prev") || b.includes("rew")) return `${sh} with a rewind icon (two left-pointing triangles) embossed ON ITS FACE`;
    if (b.includes("play")) return `${sh} with a play icon (one right-pointing triangle) embossed ON ITS FACE`;
    if (b.includes("next") || b.includes("fwd") || b.includes("forward")) return `${sh} with a fast-forward icon (two right-pointing triangles) embossed ON ITS FACE`;
    if (b.includes("stop")) return `${sh} with a stop icon (a filled square) embossed ON ITS FACE`;
    if (b.includes("pause")) return `${sh} with a pause icon (two vertical bars) embossed ON ITS FACE`;
    return sh;
  }
  if (kind === "knob") return `a round rotary knob with a pointer notch${r.label ? ` (${r.label})` : ""}`;
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
const BP_RING = "rgb(255,40,120)";    // bright magenta anchor ring (empty well → overlay)
const BP_BAKE = "rgb(0,200,255)";     // cyan ring = paint a REAL cohesive control here (baked, not a well)

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

  // sprite controls = interactive parts only, in stable (region) order. BAKED controls
  // are EXCLUDED — they're painted cohesively into the device body, not cut to the strip.
  const spriteRegs = regs.filter((r) => spriteKindOf(r) !== null && !r.baked);

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
  for (const r of regs) {
    const x = r.rect.x * GEN_W, y = r.rect.y * GEN_H;
    const w = r.rect.w * GEN_W, h = r.rect.h * GEN_H;
    const ringW = Math.max(4, Math.round(Math.min(w, h) * 0.08));
    const inset = ringW / 2;                 // keep the stroke's outer edge AT the rect boundary
    // magenta outline ONLY — no filled shape to dictate control form. Only KNOBS
    // (and round displays) get a circular guide; BUTTONS get a neutral rounded-rect
    // bounding guide so the model is free to paint any button shape inside it.
    const round = r.kind === "knob" || (r.kind === "display" && r.shape === "ellipse");
    // CYAN guide = "paint a REAL finished control here, integrated into the body"
    // (baked cluster); MAGENTA = empty well the player overlays a cut sprite onto.
    const strokeCol = r.baked ? BP_BAKE : BP_RING;
    if (round) {
      const d = Math.min(w, h);              // TRUE circle: diameter = shorter side
      const cx = x + w / 2, cy = y + h / 2;  // centered in the rect
      const rr = Math.max(0, d / 2 - inset);
      parts.push(`<circle cx="${cx}" cy="${cy}" r="${rr}" fill="none" stroke="${strokeCol}" stroke-width="${ringW}"/>`);
    } else {
      const rad0 = Math.min(w, h) * 0.3;
      parts.push(roundRect(x + inset, y + inset, w - 2 * inset, h - 2 * inset, Math.max(0, rad0 - inset), "none", strokeCol, ringW));
    }
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
  interface StripItem { bind: string; kind: SpriteKind; desc: string }
  const items: StripItem[] = [];
  for (const r of spriteRegs) {
    const kind = spriteKindOf(r)!;
    if (kind === "toggle") continue;  // toggles handled as an off/on pair below
    if (kind === "slider") continue;  // sliders/seek are NOT sprites — the skin/CSS renders the track + thumb
    const bind = bindOf(r);
    items.push({ bind, kind, desc: controlDesc(r, kind) });
    // PLAY/PAUSE is a two-state control (like the toggle off/on pair): emit a paired
    // PAUSE face — the SAME button body, only the icon differs — cut to <id>__pause and
    // swapped live by the player on play state. (id===bind for transport controls.)
    const isPlay = kind === "button" && /(^|_)play(_|$)/.test(bind) && !bind.includes("playlist");
    if (isPlay) items.push({
      bind: `${bind}__pause`, kind,
      desc: "the SAME push-button as the previous slot — IDENTICAL body, shape, size and material — but shown with a PAUSE icon (two vertical bars) embossed on its face instead of the play triangle",
    });
  }
  const hasToggle = spriteRegs.some((r) => spriteKindOf(r) === "toggle");
  if (hasToggle) {
    items.push({ bind: "switch-off", kind: "toggle", desc: "a toggle switch shown in its OFF position (lever/rocker down)" });
    items.push({ bind: "switch-on", kind: "toggle", desc: "the SAME toggle switch shown in its ON position (lever/rocker up)" });
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
    // faint magenta keyline anchor (guide only; the painter fills it + removes the magenta)
    const ringW = Math.max(4, Math.round(Math.min(cw, shh) * 0.05));
    const inset = ringW / 2;
    // knobs are round (rotary); buttons get a neutral rounded-rect slot so the model
    // paints whatever button shape it wants (the cut keeps the painted silhouette).
    const round = it.kind === "knob";
    if (round) {
      const d = Math.min(cw, shh);
      const acx = sx0 + cw / 2, acy = sy0 + shh / 2;
      const rr = Math.max(0, d / 2 - inset);
      parts.push(`<circle cx="${acx}" cy="${acy}" r="${rr}" fill="none" stroke="${BP_RING}" stroke-width="${ringW}"/>`);
    } else {
      const rad = Math.min(cw, shh) * 0.25;
      parts.push(roundRect(sx0 + inset, sy0 + inset, cw - 2 * inset, shh - 2 * inset, Math.max(0, rad - inset), "none", BP_RING, ringW));
    }
    cells.push({
      bind: it.bind, kind: it.kind,
      cellRect: [sx0 / GEN_W, sy0 / H, cw / GEN_W, shh / H],
    });
  });
  const stripDesc = items.map((it, i) => `slot ${i + 1}: ${it.desc}`).join("; ");

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${GEN_W}" height="${H}" viewBox="0 0 ${GEN_W} ${H}">${parts.join("")}</svg>`;
  const controls: BlueprintControl[] = spriteRegs.map((r) => ({
    bind: bindOf(r), kind: spriteKindOf(r)!,
    rect: [r.rect.x, r.rect.y, r.rect.w, r.rect.h], // normalized to the DEVICE region (GEN_H)
  }));
  return { svg, layout: { devFrac, controls, cells }, width: GEN_W, height: H, stripDesc };
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
