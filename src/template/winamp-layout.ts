import type { Template, Region, Kind, Content, Layer, DynamicType } from "./schema";
import { EQ_BANDS } from "../player/data";
import { PRESET_NAMES } from "../player/usePlayer";

/* ============================================================
   The canonical media-player layout, authored ONCE in pixel space
   on a 480×700 canvas, then normalized. Content is inset from the
   edges to leave gutters for ornamental "flourish" regions (corners,
   side rails, header crest, nameplate) that the image model fills
   with skin-specific detail. Every skin reuses this exact geometry;
   only the styling (the generated layers) changes.

   Layers, back to front:  frame · screen · components
   ============================================================ */

const W = 480;
const H = 700;
const L = 30, Rg = 450;            // content gutters (left / right edge)

const R: Region[] = [];
function add(
  kind: Kind, content: Content, layer: Layer,
  x: number, y: number, w: number, h: number,
  extra: Partial<Region> & { id: string }
) {
  R.push({ kind, content, layer, rect: { x: x / W, y: y / H, w: w / W, h: h / H }, ...extra });
}
const dyn = (t: DynamicType, x: number, y: number, w: number, h: number, e: Partial<Region> & { id: string }) =>
  add("display", "dynamic", "screen", x, y, w, h, { dynamicType: t, ...e });
const screen = (x: number, y: number, w: number, h: number, id: string) =>
  add("display", "sprite", "screen", x, y, w, h, { id });
const flourish = (x: number, y: number, w: number, h: number, id: string, hint: string) =>
  add("flourish", "decoration", "frame", x, y, w, h, { id, flourish: hint, label: hint });

/* ---------- FLOURISHES (non-interactive ornament) ---------- */
flourish(6, 6, 36, 36, "corner-tl", "CORNER");
flourish(438, 6, 36, 36, "corner-tr", "CORNER");
flourish(6, 658, 36, 36, "corner-bl", "CORNER");
flourish(438, 658, 36, 36, "corner-br", "CORNER");
flourish(6, 210, 18, 440, "rail-left", "RAIL");
flourish(456, 210, 18, 440, "rail-right", "RAIL");
flourish(150, 2, 180, 30, "header-crest", "CREST");
flourish(180, 672, 120, 22, "maker-plate", "NAMEPLATE");

/* ---------- TITLE BAR ---------- */
dyn("title", 48, 9, 384, 14, { id: "titlebar", label: "station" });

/* ---------- MAIN: display ---------- */
screen(34, 40, 116, 92, "lcd-left");
screen(158, 40, 180, 64, "lcd-right");
dyn("time",       40, 48, 104, 30, { id: "time", label: "0:00" });
dyn("visualizer", 40, 84, 104, 42, { id: "visualizer" });
dyn("marquee",   164, 46, 168, 16, { id: "marquee", label: "track title" });
dyn("meta",      164, 68, 168, 14, { id: "meta", label: "192kbps" });

/* knobs + xy pad */
add("knob", "sprite", "components", 348, 40, 48, 48, { id: "vol", bind: "volume", label: "VOL" });
add("knob", "sprite", "components", 400, 40, 48, 48, { id: "bal", bind: "balance", label: "BAL" });
add("xy",   "sprite", "components", 348, 94, 100, 38, { id: "field", label: "FIELD" });

/* seek */
add("slider-h", "sprite", "components", 34, 150, 416, 16, { id: "seek", bind: "seek", label: "Seek" });

/* transport */
const ty = 184, th = 30;
add("button", "sprite", "components",  34, ty, 36, th, { id: "prev",  bind: "prev",  label: "Prev" });
add("button", "sprite", "components",  74, ty, 36, th, { id: "play",  bind: "play",  label: "Play" });
add("button", "sprite", "components", 114, ty, 36, th, { id: "pause", bind: "pause", label: "Pause" });
add("button", "sprite", "components", 154, ty, 32, th, { id: "stop",  bind: "stop",  label: "Stop" });
add("button", "sprite", "components", 190, ty, 36, th, { id: "next",  bind: "next",  label: "Next" });
add("button", "sprite", "components", 230, ty, 30, th, { id: "eject", bind: "eject", label: "Eject" });
add("toggle", "sprite", "components", 300, ty, 64, th, { id: "shuffle", bind: "shuffle", label: "SHUFFLE" });
add("segmented", "sprite", "components", 372, ty, 78, th, {
  id: "repeat", bind: "repeatMode", options: ["OFF", "1", "ALL"], label: "Repeat",
});

/* ---------- EQ: head ---------- */
add("toggle", "sprite", "components", 34, 244, 34, 24, { id: "eq-on",   bind: "eqOn",   label: "ON" });
add("toggle", "sprite", "components", 72, 244, 44, 24, { id: "eq-auto", bind: "eqAuto", label: "AUTO" });
screen(120, 242, 178, 30, "eq-screen");
dyn("eq-curve", 122, 244, 174, 26, { id: "eq-curve" });
add("segmented", "sprite", "components", 304, 244, 146, 26, {
  id: "eq-preset", bind: "eqPreset", options: PRESET_NAMES, label: "Preset",
});

/* ---------- EQ: sliders (preamp + 10 bands) ---------- */
const bandY = 286, bandH = 118;
const bands = ["PRE", ...EQ_BANDS];
const slotW = (Rg - L) / bands.length;
const sW = 22;
bands.forEach((name, i) => {
  const cx = L + slotW * (i + 0.5);
  add("slider-v", "sprite", "components", cx - sW / 2, bandY, sW, bandH, {
    id: i === 0 ? "preamp" : `eq-${name}`,
    bind: "eqBand", group: "eq-bands", index: i, label: name,
  });
});

/* ---------- PLAYLIST ---------- */
dyn("title",    34, 432, 416, 14, { id: "pl-title", label: "PLAYLIST EDITOR" });
screen(34, 452, 416, 184, "pl-screen");
dyn("playlist", 40, 458, 404, 172, { id: "playlist" });

const fy = 652, fh = 30;
add("button", "sprite", "components",  34, fy, 34, fh, { id: "pl-add",  label: "ADD" });
add("button", "sprite", "components",  70, fy, 34, fh, { id: "pl-rem",  label: "REM" });
add("button", "sprite", "components", 106, fy, 34, fh, { id: "pl-sel",  label: "SEL" });
add("button", "sprite", "components", 142, fy, 44, fh, { id: "pl-misc", label: "MISC" });
dyn("meta", 196, fy, 116, fh, { id: "pl-summary", label: "8 tracks" });
add("button", "sprite", "components", 318, fy, 30, fh, { id: "pl-prev",  bind: "prev",  label: "Prev" });
add("button", "sprite", "components", 350, fy, 30, fh, { id: "pl-play",  bind: "play",  label: "Play" });
add("button", "sprite", "components", 382, fy, 30, fh, { id: "pl-pause", bind: "pause", label: "Pause" });
add("button", "sprite", "components", 414, fy, 30, fh, { id: "pl-next",  bind: "next",  label: "Next" });

export const playerTemplate: Template = {
  id: "player-3panel",
  name: "Media Player — 3 panel",
  canvas: { w: W, h: H },
  regions: R,
};
