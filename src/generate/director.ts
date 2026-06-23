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
const FONT_SUGGESTIONS = [
  "Anton", "Bebas Neue", "Bungee", "Titan One", "Luckiest Guy", "Bangers",
  "Black Ops One", "Orbitron", "Audiowide", "Michroma", "Monoton", "Nosifer",
  "Pirata One", "Rubik Mono One", "Baloo 2", "Fredoka", "Lobster", "Lilita One",
  "Cinzel Decorative", "Press Start 2P", "Faster One", "Bowlby One",
];
// donor style → a sensible default logomark font (used by the no-LLM heuristic)
const STYLE_FONT: Record<DonorStyle, string> = {
  frog: "Luckiest Guy", biomech: "Nosifer", halo: "Black Ops One",
  wmp: "Michroma", winamp: "Anton",
};

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

export async function deriveMaterial(openaiKey: string, prompt: string): Promise<Material> {
  if (!openaiKey) return heuristic(prompt);
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
              "font is the display typeface for this skin's TITLE LOGOMARK (like a film's title card): pick the real, " +
              "currently-available Google Fonts family whose character best matches the skin's vibe — favour PUNCHY, " +
              `bold, cinematic display faces (e.g. ${FONT_SUGGESTIONS.slice(0, 12).join(", ")}, or another that fits ` +
              "better). Return the exact family name as it appears on Google Fonts.",
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
    // font is best-effort + loaded dynamically, so accept any plausible family
    // name (letters/spaces/digits), else default by style. No hard allow-list.
    const raw = typeof parsed.font === "string" ? parsed.font.trim() : "";
    const font = /^[\w][\w '-]{1,40}$/.test(raw) ? raw : (STYLE_FONT[style] ?? "Anton");
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
