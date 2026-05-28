export type PanelId = "main" | "eq" | "playlist";

export interface ComponentSpec {
  id: string;
  panel: PanelId;
  kind: "button" | "switch" | "slider-h" | "slider-v";
  // Normalized coords within the panel (0..1)
  x: number; y: number; w: number; h: number;
  label?: string;
}

export interface StylePack {
  id: string;
  name: string;
  blurb: string;
}
