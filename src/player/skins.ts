import type { Layer } from "../template/schema";

// Per-skin asset registry. Layered architecture:
//   frame              = AI faceplate (bezel + blank panel, no controls/screens)
//   sprites/           = AI control sprites WITH STATES (switch-off/on, knob,
//                        button, thumb) — composited live by React
//   screens + content  = CSS recessed screens with live React content
// CSS approximations are the fallback when a layer is missing.
export interface SkinAssets {
  id: string;
  name: string;
  blurb: string;
  has: Layer[];
  // the generated frame image bakes in the controls + screens, so React
  // renders only transparent interactive overlays + live screen content
  baked?: boolean;
  // skins whose layout was EXTRACTED from a freeform design carry their own
  // template (fetched at runtime) instead of the canonical one
  templateUrl?: string;
  // CSS palette to use (the [data-skin] value); defaults to id.
  style?: string;
  // wild-shaped skins with CV-detected screen regions
  live?: boolean;
  // AI control sprites with states exist under /skins/<id>/sprites/
  sprites?: boolean;
}

export function skinLive(id: string): boolean {
  return !!skinList.find((x) => x.id === id)?.live;
}

export function skinStyle(id: string): string {
  const s = skinList.find((x) => x.id === id);
  return s?.style ?? id;
}

// sprites resolve through `style`, so a wild body (own frame/template) mounts
// its base style's control sprites
export function skinSprites(id: string): boolean {
  const sid = skinStyle(id);
  return !!skinList.find((x) => x.id === sid)?.sprites;
}

export const skinList: SkinAssets[] = [
  { id: "winamp",   name: "Winamp Classic",  blurb: "Brushed gunmetal, chrome screws, green LCD", has: ["frame"], baked: false, sprites: true },
  { id: "fallout",  name: "Fallout Pip-Boy", blurb: "Riveted RobCo handheld, green-phosphor CRT", has: ["frame"], baked: false, sprites: true },
  { id: "fantasy",  name: "Baldur's Gate",   blurb: "Carved stone, gold filigree, gem runes", has: ["frame"], baked: false, sprites: true },
  { id: "aqua",     name: "Mac OS X Aqua",   blurb: "Glossy white glass, pinstripes, candy lozenges", has: ["frame"], baked: false, sprites: true },
  { id: "hifi",     name: "70s Hi-Fi",       blurb: "Walnut & brushed aluminium, VU meters, knobs", has: ["frame"], baked: false, sprites: true },
  { id: "papercraft", name: "Papercraft",    blurb: "Folded cardboard & cut-paper, hand-made", has: ["frame"], baked: false, sprites: true },

  // wild ✦ — gpt-image-2 Y2K bodies (cut-out silhouettes, empty wells) with the
  // base style's sprite controls mounted into the wells + live screens
  { id: "y2k-pod",    name: "Y2K Pod ✦",     blurb: "Chrome pod body, sprite controls mounted", has: ["frame"], live: true, style: "winamp",  templateUrl: "/skins/y2k-pod/template.json" },
  { id: "y2k-wasp",   name: "Rust Wasp ✦",   blurb: "RobCo insectoid body, sprite controls mounted", has: ["frame"], live: true, style: "fallout", templateUrl: "/skins/y2k-wasp/template.json" },

  // absurd ✦ — memetic styles with their own sprites + palettes
  { id: "frog",    name: "Froggo ✦",        blurb: "Glossy rubber meme-frog, orange-dot hardware", has: ["frame"], live: true, sprites: true, templateUrl: "/skins/frog/template.json" },
  { id: "burger",  name: "Burger Deluxe ✦", blurb: "Sesame bun body, fry-switch, ketchup pointer", has: ["frame"], live: true, sprites: true, templateUrl: "/skins/burger/template.json" },
  { id: "bondi",   name: "Bondi G3 ✦",      blurb: "Translucent Y2K plastic, circuit shadows", has: ["frame"], live: true, sprites: true, templateUrl: "/skins/bondi/template.json" },
  { id: "toilet",  name: "Porcelain ✦",     blurb: "Gleaming ceramic, chrome flush lever", has: ["frame"], live: true, sprites: true, templateUrl: "/skins/toilet/template.json" },
  { id: "biomech", name: "Hive Mind ✦",     blurb: "Giger bone & sinew, bioluminescent veins", has: ["frame"], live: true, sprites: true, templateUrl: "/skins/biomech/template.json" },
  { id: "fiend",   name: "Chrome Fiend ✦",  blurb: "Free-designed chrome predator, blade fins", has: ["frame"], live: true, style: "winamp", templateUrl: "/skins/fiend/template.json" },
];

export function skinTemplateUrl(id: string): string | undefined {
  return skinList.find((x) => x.id === id)?.templateUrl;
}

export function skinBaked(id: string): boolean {
  return !!skinList.find((x) => x.id === id)?.baked;
}

// bump when frames/sprites are regenerated so browsers re-fetch
const ASSET_VERSION = "nb13";
const base = (id: string) => `/skins/${id}`;
export const layerUrl = (id: string, layer: Layer) => `${base(id)}/${layer}.png?v=${ASSET_VERSION}`;
export const spriteUrl = (id: string, name: string) => `${base(skinStyle(id))}/sprites/${name}.png?v=${ASSET_VERSION}`;

export function skinHas(id: string, layer: Layer): boolean {
  const s = skinList.find((x) => x.id === id);
  return !!s?.has.includes(layer);
}
