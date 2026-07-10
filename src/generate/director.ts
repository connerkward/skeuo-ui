// The DIRECTOR — derive a skin's MATERIAL from the user's prompt instead of
// asking them to pick. Given the silhouette idea, an LLM returns:
//   - style:          closest-fitting donor of the 5 (sprite/palette donor)
//   - materialPrompt: a rich custom material/finish description for the paint
// On ANY failure (bad JSON, network, invalid style, no auth) it falls back to a
// deterministic keyword heuristic — it never throws, and never calls OpenAI.
import { DONOR_STYLES, type DonorStyle } from "./pipeline";
import type { Region, Kind } from "../template/schema";
import { getVertexAccessToken, VERTEX_PROJECT, type VertexAuthOpts } from "./vertexAuth";

// ---------------------------------------------------------------------------
// Director LLM provider — Gemini 3.1 Pro via VERTEX AI, for BOTH the text-only
// calls (deriveMaterial/deriveLayout) AND the vision calls (extractSlots/
// extractMasks). ZERO gpt-4o, ZERO api.openai.com, ZERO OPENAI_API_KEY anywhere
// in this file (2026-07 — the OpenAI Director/vision fallback that used to live
// here has been removed entirely per user directive: "ZERO gpt-4o anywhere").
//
// Auth is Vertex-only (see vertexAuth.ts): a GCP_SERVICE_ACCOUNT_KEY secret in
// prod (Cloudflare Worker, JWT-bearer flow), or a gcloud user-auth access token
// in dev (server/gcloudAuth.ts) — same project (muser-2605300220) + auth pattern
// proven working by tools/mask-align-exp/gen12/genskin.py's edit_vertex(). When
// neither is available, every function below degrades to its deterministic
// fallback (heuristic() / null / []) — never throws.
//
// Model id verified live against Google's docs (2026-07-09): "gemini-3-pro-preview"
// was retired (shut down 2026-03-09) and now aliases to "gemini-3.1-pro-preview" —
// the explicit current id, used below for both text and vision (it is natively
// multimodal, so one model covers deriveMaterial/deriveLayout/extractSlots/
// extractMasks). Google's docs also warn Gemini 3.1 Pro should be run at its
// default temperature (1.0) — "reducing it may lead to looping or degraded
// performance" — so no call below forwards a custom temperature.
export interface DirectorKeys { gcpServiceAccountKey?: string; devToken?: string }

const VERTEX_MODEL = "gemini-3.1-pro-preview";
const VERTEX_LOCATION = "global";
function vertexEndpoint(model: string): string {
  return `https://aiplatform.googleapis.com/v1/projects/${VERTEX_PROJECT}/locations/${VERTEX_LOCATION}/publishers/google/models/${model}:generateContent`;
}
function authOpts(keys: DirectorKeys): VertexAuthOpts {
  return { serviceAccountKey: keys.gcpServiceAccountKey, devToken: keys.devToken };
}

interface ChatResult { content: string; finishReason?: string }

// chunked base64 (no call-stack limits on large images); atob/btoa exist in
// browsers, Workers and modern Node — the only runtimes this file targets.
function bytesToBase64(bytes: Uint8Array): string {
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  return btoa(bin);
}

// image (a data: URL or a public http(s) URL) → a Vertex generateContent inlineData
// part. Vertex takes raw bytes, not a fetchable URL, so an http(s) image is fetched
// and re-encoded server-side (this always runs server-side — Worker or Node dev).
async function toImagePart(image: string): Promise<{ inline_data: { mime_type: string; data: string } }> {
  const m = image.match(/^data:([^;]+);base64,([\s\S]+)$/);
  if (m) return { inline_data: { mime_type: m[1], data: m[2] } };
  const r = await fetch(image);
  if (!r.ok) throw new Error(`fetch image ${image} → ${r.status}`);
  const mime = r.headers.get("content-type") || "image/png";
  const bytes = new Uint8Array(await r.arrayBuffer());
  return { inline_data: { mime_type: mime, data: bytesToBase64(bytes) } };
}

// One JSON-mode Vertex generateContent call. Returns null when no Vertex auth is
// configured (dev: no gcloud session; prod: GCP_SERVICE_ACCOUNT_KEY secret unset) —
// caller falls back to its deterministic default. Throws only on a genuine HTTP/parse
// error once auth succeeded (caller catches that too).
async function directorChat(
  keys: DirectorKeys,
  opts: { system: string; user: string; maxTokens?: number; imageParts?: Array<{ inline_data: { mime_type: string; data: string } }> },
): Promise<ChatResult | null> {
  const token = await getVertexAccessToken(authOpts(keys));
  if (!token) return null;
  const parts: unknown[] = [...(opts.imageParts ?? []), { text: opts.user }];
  const body = {
    contents: [{ role: "user", parts }],
    systemInstruction: { role: "system", parts: [{ text: opts.system }] },
    generationConfig: {
      responseMimeType: "application/json",
      // gemini-3.1-pro-preview defaults to thinkingLevel "high" — verified live
      // (2026-07-10) that this burns the ENTIRE maxOutputTokens budget on internal
      // thought tokens before emitting any JSON (finishReason MAX_TOKENS, zero
      // content). These are short structured-extraction calls, not open reasoning —
      // force "low" so the token budget goes to the actual JSON response.
      thinkingConfig: { thinkingLevel: "low" },
      ...(opts.maxTokens ? { maxOutputTokens: opts.maxTokens } : {}),
    },
  };
  const r = await fetch(vertexEndpoint(VERTEX_MODEL), {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`vertex ${r.status} ${(await r.text()).slice(0, 200)}`);
  const data = (await r.json()) as {
    candidates?: Array<{ content?: { parts?: Array<{ text?: string }> }; finishReason?: string }>;
  };
  const cand = data.candidates?.[0];
  const content = cand?.content?.parts?.map((p) => p.text ?? "").join("") || "{}";
  return { content, finishReason: cand?.finishReason };
}

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

export async function deriveMaterial(keys: DirectorKeys, prompt: string, avoidFonts: string[] = []): Promise<Material> {
  // pick a random genre to favor this call + a rotated set of its exemplars, and a
  // de-duped recent-fonts avoid list — together these spread font choices across
  // generations instead of clustering on the same few popular faces.
  const genre = shuffled(Object.keys(FONT_GENRES))[0];
  const exemplars = shuffled(FONT_GENRES[genre]).slice(0, 4).join(", ");
  const avoid = [...new Set(avoidFonts.map((f) => f.trim()).filter(Boolean))].slice(0, 10);
  try {
    const system =
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
      "Return the exact family name as it appears on Google Fonts.";
    const res = await directorChat(keys, { system, user: prompt });
    if (!res) return heuristic(prompt);
    const parsed = JSON.parse(res.content);
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

// ---------------------------------------------------------------------------
// deriveLayout — the Director also designs the TEMPLATE (control layout) from
// the prompt, so each skin gets a theme-appropriate, varied set of controls
// instead of a fixed preset. Returns normalized schema Regions, or null on any
// failure (caller falls back to the constant variant). Never throws.
// ---------------------------------------------------------------------------
const VALID_KINDS = new Set<Kind>([
  "button", "toggle", "slider-h", "slider-v", "knob", "slider-arc", "segmented", "xy", "display",
]);

const LAYOUT_SYS =
  "You design the CONTROL LAYOUT for a skeuomorphic music-player skin, themed to the user's idea. " +
  "Output STRICT JSON {\"regions\":[...]} on a PORTRAIT canvas, normalized 0..1 (x,y=top-left, w,h=fractions; canvas is 2:3 tall).\n\n" +
  "ALWAYS include: one display bind \"visualizer\" (the main screen, large, upper area); one display bind \"marquee\" (track text) " +
  "and one display bind \"time\" (clock); one slider-h bind \"seek\"; transport buttons (kind button) bind prev/play/next/stop with " +
  "PLAY the largest. Button SHAPE is FREE — do NOT force buttons round (see SHAPE & BANKS).\n\n" +
  "Then add a THEME-APPROPRIATE, VARIED selection of extras (vary the set + arrangement per theme — a boombox, a handheld, a dashboard, " +
  "a compact should look different): knob (bind volume/balance/tone/bass/treble, round shape \"ellipse\"); slider-v EQ faders (bind " +
  "\"eqBand\", group \"eq\", index 0..n); toggle (bind shuffle/repeat/eqOn/power); segmented (bind \"mode\", options like [\"FM\",\"CD\",\"TAPE\"]); " +
  "xy pad (bind \"xy\"); slider-arc ring-seek around a dial (use bind \"seek\" as slider-arc INSTEAD of slider-h for dial-centric designs).\n\n" +
  "SHAPE & BANKS: real hardware groups controls into ADJACENT BANKS in a shared housing — a row of climate/transport keys that touch edge-to-edge, " +
  "a Walkman rocker cluster, a car-console keypad. You MAY place buttons DIRECTLY ADJACENT (touching, sharing edges, zero gap) to form such a bank — " +
  "this is ENCOURAGED and theme-appropriate; they must only never OVERLAP. Buttons may be ANY shape/aspect (wide pill, tall key, square, rounded-rect, " +
  "trapezoid-ish); only KNOBS stay round. Align an adjacent bank on a shared baseline with equal heights so it reads as one unit. " +
  "Vary shape + grouping to match the theme so a car dashboard, a Walkman, and a boombox look distinct.\n\n" +
  "RULES: every rect inside 0.04..0.96; controls must NOT OVERLAP each other or the screen (touching/adjacent IS allowed — overlap is not); " +
  "KNOBS are round (~square, w≈h); BUTTONS may be any aspect/shape; group/align related controls; " +
  "sizes sensible (transport buttons 0.06-0.16 with play biggest, knobs 0.08-0.16, the screen 0.4-0.85 wide). " +
  "Keep it FOCUSED — at most ~5 INTERACTABLES beyond the screen/marquee/time/seek. Avoid RANDOM clutter, but a TIGHT, INTENTIONAL adjacent bank is good, not clutter. " +
  "The marquee is WIDE (~0.5-0.65) and the time readout is NARROW (~0.14-0.22) sitting beside it on the same row, NOT stacked full-width. " +
  "If you include EQ faders, use 5-7 bands max. Make it interesting and specific to the theme.\n" +
  "ARRANGEMENT — place controls ORGANICALLY to fit the theme's FORM, like an early-2000s Winamp / WMP-XP / Sonique skin: hug a bezel, RING the screen, cluster into a sculpted facet, or scatter across an asymmetric body — vary it wildly per theme. Do NOT default to a centered rack / a plain transport row every time; asymmetric, contour-following, characterful layouts are ENCOURAGED (positions only need to not overlap).\n\n" +
  "Each region: {\"id\":\"snake_case\",\"kind\":\"button|toggle|slider-h|slider-v|knob|slider-arc|segmented|xy|display\",\"bind\":\"<state field>\"," +
  "\"label\":\"<short>\",\"x\":0,\"y\":0,\"w\":0,\"h\":0,\"shape\":\"ellipse\"(round only),\"options\":[...](segmented),\"group\":\"eq\",\"index\":0}.\n" +
  "SILHOUETTES (optional, encouraged): per control you MAY also give " +
  "\"shapeKind\":\"circle|square|hexagon|wedge|kidney|lozenge|teardrop|blob|arc\" (an organic era-correct silhouette), " +
  "OR draw ANY custom silhouette as \"path\":[{\"x\":0..1,\"y\":0..1},...] (5-12 points, a closed polygon normalized INSIDE the control's rect — " +
  "invent whatever shape fits the theme), plus \"diff\":0..1 (guide diffuseness: 0 = the painter must follow this exact silhouette, 1 = a soft " +
  "suggestion the painter is free to reinterpret). " +
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
    // studio silhouette fields (pass-through; harmless to the pipeline, drawn by the studio)
    ...(typeof r.shapeKind === "string" ? { shapeKind: String(r.shapeKind) } : {}),
    ...(typeof r.diff === "number" && Number.isFinite(r.diff) ? { diff: clamp01(Number(r.diff)) } : {}),
    ...(Array.isArray(r.path) && (r.path as unknown[]).length >= 3
      && (r.path as Array<Record<string, unknown>>).every((p) => p && typeof p.x === "number" && typeof p.y === "number")
      ? { path: (r.path as Array<{ x: number; y: number }>).slice(0, 16).map((p) => ({ x: clamp01(p.x), y: clamp01(p.y) })) } : {}),
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

export async function deriveLayout(keys: DirectorKeys, prompt: string): Promise<Region[] | null> {
  try {
    const res = await directorChat(keys, { system: LAYOUT_SYS, user: `Theme: ${prompt}`, maxTokens: 4000 });
    if (!res) return null;
    const { content, finishReason } = res;
    const parsed = JSON.parse(content) as { regions?: Record<string, unknown>[] };
    const raw = Array.isArray(parsed.regions) ? parsed.regions : [];
    const all = raw.map(normRegion).filter((x): x is Region => x !== null);
    // HARD density cap (code-enforced, not just prompt): displays always kept; then
    // transport + seek; then other extras; then EQ bands (≤5). Total interactables ≤9.
    const TRANSPORT = new Set(["prev", "play", "pause", "next", "stop"]);
    const prio = (r: Region) => (TRANSPORT.has(r.bind ?? "") || r.bind === "seek") ? 0 : r.bind === "eqBand" ? 2 : 1;
    const displays = all.filter((r) => r.kind === "display");
    const inter = all.filter((r) => r.kind !== "display")
      .map((r, i) => ({ r, i })).sort((a, b) => prio(a.r) - prio(b.r) || a.i - b.i);
    const MAX_INTERACT = 9; let eq = 0; const kept: Region[] = [];
    for (const { r } of inter) {
      if (kept.length >= MAX_INTERACT) break;
      if (r.bind === "eqBand") { if (eq >= 5) continue; eq++; }
      kept.push(r);
    }
    const regions = [...displays, ...kept];
    const hasViz = regions.some((g) => g.kind === "display");
    const hasPlay = regions.some((g) => g.kind === "button" && g.bind === "play");
    // eslint-disable-next-line no-console
    console.warn(`[deriveLayout] finish=${finishReason} raw=${raw.length} kept=${regions.length} (cap ${MAX_INTERACT}) viz=${hasViz} play=${hasPlay}`);
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
// generation/freeform.py). Give the Director vision model (Gemini 3.1 Pro via
// Vertex — see the module header) the painted device image + the template's
// control checklist; it returns each control's ACTUAL bounding box in the image,
// matched by bind/icon/shape (play=►, prev=◄◄, knob=round dial, seek=slider,
// screen=large display). Identity is correct by construction (matched by bind),
// so there is no nearest-neighbour mis-assignment. Returns [] on any failure
// (including no Vertex auth configured).
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
  keys: DirectorKeys,
  image: string,          // data: URL or public URL of the device image
  controls: SlotControl[],
): Promise<SlotBox[]> {
  if (!controls.length) return [];
  const list = controls
    .map((c) => `${c.bind} (${c.kind}${c.label ? `, labeled "${c.label}"` : ""})`)
    .join("; ");
  try {
    const imagePart = await toImagePart(image);
    const res = await directorChat(keys, {
      system: EXTRACT_SYS,
      user: `Locate these expected controls in the image (normalized 0..1 boxes): ${list}`,
      imageParts: [imagePart],
      maxTokens: 3000,
    });
    if (!res) return [];
    const parsed = JSON.parse(res.content) as { boxes?: Record<string, unknown>[] };
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

// ---- VLM MASKING arm (head-to-head vs SAM) -------------------------------------
// Ask the Director vision model to return a TIGHT POLYGON outline per control (the
// "add masking to the VLM/slot pass" approach). This is the literal VLM-does-the-
// masking contender; it tests whether a VLM can produce a usable silhouette vs
// SAM's per-pixel mask.
export interface SlotPoly { bind: string; points: [number, number][] }
const MASK_SYS =
  "You are a precise UI control SILHOUETTE tracer for skeuomorphic music-player images. Given the image " +
  "and a list of EXPECTED controls (bind + kind), return STRICT JSON " +
  "{\"polys\":[{\"bind\":\"<bind>\",\"points\":[[x,y],...]}]}. Each polygon is the TIGHT outline of that " +
  "control's visible silhouette, 8-20 points, NORMALIZED 0..1 of the WHOLE image, clockwise. Trace the actual " +
  "painted shape (a round knob/button = a circle of points; a vertical fader/toggle = its stick+cap outline; a " +
  "horizontal slider = its groove rectangle). Identify by icon: play ▶, prev ◀◀, next ▶▶, stop ■, knob = round " +
  "dial, slider-v = vertical fader, toggle = small switch. OMIT controls you cannot find. Return ONLY the JSON.";
export async function extractMasks(
  keys: DirectorKeys,
  image: string,
  controls: SlotControl[],
): Promise<SlotPoly[]> {
  if (!controls.length) return [];
  const list = controls.map((c) => `${c.bind} (${c.kind}${c.label ? `, "${c.label}"` : ""})`).join("; ");
  try {
    const imagePart = await toImagePart(image);
    const res = await directorChat(keys, {
      system: MASK_SYS,
      user: `Trace tight silhouette polygons for these controls: ${list}`,
      imageParts: [imagePart],
      maxTokens: 4000,
    });
    if (!res) return [];
    const parsed = JSON.parse(res.content) as { polys?: Record<string, unknown>[] };
    const raw = Array.isArray(parsed.polys) ? parsed.polys : [];
    const out: SlotPoly[] = [];
    for (const p of raw) {
      const bind = typeof p.bind === "string" ? p.bind : "";
      const pts = Array.isArray(p.points) ? p.points : [];
      const points: [number, number][] = [];
      for (const pt of pts) {
        if (Array.isArray(pt) && pt.length >= 2 && Number.isFinite(Number(pt[0])) && Number.isFinite(Number(pt[1])))
          points.push([clamp01(Number(pt[0])), clamp01(Number(pt[1]))]);
      }
      if (bind && points.length >= 3) out.push({ bind, points });
    }
    return out;
  } catch (e) {
    console.error("[extractMasks] failed:", e instanceof Error ? e.message : e);
    return [];
  }
}
