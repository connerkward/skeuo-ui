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

export type LayoutVariant = "radial" | "capsule" | "minimal";
export const LAYOUT_VARIANTS: LayoutVariant[] = ["radial", "capsule", "minimal"];

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
  return v === "radial" ? layoutRadial() : v === "capsule" ? layoutCapsule() : layoutMinimal();
}

export function templateForVariant(id: string, v: LayoutVariant): Template {
  return { id, name: "wild-sculpt", canvas: { w: GEN_W, h: GEN_H }, regions: regionsForVariant(v) };
}
