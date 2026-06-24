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

// id → font. Punchy, cinematic display faces — hand-picked to match each skin's
// vibe, one distinct face per skin (a logomark "title card" for the body). Covers
// the WHOLE catalog (incl. donor + currently-hidden themed bodies) so any skin —
// shown in the player, an export sheet, or once un-hidden — gets a fitting face
// instead of the generic default. All family names verified live on Google Fonts.
const SKIN_FONTS: Record<string, SkinFont> = {
  // donors / classics
  winamp:    { family: "Bebas Neue",        weight: 400, letterSpacing: "0.04em", textTransform: "uppercase" }, // tall condensed hi-fi
  toilet:    { family: "Cinzel",            weight: 600, letterSpacing: "0.04em", textTransform: "uppercase" }, // clean porcelain serif
  // visible roster (verified preloaded)
  manray:    { family: "Bungee",            weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // chunky toy signage
  frog:      { family: "Luckiest Guy",      weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // fat glossy comic
  burger:    { family: "Titan One",         weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // super-fat fast-food
  bondi:     { family: "Orbitron",          weight: 800, letterSpacing: "0.05em", textTransform: "uppercase" }, // techy Y2K
  biomech:   { family: "Nosifer",           weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // dripping horror (Giger)
  frog2:     { family: "Baloo 2",           weight: 800, letterSpacing: "0",      textTransform: "uppercase" }, // fat rounded
  bondi2:    { family: "Audiowide",         weight: 400, letterSpacing: "0.03em", textTransform: "uppercase" }, // retro-futuristic
  wmp:       { family: "Michroma",          weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" }, // Y2K geometric
  halo:      { family: "Black Ops One",     weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" }, // military stencil
  pebble:    { family: "Fredoka",           weight: 600, letterSpacing: "0",      textTransform: "uppercase" }, // friendly rounded
  // theme iterations
  burger2:   { family: "Bowlby One",        weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // beefy rounded slab
  toilet2:   { family: "Cinzel Decorative", weight: 700, letterSpacing: "0.02em", textTransform: "uppercase" }, // regal "throne" serif
  biomech2:  { family: "Metal Mania",       weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // gnarled brood metal
  fiend2:    { family: "Eater",             weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // melting chrome demon
  // body-horror / Giger family
  maw:       { family: "Creepster",         weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" }, // dripping fang horror
  flesh:     { family: "Butcherman",        weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // flayed wet sinew
  scarab:    { family: "Pirata One",        weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // dark iridescent gothic
  spore:     { family: "Griffy",            weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // creeping organic growth
  obelisk:   { family: "Metamorphous",      weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" }, // carved bone totem
  // chrome / industrial
  vortex:    { family: "Zen Dots",          weight: 400, letterSpacing: "0.02em", textTransform: "uppercase" }, // chrome octo techno
  slab:      { family: "Teko",              weight: 600, letterSpacing: "0.04em", textTransform: "uppercase" }, // wide industrial condensed
  stonehead: { family: "Eagle Lake",        weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // ancient chiselled stone
  // themed / requested
  tomato:    { family: "Lilita One",        weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // cute punchy produce
  mexico:    { family: "Fugaz One",         weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // bold sports jersey
  egypt:     { family: "Rakkas",            weight: 400, letterSpacing: "0",      textTransform: "none"      }, // exotic pharaonic display
  worldcup:  { family: "Bungee Inline",     weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // trophy outline signage
  poophero:  { family: "Bangers",           weight: 400, letterSpacing: "0.01em", textTransform: "uppercase" }, // comic-book action
  fallout:   { family: "VT323",             weight: 400, letterSpacing: "0",      textTransform: "uppercase" }, // amber CRT terminal
  cupcake:   { family: "Pacifico",          weight: 400, letterSpacing: "0",      textTransform: "none"      }, // sweet frosting script
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
  // A stylesheet <link> only downloads the CSS — the browser lazy-loads the woff2
  // binary on first glyph render, which IS the pop-in. Once the @font-face rules
  // register (link load), force the binary to download NOW via FontFaceSet.load()
  // so the title paints instantly when this skin becomes active.
  link.addEventListener("load", () => forceFontDownload(f));
  document.head.appendChild(link);
}

// Trigger the actual font-file fetch (not just the CSS). Safe to call repeatedly.
function forceFontDownload(f: SkinFont): void {
  const fonts = (document as Document & { fonts?: FontFaceSet }).fonts;
  if (!fonts?.load) return;
  try { void fonts.load(`${f.weight} 24px '${f.family}'`); } catch { /* ignore */ }
}

// is this font already downloaded? (so the title can show instantly, no fade)
export function isFontReady(f: SkinFont): boolean {
  const fonts = (document as Document & { fonts?: FontFaceSet }).fonts;
  if (typeof document === "undefined" || !fonts?.check) return false;
  try { return fonts.check(`${f.weight} 24px '${f.family}'`); } catch { return false; }
}

// kick off loading curated skin fonts up front (on app mount) so switching skins
// shows the new title instantly instead of popping in each time. Pass the visible
// roster's ids to preload only those (the default) — the full SKIN_FONTS map also
// covers hidden/donor bodies we don't want to fetch on every mount. With no ids,
// preloads the whole map.
export function preloadSkinFonts(ids?: string[]): void {
  const keys = ids?.length ? ids : Object.keys(SKIN_FONTS);
  for (const id of keys) {
    const f = SKIN_FONTS[id];
    if (f) ensureGoogleFont(f);
  }
}
