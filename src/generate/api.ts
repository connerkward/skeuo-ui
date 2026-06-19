// Shared request/response contract for POST /api/generate, used by the
// frontend Create panel, the CF Pages Function, and the local Node dev server.
// TYPES ONLY — kept DOM-free so the Node dev-server plugin and the CF Function
// (compiled without the DOM lib) can import it. The client fetch helper lives in
// postGenerate.ts (it needs `window` via apiUrl).
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
  frameUrl: string;           // public URL or data: URL of the CUT frame (white keyed transparent)
  // CLIENT-SIDE CUTOUT (CF Worker path): the alpha cutout is ~2s of pure-JS CPU
  // (UPNG decode/encode + connected-components/flood-fill) that trips the Pages
  // Function CPU ceiling → CF 1102. So the Worker SKIPS the cutout, persists the
  // RAW paint, and the browser does the cutout + uploads the finished frame.png
  // back to R2 (a no-CPU write). When `needsCutout` is set, `frameUrl` points at
  // where the cut frame WILL live (skins/<id>/frame.png) and `paintUrl` is the raw
  // paint to cut. Runtimes with no CPU limit (the Node dev server) cut server-side
  // and leave `needsCutout` falsy. See functions/api/finalize/[id].ts.
  needsCutout?: boolean;
  paintUrl?: string;          // raw paint PNG (public URL or data: URL) — present when needsCutout
  timingMs: { envelope: number; paint: number; total: number };
}
export interface GenerateError { status: "error"; error: string }
export type GenerateResponse = GeneratePending | GenerateDone | GenerateError;
