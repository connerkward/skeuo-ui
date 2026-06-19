// Shared request/response contract for POST /api/generate, used by the
// frontend Create panel, the CF Pages Function, and the local Node dev server.
import type { Template, Region } from "../template/schema";
import type { LayoutVariant } from "./layouts";
import type { DonorStyle, ModelId } from "./pipeline";

export interface GenerateRequest {
  prompt: string;             // silhouette brief, e.g. "a fanged anglerfish jaw"
  style?: DonorStyle;         // OPTIONAL donor; when absent, the Director derives material from the prompt
  variant: LayoutVariant;     // radial | capsule | minimal (layout-first only)
  refImage?: string;          // optional reference-style image as a data: URL
  model?: ModelId;            // image edit endpoint (default nano-banana-pro)
  envelope?: boolean;         // run the AI envelope pass first (default true)
  envelopeImage?: string;     // optional user-uploaded body envelope PNG as a data: URL (skips the AI envelope pass)
  regions?: Region[];         // custom layout authored in the wizard (else the variant preset)
}

export interface GeneratePending { status: "pending"; jobId: string }
export interface GenerateDone {
  status: "done";
  id: string;
  style: DonorStyle;
  variant: LayoutVariant;
  model: ModelId;
  template: Template;
  frameUrl: string;           // public URL or data: URL
  timingMs: { envelope: number; paint: number; total: number };
}
export interface GenerateError { status: "error"; error: string }
export type GenerateResponse = GeneratePending | GenerateDone | GenerateError;

// POST /api/generate and parse the JSON contract DEFENSIVELY. The endpoint can
// return HTML instead of JSON in real deployments — the SPA fallback index.html
// when the API isn't mounted (a static `dist/` / `vite preview` build with no
// Functions runtime), or a Cloudflare timeout/error page when a 30-90s fal paint
// exceeds the edge execution window. Blindly `await r.json()` on that HTML throws
// the opaque "Unexpected token '<', "<!DOCTYPE "... is not valid JSON" the user
// saw. Read as text first, check status + content-type, and surface a readable
// GenerateError instead. Same path for web (desktop + mobile browser) and the
// iOS/desktop Tauri webview, since all three call this one helper.
export async function postGenerate(req: GenerateRequest): Promise<GenerateResponse> {
  let r: Response;
  try {
    r = await fetch("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
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
