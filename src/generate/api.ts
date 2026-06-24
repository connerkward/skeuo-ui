// Shared request/response contract for POST /api/generate, used by the
// frontend Create panel, the CF Pages Function, and the local Node dev server.
// TYPES ONLY — kept DOM-free so the Node dev-server plugin and the CF Function
// (compiled without the DOM lib) can import it. The client fetch helper lives in
// postGenerate.ts (it needs `window` via apiUrl).
import type { Template, Region } from "../template/schema";
import type { LayoutVariant } from "./layouts";
import type { DonorStyle, ModelId } from "./pipeline";
import type { BlueprintLayout } from "./blueprint";

export interface GenerateRequest {
  prompt: string;             // silhouette brief, e.g. "a fanged anglerfish jaw"
  style?: DonorStyle;         // OPTIONAL donor; when absent, the Director derives material from the prompt
  variant: LayoutVariant;     // radial | capsule | minimal (layout-first only)
  refImage?: string;          // optional reference-style image as a data: URL
  model?: ModelId;            // image edit endpoint (default nano-banana-pro)
  envelope?: boolean;         // run the AI envelope pass first (default true)
  envelopeImage?: string;     // optional user-uploaded body envelope PNG as a data: URL (skips the AI envelope pass)
  regions?: Region[];         // custom layout authored in the wizard (else the variant preset)
  avoidFonts?: string[];      // recently-used logomark fonts the Director should NOT reuse (diversity)
}

// Live progress events streamed (NDJSON) ahead of the final GenerateResponse so the
// loading UI can show the user's ACTUAL skin forming — their blueprint, then the real
// grown body, then the real painted skin — as each pipeline pass completes server-side.
export type GenStage = "blueprint" | "envelope" | "paint";
export interface GenStageEvent { stage: GenStage; url: string }

export interface GeneratePending { status: "pending"; jobId: string }
export interface GenerateDone {
  status: "done";
  id: string;
  style: DonorStyle;
  variant: LayoutVariant;
  model: ModelId;
  font?: string;              // logomark title font (Director pick; one of LOGO_FONTS)
  name?: string;              // concise skin title (Director)
  blurb?: string;             // one-line description (Director)
  template: Template;
  frameUrl: string;           // public URL or data: URL of the CUT device frame (background removed)
  // LAYOUT: devFrac (device region = top devFrac of the combined paint) + per-control
  // rects (normalized to the DEVICE region) + sprite-strip cells. The browser cuts the
  // device + each control sprite by this; the app sizes each sprite to its OWN template
  // region rect (so the bigger play region → bigger play button). See blueprint.ts.
  layout: BlueprintLayout;
  // SPRITES: true once per-skin control sprites exist at
  // /api/asset/skins/<id>/sprites/<bind>.png. Set by the browser after it cuts +
  // uploads them in the finalize step; the render team reads this to decide whether
  // to use per-skin sprites or fall back to the shared donor sprites.
  sprites?: boolean;
  // SINGLE-PASS CUTOUT: the combined paint must be background-removed (device region)
  // AND each control sprite cut from its cell — pure-JS CPU that trips the Pages
  // Function CPU ceiling → CF 1102. So the Worker SKIPS the cutout, persists the RAW
  // combined paint, and the browser does the cutout + uploads frame.png (+ each
  // sprites/<bind>.png) back to R2 (no-CPU writes). `frameUrl` points at where the cut
  // device frame WILL live (skins/<id>/frame.png) and `paintUrl` is the raw combined
  // paint. needsCutout is always set in the single-pass pipeline. See
  // functions/api/cutout.ts + functions/api/finalize/[id].ts.
  needsCutout?: boolean;
  paintUrl?: string;          // raw combined paint PNG (public URL or data: URL) — present when needsCutout
  keyColor?: [number, number, number]; // backdrop the device was painted on — the colour the client cutout keys out (absent ⇒ white)
  timingMs: { envelope: number; paint: number; total: number };
}
export interface GenerateError { status: "error"; error: string }
export type GenerateResponse = GeneratePending | GenerateDone | GenerateError;
