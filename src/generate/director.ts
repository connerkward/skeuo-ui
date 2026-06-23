// The DIRECTOR — derive a skin's MATERIAL from the user's prompt instead of
// asking them to pick. Given the silhouette idea, an LLM returns:
//   - style:          closest-fitting donor of the 5 (sprite/palette donor)
//   - materialPrompt: a rich custom material/finish description for the paint
// On ANY failure (bad JSON, network, invalid style) it falls back to a
// deterministic keyword heuristic — it never throws.
import { DONOR_STYLES, type DonorStyle } from "./pipeline";

const MODEL = "gpt-4o";

// Logomark fonts the Director may choose from — EXACTLY the families pre-loaded
// via the Google Fonts <link> in index.html, so a generated skin's title is
// always renderable with no runtime font injection. Keep in sync with index.html.
export const LOGO_FONTS = [
  "Cinzel", "Orbitron", "Audiowide", "Bungee", "Lobster", "Bigshot One",
  "Metamorphous", "Fredoka", "Saira Condensed", "VT323", "Share Tech Mono",
] as const;
// donor style → a sensible default logomark font (used by the no-LLM heuristic)
const STYLE_FONT: Record<DonorStyle, string> = {
  frog: "Fredoka", biomech: "Metamorphous", halo: "Saira Condensed",
  wmp: "Audiowide", winamp: "Orbitron",
};

// keyword → donor, scanned in order; first hit wins. Generic fallback: winamp.
const HEURISTIC: Array<[RegExp, DonorStyle]> = [
  [/frog|toad|rubber|toy|cute|lily|amphib|gecko|slime/i, "frog"],
  [/bone|flesh|organ|biomech|giger|alien|sinew|chitin|fang|jaw|anglerfish|creature|monster/i, "biomech"],
  [/halo|military|armor|tactical|combat|unsc|metal plat|hex bolt|rugged/i, "halo"],
  [/aqua|y2k|translucent|gel|glossy white|luna|xp|bondi|frutiger|jelly|grape|gadget/i, "wmp"],
  [/chrome|brushed|gunmetal|boombox|led|winamp|stereo|hi-fi|silver/i, "winamp"],
];

function heuristic(prompt: string): { style: DonorStyle; materialPrompt: string; font: string } {
  const hit = HEURISTIC.find(([re]) => re.test(prompt));
  const style = hit ? hit[1] : ("winamp" as DonorStyle);
  return {
    style,
    materialPrompt:
      `a richly detailed photoreal skeuomorphic finish evoking "${prompt}": ` +
      "cohesive material palette, tactile surface highlights, crisp moulded edges and hardware accents.",
    font: STYLE_FONT[style] ?? "Cinzel",
  };
}

export async function deriveMaterial(
  openaiKey: string,
  prompt: string,
): Promise<{ style: DonorStyle; materialPrompt: string; font: string }> {
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
              `{"style": <one of ${DONOR_STYLES.join("|")}>, "materialPrompt": <1-2 sentence rich custom ` +
              "material/finish description derived from the idea: surface, color, sheen, hardware accents>, " +
              `"font": <one of ${LOGO_FONTS.join("|")}>}. ` +
              "style is the closest-fitting donor for palette/sprite reuse and MUST be exactly one of the listed values. " +
              "font is the display typeface for this skin's TITLE LOGOMARK (like a film's title card) — pick the listed " +
              "family whose character best matches the skin's vibe; it MUST be exactly one of the listed values.",
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
    // font is best-effort: validate against the allow-list, else default by style
    const font = LOGO_FONTS.includes(parsed.font) ? (parsed.font as string) : (STYLE_FONT[style] ?? "Cinzel");
    return { style, materialPrompt, font };
  } catch {
    return heuristic(prompt);
  }
}
