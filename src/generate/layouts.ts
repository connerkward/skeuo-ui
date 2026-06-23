// ============================================================
// LAYOUT-FIRST templates — a faithful TS port of the three
// `layout_*()` functions in generation/wild_sculpt.py.
//
// KEY PROPERTY (the reason these are portable to a serverless
// function with NO computer-vision): each function returns the
// SAME regions every call, independent of any body image. The
// arc-native control template is drawn FIRST; the image model
// grows the creature AROUND it. So coordinate math is all we need
// server-side — no mask, no BiRefNet, no detection.
//
// Canvas is 1024×1536, identical to the Python pipeline. Region
// rects are normalized (0..1), matching template.json on disk.
// ============================================================
import type { Region, Template, Kind } from "../template/schema";

export const GEN_W = 1024;
export const GEN_H = 1536;

// transport button size hierarchy (× base diameter) — PLAY dominates,
// stop is smallest. Mirrors BSIZE in wild_sculpt.py.
const BSIZE: Record<string, number> = {
  play: 1.5, pause: 1.0, prev: 0.9, next: 0.9, stop: 0.82,
};

export type LayoutVariant = "simple" | "radial" | "capsule" | "minimal";
export const LAYOUT_VARIANTS: LayoutVariant[] = ["simple", "radial", "capsule", "minimal"];

// internal builder mirroring the Python `add()` closures (px in, normalized out)
type AddExtra = Partial<Region> & { content?: Region["content"]; layer?: Region["layer"] };
function makeAdder(regs: Region[]) {
  return (id: string, kind: Kind, x: number, y: number, w: number, h: number, kw: AddExtra = {}) => {
    const { content = "sprite", layer = "components", ...rest } = kw;
    regs.push({
      id, kind, content, layer,
      rect: { x: x / GEN_W, y: y / GEN_H, w: w / GEN_W, h: h / GEN_H },
      ...rest,
    });
  };
}
const rad = (deg: number) => (deg * Math.PI) / 180;
// randomizer helpers (used by layoutRandom — user-triggered, so Math.random is fine)
const rnd = (a: number, b: number) => a + Math.random() * (b - a);
const chance = (p: number) => Math.random() < p;

// ---- simple: the friendly default — a COMPLETE, symmetric "classic rack":
// wide visualizer up top, marquee + clock row, full-width seek, a centred
// prev/play/next/stop transport (play dominant), and volume + balance knobs.
// ~11 controls, balanced on the centre line — what a first-time user starts on.
export function layoutSimple(): Region[] {
  const regs: Region[] = [];
  const add = makeAdder(regs);
  const mx = GEN_W * 0.08;                  // side margin
  const x0 = mx, w = GEN_W - 2 * mx, cx = GEN_W / 2;

  // wide visualizer screen up top
  add("visualizer", "display", x0, GEN_H * 0.12, w, GEN_H * 0.235,
    { content: "dynamic", layer: "screen", dynamicType: "visualizer" });

  // marquee (left) + clock (right) sharing one row beneath it
  const my = GEN_H * 0.385, mh = 70, clockW = w * 0.26;
  add("marquee", "display", x0, my, w - clockW - 20, mh,
    { content: "dynamic", layer: "screen", dynamicType: "marquee" });
  add("time", "display", x0 + w - clockW, my, clockW, mh,
    { content: "dynamic", layer: "screen", dynamicType: "time" });

  // full-width seek bar
  const sy = my + mh + 26;
  add("seek", "slider-h", x0, sy, w, 30, { bind: "seek", label: "Seek" });

  // transport row — prev / play / next / stop, play dominant, centred
  const playD = 150, smallD = 92, stopD = 78, gap = 40;
  const rowW = smallD + gap + playD + gap + smallD + gap + stopD;
  const tx = cx - rowW / 2, ty = sy + 60, cyR = ty + playD / 2;
  add("prev", "button", tx, cyR - smallD / 2, smallD, smallD, { bind: "prev", label: "prev", shape: "ellipse" });
  add("play", "button", tx + smallD + gap, cyR - playD / 2, playD, playD, { bind: "play", label: "play", shape: "ellipse" });
  add("next", "button", tx + smallD + gap + playD + gap, cyR - smallD / 2, smallD, smallD, { bind: "next", label: "next", shape: "ellipse" });
  add("stop", "button", tx + smallD + gap + playD + gap + smallD + gap, cyR - stopD / 2, stopD, stopD, { bind: "stop", label: "stop", shape: "ellipse" });

  // volume + balance knobs, centred under the transport
  const kd = 116, kgap = 90, kw = kd + kgap + kd, kx = cx - kw / 2, ky = cyR + playD / 2 + 48;
  add("knob0", "knob", kx, ky, kd, kd, { bind: "volume", label: "VOL" });
  add("knob1", "knob", kx + kd + kgap, ky, kd, kd, { bind: "balance", label: "BAL" });

  return regs;
}

// 6-band EQ with shuffle / EQ-on toggles flanking it — shared by the randomizer.
function addEq(add: ReturnType<typeof makeAdder>, x0: number, y: number, w: number) {
  const eh = 128, sww = 44;
  add("sw0", "toggle", x0, y + 6, sww, eh - 12, { bind: "shuffle", label: "SHUF" });
  add("sw1", "toggle", x0 + w - sww, y + 6, sww, eh - 12, { bind: "eqOn", label: "EQ" });
  const sx = x0 + sww + w * 0.05, ex = x0 + w - sww - w * 0.05, sw_ = (ex - sx) / 6;
  for (let i = 0; i < 6; i++)
    add(`eq${i}`, "slider-v", sx + i * sw_ + sw_ * 0.28, y, sw_ * 0.44, eh,
      { bind: "eqBand", group: "eq-bands", index: i, label: "" });
}

// ---- random: a HEURISTIC randomizer. Not chaos — controls drop into vertical
// zones (or orbit a dial), with randomized sizes / inclusion, so every roll is a
// plausible, usable, mostly non-overlapping player. Drives the 🎲 button.
export function layoutRandom(): Region[] {
  const regs: Region[] = [];
  const add = makeAdder(regs);
  const mx = GEN_W * rnd(0.06, 0.11);
  const x0 = mx, w = GEN_W - 2 * mx, cx = GEN_W / 2;

  if (chance(0.4)) {
    // dial archetype: round visualizer, buttons orbiting the lower rim, arc seek
    const cyD = GEN_H * rnd(0.24, 0.30), rg = GEN_W * rnd(0.16, 0.21);
    add("visualizer", "display", cx - rg, cyD - rg, 2 * rg, 2 * rg,
      { content: "dynamic", layer: "screen", dynamicType: "visualizer", shape: "ellipse" });
    const rc = rg + rnd(60, 92);
    const btns = chance(0.5) ? ["prev", "play", "pause", "next"] : ["prev", "play", "next"];
    // keep transport in the LOWER arc (centred on 90° = bottom) so it never rides
    // up into the knob "eyes" at the top of the dial.
    const spread = rnd(58, 82), start = 90 - spread, stepA = (2 * spread) / (btns.length - 1);
    let maxBd = 0;
    btns.forEach((b, i) => {
      const a = rad(start + i * stepA), bd = 64 * (BSIZE[b] ?? 1);
      maxBd = Math.max(maxBd, bd);
      add(b, "button", cx + rc * Math.cos(a) - bd / 2, cyD + rc * Math.sin(a) - bd / 2, bd, bd,
        { bind: b, label: b, shape: "ellipse" });
    });
    const side = 2 * (rc + 18);
    add("seek", "slider-arc", cx - side / 2, cyD - side / 2, side, side,
      { bind: "seek", label: "Seek", arc: { start: 200, end: 340 } });
    if (chance(0.6)) {  // knobs as "eyes" flanking the TOP of the dial (270°)
      const kd = rnd(64, 86), ka = rad(rnd(248, 262)), ox = rc * Math.cos(ka), oy = rc * Math.sin(ka);
      add("knob0", "knob", cx + ox - kd / 2, cyD + oy - kd / 2, kd, kd, { bind: "volume", label: "VOL" });
      add("knob1", "knob", cx - ox - kd / 2, cyD + oy - kd / 2, kd, kd, { bind: "balance", label: "BAL" });
    }
    // marquee clears the LOWEST orbiting button (bottom of the ring at 90°), not
    // just the glass — otherwise a big orbit radius overlaps the marquee.
    let y = cyD + rc + maxBd / 2 + rnd(34, 64);
    add("marquee", "display", x0, y, w, rnd(40, 64),
      { content: "dynamic", layer: "screen", dynamicType: "marquee" });
    y += 96;
    if (chance(0.5) && y < GEN_H * 0.6) { addEq(add, x0, y, w); y += 150; }
    if (chance(0.45) && y < GEN_H * 0.82)
      add("playlist", "display", x0, y, w, GEN_H * 0.94 - y,
        { content: "dynamic", layer: "screen", dynamicType: "playlist" });
    return regs;
  }

  // stack archetype: a vertical flow of zones
  let y = GEN_H * rnd(0.09, 0.14);
  const visH = GEN_H * rnd(0.16, 0.24);
  if (chance(0.25)) { const d = Math.min(w, visH * 1.3); add("visualizer", "display", cx - d / 2, y, d, d, { content: "dynamic", layer: "screen", dynamicType: "visualizer", shape: "ellipse" }); y += d; }
  else { add("visualizer", "display", x0, y, w, visH, { content: "dynamic", layer: "screen", dynamicType: "visualizer" }); y += visH; }
  y += rnd(28, 56);

  const mh = rnd(42, 64);
  if (chance(0.5)) { const cwc = w * 0.27; add("marquee", "display", x0, y, w - cwc - 20, mh, { content: "dynamic", layer: "screen", dynamicType: "marquee" }); add("time", "display", x0 + w - cwc, y, cwc, mh, { content: "dynamic", layer: "screen", dynamicType: "time" }); }
  else add("marquee", "display", x0, y, w, mh, { content: "dynamic", layer: "screen", dynamicType: "marquee" });
  y += mh + rnd(22, 40);

  add("seek", "slider-h", x0, y, w, 30, { bind: "seek", label: "Seek" });
  y += rnd(58, 84);

  const set = ["play"];
  if (chance(0.92)) { set.unshift("prev"); set.push("next"); }
  if (chance(0.3)) set.splice(1, 0, "pause");
  if (chance(0.4)) set.push("stop");
  const sizes = set.map((b) => 92 * (BSIZE[b] ?? 1)), gap = rnd(30, 52);
  const rowW = sizes.reduce((s, d) => s + d, 0) + gap * (set.length - 1), maxD = Math.max(...sizes);
  let tx = cx - rowW / 2; const cyR = y + maxD / 2;
  set.forEach((b, i) => { add(b, "button", tx, cyR - sizes[i] / 2, sizes[i], sizes[i], { bind: b, label: b, shape: "ellipse" }); tx += sizes[i] + gap; });
  y = cyR + maxD / 2 + rnd(36, 60);

  if (chance(0.8)) { const two = chance(0.6), kd = rnd(96, 124), kw = two ? kd * 2 + 90 : kd, kx = cx - kw / 2; add("knob0", "knob", kx, y, kd, kd, { bind: "volume", label: "VOL" }); if (two) add("knob1", "knob", kx + kd + 90, y, kd, kd, { bind: "balance", label: "BAL" }); y += kd + rnd(28, 48); }
  if (chance(0.4) && y < GEN_H * 0.62) { addEq(add, x0, y, w); y += 150; }
  if (chance(0.4) && y < GEN_H * 0.8) add("playlist", "display", x0, y, w, GEN_H * 0.93 - y, { content: "dynamic", layer: "screen", dynamicType: "playlist" });
  return regs;
}

// ---- radial: round dial, buttons orbiting lower rim, knobs as eyes, seek ring
export function layoutRadial(): Region[] {
  const regs: Region[] = [];
  const add = makeAdder(regs);
  const cx = GEN_W / 2, cy = GEN_H * 0.287, r = GEN_W * 0.21;
  const d = 64.0;
  const rg = r - d - 12;          // dial glass radius
  const rc = rg + 8 + d / 2;      // orbit/ring radius
  add("visualizer", "display", cx - rg, cy - rg, 2 * rg, 2 * rg,
    { content: "dynamic", layer: "screen", dynamicType: "visualizer", shape: "ellipse" });
  const ring: [number, string][] = [[150, "prev"], [120, "play"], [90, "pause"], [60, "stop"], [30, "next"]];
  for (const [ang, b] of ring) {
    const a = rad(ang), bd = d * BSIZE[b];
    add(b, "button", cx + rc * Math.cos(a) - bd / 2, cy + rc * Math.sin(a) - bd / 2, bd, bd,
      { bind: b, label: b, shape: "ellipse" });
  }
  const kd = 72.0;
  const knobs: [number, string, string, string][] = [[205, "knob0", "volume", "VOL"], [335, "knob1", "balance", "BAL"]];
  for (const [ang, kid, bind, lab] of knobs) {
    const a = rad(ang);
    add(kid, "knob", cx + rc * Math.cos(a) - kd / 2, cy + rc * Math.sin(a) - kd / 2, kd, kd, { bind, label: lab });
  }
  const side = 2 * (rc + 14);     // seek ring: upper arc of the same radius
  add("seek", "slider-arc", cx - side / 2, cy - side / 2, side, side,
    { bind: "seek", label: "Seek", arc: { start: 212, end: 328 } });
  const my = cy + r + 16;
  add("marquee", "display", GEN_W * 0.18, my, GEN_W * 0.64, 38,
    { content: "dynamic", layer: "screen", dynamicType: "marquee" });
  const ey = my + 56, eh = 130;
  const ex0 = GEN_W * 0.17, span = GEN_W * 0.66;
  const sww = 42.0;
  add("sw0", "toggle", ex0, ey + 8, sww, eh - 16, { bind: "shuffle", label: "SHUF" });
  add("sw1", "toggle", ex0 + span - sww, ey + 8, sww, eh - 16, { bind: "eqOn", label: "EQ" });
  const sx = ex0 + sww + span * 0.05, exx = ex0 + span - sww - span * 0.05;
  const sw_ = (exx - sx) / 6;
  for (let i = 0; i < 6; i++) {
    add(`eq${i}`, "slider-v", sx + i * sw_ + sw_ * 0.28, ey, sw_ * 0.44, eh,
      { bind: "eqBand", group: "eq-bands", index: i, label: "" });
  }
  const py = ey + eh + 28;
  add("playlist", "display", GEN_W * 0.19, py, GEN_W * 0.62, GEN_H * 0.945 - py,
    { content: "dynamic", layer: "screen", dynamicType: "playlist" });
  return regs;
}

// ---- capsule: WMP9 dial pod left, buttons fully ringing it, pill marquee right
export function layoutCapsule(): Region[] {
  const regs: Region[] = [];
  const add = makeAdder(regs);
  const cx = GEN_W * 0.30, cy = GEN_H * 0.235, r = GEN_W * 0.205;
  const d = 56.0;
  const rg = r - d - 12;
  const rc = rg + 6 + d / 2;
  add("visualizer", "display", cx - rg, cy - rg, 2 * rg, 2 * rg,
    { content: "dynamic", layer: "screen", dynamicType: "visualizer", shape: "ellipse" });
  const ring: [number, string][] = [[40, "next"], [88, "stop"], [136, "pause"], [184, "play"], [232, "prev"]];
  for (const [ang, b] of ring) {
    const a = rad(ang), bd = d * BSIZE[b];
    add(b, "button", cx + rc * Math.cos(a) - bd / 2, cy + rc * Math.sin(a) - bd / 2, bd, bd,
      { bind: b, label: b, shape: "ellipse" });
  }
  const sws: [number, string, string, string][] = [[280, "sw0", "shuffle", "SHUF"], [322, "sw1", "eqOn", "EQ"]];
  for (const [ang, kid, bind, lab] of sws) {
    const a = rad(ang);
    add(kid, "toggle", cx + rc * Math.cos(a) - d * 0.42, cy + rc * Math.sin(a) - d * 0.55,
      d * 0.84, d * 1.1, { bind, label: lab });
  }
  const rOut = rc + d / 2 + 16;   // seek ring OUTSIDE the button ring
  const side = 2 * (rOut + 12);
  add("seek", "slider-arc", cx - side / 2, cy - side / 2, side, side,
    { bind: "seek", label: "Seek", arc: { start: 60, end: 300 } });
  const px0 = cx + rOut + 26;     // chrome pill marquee sweeping right
  add("marquee", "display", px0, cy - 36, GEN_W * 0.95 - px0, 72,
    { content: "dynamic", layer: "screen", dynamicType: "marquee" });
  const kd = 76.0;
  add("knob0", "knob", px0 + 30, cy + 64, kd, kd, { bind: "volume", label: "VOL" });
  add("knob1", "knob", px0 + 30 + kd + 28, cy + 64, kd, kd, { bind: "balance", label: "BAL" });
  const ey = GEN_H * 0.475, eh = 124;
  const ex0 = GEN_W * 0.20, span = GEN_W * 0.60;
  const sw_ = span / 6;
  for (let i = 0; i < 6; i++) {
    add(`eq${i}`, "slider-v", ex0 + i * sw_ + sw_ * 0.30, ey, sw_ * 0.40, eh,
      { bind: "eqBand", group: "eq-bands", index: i, label: "" });
  }
  add("playlist", "display", GEN_W * 0.185, GEN_H * 0.575, GEN_W * 0.63, GEN_H * 0.355,
    { content: "dynamic", layer: "screen", dynamicType: "playlist" });
  return regs;
}

// ---- minimal: now-playing puck — dial, seek, big PLAY + prev/next, one knob
export function layoutMinimal(): Region[] {
  const regs: Region[] = [];
  const add = makeAdder(regs);
  const cx = GEN_W / 2, cy = GEN_H * 0.255, rg = GEN_W * 0.185;
  add("visualizer", "display", cx - rg, cy - rg, 2 * rg, 2 * rg,
    { content: "dynamic", layer: "screen", dynamicType: "visualizer", shape: "ellipse" });
  const sy = cy + rg + 30;        // horizontal seek under the dial
  add("seek", "slider-h", GEN_W * 0.23, sy, GEN_W * 0.54, 28, { bind: "seek", label: "Seek" });
  const by = sy + 96;             // transport row, PLAY dominant
  const playD = 132.0, smallD = 78.0, gap = 44.0;
  add("play", "button", cx - playD / 2, by - playD / 2, playD, playD, { bind: "play", label: "play", shape: "ellipse" });
  add("prev", "button", cx - playD / 2 - gap - smallD, by - smallD / 2, smallD, smallD, { bind: "prev", label: "prev", shape: "ellipse" });
  add("next", "button", cx + playD / 2 + gap, by - smallD / 2, smallD, smallD, { bind: "next", label: "next", shape: "ellipse" });
  const ky = by + playD / 2 + 40; // one volume knob
  const kd = 96.0;
  add("knob0", "knob", cx - kd / 2, ky, kd, kd, { bind: "volume", label: "VOL" });
  const my = ky + kd + 32;        // marquee at the foot
  add("marquee", "display", GEN_W * 0.19, my, GEN_W * 0.62, 50,
    { content: "dynamic", layer: "screen", dynamicType: "marquee" });
  return regs;
}

export function regionsForVariant(v: LayoutVariant): Region[] {
  return v === "simple" ? layoutSimple()
    : v === "radial" ? layoutRadial()
    : v === "capsule" ? layoutCapsule()
    : layoutMinimal();
}

export function templateForVariant(id: string, v: LayoutVariant): Template {
  return { id, name: "wild-sculpt", canvas: { w: GEN_W, h: GEN_H }, regions: regionsForVariant(v) };
}

// ---------------------------------------------------------------------------
// resolveOverlaps — GUARANTEE no two INTERACTABLE controls overlap (and no
// control overlaps a display). A template with overlapping interactables must
// NEVER reach the painter or the renderer. Displays are treated as fixed
// obstacles (they're layered content); controls repel off each other + off
// displays, then a final shrink pass removes any residual overlap so the
// guarantee is hard, not best-effort. All math in normalized 0..1 coords.
// ---------------------------------------------------------------------------
type Box = { x: number; y: number; w: number; h: number };
const ov = (a: Box, b: Box): { ox: number; oy: number } | null => {
  const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return ox > 0 && oy > 0 ? { ox, oy } : null;
};
const clampBox = (r: Box) => {
  r.w = Math.min(r.w, 0.94); r.h = Math.min(r.h, 0.94);
  r.x = Math.max(0.02, Math.min(r.x, 0.98 - r.w));
  r.y = Math.max(0.02, Math.min(r.y, 0.98 - r.h));
};

export function resolveOverlaps(regions: Region[]): Region[] {
  const items = regions.map((r) => ({ reg: r, rect: { ...r.rect }, fixed: r.kind === "display" }));
  // iterative separation: push overlapping pairs apart along the axis of LEAST overlap
  for (let iter = 0; iter < 60; iter++) {
    let any = false;
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const A = items[i], B = items[j];
        if (A.fixed && B.fixed) continue;          // two displays may layer
        const o = ov(A.rect, B.rect);
        if (!o) continue;
        any = true;
        const a = A.rect, b = B.rect;
        // weights: a fixed box doesn't move; the movable one takes the full push
        const wa = A.fixed ? 0 : (B.fixed ? 1 : 0.5);
        const wb = B.fixed ? 0 : (A.fixed ? 1 : 0.5);
        if (o.ox < o.oy) {
          const d = o.ox + 0.004; const ac = a.x + a.w / 2, bc = b.x + b.w / 2;
          if (ac <= bc) { a.x -= d * wa; b.x += d * wb; } else { a.x += d * wa; b.x -= d * wb; }
        } else {
          const d = o.oy + 0.004; const ac = a.y + a.h / 2, bc = b.y + b.h / 2;
          if (ac <= bc) { a.y -= d * wa; b.y += d * wb; } else { a.y += d * wa; b.y -= d * wb; }
        }
        if (!A.fixed) clampBox(a);
        if (!B.fixed) clampBox(b);
      }
    }
    if (!any) break;
  }
  // HARD guarantee: shrink any residual control-control overlap (smaller box yields)
  for (let pass = 0; pass < 8; pass++) {
    let any = false;
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const A = items[i], B = items[j];
        if (A.fixed && B.fixed) continue;
        const o = ov(A.rect, B.rect);
        if (!o) continue;
        any = true;
        // shrink the movable (or smaller) box on the least-overlap axis
        const target = A.fixed ? B : B.fixed ? A : (A.rect.w * A.rect.h <= B.rect.w * B.rect.h ? A : B);
        const r = target.rect;
        if (o.ox < o.oy) { r.x += o.ox / 2 + 0.004 * (r.x < (A === target ? B : A).rect.x ? -1 : 1); r.w = Math.max(0.03, r.w - o.ox - 0.008); }
        else { r.h = Math.max(0.03, r.h - o.oy - 0.008); }
        clampBox(r);
      }
    }
    if (!any) break;
  }
  return items.map((it) => ({ ...it.reg, rect: it.rect }));
}
