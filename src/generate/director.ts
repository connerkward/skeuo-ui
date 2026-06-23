// The DIRECTOR — derive a skin's MATERIAL from the user's prompt instead of
// asking them to pick. Given the silhouette idea, an LLM returns:
//   - style:          closest-fitting donor of the 5 (sprite/palette donor)
//   - materialPrompt: a rich custom material/finish description for the paint
// On ANY failure (bad JSON, network, invalid style) it falls back to a
// deterministic keyword heuristic — it never throws.
import { DONOR_STYLES, type DonorStyle } from "./pipeline";
import type { Region, Kind } from "../template/schema";

const MODEL = "gpt-4o";

// keyword → donor, scanned in order; first hit wins. Generic fallback: winamp.
const HEURISTIC: Array<[RegExp, DonorStyle]> = [
  [/frog|toad|rubber|toy|cute|lily|amphib|gecko|slime/i, "frog"],
  [/bone|flesh|organ|biomech|giger|alien|sinew|chitin|fang|jaw|anglerfish|creature|monster/i, "biomech"],
  [/halo|military|armor|tactical|combat|unsc|metal plat|hex bolt|rugged/i, "halo"],
  [/aqua|y2k|translucent|gel|glossy white|luna|xp|bondi|frutiger|jelly|grape|gadget/i, "wmp"],
  [/chrome|brushed|gunmetal|boombox|led|winamp|stereo|hi-fi|silver/i, "winamp"],
];

function heuristic(prompt: string): { style: DonorStyle; materialPrompt: string } {
  const hit = HEURISTIC.find(([re]) => re.test(prompt));
  const style = hit ? hit[1] : ("winamp" as DonorStyle);
  return {
    style,
    materialPrompt:
      `a richly detailed photoreal skeuomorphic finish evoking "${prompt}": ` +
      "cohesive material palette, tactile surface highlights, crisp moulded edges and hardware accents.",
  };
}

export async function deriveMaterial(
  openaiKey: string,
  prompt: string,
): Promise<{ style: DonorStyle; materialPrompt: string }> {
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
              "material/finish description derived from the idea: surface, color, sheen, hardware accents>}. " +
              "style is the closest-fitting donor for palette/sprite reuse and MUST be exactly one of the listed values.",
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
    return { style, materialPrompt };
  } catch {
    return heuristic(prompt);
  }
}

// ---------------------------------------------------------------------------
// deriveLayout — the Director also designs the TEMPLATE (control layout) from
// the prompt, so each skin gets a theme-appropriate, varied set of controls
// instead of a fixed preset. Returns normalized schema Regions, or null on any
// failure (caller falls back to the constant variant). Never throws.
// ---------------------------------------------------------------------------
const LAYOUT_MODEL = "gpt-4o";
const VALID_KINDS = new Set<Kind>([
  "button", "toggle", "slider-h", "slider-v", "knob", "slider-arc", "segmented", "xy", "display",
]);

const LAYOUT_SYS =
  "You design the CONTROL LAYOUT for a skeuomorphic music-player skin, themed to the user's idea. " +
  "Output STRICT JSON {\"regions\":[...]} on a PORTRAIT canvas, normalized 0..1 (x,y=top-left, w,h=fractions; canvas is 2:3 tall).\n\n" +
  "ALWAYS include: one display bind \"visualizer\" (the main screen, large, upper area); one display bind \"marquee\" (track text) " +
  "and one display bind \"time\" (clock); one slider-h bind \"seek\"; transport buttons (kind button) bind prev/play/next/stop with " +
  "PLAY the largest and round (shape \"ellipse\").\n\n" +
  "Then add a THEME-APPROPRIATE, VARIED selection of extras (vary the set + arrangement per theme — a boombox, a handheld, a dashboard, " +
  "a compact should look different): knob (bind volume/balance/tone/bass/treble, round shape \"ellipse\"); slider-v EQ faders (bind " +
  "\"eqBand\", group \"eq\", index 0..n); toggle (bind shuffle/repeat/eqOn/power); segmented (bind \"mode\", options like [\"FM\",\"CD\",\"TAPE\"]); " +
  "xy pad (bind \"xy\"); slider-arc ring-seek around a dial (use bind \"seek\" as slider-arc INSTEAD of slider-h for dial-centric designs).\n\n" +
  "RULES: every rect inside 0.04..0.96; controls must NOT overlap each other or the screen; round controls ~square (w≈h); group/align related " +
  "controls; sizes sensible (transport buttons 0.06-0.16 with play biggest, knobs 0.08-0.16, the screen 0.4-0.85 wide). " +
  "Keep it UNCLUTTERED — about 6 to 10 controls total, with generous breathing room between them; do NOT cram the face. " +
  "The marquee is WIDE (~0.5-0.65) and the time readout is NARROW (~0.14-0.22) sitting beside it on the same row, NOT stacked full-width. " +
  "If you include EQ faders, use 5-7 bands max. Make it interesting and specific to the theme.\n\n" +
  "Each region: {\"id\":\"snake_case\",\"kind\":\"button|toggle|slider-h|slider-v|knob|slider-arc|segmented|xy|display\",\"bind\":\"<state field>\"," +
  "\"label\":\"<short>\",\"x\":0,\"y\":0,\"w\":0,\"h\":0,\"shape\":\"ellipse\"(round only),\"options\":[...](segmented),\"group\":\"eq\",\"index\":0}. " +
  "Return ONLY the JSON object.";

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

// display ROLES the model sometimes puts in `kind` (or `id`/`bind`) instead of "display".
const DISPLAY_ROLES = new Set(["visualizer", "marquee", "time", "screen", "lcd", "playlist", "display", "track_info"]);

// normalize one raw LLM region into a schema Region, or null if unusable. Robust to
// the model using a display ROLE as the kind (kind:"visualizer" → kind:"display").
function normRegion(r: Record<string, unknown>, i: number): Region | null {
  let kind = String(r.kind ?? "");
  const id = (typeof r.id === "string" && r.id) || `r${i}`;
  const bindRaw = typeof r.bind === "string" ? r.bind : undefined;
  // figure out if this is a display, even if the model mislabeled the kind
  const isDisplay = kind === "display" || DISPLAY_ROLES.has(kind) || DISPLAY_ROLES.has(bindRaw ?? "") ||
    (!VALID_KINDS.has(kind as Kind) && DISPLAY_ROLES.has(id));
  if (isDisplay) kind = "display";
  if (!VALID_KINDS.has(kind as Kind)) return null;
  const x = Number(r.x), y = Number(r.y), w = Number(r.w), h = Number(r.h);
  if (![x, y, w, h].every((n) => Number.isFinite(n)) || w <= 0 || h <= 0) return null;
  // clamp into bounds (keep within 0.02..0.98)
  const cw = Math.min(w, 0.96), ch = Math.min(h, 0.96);
  const cx = Math.max(0.02, Math.min(x, 0.98 - cw)), cy = Math.max(0.02, Math.min(y, 0.98 - ch));
  const bind = isDisplay ? undefined : bindRaw;
  const reg: Region = {
    id,
    kind: kind as Kind,
    content: isDisplay ? "dynamic" : "sprite",
    layer: isDisplay ? "screen" : "components",
    rect: { x: cx, y: cy, w: cw, h: ch },
    ...(typeof r.label === "string" ? { label: r.label } : {}),
    ...(bind ? { bind } : {}),
    ...(r.shape === "ellipse" ? { shape: "ellipse" as const } : {}),
    ...(Array.isArray(r.options) ? { options: (r.options as unknown[]).map(String) } : {}),
    ...(typeof r.group === "string" ? { group: r.group } : {}),
    ...(typeof r.index === "number" ? { index: r.index } : {}),
  };
  if (isDisplay) {
    // dynamicType from whichever field carried the role
    const role = [String(r.kind ?? ""), bindRaw ?? "", id].find((v) => v === "visualizer" || v === "marquee" || v === "time")
      ?? (DISPLAY_ROLES.has(id) ? id : "marquee");
    reg.dynamicType = role === "visualizer" ? "visualizer" : role === "time" ? "time" : "marquee";
    // keep a bind for the VLM checklist identity (visualizer/marquee/time)
    reg.bind = reg.dynamicType;
  }
  return reg;
}

export async function deriveLayout(openaiKey: string, prompt: string): Promise<Region[] | null> {
  if (!openaiKey) return null;
  try {
    const r = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${openaiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: LAYOUT_MODEL,
        response_format: { type: "json_object" },
        temperature: 0.9,   // variety across skins
        max_tokens: 4000,
        messages: [
          { role: "system", content: LAYOUT_SYS },
          { role: "user", content: `Theme: ${prompt}` },
        ],
      }),
    });
    if (!r.ok) throw new Error(`openai ${r.status} ${(await r.text()).slice(0, 200)}`);
    const data = (await r.json()) as { choices?: Array<{ message?: { content?: string }; finish_reason?: string }> };
    const content = data.choices?.[0]?.message?.content ?? "{}";
    const parsed = JSON.parse(content) as { regions?: Record<string, unknown>[] };
    const raw = Array.isArray(parsed.regions) ? parsed.regions : [];
    const regions = raw.map(normRegion).filter((x): x is Region => x !== null);
    const hasViz = regions.some((g) => g.kind === "display");
    const hasPlay = regions.some((g) => g.kind === "button" && g.bind === "play");
    // eslint-disable-next-line no-console
    console.warn(`[deriveLayout] finish=${data.choices?.[0]?.finish_reason} raw=${raw.length} valid=${regions.length} viz=${hasViz} play=${hasPlay}`);
    if (!hasViz || !hasPlay || regions.length < 4) throw new Error("layout missing required controls");
    return regions;
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn(`[deriveLayout] FELL BACK: ${e instanceof Error ? e.message : String(e)}`);
    return null;   // caller falls back to the constant variant preset
  }
}

// ---------------------------------------------------------------------------
// extractSlots — the VLM ALIGN pass (the approach Conner landed on, see
// generation/freeform.py). Give gpt-4o the painted device image + the template's
// control checklist; it returns each control's ACTUAL bounding box in the image,
// matched by bind/icon/shape (play=►, prev=◄◄, knob=round dial, seek=slider,
// screen=large display). Identity is correct by construction (matched by bind),
// so there is no nearest-neighbour mis-assignment. Returns [] on any failure.
// ---------------------------------------------------------------------------
export interface SlotControl { bind: string; kind: string; label?: string }
export interface SlotBox { bind: string; x: number; y: number; w: number; h: number; conf?: number }

const EXTRACT_SYS =
  "You are a precise UI control LOCATOR for skeuomorphic music-player images. You are given the painted " +
  "device image and a list of EXPECTED controls (by bind name + kind). Return STRICT JSON " +
  "{\"boxes\":[{\"bind\":\"<the expected bind>\",\"x\":0,\"y\":0,\"w\":0,\"h\":0,\"conf\":0..1}]}. " +
  "Coordinates are NORMALIZED 0..1, x,y = TOP-LEFT, w,h = width/height fraction of the WHOLE image. " +
  "Locate where each expected control ACTUALLY appears in the painting, identifying it by its icon/shape: " +
  "play = a triangle ▶, prev/rewind = ◀◀, next/forward = ▶▶, stop = a square ■, a knob = a round rotary dial, " +
  "a slider-h/seek = a horizontal groove/track, a slider-v = a vertical fader, a toggle = a small switch, the " +
  "visualizer/screen/display = the large dark inset screen, marquee/time = the text readout areas. Use the bind " +
  "label as a hint. Give a tight box around the actual painted control (the round cap for a button/knob; the full " +
  "groove for a slider; the glass for a screen). Only include a control if you can confidently locate it; OMIT any " +
  "you cannot find. Return ONLY the JSON object.";

export async function extractSlots(
  openaiKey: string,
  image: string,          // data: URL or public URL of the device image
  controls: SlotControl[],
): Promise<SlotBox[]> {
  if (!openaiKey || !controls.length) return [];
  const list = controls
    .map((c) => `${c.bind} (${c.kind}${c.label ? `, labeled "${c.label}"` : ""})`)
    .join("; ");
  try {
    const r = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${openaiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: MODEL,
        response_format: { type: "json_object" },
        max_tokens: 3000,
        messages: [
          { role: "system", content: EXTRACT_SYS },
          {
            role: "user",
            content: [
              { type: "text", text: `Locate these expected controls in the image (normalized 0..1 boxes): ${list}` },
              { type: "image_url", image_url: { url: image, detail: "high" } },
            ],
          },
        ],
      }),
    });
    if (!r.ok) throw new Error(`openai ${r.status}`);
    const data = (await r.json()) as { choices?: Array<{ message?: { content?: string } }> };
    const parsed = JSON.parse(data.choices?.[0]?.message?.content ?? "{}") as { boxes?: Record<string, unknown>[] };
    const raw = Array.isArray(parsed.boxes) ? parsed.boxes : [];
    const out: SlotBox[] = [];
    for (const b of raw) {
      const bind = typeof b.bind === "string" ? b.bind : "";
      const x = Number(b.x), y = Number(b.y), w = Number(b.w), h = Number(b.h);
      if (!bind || ![x, y, w, h].every((n) => Number.isFinite(n)) || w <= 0 || h <= 0) continue;
      out.push({ bind, x: clamp01(x), y: clamp01(y), w: clamp01(w), h: clamp01(h), conf: Number(b.conf) || undefined });
    }
    return out;
  } catch {
    return [];
  }
}
