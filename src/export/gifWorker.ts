/// <reference lib="webworker" />
import { GIFEncoder, quantize } from "gifenc";

// Off-main-thread GIF encoder. The main thread captures frames (still on-main —
// that's DOM rasterization, can't leave the main thread) and ships the raw RGBA
// buffers here; quantize + dithered palette mapping + gifenc all run in this
// worker, so the page stays responsive through the entire ENCODE phase.
//
// QUALITY: gifenc@1.0.3 ships NO dithering (its applyPalette only does a flat
// nearest-color snap, which is exactly what bands smooth gradients into ugly
// stair-steps at 256 colors). So we do our own Floyd–Steinberg error-diffusion
// dither against the shared palette here. Combined with the larger capture width
// (see exportGif TARGET_W) this removes the visible banding the flat snap left.

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

type Palette = number[][]; // array of [r,g,b] (gifenc rgb565 palette)

// Nearest palette index for an (r,g,b) by euclidean distance, memoized on a
// coarse 5-bit-per-channel key so the per-pixel cost stays low.
function makeNearest(palette: Palette) {
  const cache = new Int16Array(32768).fill(-1); // 32^3 buckets
  return (r: number, g: number, b: number): number => {
    const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
    const hit = cache[key];
    if (hit >= 0) return hit;
    let best = 0;
    let bestD = Infinity;
    for (let i = 0; i < palette.length; i++) {
      const p = palette[i];
      const dr = r - p[0], dg = g - p[1], db = b - p[2];
      const d = dr * dr + dg * dg + db * db;
      if (d < bestD) { bestD = d; best = i; if (d === 0) break; }
    }
    cache[key] = best;
    return best;
  };
}

// Floyd–Steinberg error-diffusion: map RGBA → palette indices while pushing the
// quantization error to neighbouring pixels, turning hard colour steps into a
// fine stipple the eye reads as a smooth gradient.
function ditherToIndices(rgba: Uint8Array, width: number, height: number, palette: Palette): Uint8Array {
  const nearest = makeNearest(palette);
  const out = new Uint8Array(width * height);
  // working error buffers (current + next row), in float so error accumulates
  const errR = new Float32Array(width + 2);
  const errG = new Float32Array(width + 2);
  const errB = new Float32Array(width + 2);
  const nextR = new Float32Array(width + 2);
  const nextG = new Float32Array(width + 2);
  const nextB = new Float32Array(width + 2);
  for (let y = 0; y < height; y++) {
    nextR.fill(0); nextG.fill(0); nextB.fill(0);
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const ex = x + 1; // err buffers are padded by 1 on each side
      const r = clamp8(rgba[i] + errR[ex]);
      const g = clamp8(rgba[i + 1] + errG[ex]);
      const b = clamp8(rgba[i + 2] + errB[ex]);
      const idx = nearest(r, g, b);
      out[y * width + x] = idx;
      const p = palette[idx];
      const dr = r - p[0], dg = g - p[1], db = b - p[2];
      // distribute error: 7/16 right, 3/16 down-left, 5/16 down, 1/16 down-right
      errR[ex + 1] += (dr * 7) / 16; errG[ex + 1] += (dg * 7) / 16; errB[ex + 1] += (db * 7) / 16;
      nextR[ex - 1] += (dr * 3) / 16; nextG[ex - 1] += (dg * 3) / 16; nextB[ex - 1] += (db * 3) / 16;
      nextR[ex] += (dr * 5) / 16; nextG[ex] += (dg * 5) / 16; nextB[ex] += (db * 5) / 16;
      nextR[ex + 1] += dr / 16; nextG[ex + 1] += dg / 16; nextB[ex + 1] += db / 16;
    }
    errR.set(nextR); errG.set(nextG); errB.set(nextB);
  }
  return out;
}

function clamp8(v: number): number { return v < 0 ? 0 : v > 255 ? 255 : v; }

self.onmessage = (e: MessageEvent<EncodeMsg>) => {
  const msg = e.data;
  if (msg.type !== "encode") return;
  const { width, height, delay, frames } = msg;

  // ONE shared palette for the whole animation (removes inter-frame flicker).
  // Build it from a concatenation of a FEW frames (early/mid/late) so colours
  // that only appear during the motion (e.g. the swinging spectrum) still get
  // palette slots — quantizing one frame alone misses them and bands them.
  const sampleIdxs = [0, Math.floor(frames.length / 2), frames.length - 1]
    .filter((v, i, a) => a.indexOf(v) === i && frames[v]);
  let sampleLen = 0;
  for (const s of sampleIdxs) sampleLen += frames[s].byteLength;
  const sample = new Uint8Array(sampleLen);
  { let off = 0; for (const s of sampleIdxs) { const u = new Uint8Array(frames[s]); sample.set(u, off); off += u.length; } }
  const palette = quantize(sample, 256) as Palette;

  const enc = GIFEncoder();
  for (let i = 0; i < frames.length; i++) {
    const rgba = new Uint8Array(frames[i]);
    const index = ditherToIndices(rgba, width, height, palette);
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
