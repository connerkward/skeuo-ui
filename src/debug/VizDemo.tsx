import { useEffect, useState } from "react";
import { PipelineVisualizer } from "../generate/PipelineVisualizer";
import { initSteps, applyStepEvent, type StepsState, type StepEvent, STAGE_ORDER } from "../generate/pipelineViz";

// DEV-ONLY harness (?vizdemo) to preview + screenshot the REAL PipelineVisualizer
// component mid-animation without spending a paid fal generation. It drives the exact
// same component the wizard uses, via the exact same applyStepEvent reducer — only the
// events are scripted (with placeholder artifacts) instead of coming off the wire.
// `?vizdemo=frozen` steps to a fixed mid-run state (for a deterministic screenshot);
// otherwise it plays through on a realistic schedule and loops.

// a tiny labelled gradient thumbnail so the fade-in / scan animation has something to show
function thumb(label: string, hue: number): string {
  const c = document.createElement("canvas");
  c.width = 120; c.height = 120;
  const ctx = c.getContext("2d")!;
  const g = ctx.createLinearGradient(0, 0, 120, 120);
  g.addColorStop(0, `hsl(${hue} 60% 24%)`);
  g.addColorStop(1, `hsl(${(hue + 40) % 360} 65% 42%)`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, 120, 120);
  ctx.fillStyle = "rgba(255,255,255,.85)"; ctx.font = "600 20px system-ui"; ctx.textAlign = "center";
  ctx.fillText(label, 60, 66);
  return c.toDataURL();
}

// scripted, real-SHAPED event stream (mirrors what the server + finishCutoutFull emit)
const SCRIPT: { at: number; ev: StepEvent }[] = [
  { at: 0,    ev: { stage: "blueprint", status: "running" } },
  { at: 900,  ev: { stage: "blueprint", status: "done", artifact: thumb("guide", 210), note: "6 sockets keyed" } },
  { at: 900,  ev: { stage: "paint", status: "running" } },
  { at: 3200, ev: { stage: "paint", status: "done", artifact: thumb("skin", 30), note: "nano-banana-pro" } },
  { at: 3200, ev: { stage: "cut", status: "running", artifact: thumb("device", 30), note: "matting device" } },
  { at: 4600, ev: { stage: "cut", status: "done", artifact: thumb("strip", 140), note: "body + strip matted" } },
  { at: 4600, ev: { stage: "detect", status: "running" } },
  { at: 5600, ev: { stage: "detect", status: "done", artifact: thumb("blobs", 140), note: "6/6 controls located" } },
  { at: 5600, ev: { stage: "align", status: "done", note: "6 sockets (blueprint-seated)" } },
  { at: 5600, ev: { stage: "fit", status: "running" } },
  { at: 7000, ev: { stage: "fit", status: "done", artifact: thumb("play", 120), note: "6 sprites sized to slots" } },
  { at: 7000, ev: { stage: "correct", status: "done", note: "no repair needed" } },
];

// how far into the script to freeze for a deterministic screenshot (mid-run: cut done,
// detect running, so the pulse + scan animation is visible)
const FROZEN_AT = 5000;

export default function VizDemo() {
  const frozen = new URLSearchParams(location.search).get("vizdemo") === "frozen";
  const [steps, setSteps] = useState<StepsState>(initSteps);

  useEffect(() => {
    if (frozen) {
      let s = initSteps();
      for (const { at, ev } of SCRIPT) if (at <= FROZEN_AT) s = applyStepEvent(s, ev);
      // ensure at least the running/pending mix the frozen instant implies
      setSteps(s);
      return;
    }
    const timers = SCRIPT.map(({ at, ev }) => setTimeout(() => setSteps((s) => applyStepEvent(s, ev)), at));
    // loop after a pause
    const loop = setTimeout(() => setSteps(initSteps()), SCRIPT[SCRIPT.length - 1].at + 3500);
    return () => { timers.forEach(clearTimeout); clearTimeout(loop); };
  }, [frozen]);

  // restart the play-through when it resets to all-pending (simple loop)
  useEffect(() => {
    if (frozen) return;
    const allPending = STAGE_ORDER.every((id) => steps[id].status === "pending");
    if (!allPending) return;
    const timers = SCRIPT.map(({ at, ev }) => setTimeout(() => setSteps((s) => applyStepEvent(s, ev)), at));
    return () => timers.forEach(clearTimeout);
  }, [steps, frozen]);

  return (
    <div style={{ position: "fixed", inset: 0, background: "#08080b", color: "#888", font: "13px system-ui" }}>
      <div style={{ padding: 16 }}>
        <b style={{ color: "#ccc" }}>PipelineVisualizer demo</b> — scripted real-shaped events into the shipping component.
        {" "}<a style={{ color: "#4a8aff" }} href="?vizdemo=frozen">?vizdemo=frozen</a> for a fixed mid-run state.
      </div>
      <PipelineVisualizer steps={steps} open onClose={() => { /* demo: no-op */ }} modelLabel="Nano Banana Pro" current="a cute Y2K virtual-pet egg" />
    </div>
  );
}
