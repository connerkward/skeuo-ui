import type { Layer } from "../template/schema";

// Per-skin asset registry. When a layer image exists (generated art under
// /skins/<id>/), the compositor draws it; otherwise it falls back to the
// CSS-skeuomorphic baseline so the UI is always aligned and presentable.
//
//   frame      = the chrome/bezel background (the "frame" layer)
//   components = baked button/slider faces, transparent elsewhere
//   screen     = styled-but-empty recessed screens (live content renders over)
//
// `has` lists which generated layers are present for the skin.
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
  // CSS palette to use (the [data-skin] value); defaults to id. Lets a
  // freeform skin (own assets) reuse an existing style's look.
  style?: string;
}

export function skinStyle(id: string): string {
  const s = skinList.find((x) => x.id === id);
  return s?.style ?? id;
}

export const skinList: SkinAssets[] = [
  { id: "winamp",   name: "Winamp Classic",  blurb: "Brushed gunmetal, chrome screws, green LCD", has: ["frame"], baked: true },
  { id: "fallout",  name: "Fallout Pip-Boy", blurb: "Riveted RobCo handheld, green-phosphor CRT", has: ["frame"], baked: true },
  { id: "fantasy",  name: "Baldur's Gate",   blurb: "Carved stone, gold filigree, gem runes", has: ["frame"], baked: true },
  { id: "aqua",     name: "Mac OS X Aqua",   blurb: "Glossy white glass, pinstripes, candy lozenges", has: ["frame"], baked: true },
  { id: "hifi",     name: "70s Hi-Fi",       blurb: "Walnut & brushed aluminium, VU meters, knobs", has: ["frame"], baked: true },
  { id: "papercraft", name: "Papercraft",    blurb: "Folded cardboard & cut-paper, hand-made", has: ["frame"], baked: true },

  // freeform ✦ — each layout reverse-engineered from its OWN gpt-image-2 design
  { id: "ff-winamp",     name: "Winamp ✦ freeform",     blurb: "Unique layout from a gpt-image-2 design", has: ["frame"], baked: true, style: "winamp",     templateUrl: "/skins/ff-winamp/template.json" },
  { id: "ff-fallout",    name: "Fallout ✦ freeform",    blurb: "Unique layout from a gpt-image-2 design", has: ["frame"], baked: true, style: "fallout",    templateUrl: "/skins/ff-fallout/template.json" },
  { id: "ff-fantasy",    name: "Baldur's Gate ✦ freeform", blurb: "Unique layout from a gpt-image-2 design", has: ["frame"], baked: true, style: "fantasy",    templateUrl: "/skins/ff-fantasy/template.json" },
  { id: "ff-aqua",       name: "Aqua ✦ freeform",       blurb: "Unique layout from a gpt-image-2 design", has: ["frame"], baked: true, style: "aqua",       templateUrl: "/skins/ff-aqua/template.json" },
  { id: "ff-hifi",       name: "70s Hi-Fi ✦ freeform",  blurb: "Unique layout from a gpt-image-2 design", has: ["frame"], baked: true, style: "hifi",       templateUrl: "/skins/ff-hifi/template.json" },
  { id: "ff-papercraft", name: "Papercraft ✦ freeform", blurb: "Unique layout from a gpt-image-2 design", has: ["frame"], baked: true, style: "papercraft", templateUrl: "/skins/ff-papercraft/template.json" },

  // shaped ✦ — irregular non-rectangular silhouettes (background cut out)
  { id: "winamp-shaped",  name: "Winamp ✦ shaped",      blurb: "Irregular cut-out silhouette, not a rectangle", has: ["frame"], baked: true, style: "winamp",  templateUrl: "/skins/winamp-shaped/template.json" },
  { id: "fantasy-shaped", name: "Baldur's Gate ✦ shaped", blurb: "Irregular cut-out silhouette, not a rectangle", has: ["frame"], baked: true, style: "fantasy", templateUrl: "/skins/fantasy-shaped/template.json" },
];

export function skinTemplateUrl(id: string): string | undefined {
  return skinList.find((x) => x.id === id)?.templateUrl;
}

export function skinBaked(id: string): boolean {
  return !!skinList.find((x) => x.id === id)?.baked;
}

// bump when frames are regenerated so browsers re-fetch (frame.png URLs are
// otherwise stable and get served from disk cache)
const ASSET_VERSION = "nb2k";
const base = (id: string) => `/skins/${id}`;
export const layerUrl = (id: string, layer: Layer) => `${base(id)}/${layer}.png?v=${ASSET_VERSION}`;

export function skinHas(id: string, layer: Layer): boolean {
  const s = skinList.find((x) => x.id === id);
  return !!s?.has.includes(layer);
}
