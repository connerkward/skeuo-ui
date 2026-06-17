import { domToCanvas, createContext, destroyContext, type Context } from "modern-screenshot";
import type { DoneMsg, ProgressMsg } from "./gifWorker";

// ── tuning ───────────────────────────────────────────────────────────────────
const DURATION_MS = 2500;       // ~2.5s of motion
const FPS = 10;                  // ~10 fps (fewer heavy DOM rasters → less main-thread jank)
const FRAME_COUNT = Math.round((DURATION_MS / 1000) * FPS); // ~25
const FRAME_DELAY = Math.round(1000 / FPS);                 // ~100ms
const TARGET_W = 640;            // GIF downscale width; height follows the player aspect.
                                 // Up from 400 — bigger source pixels survive the 256-color quantize
                                 // far better, and dithering (see gifWorker) kills the residual banding.
const PNG_W = 1080;              // SHARE artifact: a crisp full-res PNG still (much sharper than the GIF).
const PAGE_BG = "#0d0d0f";       // matches the dark stage so the transparent player isn't a weird matte

export interface ExportProgress {
  // 0..1 over the whole job (capture phase then encode phase)
  phase: "capturing" | "encoding" | "done";
  pct: number;
}

const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

// ── benchmark: real numbers for "is the page actually responsive during export" ─
// Exposes window.__gifBench after each run. An INDEPENDENT rAF tick counter runs
// for the whole export: a responsive page fires ~60 rAF ticks/sec; a frozen one
// fires far fewer and shows a large worst-stall gap between consecutive ticks.
export interface GifBench {
  perFrameMs: number[];     // per-frame COMPOSITE cost (base blit + live overlays)
  frameMaxMs: number;
  frameMeanMs: number;
  baseMs: number;           // ONE-TIME static base raster (the only ~4MB SVG decode)
  encodeMs: number;         // now runs in a worker (off main thread)
  totalMs: number;
  rafTicks: number;
  rafSeconds: number;
  rafPerSec: number;        // ~60 = smooth, low = janky
  rafWorstStallMs: number;        // longest rAF gap over the whole export
  rafWorstStallCaptureMs: number; // longest rAF gap DURING the per-frame capture loop
}
function startBench() {
  const t0 = performance.now();
  const perFrameMs: number[] = [];
  let lastRaf = t0;
  let rafTicks = 0;
  let worstStall = 0;
  let worstStallCapture = 0;
  let inCapture = false;     // true only during the per-frame composite loop
  let running = true;
  const tick = () => {
    if (!running) return;
    const now = performance.now();
    const gap = now - lastRaf;
    if (rafTicks > 0 && gap > worstStall) worstStall = gap;
    if (rafTicks > 0 && inCapture && gap > worstStallCapture) worstStallCapture = gap;
    lastRaf = now;
    rafTicks++;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  let encodeMs = 0;
  let baseMs = 0;
  return {
    base: (ms: number) => { baseMs = ms; },
    captureStart: () => { inCapture = true; },
    captureEnd: () => { inCapture = false; },
    frame: (ms: number) => perFrameMs.push(ms),
    encode: (ms: number) => { encodeMs = ms; },
    done: () => {
      running = false;
      const totalMs = performance.now() - t0;
      const frameMaxMs = perFrameMs.length ? Math.max(...perFrameMs) : 0;
      const frameMeanMs = perFrameMs.length ? perFrameMs.reduce((a, b) => a + b, 0) / perFrameMs.length : 0;
      const rafSeconds = totalMs / 1000;
      const b: GifBench = {
        perFrameMs, frameMaxMs, frameMeanMs, baseMs, encodeMs, totalMs,
        rafTicks, rafSeconds, rafPerSec: rafTicks / rafSeconds,
        rafWorstStallMs: worstStall, rafWorstStallCaptureMs: worstStallCapture,
      };
      (window as unknown as { __gifBench?: GifBench }).__gifBench = b;
      console.info("[gif-bench]", JSON.stringify(b));
    },
  };
}

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
  const pad = Math.round(w * 0.02);
  const logoSize = Math.round(w * 0.07);          // subtler — smaller mark
  const fontSize = Math.round(logoSize * 0.62);
  ctx.font = `700 ${fontSize}px -apple-system, "Segoe UI", system-ui, sans-serif`;
  const word = "skeuo", tld = ".fm";
  const wordW = ctx.measureText(word).width;
  const textW = wordW + ctx.measureText(tld).width;
  const gap = Math.round(logoSize * 0.28);
  const innerW = logoSize + gap + textW;
  const pillH = logoSize + pad;
  const pillW = innerW + pad * 2;
  const x = w - pillW - pad;
  const y = h - pillH - pad;
  const r = pillH / 2;

  // whole watermark is drawn at reduced opacity so it reads as a subtle mark
  ctx.save();
  ctx.globalAlpha = 0.55;

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
  ctx.font = `700 ${fontSize}px -apple-system, "Segoe UI", system-ui, sans-serif`;
  ctx.textBaseline = "middle";
  const tx = lx + logoSize + gap;
  ctx.fillStyle = "rgba(240,242,246,0.95)";
  ctx.fillText(word, tx, cy + 1);
  ctx.fillStyle = "#2dff6e";                 // green ".fm" — matches the brand
  ctx.fillText(tld, tx + wordW, cy + 1);
  ctx.restore();                              // end reduced-opacity watermark
}

// ── live-overlay compositing ────────────────────────────────────────────────
// The bottleneck was NOT the DOM clone (only ~17ms once the Context is reused) —
// it was the per-frame SVG→<img> DECODE of a ~4 MB inlined-PNG foreignObject
// (~140ms × 25 frames = the freeze). Those PNGs (the skin faceplate, screen, and
// sprite layers) are STATIC across the recording. So:
//   • rasterize the WHOLE player ONCE → a static base (one 4 MB decode, paid once)
//   • per frame, redraw the base (instant) then composite only the LIVE elements:
//       - <canvas class="vis-canvas">  → drawImage straight from the live canvas (~0ms)
//       - text overlays (marquee/clock) → a tiny per-element capture (~5ms, 6 KB SVG)
// Per-frame cost goes from ~180ms (full re-raster) to single-digit ms.

// Live text overlays whose content changes mid-recording: the scrolling marquee
// and the ticking clock read-outs. Captured per frame (cheap — they're tiny).
const LIVE_TEXT_SEL = ".marquee, .lcd-time, .dial-time, .dial-track";

interface LiveRegion {
  el: HTMLElement;
  // destination rect in OUTPUT canvas pixels
  dx: number; dy: number; dw: number; dh: number;
  // reused per-element capture context (text overlays only; canvases don't need one)
  ctx?: Context<HTMLElement>;
}

// player-relative rect → output-canvas pixels
function regionRect(el: HTMLElement, playerRect: DOMRect, sx: number, sy: number) {
  const r = el.getBoundingClientRect();
  return {
    dx: Math.round((r.left - playerRect.left) * sx),
    dy: Math.round((r.top - playerRect.top) * sy),
    dw: Math.max(1, Math.round(r.width * sx)),
    dh: Math.max(1, Math.round(r.height * sy)),
  };
}

export interface ExportResult {
  blob: Blob;
  width: number;
  height: number;
  frames: number;
  // sample ImageData (early/mid/late) for verification
  samples: ImageData[];
}

// ── shared compositor setup ──────────────────────────────────────────────────
// Both the GIF and the VIDEO export need the exact same pipeline: rasterize the
// static base ONCE (excluding the live elements), then per-frame blit that base
// and composite only the cheap live regions (the real spectrum <canvas> straight
// via drawImage + the tiny changing text overlays). This builds that machinery
// once and hands back a `composite()` that paints one frame into `outCtx`, plus a
// `dispose()` to release the heavy capture contexts. Reused by recordPlayerGif
// (encode → GIF) and recordPlayerVideo (captureStream → MediaRecorder).
interface Compositor {
  outCanvas: HTMLCanvasElement;
  outCtx: CanvasRenderingContext2D;
  outW: number;
  outH: number;
  composite: () => Promise<void>;
  dispose: () => void;
}

async function buildCompositor(
  el: HTMLElement,
  outW: number,
  logo: HTMLImageElement | null,
  bench?: ReturnType<typeof startBench>,
  willReadFrequently = true,
): Promise<Compositor> {
  const playerRect = el.getBoundingClientRect();
  const aspect = el.offsetHeight / el.offsetWidth || 1536 / 1024;
  const outH = Math.round(outW * aspect);
  const sx = outW / (playerRect.width || outW);
  const sy = outH / (playerRect.height || outH);

  // identify the live elements to re-composite each frame (general across skins):
  // every real <canvas> visualizer (drawn straight from the live canvas) and the
  // changing text overlays (captured tiny, per frame).
  const liveCanvasEls = [...el.querySelectorAll<HTMLCanvasElement>(".vis-canvas")];
  const liveTextEls = [...el.querySelectorAll<HTMLElement>(LIVE_TEXT_SEL)];
  const liveSet = new Set<Node>([...liveCanvasEls, ...liveTextEls]);

  // ── rasterize the STATIC base ONCE, EXCLUDING the live elements ──────────────
  // The static faceplate/sprite PNGs (~4 MB inlined) are captured a single time
  // with the live spectrum + text FILTERED OUT, so the base is pure static art.
  // We never pay the ~4 MB SVG decode again — every frame just blits this base and
  // composites the (cheap) live regions over the holes left for them.
  const ctxCache = await createContext(el, {
    width: el.offsetWidth, height: el.offsetHeight,
    scale: Math.min(1, outW / (el.offsetWidth || outW)),
    autoDestruct: false,
    filter: (node) => !liveSet.has(node),
  });
  const baseT0 = performance.now();
  const baseCanvas = await domToCanvas(ctxCache);
  bench?.base(performance.now() - baseT0);

  const liveCanvases: LiveRegion[] = liveCanvasEls
    .map((c) => ({ el: c, ...regionRect(c, playerRect, sx, sy) }));
  const liveTexts: LiveRegion[] = [];
  for (const t of liveTextEls) {
    const rect = regionRect(t, playerRect, sx, sy);
    const tctx = await createContext(t, {
      width: t.offsetWidth, height: t.offsetHeight, autoDestruct: false,
    });
    liveTexts.push({ el: t, ...rect, ctx: tctx });
  }

  const out = document.createElement("canvas");
  out.width = outW; out.height = outH;
  const outCtx = out.getContext("2d", { willReadFrequently })!;
  outCtx.imageSmoothingEnabled = true;
  outCtx.imageSmoothingQuality = "high";

  const composite = async () => {
    outCtx.fillStyle = PAGE_BG;
    outCtx.fillRect(0, 0, outW, outH);
    outCtx.drawImage(baseCanvas, 0, 0, outW, outH);
    // live visualizers: a real canvas → straight drawImage, no raster cost. The
    // base has a HOLE here (live element filtered out), so just draw over it.
    for (const r of liveCanvases) {
      outCtx.drawImage(r.el as HTMLCanvasElement, r.dx, r.dy, r.dw, r.dh);
    }
    // live text overlays (marquee/clock): tiny per-element capture (~5ms, ~6 KB SVG)
    // drawn over the hole left in the base. A single bad capture must not abort the
    // whole export — fall back to leaving the base's hole (no overlay) for that one.
    for (const r of liveTexts) {
      try {
        const snap = await domToCanvas(r.ctx!);
        outCtx.drawImage(snap, r.dx, r.dy, r.dw, r.dh);
      } catch { /* skip this overlay this frame */ }
    }
    drawWatermark(outCtx, outW, outH, logo);
  };

  const dispose = () => {
    destroyContext(ctxCache);
    for (const r of liveTexts) r.ctx && destroyContext(r.ctx);
  };

  return { outCanvas: out, outCtx, outW, outH, composite, dispose };
}

// Record the given element as an animated GIF. onProgress fires through capture
// then encode. Returns the gif Blob plus sample frames for verification.
export async function recordPlayerGif(
  el: HTMLElement,
  onProgress?: (p: ExportProgress) => void,
): Promise<ExportResult> {
  const logo = await loadLogo();
  const bench = startBench();

  const comp = await buildCompositor(el, TARGET_W, logo, bench);
  const { outCtx, outW, outH } = comp;

  // spin up the encode worker NOW so it's warm by the time capture finishes
  const worker = new Worker(new URL("./gifWorker.ts", import.meta.url), { type: "module" });

  // ── capture phase: composite across real animation time ─────────────────────
  const frameBuffers: ArrayBuffer[] = [];   // RGBA, transferred to the worker
  const samples: ImageData[] = [];          // kept copies for verification
  const interval = DURATION_MS / FRAME_COUNT;
  const t0 = performance.now();
  bench.captureStart();
  for (let i = 0; i < FRAME_COUNT; i++) {
    const target = t0 + i * interval;
    // let the live animation advance to this frame's wall-clock target
    while (performance.now() < target) await nextFrame();
    const cap0 = performance.now();

    await comp.composite();

    const rgba = outCtx.getImageData(0, 0, outW, outH).data;
    bench.frame(performance.now() - cap0);
    const copy = new Uint8ClampedArray(rgba);
    frameBuffers.push(copy.buffer);
    onProgress?.({ phase: "capturing", pct: ((i + 1) / FRAME_COUNT) * 0.7 });
  }
  bench.captureEnd();
  // capture done — the expensive contexts can go
  comp.dispose();

  // keep early/mid/late samples for verification BEFORE the buffers are transferred
  const midIdx = Math.floor(frameBuffers.length / 2);
  for (const idx of [0, midIdx, frameBuffers.length - 1]) {
    const b = frameBuffers[idx];
    if (b) samples.push(new ImageData(new Uint8ClampedArray(b.slice(0)), outW, outH));
  }

  // ── encode phase: entirely OFF the main thread ──────────────────────────────
  const encT0 = performance.now();
  const blob = await new Promise<Blob>((resolve, reject) => {
    worker.onmessage = (e: MessageEvent<ProgressMsg | DoneMsg>) => {
      const m = e.data;
      if (m.type === "progress") {
        onProgress?.({ phase: "encoding", pct: 0.7 + (m.current / m.total) * 0.3 });
      } else if (m.type === "done") {
        resolve(new Blob([m.gif], { type: "image/gif" }));
      }
    };
    worker.onerror = (err) => { worker.terminate(); reject(err); };
    worker.postMessage(
      { type: "encode", width: outW, height: outH, delay: FRAME_DELAY, frames: frameBuffers },
      frameBuffers, // transfer (zero-copy) — encode runs in the worker
    );
  });
  worker.terminate();
  bench.encode(performance.now() - encT0);
  bench.done();
  onProgress?.({ phase: "done", pct: 1 });

  return { blob, width: outW, height: outH, frames: FRAME_COUNT, samples };
}

// ── short looping VIDEO of the running skin ──────────────────────────────────
// Same static-base + live-canvas compositor as the GIF, but instead of capturing
// RGBA frames for a quantized GIF we drive the output canvas in real time and let
// MediaRecorder pull from canvas.captureStream(). That keeps the heavy work the
// same (the page stays responsive — base is rastered once, per-frame is the cheap
// composite) while producing a full-color, properly-compressed clip. We prefer
// H.264 in MP4 (universally playable) and fall back to VP9/WebM where MP4 isn't
// offered (Chrome/Firefox). ~3s, then download.
const VIDEO_W = 720;             // video output width; height follows player aspect
const VIDEO_MS = 3000;           // ~3s loop
const VIDEO_FPS = 30;            // smooth playback

export interface VideoResult {
  blob: Blob;
  mimeType: string;
  ext: "mp4" | "webm";
  width: number;
  height: number;
  durationMs: number;
}

// Pick the best supported recording container/codec. MP4/avc1 first (plays
// everywhere incl. iOS/QuickTime/Discord), then VP9/WebM, then a plain fallback.
function pickVideoMime(): { mimeType: string; ext: "mp4" | "webm" } {
  const candidates: { mimeType: string; ext: "mp4" | "webm" }[] = [
    { mimeType: "video/mp4;codecs=avc1.42E01E", ext: "mp4" },
    { mimeType: "video/mp4;codecs=avc1", ext: "mp4" },
    { mimeType: "video/mp4", ext: "mp4" },
    { mimeType: "video/webm;codecs=vp9", ext: "webm" },
    { mimeType: "video/webm;codecs=vp8", ext: "webm" },
    { mimeType: "video/webm", ext: "webm" },
  ];
  const supports =
    typeof MediaRecorder !== "undefined" && typeof MediaRecorder.isTypeSupported === "function";
  for (const c of candidates) {
    if (supports && MediaRecorder.isTypeSupported(c.mimeType)) return c;
  }
  return { mimeType: "video/webm", ext: "webm" }; // last-ditch
}

export async function recordPlayerVideo(
  el: HTMLElement,
  onProgress?: (p: ExportProgress) => void,
): Promise<VideoResult> {
  const logo = await loadLogo();
  const { mimeType, ext } = pickVideoMime();

  // willReadFrequently=false: captureStream pulls the canvas via the GPU path, so
  // we do NOT want the readback-optimized (CPU) backing store here.
  const comp = await buildCompositor(el, VIDEO_W, logo, undefined, false);
  const { outCanvas, outW, outH } = comp;

  // ── DETERMINISTIC capture (no flicker) ───────────────────────────────────────
  // The OLD path used captureStream(VIDEO_FPS): MediaRecorder pulled frames on its
  // OWN timer, asynchronously, so it frequently sampled the canvas MID-composite —
  // after drawImage(base) but before the marquee/visualizer overlay landed. That
  // gave torn frames and a flickering marquee. The fix: open the stream at 0 fps
  // (captureStream(0) → MediaRecorder NEVER auto-samples) and push exactly one
  // frame per FULLY-composited paint via track.requestFrame(). Every recorded
  // frame is therefore a complete, consistent composite → smooth marquee, no tear.
  await comp.composite();

  const stream = outCanvas.captureStream(0);
  const track = stream.getVideoTracks()[0] as CanvasCaptureMediaStreamTrack | undefined;
  const recorder = new MediaRecorder(stream, {
    mimeType,
    videoBitsPerSecond: 8_000_000, // generous — short clip, want it clean
  });
  const chunks: BlobPart[] = [];
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

  const done = new Promise<void>((resolve) => { recorder.onstop = () => resolve(); });
  recorder.start();
  // push the opening frame (already composited above) into the stream
  track?.requestFrame();

  // Drive the compositor on a FIXED frame clock. Each iteration: fully composite,
  // THEN request exactly that frame — the only frames the recorder ever sees are
  // complete ones. Paced to VIDEO_FPS via the wall clock so playback runs at real
  // speed regardless of how long a composite() takes.
  const frameInterval = 1000 / VIDEO_FPS;
  const totalFrames = Math.round(VIDEO_MS / frameInterval);
  const t0 = performance.now();
  for (let i = 1; i <= totalFrames; i++) {
    // wait until this frame's wall-clock slot so the marquee advances at real speed
    const target = t0 + i * frameInterval;
    while (performance.now() < target) await nextFrame();
    await comp.composite();      // fully paint base + live overlays + watermark
    track?.requestFrame();        // emit ONLY this complete frame to the recorder
    onProgress?.({ phase: "capturing", pct: Math.min(0.95, (performance.now() - t0) / VIDEO_MS) });
  }

  recorder.stop();
  await done;
  comp.dispose();
  stream.getTracks().forEach((t) => t.stop());

  const blob = new Blob(chunks, { type: mimeType.split(";")[0] });
  onProgress?.({ phase: "done", pct: 1 });
  return { blob, mimeType, ext, width: outW, height: outH, durationMs: VIDEO_MS };
}

// Trigger a browser download of the recorded video.
export function downloadVideo(blob: Blob, skinId: string, ext: "mp4" | "webm") {
  downloadBlob(blob, `skeuo-${skinId}.${ext}`);
}

// ── crisp full-res PNG still (the primary SHARE artifact) ────────────────────
// A single high-resolution snapshot of the live player — no quantization, no
// frame budget — so it's MUCH sharper than the GIF. Renders the player at PNG_W
// directly via modern-screenshot (the live spectrum + clock are captured in
// whatever state they're in at the click), composites the watermark, returns a
// PNG Blob plus a File suitable for navigator.share({ files }).
export interface SnapshotResult {
  blob: Blob;
  file: File;
  width: number;
  height: number;
}

export async function snapshotPlayerPng(el: HTMLElement, skinId: string): Promise<SnapshotResult> {
  const logo = await loadLogo();
  const aspect = el.offsetHeight / el.offsetWidth || 1536 / 1024;
  const outW = PNG_W;
  const outH = Math.round(PNG_W * aspect);
  // scale up from the live element's CSS size to the target resolution
  const scale = outW / (el.offsetWidth || outW);

  // one high-res raster of the whole player (static art + live overlays as-is)
  const canvas = await domToCanvas(el, {
    width: el.offsetWidth,
    height: el.offsetHeight,
    scale,
    backgroundColor: null,
  });

  // composite onto the dark stage bg + watermark, at exact target dims
  const out = document.createElement("canvas");
  out.width = outW; out.height = outH;
  const octx = out.getContext("2d")!;
  octx.imageSmoothingEnabled = true;
  octx.imageSmoothingQuality = "high";
  octx.fillStyle = PAGE_BG;
  octx.fillRect(0, 0, outW, outH);
  octx.drawImage(canvas, 0, 0, outW, outH);
  drawWatermark(octx, outW, outH, logo);

  const blob = await new Promise<Blob>((resolve, reject) =>
    out.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png"),
  );
  const file = new File([blob], `skeuo-${skinId}.png`, { type: "image/png" });
  return { blob, file, width: outW, height: outH };
}

// Trigger a browser download of a blob with a given filename.
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Trigger a browser download of the gif blob.
export function downloadGif(blob: Blob, skinId: string) {
  downloadBlob(blob, `skeuo-${skinId}.gif`);
}

// Trigger a browser download of the PNG still.
export function downloadPng(blob: Blob, skinId: string) {
  downloadBlob(blob, `skeuo-${skinId}.png`);
}
