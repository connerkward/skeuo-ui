import type { StylePack, ComponentSpec, PanelId } from "../types";

export const packs: StylePack[] = [
  { id: "pipboy",    name: "Pip-Boy 3000",      blurb: "Vault-tec rugged steel" },
  { id: "winamp",    name: "Winamp Organic 9x", blurb: "Chromatic plasma blob" },
  { id: "ipod",      name: "Chrome iPod",       blurb: "Polished white plastic" },
  { id: "nautical",  name: "Nautical Brass",    blurb: "Walnut + brass ship's bridge" },
  { id: "cyberpunk", name: "Cyberpunk Holo",    blurb: "Neon glass HUD" },
];

// Panel y-ranges (image-relative). Used to convert image-relative hotspot coords to panel-relative.
export const PANEL_RANGES: Record<PanelId, [number, number]> = {
  main:     [0.000, 0.380],
  eq:       [0.385, 0.665],
  playlist: [0.670, 1.000],
};

// All hotspots in IMAGE-RELATIVE normalized coordinates.
// Conversion to panel-relative happens at render time.
export const components: ComponentSpec[] = [
  // MAIN panel
  { id: "seek",    panel: "main", kind: "slider-h", x: 0.370, y: 0.220, w: 0.435, h: 0.045, label: "Seek" },
  { id: "prev",    panel: "main", kind: "button",   x: 0.073, y: 0.290, w: 0.075, h: 0.075, label: "Prev" },
  { id: "play",    panel: "main", kind: "button",   x: 0.155, y: 0.286, w: 0.080, h: 0.082, label: "Play" },
  { id: "pause",   panel: "main", kind: "button",   x: 0.245, y: 0.290, w: 0.065, h: 0.075, label: "Pause" },
  { id: "stop",    panel: "main", kind: "button",   x: 0.318, y: 0.290, w: 0.065, h: 0.075, label: "Stop" },
  { id: "next",    panel: "main", kind: "button",   x: 0.389, y: 0.290, w: 0.075, h: 0.075, label: "Next" },
  { id: "eject",   panel: "main", kind: "button",   x: 0.476, y: 0.290, w: 0.050, h: 0.070, label: "Eject" },
  { id: "shuffle", panel: "main", kind: "switch",   x: 0.555, y: 0.290, w: 0.140, h: 0.072, label: "Shuffle" },
  { id: "repeat",  panel: "main", kind: "switch",   x: 0.705, y: 0.290, w: 0.060, h: 0.072, label: "Repeat" },
  { id: "eq",      panel: "main", kind: "switch",   x: 0.770, y: 0.225, w: 0.060, h: 0.045, label: "EQ" },
  { id: "pl",      panel: "main", kind: "switch",   x: 0.840, y: 0.225, w: 0.060, h: 0.045, label: "PL" },

  // EQ panel
  { id: "eq-on",   panel: "eq", kind: "switch", x: 0.087, y: 0.432, w: 0.045, h: 0.045, label: "On" },
  { id: "eq-auto", panel: "eq", kind: "switch", x: 0.137, y: 0.432, w: 0.060, h: 0.045, label: "Auto" },
  { id: "presets", panel: "eq", kind: "button", x: 0.857, y: 0.432, w: 0.070, h: 0.045, label: "Presets" },

  // EQ sliders
  { id: "preamp", panel: "eq", kind: "slider-v", x: 0.095, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-60",  panel: "eq", kind: "slider-v", x: 0.215, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-170", panel: "eq", kind: "slider-v", x: 0.280, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-310", panel: "eq", kind: "slider-v", x: 0.343, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-600", panel: "eq", kind: "slider-v", x: 0.406, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-1k",  panel: "eq", kind: "slider-v", x: 0.468, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-3k",  panel: "eq", kind: "slider-v", x: 0.531, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-6k",  panel: "eq", kind: "slider-v", x: 0.594, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-12k", panel: "eq", kind: "slider-v", x: 0.657, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-14k", panel: "eq", kind: "slider-v", x: 0.720, y: 0.483, w: 0.045, h: 0.158 },
  { id: "eq-16k", panel: "eq", kind: "slider-v", x: 0.783, y: 0.483, w: 0.045, h: 0.158 },
  { id: "gain",   panel: "eq", kind: "slider-v", x: 0.905, y: 0.483, w: 0.045, h: 0.158 },

  // PLAYLIST panel
  { id: "pl-add",   panel: "playlist", kind: "button", x: 0.083, y: 0.913, w: 0.045, h: 0.050, label: "Add" },
  { id: "pl-rem",   panel: "playlist", kind: "button", x: 0.135, y: 0.913, w: 0.045, h: 0.050, label: "Rem" },
  { id: "pl-sel",   panel: "playlist", kind: "button", x: 0.188, y: 0.913, w: 0.045, h: 0.050, label: "Sel" },
  { id: "pl-misc",  panel: "playlist", kind: "button", x: 0.240, y: 0.913, w: 0.055, h: 0.050, label: "Misc" },
  { id: "pl-play",  panel: "playlist", kind: "button", x: 0.555, y: 0.913, w: 0.050, h: 0.052, label: "Play" },
  { id: "pl-pause", panel: "playlist", kind: "button", x: 0.610, y: 0.913, w: 0.045, h: 0.052, label: "Pause" },
  { id: "pl-stop",  panel: "playlist", kind: "button", x: 0.660, y: 0.913, w: 0.045, h: 0.052, label: "Stop" },
  { id: "pl-next",  panel: "playlist", kind: "button", x: 0.710, y: 0.913, w: 0.050, h: 0.052, label: "Next" },
  { id: "pl-list",  panel: "playlist", kind: "button", x: 0.905, y: 0.910, w: 0.070, h: 0.060, label: "Opts" },
];

// Convert image-relative coords to panel-relative.
export function toPanelCoords(c: ComponentSpec): { x: number; y: number; w: number; h: number } {
  const [y0, y1] = PANEL_RANGES[c.panel];
  const ph = y1 - y0;
  return {
    x: c.x,
    y: (c.y - y0) / ph,
    w: c.w,
    h: c.h / ph,
  };
}
