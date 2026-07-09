// Shared, DOM-free contract for the live pipeline STEP VISUALIZER — the panel that
// animates through the real generation stages while a template is sent to fal, so
// the user can watch each pass happen (blueprint → paint → cut → detect → align →
// fit → correct) like observing an agent work.
//
// The stage names + blurbs mirror the REAL shipping pipeline vocabulary:
//   blueprint  combinedBlueprint() — guide + colour-keyed sockets (blueprint.ts)
//   paint      fal image-edit joint paint (pipeline.generateSkin, streamed onStage)
//   cut        BiRefNet matte + split of body/strip (cutoutClient.serverCutout; biref12)
//   detect     locate each control — circle-fit / rrect-fit (segmentStripByComponents; extract12)
//   align      seat parts onto their sockets — travel/seat (maskAlign; extract12 [travel])
//   fit        rotate + resize each sprite to its slot ([angle]/[rrect-fit]/[state-align])
//   correct    gates + repairs — leak / emptiness ([leak gate] / [emptiness gate] / [GATE])
//
// The visualizer is driven by REAL events: server-streamed GenStageEvents for
// blueprint/paint (server/devApiPlugin.ts, functions/api/generate.ts) and client
// StepEvents emitted at the real await-points inside finishCutoutFull. It never
// runs on a fake fixed timer for a real generation.

export type StageId =
  | "blueprint" | "paint" | "cut" | "detect" | "align" | "fit" | "correct";

export type StepStatus = "pending" | "running" | "done" | "failed";

// One live event. `artifact` is a URL or data: URL of the ACTUAL image for that
// step (blueprint, painted skin, matted strip, a cut sprite) when one exists.
export interface StepEvent {
  stage: StageId;
  status: StepStatus;
  artifact?: string;
  note?: string;
}

export interface StepState {
  status: StepStatus;
  artifact?: string;
  note?: string;
}
export type StepsState = Record<StageId, StepState>;

export const STAGES: { id: StageId; label: string; blurb: string; glyph: string }[] = [
  { id: "blueprint", label: "Blueprint", blurb: "Drawing the guide + colour-keyed sockets", glyph: "▦" },
  { id: "paint",     label: "Paint",     blurb: "fal image-edit paints the skin",           glyph: "✦" },
  { id: "cut",       label: "Cut",       blurb: "BiRefNet mattes the body + control strip",  glyph: "✂" },
  { id: "detect",    label: "Detect",    blurb: "Locating each control (circle / rect fit)", glyph: "⊙" },
  { id: "align",     label: "Align",     blurb: "Seating parts onto their sockets",          glyph: "⌖" },
  { id: "fit",       label: "Fit",       blurb: "Rotate + resize sprites to each slot",      glyph: "⤢" },
  { id: "correct",   label: "Correct",   blurb: "Gates + repairs (leak / emptiness)",        glyph: "✚" },
];

export const STAGE_ORDER: StageId[] = STAGES.map((s) => s.id);

export function initSteps(): StepsState {
  return Object.fromEntries(
    STAGE_ORDER.map((id) => [id, { status: "pending" } as StepState]),
  ) as StepsState;
}

// Merge one event, auto-completing any EARLIER pending/running stage so a dropped
// event never leaves the bar stalled behind a stage that already finished.
export function applyStepEvent(prev: StepsState, ev: StepEvent): StepsState {
  const idx = STAGE_ORDER.indexOf(ev.stage);
  const next: StepsState = { ...prev };
  if (ev.status === "running" || ev.status === "done") {
    for (let i = 0; i < idx; i++) {
      const id = STAGE_ORDER[i];
      if (next[id].status === "pending" || next[id].status === "running") {
        next[id] = { ...next[id], status: "done" };
      }
    }
  }
  next[ev.stage] = {
    status: ev.status,
    artifact: ev.artifact ?? next[ev.stage].artifact,
    note: ev.note ?? next[ev.stage].note,
  };
  return next;
}

// Mark every stage not already failed as done — used when the flow finishes (or a
// stage produced no event, e.g. the legacy data-URL cutout path) so the visualizer
// resolves cleanly to all-checks.
export function completeSteps(prev: StepsState): StepsState {
  const next: StepsState = { ...prev };
  for (const id of STAGE_ORDER) {
    if (next[id].status !== "failed") next[id] = { ...next[id], status: "done" };
  }
  return next;
}

// Fraction of stages resolved (done|failed) — drives the header progress bar.
export function stepsProgress(s: StepsState): number {
  const done = STAGE_ORDER.filter((id) => s[id].status === "done" || s[id].status === "failed").length;
  return done / STAGE_ORDER.length;
}
