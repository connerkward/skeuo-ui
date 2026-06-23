// Per-skin display typeface — the "logomark" font for a skin's title, the way a
// film's title card sets the name in type that captures its character. Fonts are
// loaded DYNAMICALLY from Google Fonts on demand (ensureGoogleFont), so a skin —
// curated OR generated — can use ANY Google family, not a fixed allow-list.

export interface SkinFont {
  family: string;
  weight: number;
  letterSpacing: string;
  textTransform: "none" | "uppercase";
}

export const DEFAULT_SKIN_FONT: SkinFont = {
  family: "Anton", weight: 400, letterSpacing: "0.01em", textTransform: "uppercase",
};

// id → font. Punchy, cinematic display faces — picked to match each skin's vibe.
const SKIN_FONTS: Record<string, SkinFont> = {
  manray:  { family: "Bungee",        weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // chunky toy signage
  frog:    { family: "Luckiest Guy",  weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // fat glossy comic
  burger:  { family: "Titan One",     weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // super-fat fast-food
  bondi:   { family: "Orbitron",      weight: 800, letterSpacing: "0.05em", textTransform: "uppercase" }, // techy Y2K
  biomech: { family: "Nosifer",       weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // dripping horror (Giger)
  frog2:   { family: "Baloo 2",       weight: 800, letterSpacing: "0",      textTransform: "uppercase" }, // fat rounded
  bondi2:  { family: "Audiowide",     weight: 400, letterSpacing: "0.03em", textTransform: "uppercase" }, // retro-futuristic
  wmp:     { family: "Michroma",      weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" }, // Y2K geometric
  halo:    { family: "Black Ops One", weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" }, // military stencil
  pebble:  { family: "Fredoka",       weight: 600, letterSpacing: "0",      textTransform: "uppercase" }, // friendly rounded
};

// Resolve the font for the active skin. A generated skin's own `font` (a family
// name from the Director) wins; otherwise the curated map, else the default.
export function skinFont(id: string, runtimeFont?: string): SkinFont {
  if (runtimeFont) return { family: runtimeFont, weight: 700, letterSpacing: "0.01em", textTransform: "uppercase" };
  return SKIN_FONTS[id] ?? DEFAULT_SKIN_FONT;
}

// CSS props for a title set in a skin's logomark font.
export function skinFontStyle(f: SkinFont): React.CSSProperties {
  return {
    fontFamily: `'${f.family}', 'Anton', system-ui, sans-serif`,
    fontWeight: f.weight,
    letterSpacing: f.letterSpacing,
    textTransform: f.textTransform,
  };
}

// ── dynamic Google Fonts loader ──────────────────────────────────────────────
// Inject a <link> for a family on first use so ANY Google font is available with
// no static allow-list. De-duped; single-weight families are requested without a
// wght axis (Google 400s a wght query an unvariable font doesn't support).
const requested = new Set<string>();
export function ensureGoogleFont(f: SkinFont): void {
  if (typeof document === "undefined") return;
  const key = `${f.family}@${f.weight}`;
  if (requested.has(key)) return;
  requested.add(key);
  const fam = f.family.trim().replace(/\s+/g, "+");
  const axis = f.weight && f.weight !== 400 ? `:wght@${f.weight}` : "";
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `https://fonts.googleapis.com/css2?family=${fam}${axis}&display=swap`;
  document.head.appendChild(link);
}
