// Per-skin display typeface — the "logomark" font for a skin's title, the way a
// film's title card sets the name in type that captures its character. Curated
// per visible skin (the families are pre-loaded via the Google Fonts <link> in
// index.html). Generated skins carry their own `font` (picked by the Director at
// gen time); anything unmapped falls back to Cinzel (cinematic default).

export interface SkinFont {
  family: string;
  weight: number;
  letterSpacing: string;
  textTransform: "none" | "uppercase";
}

export const DEFAULT_SKIN_FONT: SkinFont = {
  family: "Cinzel", weight: 700, letterSpacing: "0.04em", textTransform: "none",
};

// id → font. Keep families in sync with the index.html Google Fonts link.
const SKIN_FONTS: Record<string, SkinFont> = {
  manray:  { family: "Bungee",          weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" },
  frog:    { family: "Lobster",         weight: 400, letterSpacing: "0",      textTransform: "none" },
  burger:  { family: "Bigshot One",     weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" },
  bondi:   { family: "Orbitron",        weight: 800, letterSpacing: "0.06em", textTransform: "uppercase" },
  biomech: { family: "Metamorphous",    weight: 400, letterSpacing: "0.04em", textTransform: "uppercase" },
  frog2:   { family: "Fredoka",         weight: 600, letterSpacing: "0.02em", textTransform: "none" },
  bondi2:  { family: "Audiowide",       weight: 400, letterSpacing: "0.04em", textTransform: "uppercase" },
  wmp:     { family: "Audiowide",       weight: 400, letterSpacing: "0.02em", textTransform: "none" },
  halo:    { family: "Saira Condensed", weight: 700, letterSpacing: "0.06em", textTransform: "uppercase" },
  pebble:  { family: "Fredoka",         weight: 600, letterSpacing: "0.01em", textTransform: "none" },
};

// Resolve the font for the active skin. A generated skin's own `font` (a family
// name from the Director allow-list) wins; otherwise the curated map, else Cinzel.
export function skinFont(id: string, runtimeFont?: string): SkinFont {
  if (runtimeFont) return { family: runtimeFont, weight: 600, letterSpacing: "0.03em", textTransform: "none" };
  return SKIN_FONTS[id] ?? DEFAULT_SKIN_FONT;
}

// CSS props for a title set in a skin's logomark font.
export function skinFontStyle(f: SkinFont): React.CSSProperties {
  return {
    fontFamily: `'${f.family}', 'Cinzel', system-ui, sans-serif`,
    fontWeight: f.weight,
    letterSpacing: f.letterSpacing,
    textTransform: f.textTransform,
  };
}
