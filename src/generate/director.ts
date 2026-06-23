// The DIRECTOR — derive a skin's MATERIAL from the user's prompt instead of
// asking them to pick. Given the silhouette idea, an LLM returns:
//   - style:          closest-fitting donor of the 5 (sprite/palette donor)
//   - materialPrompt: a rich custom material/finish description for the paint
// On ANY failure (bad JSON, network, invalid style) it falls back to a
// deterministic keyword heuristic — it never throws.
import { DONOR_STYLES, type DonorStyle } from "./pipeline";

const MODEL = "gpt-4o";

// Punchy, cinematic Google-Fonts families SUGGESTED to the Director — these are
// examples, NOT a hard allow-list: the chosen font is loaded dynamically at render
// (ensureGoogleFont), so the LLM may return any real Google family that fits.
// DIVERSITY SYSTEM. The LLM, left to free-pick, anchors on the same few popular
// faces (Anton/Bebas/Orbitron) every time. To force spread, each Director call
// randomly favors ONE genre bucket and shows a rotated handful of its exemplars,
// so consecutive skins land in different type genres. Soft steer — the model may
// override for a strong vibe. Not an allow-list: any real Google family is valid
// (loaded dynamically at render; cross-validated in resolveFont).
const FONT_GENRES: Record<string, string[]> = {
  "chunky toy / rounded":      ["Bungee", "Titan One", "Luckiest Guy", "Bowlby One", "Chango", "Sigmar One", "Paytone One"],
  "techno / Y2K / sci-fi":     ["Orbitron", "Audiowide", "Michroma", "Wallpoet", "Zen Dots", "Tektur", "Syncopate"],
  "horror / metal / military": ["Nosifer", "Black Ops One", "Metal Mania", "Eater", "Creepster", "Butcherman", "Pirata One"],
  "retro pixel / arcade":      ["Press Start 2P", "VT323", "Silkscreen", "Rubik Glitch", "Bungee Inline", "Honk"],
  "blackletter / gothic":      ["UnifrakturCook", "Metamorphous", "Grenze Gotisch", "Pirata One"],
  "elegant serif display":     ["Abril Fatface", "Playfair Display", "Cinzel Decorative", "Yeseva One", "DM Serif Display"],
  "bold grotesque / condensed":["Anton", "Archivo Black", "Big Shoulders Display", "Squada One", "Teko", "Saira Condensed"],
  "retro script / signage":    ["Lobster", "Pacifico", "Monoton", "Rye", "Bungee Shade", "Faster One"],
};

// Fisher–Yates-ish shuffle (Math.random is fine in app/runtime code; this is not a
// resumable workflow script). Returns a new array.
function shuffled<T>(arr: readonly T[]): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
// donor style → a sensible default logomark font (used by the no-LLM heuristic)
const STYLE_FONT: Record<DonorStyle, string> = {
  frog: "Luckiest Guy", biomech: "Nosifer", halo: "Black Ops One",
  wmp: "Michroma", winamp: "Anton",
};

// Cross-validate ONE LLM-chosen family against Google Fonts (no catalog pull): the
// css2 endpoint 400s on an unknown family and 200s on a real one. A hallucinated
// or malformed name falls back to the style default; a network blip trusts the LLM
// (the client font loader degrades to the CSS stack if it turns out wrong anyway).
async function resolveFont(raw: string, style: DonorStyle): Promise<string> {
  const fallback = STYLE_FONT[style] ?? "Anton";
  const name = raw.trim();
  if (!/^[\w][\w '-]{1,40}$/.test(name)) return fallback;
  try {
    const fam = encodeURIComponent(name).replace(/%20/g, "+");
    const r = await fetch(`https://fonts.googleapis.com/css2?family=${fam}`);
    return r.ok ? name : fallback;
  } catch {
    return name;
  }
}

// keyword → donor, scanned in order; first hit wins. Generic fallback: winamp.
const HEURISTIC: Array<[RegExp, DonorStyle]> = [
  [/frog|toad|rubber|toy|cute|lily|amphib|gecko|slime/i, "frog"],
  [/bone|flesh|organ|biomech|giger|alien|sinew|chitin|fang|jaw|anglerfish|creature|monster/i, "biomech"],
  [/halo|military|armor|tactical|combat|unsc|metal plat|hex bolt|rugged/i, "halo"],
  [/aqua|y2k|translucent|gel|glossy white|luna|xp|bondi|frutiger|jelly|grape|gadget/i, "wmp"],
  [/chrome|brushed|gunmetal|boombox|led|winamp|stereo|hi-fi|silver/i, "winamp"],
];

export interface Material {
  style: DonorStyle;
  materialPrompt: string;
  font: string;
  name: string;        // concise skin TITLE (1-3 words) — never the raw prompt
  blurb: string;       // one short descriptive line
}

// a clean fallback title from the prompt (drop a leading article, Title-Case the
// first ~3 words) so a generated skin never shows "a fanged anglerfis · model".
export function titleFromPrompt(prompt: string): string {
  const words = prompt.trim().replace(/^(a|an|the)\s+/i, "").replace(/[^\w\s-]/g, "")
    .split(/\s+/).filter(Boolean).slice(0, 3);
  const t = words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  return t || "New Skin";
}
export function blurbFromPrompt(prompt: string): string {
  const p = prompt.trim().replace(/\s+/g, " ");
  const s = p.charAt(0).toUpperCase() + p.slice(1);
  return s.length > 64 ? s.slice(0, 61).trimEnd() + "…" : s;
}

function heuristic(prompt: string): Material {
  const hit = HEURISTIC.find(([re]) => re.test(prompt));
  const style = hit ? hit[1] : ("winamp" as DonorStyle);
  return {
    style,
    materialPrompt:
      `a richly detailed photoreal skeuomorphic finish evoking "${prompt}": ` +
      "cohesive material palette, tactile surface highlights, crisp moulded edges and hardware accents.",
    font: STYLE_FONT[style] ?? "Cinzel",
    name: titleFromPrompt(prompt),
    blurb: blurbFromPrompt(prompt),
  };
}

export async function deriveMaterial(openaiKey: string, prompt: string, avoidFonts: string[] = []): Promise<Material> {
  if (!openaiKey) return heuristic(prompt);
  // pick a random genre to favor this call + a rotated set of its exemplars, and a
  // de-duped recent-fonts avoid list — together these spread font choices across
  // generations instead of clustering on the same few popular faces.
  const genre = shuffled(Object.keys(FONT_GENRES))[0];
  const exemplars = shuffled(FONT_GENRES[genre]).slice(0, 4).join(", ");
  const avoid = [...new Set(avoidFonts.map((f) => f.trim()).filter(Boolean))].slice(0, 10);
  try {
    const r = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${openaiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: MODEL,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "system",
            content:
              "You art-direct skeuomorphic MP3-player skins. Given a silhouette idea, reply with JSON " +
              `{"name": <title>, "blurb": <description>, "style": <one of ${DONOR_STYLES.join("|")}>, ` +
              `"materialPrompt": <1-2 sentence rich custom material/finish description derived from the idea: ` +
              `surface, color, sheen, hardware accents>, "font": <a Google Fonts family name>}. ` +
              "name is a CONCISE, punchy skin TITLE — 1 to 3 words, like a product or film name (e.g. 'Angler Maw', " +
              "'Bondi G3', 'Spartan Ring'); NEVER echo the raw prompt or include a model name. " +
              "blurb is ONE short descriptive line, at most ~8 words (e.g. 'Fanged jaw grown around the dial'). " +
              "style is the closest-fitting donor for palette/sprite reuse and MUST be exactly one of the listed values. " +
              "font is the display typeface for this skin's TITLE LOGOMARK (like a film's title card): a real, " +
              "currently-available Google Fonts family — favour PUNCHY, bold, cinematic display faces. " +
              `For VARIETY, lean toward a ${genre} face this time (e.g. ${exemplars}), UNLESS the skin's vibe ` +
              "strongly calls for a different genre — then follow the vibe. " +
              (avoid.length ? `Do NOT reuse any of these recently-used families: ${avoid.join(", ")}. ` : "") +
              "Avoid defaulting to the same handful of popular faces (Anton, Bebas Neue, Oswald) unless truly apt. " +
              "Return the exact family name as it appears on Google Fonts.",
          },
          { role: "user", content: prompt },
        ],
      }),
    });
    if (!r.ok) throw new Error(`openai ${r.status}`);
    const data = (await r.json()) as { choices?: Array<{ message?: { content?: string } }> };
    const parsed = JSON.parse(data.choices?.[0]?.message?.content ?? "{}");
    const style = parsed.style as DonorStyle;
    const materialPrompt = (parsed.materialPrompt ?? "").trim();
    if (!DONOR_STYLES.includes(style) || !materialPrompt) throw new Error("invalid director output");
    // font is best-effort + loaded dynamically. Let the LLM pick any family from
    // its own knowledge, then CROSS-VALIDATE that one name against Google Fonts
    // (resolveFont probes the css2 endpoint — real → 200, hallucinated → 400) so a
    // made-up name falls back to a real style-appropriate face instead of silently
    // degrading to the generic stack. No catalog dump, no API key, one tiny probe.
    const raw = typeof parsed.font === "string" ? parsed.font.trim() : "";
    const font = await resolveFont(raw, style);
    // name/blurb: clean LLM output, else derive a tidy fallback from the prompt
    const name = (typeof parsed.name === "string" && parsed.name.trim())
      ? parsed.name.trim().replace(/[·|].*$/, "").slice(0, 28).trim() : titleFromPrompt(prompt);
    const blurb = (typeof parsed.blurb === "string" && parsed.blurb.trim())
      ? parsed.blurb.trim().slice(0, 72) : blurbFromPrompt(prompt);
    return { style, materialPrompt, font, name, blurb };
  } catch {
    return heuristic(prompt);
  }
}
