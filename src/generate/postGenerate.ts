// Client-only entry to POST /api/generate. Kept SEPARATE from api.ts (the shared
// request/response contract) because this file imports platform.ts (apiUrl → uses
// `window`), and api.ts is transitively imported by the Node dev-server plugin and
// the CF Function — both compiled WITHOUT the DOM lib. Keeping the contract types
// DOM-free and the fetch helper here avoids dragging `window` into those builds.
import type { GenerateRequest, GenerateResponse } from "./api";
import { apiUrl } from "../platform";

// POST /api/generate and parse the JSON contract DEFENSIVELY. The endpoint can
// return HTML instead of JSON in real deployments — the SPA fallback index.html
// when the API isn't mounted (a static `dist/` / `vite preview` build with no
// Functions runtime), or a Cloudflare timeout/error page when a 30-90s fal paint
// exceeds the edge execution window. Blindly `await r.json()` on that HTML throws
// the opaque "Unexpected token '<', "<!DOCTYPE "... is not valid JSON" the user
// saw. Read as text first, check status + content-type, and surface a readable
// GenerateError instead. apiUrl() makes the path absolute under the native shells
// (tauri:// origin) so the call reaches skeuo.fm; on the web it stays same-origin.
// Recently-used logomark fonts from the persisted skins (skeuo:skins), newest
// first, deduped — handed to the Director as an avoid-list so it doesn't keep
// picking the same families. Best-effort: any parse/storage failure → none.
function recentFonts(limit = 8): string[] {
  try {
    const raw = localStorage.getItem("skeuo:skins");
    if (!raw) return [];
    const skins = JSON.parse(raw) as Array<{ font?: string }>;
    const fonts = skins.map((s) => s.font).filter((f): f is string => !!f).reverse();
    return [...new Set(fonts)].slice(0, limit);
  } catch { return []; }
}

export async function postGenerate(req: GenerateRequest): Promise<GenerateResponse> {
  // attach the recent-fonts avoid-list unless the caller set one explicitly
  const body = req.avoidFonts ? req : { ...req, avoidFonts: recentFonts() };
  let r: Response;
  try {
    r = await fetch(apiUrl("/api/generate"), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch (e) {
    return { status: "error", error: `network error: ${e instanceof Error ? e.message : String(e)}` };
  }
  const ct = r.headers.get("content-type") ?? "";
  const text = await r.text();
  if (!ct.includes("application/json")) {
    const hint =
      r.status === 404 ? " — /api/generate not found (static build with no API?)" :
      r.status >= 500 || r.status === 408 ? " — the generate endpoint errored or timed out" :
      "";
    return { status: "error", error: `server returned ${r.status || "no status"} (${ct || "non-JSON"})${hint}` };
  }
  try {
    return JSON.parse(text) as GenerateResponse;
  } catch {
    return { status: "error", error: `malformed JSON from /api/generate (HTTP ${r.status})` };
  }
}
