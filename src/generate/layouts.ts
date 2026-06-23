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
import type { Region, Template, Kind, DynamicType } from "../template/schema";

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

// ════════════════════════════════════════════════════════════════════════════
// random — the generative layout engine, baked from the layout-randomization
// lookdev. TEN graphic-design-informed archetypes (stack, dial, split,
// mini-widget, console, diagonal/Z, golden-section, Swiss grid, L-corner,
// arc/fan), each a complete working player. A repel + min-spacing pass
// (resolveOverlaps) guarantees no two controls overlap or sit too close; the
// dial glass + arc ring carry `nopush` so controls ride them intentionally.
// Feel matches the studio config dialed in by hand (mini + arc heavy, full
// symmetry, max play-dominance); density varies per roll for variety.
// All coords are normalized 0..1; AR keeps square controls square on the 2:3 canvas.
// ════════════════════════════════════════════════════════════════════════════
const AR = GEN_W / GEN_H;                 // 0.667 — a square control is h = w * AR
const clampN = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

interface Params {
  density: number; symmetry: number; bias: number; hierarchy: number;
  margin: number; gapScale: number; spacing: number;
  wStack: number; wDial: number; wSplit: number; wMini: number; wConsole: number;
  wDiagonal: number; wGolden: number; wGrid: number; wCorner: number; wArc: number;
}
type W = Region & { nopush?: boolean };   // working region (nopush stripped before return)
const sideOf = (P: Params) => (Math.random() < (P.bias + 1) / 2 ? -1 : 1); // -1 left, +1 right

interface RegOpts { bind?: string; dyn?: DynamicType; ell?: boolean; arc?: { start: number; end: number }; group?: string; index?: number; nopush?: boolean; }
function reg(id: string, kind: Kind, x: number, y: number, w: number, h: number, o: RegOpts = {}): W {
  const screen = kind === "display";
  const r: W = { id, kind, content: screen ? "dynamic" : "sprite", layer: screen ? "screen" : "components", rect: { x, y, w, h } };
  if (o.bind) r.bind = o.bind;
  if (o.dyn) r.dynamicType = o.dyn;
  if (o.ell) r.shape = "ellipse";
  if (o.arc) r.arc = o.arc;
  if (o.group) { r.group = o.group; r.index = o.index; }
  if (o.nopush) r.nopush = true;
  return r;
}
// push a square/round control of width d, centred at (cx,cy)
const ccN = (out: W[], id: string, kind: Kind, cx: number, cy: number, d: number, o: RegOpts = {}) =>
  out.push(reg(id, kind, cx - d / 2, cy - d * AR / 2, d, d * AR, o));

function addEqN(out: W[], x0: number, y: number, w: number) {
  const eh = 0.085, sw = 0.035;
  out.push(reg("shuffle", "toggle", x0, y, sw, eh, { bind: "shuffle" }));
  out.push(reg("eqOn", "toggle", x0 + w - sw, y, sw, eh, { bind: "eqOn" }));
  const sx = x0 + sw + w * 0.05, ex = x0 + w - sw - w * 0.05, step = (ex - sx) / 6;
  for (let i = 0; i < 6; i++) out.push(reg("eq" + i, "slider-v", sx + i * step + step * 0.28, y, step * 0.44, eh, { bind: "eqBand", group: "eq-bands", index: i }));
}

function genStack(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, w = 1 - 2 * m, cx = 0.5;
  let y = rnd(0.08, 0.12);
  if (chance(0.25)) { const d = Math.min(w, rnd(0.34, 0.46)); out.push(reg("visualizer", "display", cx - d / 2, y, d, d * AR, { dyn: "visualizer", ell: true })); y += d * AR; }
  else { const vh = rnd(0.15, 0.22); out.push(reg("visualizer", "display", x0, y, w, vh, { dyn: "visualizer" })); y += vh; }
  y += rnd(0.02, 0.04);
  const mh = rnd(0.035, 0.05);
  if (chance(0.5)) { const cw = w * 0.27; out.push(reg("marquee", "display", x0, y, w - cw - 0.02, mh, { dyn: "marquee" })); out.push(reg("time", "display", x0 + w - cw, y, cw, mh, { dyn: "time" })); }
  else out.push(reg("marquee", "display", x0, y, w, mh, { dyn: "marquee" }));
  y += mh + rnd(0.015, 0.03);
  out.push(reg("seek", "slider-h", x0, y, w, 0.022, { bind: "seek" })); y += rnd(0.05, 0.07);
  const set = ["play"]; if (chance(0.92)) { set.unshift("prev"); set.push("next"); } if (chance(0.3)) set.splice(1, 0, "pause"); if (chance(0.4)) set.push("stop");
  const base = 0.085 * (1 + P.hierarchy * 0.4), sizes = set.map((b) => base * (BSIZE[b] ?? 1)), gap = rnd(0.02, 0.035) * P.gapScale;
  const rowW = sizes.reduce((s, d) => s + d, 0) + gap * (set.length - 1), maxD = Math.max(...sizes); let tx = cx - rowW / 2; const cyR = y + maxD * AR / 2;
  set.forEach((b, i) => { ccN(out, b, "button", tx + sizes[i] / 2, cyR, sizes[i], { bind: b, ell: true }); tx += sizes[i] + gap; });
  y = cyR + maxD * AR / 2 + rnd(0.03, 0.05);
  if (chance(0.4 + P.density * 0.5)) { const two = chance(P.symmetry + 0.2), kd = rnd(0.11, 0.15), kyc = y + kd * AR / 2;
    if (two) { ccN(out, "volume", "knob", cx - kd / 2 - 0.03, kyc, kd, { bind: "volume" }); ccN(out, "balance", "knob", cx + kd / 2 + 0.03, kyc, kd, { bind: "balance" }); }
    else ccN(out, "volume", "knob", cx + sideOf(P) * (1 - P.symmetry) * 0.18, kyc, kd, { bind: "volume" }); y += kd * AR + 0.03; }
  if (chance(P.density * 0.7) && y < 0.62) { addEqN(out, x0, y, w); y += 0.1; }
  if (chance(P.density * 0.7) && y < 0.8) out.push(reg("playlist", "display", x0, y, w, 0.93 - y, { dyn: "playlist" }));
  return out;
}
function genDial(P: Params): W[] {
  const out: W[] = []; const cx = 0.5, cyD = rnd(0.22, 0.28), rg = rnd(0.17, 0.22);
  out.push(reg("visualizer", "display", cx - rg, cyD - rg * AR, 2 * rg, 2 * rg * AR, { dyn: "visualizer", ell: true, nopush: true }));
  const btns = chance(0.5) ? ["prev", "play", "pause", "next"] : ["prev", "play", "next"];
  const bdOf = (b: string) => 0.085 * (BSIZE[b] ?? 1) * (1 + P.hierarchy * 0.3), bdMax = Math.max(...btns.map(bdOf));
  const rc = rg + bdMax / 2 + rnd(0.03, 0.055);   // every orbiting button clears the glass
  const spread = rnd(64, 86), start = 90 - spread, stepA = (2 * spread) / (btns.length - 1);
  btns.forEach((b, i) => { const a = rad(start + i * stepA); ccN(out, b, "button", cx + rc * Math.cos(a), cyD + rc * AR * Math.sin(a), bdOf(b), { bind: b, ell: true }); });
  const sd2 = 2 * (rc + bdMax / 2 + 0.015);
  out.push(reg("seek", "slider-arc", cx - sd2 / 2, cyD - sd2 * AR / 2, sd2, sd2 * AR, { bind: "seek", ell: true, nopush: true, arc: { start: 200, end: 340 } }));
  if (chance(0.4 + P.density * 0.4)) { const kd = rnd(0.08, 0.11), ka = rad(rnd(248, 262)), ox = rc * Math.cos(ka), oy = rc * AR * Math.sin(ka);
    ccN(out, "volume", "knob", cx + ox, cyD + oy, kd, { bind: "volume" }); ccN(out, "balance", "knob", cx - ox, cyD + oy, kd, { bind: "balance" }); }
  let y = cyD + rc * AR + bdMax * AR / 2 + rnd(0.04, 0.07);
  out.push(reg("marquee", "display", P.margin, y, 1 - 2 * P.margin, rnd(0.035, 0.05), { dyn: "marquee" })); y += 0.08;
  if (chance(P.density * 0.7) && y < 0.6) { addEqN(out, P.margin, y, 1 - 2 * P.margin); y += 0.1; }
  if (chance(P.density * 0.6) && y < 0.82) out.push(reg("playlist", "display", P.margin, y, 1 - 2 * P.margin, 0.94 - y, { dyn: "playlist" }));
  return out;
}
function genSplit(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, sd = sideOf(P);
  const vw = rnd(0.42, 0.52), vx = sd < 0 ? m : 1 - m - vw;
  out.push(reg("visualizer", "display", vx, rnd(0.12, 0.18), vw, rnd(0.34, 0.46), { dyn: "visualizer" }));
  const cx0 = sd < 0 ? vx + vw + 0.03 : x0, cw = 1 - m - vw - 0.03 - m;
  let y = rnd(0.14, 0.18);
  out.push(reg("marquee", "display", cx0, y, cw, 0.05, { dyn: "marquee" })); y += 0.08;
  out.push(reg("seek", "slider-h", cx0, y, cw, 0.022, { bind: "seek" })); y += 0.06;
  const pd = Math.min(cw * 0.32, 0.16), sdd = cw * 0.20, g = cw * 0.07, rowW = sdd + g + pd + g + sdd; let bx = cx0 + (cw - rowW) / 2; const ty = y;
  ([["prev", sdd], ["play", pd], ["next", sdd]] as [string, number][]).forEach(([b, d]) => { ccN(out, b, "button", bx + d / 2, ty + pd * AR / 2, d, { bind: b, ell: true }); bx += d + g; });
  y += pd * AR + 0.05;
  ccN(out, "volume", "knob", cx0 + cw / 2, y + 0.04, Math.min(0.12, cw * 0.4), { bind: "volume" });
  return out;
}
function genMini(P: Params): W[] {
  const out: W[] = []; const m = P.margin, sd = sideOf(P);
  const sq = rnd(0.20, 0.26), top = rnd(0.10, 0.16), sx = sd < 0 ? m : 1 - m - sq;
  out.push(reg("visualizer", "display", sx, top, sq, sq * AR, { dyn: "visualizer", ell: chance(0.3) }));
  const tx0 = sd < 0 ? sx + sq + 0.03 : m, tw = 1 - m - sq - 0.03 - m;
  out.push(reg("marquee", "display", tx0, top, tw * 0.68, 0.05, { dyn: "marquee" }));
  out.push(reg("time", "display", tx0 + tw * 0.70, top, tw * 0.30, 0.05, { dyn: "time" }));
  out.push(reg("seek", "slider-h", tx0, top + 0.07, tw, 0.018, { bind: "seek" }));
  const base = 0.07 * (1 + P.hierarchy * 0.3), gap = 0.018 * P.gapScale, set = ["prev", "play", "next"];
  const sizes = set.map((b) => base * (BSIZE[b] ?? 1)), rowW = sizes.reduce((s, d) => s + d, 0) + gap * 2; let bx = tx0; const by = top + 0.115;
  set.forEach((b, i) => { ccN(out, b, "button", bx + sizes[i] / 2, by + sizes[i] * AR / 2, sizes[i], { bind: b, ell: true }); bx += sizes[i] + gap; });
  if (chance(P.density)) ccN(out, "volume", "knob", tx0 + rowW + 0.04 + base / 2, by + base * AR / 2, base, { bind: "volume" });
  return out;
}
function genConsole(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, w = 1 - 2 * m;
  out.push(reg("visualizer", "display", x0, rnd(0.08, 0.12), w, rnd(0.16, 0.22), { dyn: "visualizer" }));
  let y = rnd(0.34, 0.40);
  out.push(reg("marquee", "display", x0, y, w * 0.66, 0.045, { dyn: "marquee" })); out.push(reg("time", "display", x0 + w * 0.68, y, w * 0.32, 0.045, { dyn: "time" })); y += 0.06;
  out.push(reg("seek", "slider-h", x0, y, w, 0.02, { bind: "seek" })); y += 0.045;
  const base = 0.085 * (1 + P.hierarchy * 0.35); let bx = x0;
  ["prev", "play", "next", "stop"].forEach((b) => { const d = base * (BSIZE[b] ?? 1); ccN(out, b, "button", bx + d / 2, y + d * AR / 2, d, { bind: b, ell: true }); bx += d + 0.018 * P.gapScale; });
  ccN(out, "volume", "knob", x0 + w - 0.19, y + 0.045, 0.11, { bind: "volume" }); ccN(out, "balance", "knob", x0 + w - 0.06, y + 0.045, 0.11, { bind: "balance" }); y += base * AR + 0.04;
  if (chance(0.4 + P.density * 0.5) && y < 0.62) { addEqN(out, x0, y, w); y += 0.1; }
  if (chance(P.density * 0.6) && y < 0.8) out.push(reg("playlist", "display", x0, y, w, 0.93 - y, { dyn: "playlist" }));
  return out;
}
function genDiagonal(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, w = 1 - 2 * m;
  const vw = rnd(0.44, 0.55), vh = rnd(0.20, 0.28);
  out.push(reg("visualizer", "display", x0, rnd(0.08, 0.12), vw, vh, { dyn: "visualizer" }));
  out.push(reg("marquee", "display", x0 + vw + 0.03, rnd(0.10, 0.14), w - vw - 0.03, 0.05, { dyn: "marquee" }));
  out.push(reg("seek", "slider-h", x0 + vw + 0.03, rnd(0.20, 0.24), w - vw - 0.03, 0.022, { bind: "seek" }));
  const set = ["prev", "play", "next"], n = set.length, ax = rnd(0.20, 0.30), ay = rnd(0.46, 0.52), bx = rnd(0.70, 0.82), by = rnd(0.66, 0.74);
  set.forEach((b, i) => { const t = i / (n - 1), d = 0.085 * (BSIZE[b] ?? 1) * (1 + P.hierarchy * 0.3); ccN(out, b, "button", ax + (bx - ax) * t, ay + (by - ay) * t, d, { bind: b, ell: true }); });
  if (chance(0.7)) ccN(out, "volume", "knob", rnd(0.18, 0.26), rnd(0.74, 0.82), rnd(0.09, 0.12), { bind: "volume" });
  return out;
}
function genGolden(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, w = 1 - 2 * m, PHI = 0.618, sd = sideOf(P);
  const top = rnd(0.09, 0.13), bigW = w * PHI, bigH = rnd(0.40, 0.50), bigX = sd < 0 ? x0 : x0 + w - bigW;
  out.push(reg("visualizer", "display", bigX, top, bigW, bigH, { dyn: "visualizer" }));
  const colX = sd < 0 ? x0 + bigW + 0.03 : x0, colW = w - bigW - 0.03; let y = top;
  out.push(reg("marquee", "display", colX, y, colW, 0.05, { dyn: "marquee" })); y += 0.08;
  out.push(reg("seek", "slider-h", colX, y, colW, 0.022, { bind: "seek" })); y += 0.06;
  const bw = Math.min(colW * 0.5, 0.12);
  ["play", "prev", "next"].forEach((b, i) => { const d = bw * (b === "play" ? 1 : 0.8); ccN(out, b, "button", colX + colW / 2, y + i * (d * AR + 0.03) + d * AR / 2, d, { bind: b, ell: true }); });
  const by = top + bigH + 0.05;
  if (chance(0.75)) { ccN(out, "volume", "knob", bigX + bigW * 0.3, by, 0.11, { bind: "volume" }); ccN(out, "balance", "knob", bigX + bigW * 0.7, by, 0.11, { bind: "balance" }); }
  if (chance(P.density * 0.6) && by < 0.7) addEqN(out, x0, by + 0.12, w);
  return out;
}
function genGrid(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, w = 1 - 2 * m, top = rnd(0.08, 0.11), H = 0.93 - top;
  const cols = 4, rows = 6, cw = w / cols, ch = H / rows, g = 0.012;
  const cell = (cx: number, cy: number, cs: number, rs: number) => ({ x: x0 + cx * cw, y: top + cy * ch, w: cs * cw - g, h: rs * ch - g });
  const vSpan = chance(0.5) ? 4 : 3; let r = cell(chance(0.5) && vSpan === 3 ? 1 : 0, 0, vSpan, 2);
  out.push(reg("visualizer", "display", r.x, r.y, r.w, r.h, { dyn: "visualizer" }));
  r = cell(0, 2, 3, 1); out.push(reg("marquee", "display", r.x, r.y, r.w, r.h, { dyn: "marquee" }));
  r = cell(3, 2, 1, 1); out.push(reg("time", "display", r.x, r.y, r.w, r.h, { dyn: "time" }));
  r = cell(0, 3, 4, 1); out.push(reg("seek", "slider-h", r.x, r.y + ch * 0.3, r.w, 0.022, { bind: "seek" }));
  const d = Math.min(cw, ch) * 0.82;
  ["prev", "play", "next", "stop"].forEach((b, i) => { const c = cell(i, 4, 1, 1); ccN(out, b, "button", c.x + cw / 2 - g / 2, c.y + ch / 2 - g / 2, d * (b === "play" ? 1 : 0.85), { bind: b, ell: true }); });
  if (chance(0.75)) { const c1 = cell(0, 5, 1, 1), c2 = cell(1, 5, 1, 1); ccN(out, "volume", "knob", c1.x + cw / 2 - g / 2, c1.y + ch / 2 - g / 2, d * 0.9, { bind: "volume" }); ccN(out, "balance", "knob", c2.x + cw / 2 - g / 2, c2.y + ch / 2 - g / 2, d * 0.9, { bind: "balance" }); }
  if (chance(P.density * 0.6)) { const c = cell(2, 5, 2, 1); out.push(reg("playlist", "display", c.x, c.y, c.w, c.h, { dyn: "playlist" })); }
  return out;
}
function genCorner(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, w = 1 - 2 * m, sd = sideOf(P);
  const colW = rnd(0.17, 0.23), colX = sd < 0 ? x0 : x0 + w - colW, visX = sd < 0 ? x0 + colW + 0.03 : x0;
  out.push(reg("visualizer", "display", visX, rnd(0.08, 0.12), w - colW - 0.03, rnd(0.34, 0.44), { dyn: "visualizer" }));
  let cy = rnd(0.10, 0.14);
  out.push(reg("marquee", "display", colX, cy, colW, 0.06, { dyn: "marquee" })); cy += 0.11;
  if (chance(0.75)) { ccN(out, "volume", "knob", colX + colW / 2, cy, Math.min(colW, 0.12), { bind: "volume" }); cy += 0.15; }
  if (chance(0.6)) ccN(out, "balance", "knob", colX + colW / 2, cy, Math.min(colW, 0.12), { bind: "balance" });
  const by = rnd(0.72, 0.80);
  out.push(reg("seek", "slider-h", x0, by - 0.06, w, 0.022, { bind: "seek" }));
  const bw = 0.085 * (1 + P.hierarchy * 0.3); let bx = x0 + 0.02;
  ["prev", "play", "next", "stop"].forEach((b) => { const d = bw * (BSIZE[b] ?? 1); ccN(out, b, "button", bx + d / 2, by, d, { bind: b, ell: true }); bx += d + 0.03; });
  return out;
}
function genArc(P: Params): W[] {
  const out: W[] = []; const m = P.margin, x0 = m, w = 1 - 2 * m, cx = 0.5;
  out.push(reg("visualizer", "display", x0, rnd(0.08, 0.12), w, rnd(0.18, 0.24), { dyn: "visualizer" }));
  out.push(reg("marquee", "display", x0, rnd(0.36, 0.40), w, 0.05, { dyn: "marquee" }));
  const set = chance(0.5) ? ["prev", "play", "pause", "next"] : ["prev", "play", "next"], n = set.length;
  const cyA = rnd(0.56, 0.62), depth = rnd(0.05, 0.11), spanX = w * 0.82, ax = cx - spanX / 2, dir = chance(0.5) ? 1 : -1;
  set.forEach((b, i) => { const t = i / (n - 1), px = ax + spanX * t, py = cyA - depth * Math.sin(Math.PI * t) * dir, d = 0.085 * (BSIZE[b] ?? 1) * (1 + P.hierarchy * 0.3); ccN(out, b, "button", px, py, d, { bind: b, ell: true }); });
  out.push(reg("seek", "slider-h", x0, cyA + 0.14, w, 0.022, { bind: "seek" }));
  if (chance(0.7)) { ccN(out, "volume", "knob", cx - 0.08, cyA + 0.22, 0.11, { bind: "volume" }); ccN(out, "balance", "knob", cx + 0.08, cyA + 0.22, 0.11, { bind: "balance" }); }
  return out;
}

// repel + min-spacing: no two controls overlap or sit closer than P.spacing.
// `nopush` regions (dial glass + arc ring) are skipped — controls ride them.
function resolveOverlaps(all: W[], P: Params) {
  const sp = P.spacing, lo = P.margin * 0.5, hi = 1 - P.margin * 0.5;
  const S = all.filter((r) => !r.nopush), area = (r: W) => r.rect.w * r.rect.h;
  for (let it = 0; it < 160; it++) {
    let moved = false;
    for (let i = 0; i < S.length; i++) for (let j = i + 1; j < S.length; j++) {
      const a = S[i].rect, b = S[j].rect;
      const dx = (a.x + a.w / 2) - (b.x + b.w / 2), dy = (a.y + a.h / 2) - (b.y + b.h / 2);
      const px = (a.w + b.w) / 2 + sp - Math.abs(dx), py = (a.h + b.h) / 2 + sp - Math.abs(dy);
      if (px <= 0 || py <= 0) continue;
      moved = true;
      const wa = area(S[j]) / (area(S[i]) + area(S[j])) || 0.5, wb = 1 - wa;
      if (px < py) { const dir = dx < 0 ? -1 : 1; a.x += dir * px * wa; b.x -= dir * px * wb; }
      else { const dir = dy < 0 ? -1 : 1; a.y += dir * py * wa; b.y -= dir * py * wb; }
      a.x = clampN(a.x, lo, hi - a.w); a.y = clampN(a.y, lo, hi - a.h);
      b.x = clampN(b.x, lo, hi - b.w); b.y = clampN(b.y, lo, hi - b.h);
    }
    if (!moved) break;
  }
}

const ARCH_FNS: Record<string, (P: Params) => W[]> = {
  stack: genStack, dial: genDial, split: genSplit, mini: genMini, console: genConsole,
  diagonal: genDiagonal, golden: genGolden, grid: genGrid, corner: genCorner, arc: genArc,
};
function pickArch(P: Params): string {
  const all: [string, number][] = [
    ["stack", P.wStack], ["dial", P.wDial], ["split", P.wSplit], ["mini", P.wMini], ["console", P.wConsole],
    ["diagonal", P.wDiagonal], ["golden", P.wGolden], ["grid", P.wGrid], ["corner", P.wCorner], ["arc", P.wArc],
  ];
  const ws = all.filter((x) => x[1] > 0);
  const tot = ws.reduce((s, x) => s + x[1], 0) || 1; let r = Math.random() * tot;
  for (const [k, wt] of ws) { if ((r -= wt) <= 0) return k; }
  return ws.length ? ws[0][0] : "stack";
}

// ---- the 🎲: pick an archetype, generate, repel, strip the transient flag.
export function layoutRandom(): Region[] {
  const P: Params = {
    density: rnd(0, 0.6),            // varies per roll for variety (vs the studio's flat 0)
    symmetry: 1, bias: 1, hierarchy: 1, margin: 0.14, gapScale: 1.5, spacing: 0.02,
    wStack: 0.4, wDial: 0.5, wSplit: 0.5, wMini: 1, wConsole: 0.45,
    wDiagonal: 0.05, wGolden: 0.6, wGrid: 0.45, wCorner: 0.2, wArc: 1,
  };
  const raw = ARCH_FNS[pickArch(P)](P);
  resolveOverlaps(raw, P);
  return raw.map(({ nopush, ...r }) => r as Region);
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
