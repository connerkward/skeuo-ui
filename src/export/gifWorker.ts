/// <reference lib="webworker" />
import { GIFEncoder, quantize, applyPalette } from "gifenc";

// Off-main-thread GIF encoder. The main thread captures frames (still on-main —
// that's DOM rasterization, can't leave the main thread) and ships the raw RGBA
// buffers here; quantize + applyPalette + gifenc all run in this worker, so the
// page stays responsive through the entire ENCODE phase (previously ~300ms+ of
// blocking main-thread quantize/encode).

interface EncodeMsg {
  type: "encode";
  width: number;
  height: number;
  delay: number;
  // RGBA bytes per frame, transferred (zero-copy) from the main thread
  frames: ArrayBuffer[];
}
interface ProgressMsg { type: "progress"; current: number; total: number }
interface DoneMsg { type: "done"; gif: ArrayBuffer }

self.onmessage = (e: MessageEvent<EncodeMsg>) => {
  const msg = e.data;
  if (msg.type !== "encode") return;
  const { width, height, delay, frames } = msg;

  // ONE shared palette (from a mid frame) — removes inter-frame flicker and is
  // far cheaper than quantizing every frame.
  const mid = frames[Math.floor(frames.length / 2)] ?? frames[0];
  const palette = quantize(new Uint8Array(mid), 256);

  const enc = GIFEncoder();
  for (let i = 0; i < frames.length; i++) {
    const rgba = new Uint8Array(frames[i]);
    const index = applyPalette(rgba, palette);
    enc.writeFrame(index, width, height, { palette, delay });
    (self as unknown as Worker).postMessage({ type: "progress", current: i + 1, total: frames.length } as ProgressMsg);
  }
  enc.finish();

  // copy into a standalone ArrayBuffer so it can be transferred back cleanly
  const view = enc.bytesView();
  const out = new Uint8Array(view.length);
  out.set(view);
  (self as unknown as Worker).postMessage({ type: "done", gif: out.buffer } as DoneMsg, [out.buffer]);
};

export type { EncodeMsg, ProgressMsg, DoneMsg };
