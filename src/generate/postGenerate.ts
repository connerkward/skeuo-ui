// Client-only entry to POST /api/generate. Kept SEPARATE from api.ts (the shared
// request/response contract) because this file imports platform.ts (apiUrl → uses
// `window`), and api.ts is transitively imported by the Node dev-server plugin and
// the CF Function — both compiled WITHOUT the DOM lib. Keeping the contract types
// DOM-free and the fetch helper here avoids dragging `window` into those builds.
import type { GenerateRequest, GenerateResponse, GenStageEvent } from "./api";
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

// onStage fires for each {stage,url} progress line the server streams ahead of the
// final result, so the caller can preview the user's actual skin forming.
export async function postGenerate(
  req: GenerateRequest,
  onStage?: (ev: GenStageEvent) => void,
): Promise<GenerateResponse> {
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
  // SPA-fallback / error pages come back as HTML — surface a readable error instead
  // of trying to parse "<!DOCTYPE …" as the contract.
  if (ct.includes("text/html") || !r.body) {
    const hint =
      r.status === 404 ? " — /api/generate not found (static build with no API?)" :
      r.status >= 500 || r.status === 408 ? " — the generate endpoint errored or timed out" :
      "";
    return { status: "error", error: `server returned ${r.status || "no status"} (${ct || "non-JSON"})${hint}` };
  }
  // Read the NDJSON stream line-by-line. Lines with a `stage` are live progress
  // events; the line carrying `status` (no `stage`) is the final GenerateResponse.
  // A single non-streamed JSON (e.g. the spend-cap 429) is just one line → final.
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let final: GenerateResponse | null = null;
  const handleLine = (line: string) => {
    const s = line.trim();
    if (!s) return;
    let obj: unknown;
    try { obj = JSON.parse(s); } catch { return; }
    if (obj && typeof obj === "object" && "stage" in obj && !("status" in obj)) {
      onStage?.(obj as GenStageEvent);
    } else {
      final = obj as GenerateResponse;
    }
  };
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (value) {
        buf += decoder.decode(value, { stream: true });
        let nl: number;
        while ((nl = buf.indexOf("\n")) >= 0) { handleLine(buf.slice(0, nl)); buf = buf.slice(nl + 1); }
      }
      if (done) break;
    }
    handleLine(buf);   // trailing line without a newline
  } catch (e) {
    return { status: "error", error: `stream read failed: ${e instanceof Error ? e.message : String(e)}` };
  }
  return final ?? { status: "error", error: `no result from /api/generate (HTTP ${r.status})` };
}
