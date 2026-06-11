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
}

export const skinList: SkinAssets[] = [
  { id: "winamp",   name: "Winamp Classic",  blurb: "Gunmetal & green LCD — whips the llama's ass", has: ["frame"], baked: true },
  { id: "fallout",  name: "Fallout Pip-Boy", blurb: "RobCo green-phosphor CRT terminal", has: ["frame"], baked: true },
  { id: "warcraft", name: "Warcraft III",    blurb: "Carved stone, bronze & gold filigree", has: ["frame"], baked: true },
];

export function skinBaked(id: string): boolean {
  return !!skinList.find((x) => x.id === id)?.baked;
}

const base = (id: string) => `/skins/${id}`;
export const layerUrl = (id: string, layer: Layer) => `${base(id)}/${layer}.png`;

export function skinHas(id: string, layer: Layer): boolean {
  const s = skinList.find((x) => x.id === id);
  return !!s?.has.includes(layer);
}
