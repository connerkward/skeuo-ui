// Shared request/response contract for POST /api/generate, used by the
// frontend Create panel, the CF Pages Function, and the local Node dev server.
import type { Template, Region } from "../template/schema";
import type { LayoutVariant } from "./layouts";
import type { DonorStyle, ModelId } from "./pipeline";

export interface GenerateRequest {
  prompt: string;             // silhouette brief, e.g. "a fanged anglerfish jaw"
  style: DonorStyle;          // donor material: frog | biomech | winamp | wmp | halo
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
