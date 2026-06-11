import type { Template, Region, Kind, Content, Layer, DynamicType } from "./schema";
import { EQ_BANDS } from "../player/data";

/* ============================================================
   The canonical "media player" layout, authored ONCE in pixel
   space on a 480×700 canvas, then normalized. Every skin reuses
   this exact geometry; only the styling (the generated layers)
   changes. This is what makes alignment consistent across skins.

   Layers, back to front:
     frame      — bezel/chrome background
     screen     — recessed dark screens (backdrops for dynamic text)
     components — button / slider / toggle faces
   ============================================================ */

const W = 480;
const H = 700;

const R: Region[] = [];
function add(
  kind: Kind, content: Content, layer: Layer,
  x: number, y: number, w: number, h: number,
  extra: Partial<Region> & { id: string }
) {
  R.push({ kind, content, layer, rect: { x: x / W, y: y / H, w: w / W, h: h / H }, ...extra });
}
function dyn(t: DynamicType, x: number, y: number, w: number, h: number, extra: Partial<Region> & { id: string }) {
  add("display", "dynamic", "screen", x, y, w, h, { dynamicType: t, ...extra });
}
// purely visual recessed screen (no live content of its own)
function screen(x: number, y: number, w: number, h: number, id: string) {
  add("display", "sprite", "screen", x, y, w, h, { id });
}

/* ---------- TITLE BAR ---------- */
dyn("title", 10, 7, 360, 13, { id: "titlebar", label: "station" });

/* ---------- MAIN display screens ---------- */
screen(12, 36, 120, 92, "lcd-left");
screen(140, 36, 328, 46, "lcd-right");

dyn("time",       20, 44, 104, 30, { id: "time", label: "0:00" });
dyn("visualizer", 20, 80, 104, 42, { id: "visualizer" });
dyn("marquee",   148, 42, 312, 16, { id: "marquee", label: "track title" });
dyn("meta",      148, 64, 312, 14, { id: "meta", label: "192kbps 44kHz stereo" });

/* vol / bal sit on the panel surface (not in a screen) */
add("slider-h", "sprite", "components", 148, 96, 150, 14, { id: "vol", bind: "volume", label: "VOL" });
add("slider-h", "sprite", "components", 312, 96, 150, 14, { id: "bal", bind: "balance", label: "BAL" });

/* ---------- MAIN: seek ---------- */
add("slider-h", "sprite", "components", 12, 150, 456, 16, { id: "seek", bind: "seek", label: "Seek" });

/* ---------- MAIN: transport ---------- */
const ty = 184, th = 30;
add("button", "sprite", "components",  12, ty, 36, th, { id: "prev",  bind: "prev",  label: "Prev" });
add("button", "sprite", "components",  52, ty, 36, th, { id: "play",  bind: "play",  label: "Play" });
add("button", "sprite", "components",  92, ty, 36, th, { id: "pause", bind: "pause", label: "Pause" });
add("button", "sprite", "components", 132, ty, 32, th, { id: "stop",  bind: "stop",  label: "Stop" });
add("button", "sprite", "components", 168, ty, 36, th, { id: "next",  bind: "next",  label: "Next" });
add("button", "sprite", "components", 208, ty, 30, th, { id: "eject", bind: "eject", label: "Eject" });
add("toggle", "sprite", "components", 300, ty, 80, th, { id: "shuffle", bind: "shuffle", label: "SHUFFLE" });
add("toggle", "sprite", "components", 384, ty, 84, th, { id: "repeat",  bind: "repeat",  label: "REPEAT" });

/* ---------- EQ: head ---------- */
add("toggle", "sprite", "components",  12, 244, 36, 24, { id: "eq-on",   bind: "eqOn",   label: "ON" });
add("toggle", "sprite", "components",  52, 244, 46, 24, { id: "eq-auto", bind: "eqAuto", label: "AUTO" });
screen(106, 242, 290, 30, "eq-screen");
dyn("eq-curve", 108, 244, 286, 26, { id: "eq-curve" });
add("button", "sprite", "components", 402, 244, 66, 24, { id: "presets", bind: "presets", label: "PRESETS" });

/* ---------- EQ: sliders (preamp + 10 bands) ---------- */
const bandY = 284, bandH = 120;
const bands = ["PRE", ...EQ_BANDS];
const slotW = 456 / bands.length;
const sW = 22;
bands.forEach((name, i) => {
  const cx = 12 + slotW * (i + 0.5);
  add("slider-v", "sprite", "components", cx - sW / 2, bandY, sW, bandH, {
    id: i === 0 ? "preamp" : `eq-${name}`,
    bind: "eqBand", group: "eq-bands", index: i, label: name,
  });
});

/* ---------- PLAYLIST ---------- */
dyn("title",    12, 432, 456, 14, { id: "pl-title", label: "PLAYLIST EDITOR" });
screen(12, 452, 456, 188, "pl-screen");
dyn("playlist", 18, 458, 444, 176, { id: "playlist" });

const fy = 656, fh = 30;
add("button", "sprite", "components",  12, fy, 36, fh, { id: "pl-add",  label: "ADD" });
add("button", "sprite", "components",  52, fy, 36, fh, { id: "pl-rem",  label: "REM" });
add("button", "sprite", "components",  92, fy, 36, fh, { id: "pl-sel",  label: "SEL" });
add("button", "sprite", "components", 132, fy, 44, fh, { id: "pl-misc", label: "MISC" });
dyn("meta", 184, fy, 132, fh, { id: "pl-summary", label: "8 tracks" });
add("button", "sprite", "components", 320, fy, 36, fh, { id: "pl-prev",  bind: "prev",  label: "Prev" });
add("button", "sprite", "components", 360, fy, 36, fh, { id: "pl-play",  bind: "play",  label: "Play" });
add("button", "sprite", "components", 400, fy, 36, fh, { id: "pl-pause", bind: "pause", label: "Pause" });
add("button", "sprite", "components", 440, fy, 36, fh, { id: "pl-next",  bind: "next",  label: "Next" });

export const playerTemplate: Template = {
  id: "player-3panel",
  name: "Media Player — 3 panel",
  canvas: { w: W, h: H },
  regions: R,
};
