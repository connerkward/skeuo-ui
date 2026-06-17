import { domToCanvas } from "modern-screenshot";
import { GIFEncoder, quantize, applyPalette } from "gifenc";

// ── tuning ───────────────────────────────────────────────────────────────────
const DURATION_MS = 2500;       // ~2.5s of motion
const FPS = 10;                  // ~10 fps (fewer heavy DOM rasters → less main-thread jank)
const FRAME_COUNT = Math.round((DURATION_MS / 1000) * FPS); // ~25
const FRAME_DELAY = Math.round(1000 / FPS);                 // ~100ms
const TARGET_W = 400;            // downscale width; height follows the player aspect
const PAGE_BG = "#0d0d0f";       // matches the dark stage so the transparent player isn't a weird matte

export interface ExportProgress {
  // 0..1 over the whole job (capture phase then encode phase)
  phase: "capturing" | "encoding" | "done";
  pct: number;
}

const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

// Load the watermark logo once. Returns null on any failure (we still emit a GIF).
let logoPromise: Promise<HTMLImageElement | null> | null = null;
function loadLogo(): Promise<HTMLImageElement | null> {
  if (!logoPromise) {
    logoPromise = new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = "/favicon.svg";
    });
  }
  return logoPromise;
}

// Draw the skeuo watermark: a rounded dark backing pill in the bottom-right with
// the chrome-knob logomark and the "skeuo" wordmark beside it. Sized to the
// output canvas so it stays legible at the GIF's small dimensions.
function drawWatermark(ctx: CanvasRenderingContext2D, w: number, h: number, logo: HTMLImageElement | null) {
  const pad = Math.round(w * 0.022);
  const logoSize = Math.round(w * 0.09);          // ~36px at 400w
  const fontSize = Math.round(logoSize * 0.62);
  ctx.font = `600 ${fontSize}px -apple-system, "Segoe UI", system-ui, sans-serif`;
  const word = "skeuo";
  const textW = ctx.measureText(word).width;
  const gap = Math.round(logoSize * 0.28);
  const innerW = logoSize + gap + textW;
  const pillH = logoSize + pad;
  const pillW = innerW + pad * 2;
  const x = w - pillW - pad;
  const y = h - pillH - pad;
  const r = pillH / 2;

  // backing pill
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + pillW, y, x + pillW, y + pillH, r);
  ctx.arcTo(x + pillW, y + pillH, x, y + pillH, r);
  ctx.arcTo(x, y + pillH, x, y, r);
  ctx.arcTo(x, y, x + pillW, y, r);
  ctx.closePath();
  ctx.fillStyle = "rgba(8,9,11,0.62)";
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(255,255,255,0.10)";
  ctx.stroke();
  ctx.restore();

  const cy = y + pillH / 2;
  const lx = x + pad;
  if (logo) {
    ctx.drawImage(logo, lx, cy - logoSize / 2, logoSize, logoSize);
  }
  ctx.font = `600 ${fontSize}px -apple-system, "Segoe UI", system-ui, sans-serif`;
  ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(240,242,246,0.95)";
  ctx.fillText(word, lx + logoSize + gap, cy + 1);
}

// Capture the live player element to a downscaled canvas, on a dark bg, with the
// watermark composited in. Returns ImageData ready for the GIF encoder.
async function captureFrame(
  el: HTMLElement,
  outW: number,
  outH: number,
  logo: HTMLImageElement | null,
): Promise<ImageData> {
  // rasterize the DOM, capping the raster scale at the output size so we never
  // pay to render larger than the GIF needs (cheaper per-frame, less main-thread jank)
  const snap = await domToCanvas(el, {
    width: el.offsetWidth, height: el.offsetHeight,
    scale: Math.min(1, outW / (el.offsetWidth || outW)),
  });

  const out = document.createElement("canvas");
  out.width = outW;
  out.height = outH;
  const ctx = out.getContext("2d", { willReadFrequently: true })!;
  ctx.fillStyle = PAGE_BG;
  ctx.fillRect(0, 0, outW, outH);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(snap, 0, 0, outW, outH);
  drawWatermark(ctx, outW, outH, logo);

  return ctx.getImageData(0, 0, outW, outH);
}

export interface ExportResult {
  blob: Blob;
  width: number;
  height: number;
  frames: number;
  // sample ImageData (early/mid/late) for verification
  samples: ImageData[];
}

// Record the given element as an animated GIF. onProgress fires through capture
// then encode. Returns the gif Blob plus sample frames for verification.
export async function recordPlayerGif(
  el: HTMLElement,
  onProgress?: (p: ExportProgress) => void,
): Promise<ExportResult> {
  const logo = await loadLogo();

  const aspect = el.offsetHeight / el.offsetWidth || 1536 / 1024;
  const outW = TARGET_W;
  const outH = Math.round(TARGET_W * aspect);

  // ── capture phase: snapshot across real animation time ──────────────────────
  const frames: ImageData[] = [];
  const interval = DURATION_MS / FRAME_COUNT;
  const t0 = performance.now();
  for (let i = 0; i < FRAME_COUNT; i++) {
    const target = t0 + i * interval;
    // let the live animation advance to this frame's wall-clock target
    while (performance.now() < target) await nextFrame();
    frames.push(await captureFrame(el, outW, outH, logo));
    onProgress?.({ phase: "capturing", pct: ((i + 1) / FRAME_COUNT) * 0.7 });
  }

  // ── encode phase ────────────────────────────────────────────────────────────
  // Quantize ONE shared palette (from a mid frame) instead of per-frame — the
  // per-frame quantize() was the main main-thread hog. Also yields every frame so
  // the page stays responsive, and a shared palette removes inter-frame flicker.
  const enc = GIFEncoder();
  const mid0 = frames[Math.floor(frames.length / 2)] ?? frames[0];
  const palette = quantize(mid0.data, 256);
  for (let i = 0; i < frames.length; i++) {
    const { data, width, height } = frames[i];
    const index = applyPalette(data, palette);
    enc.writeFrame(index, width, height, { palette, delay: FRAME_DELAY });
    onProgress?.({ phase: "encoding", pct: 0.7 + ((i + 1) / frames.length) * 0.3 });
    await nextFrame(); // yield every frame so the UI doesn't freeze
  }
  enc.finish();

  // copy into a fresh ArrayBuffer-backed view (gifenc's view may be over a
  // pooled buffer; the copy also satisfies the Blob/ArrayBuffer typing)
  const bytes = Uint8Array.from(enc.bytesView());
  const blob = new Blob([bytes], { type: "image/gif" });
  onProgress?.({ phase: "done", pct: 1 });

  const mid = Math.floor(frames.length / 2);
  const samples = [frames[0], frames[mid], frames[frames.length - 1]].filter(Boolean);
  return { blob, width: outW, height: outH, frames: frames.length, samples };
}

// Trigger a browser download of the gif blob.
export function downloadGif(blob: Blob, skinId: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `skeuo-${skinId}.gif`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
