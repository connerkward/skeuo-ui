import type { DoneMsg, ProgressMsg } from "./gifWorker";
import { paintTree, preloadAssets, type Mapping } from "./domCompositor";
import { skinName, skinBlurb } from "../player/skins";

// ── tuning ───────────────────────────────────────────────────────────────────
const DURATION_MS = 2500;       // ~2.5s of motion
const FPS = 12;                  // a touch smoother now that frames are cheap
const FRAME_COUNT = Math.round((DURATION_MS / 1000) * FPS);
const FRAME_DELAY = Math.round(1000 / FPS);
const PAGE_BG = "#08080a";       // near-black IG backdrop (matches the reference)

// ── Instagram 9:16 canvas ────────────────────────────────────────────────────
// All export artifacts (PNG / GIF / Video) render into a 1080×1920 story/reel
// frame. Layout mirrors the hero reference (Bone Totem / Scarab): a BIG hero
// device floating high in a pool of near-black, with whisper-thin micro-type
// hugging the corners — nothing overlaps the device, nothing shouts.
const IG_W = 1080;
const IG_H = 1920;
// the device is the hero — it occupies this fraction of the frame HEIGHT
const DEVICE_H_FRAC = 0.72;
// safe horizontal inset for the player (also caps width on wide skins)
const SIDE_PAD = 72;
// margin label geometry (output px)
const LABEL_PAD = 56;

const INK = "#e8ece2";           // near-white text
const DIM = "#6c7466";           // muted meta text
// proportional sans for the skin name (the brand/meta lines stay mono)
const SANS = `"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`;

export interface ExportProgress {
  phase: "capturing" | "encoding" | "done";
  pct: number;
}

const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

// Load the watermark logomark once (drawn small in the top-left brand line).
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

// monospace stack matching the on-screen LCD/terminal type for the margin labels
const MONO = `"Share Tech Mono", "VT323", ui-monospace, SFMono-Regular, Menlo, monospace`;

// word-wrap a string to a max pixel width using the current ctx.font
function wrapLines(ctx: CanvasRenderingContext2D, text: string, maxW: number, maxLines = 2): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let cur = "";
  for (const word of words) {
    const test = cur ? `${cur} ${word}` : word;
    if (ctx.measureText(test).width > maxW && cur) {
      lines.push(cur);
      cur = word;
      if (lines.length === maxLines - 1) break;
    } else {
      cur = test;
    }
  }
  if (cur) lines.push(cur);
  return lines.slice(0, maxLines);
}

// ── the IG layout chrome (drawn under/around the device, every frame) ─────────
// Returns the device destination box so the compositor knows where to paint the
// player. Text is drawn in the margins only — never over the device.
interface DeviceBox { destX: number; destY: number; destW: number; destH: number; }
function drawIgChrome(
  ctx: CanvasRenderingContext2D,
  skinId: string,
  playerAspect: number,        // player w/h
  logo: HTMLImageElement | null,
): DeviceBox {
  // backdrop
  ctx.fillStyle = PAGE_BG;
  ctx.fillRect(0, 0, IG_W, IG_H);
  // a barely-there pool of light, sat slightly high so the device floats in it
  const grad = ctx.createRadialGradient(IG_W / 2, IG_H * 0.42, IG_H * 0.08, IG_W / 2, IG_H * 0.42, IG_H * 0.58);
  grad.addColorStop(0, "rgba(26,28,24,0.45)");
  grad.addColorStop(1, "rgba(8,8,10,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, IG_W, IG_H);

  // ── device box: the hero. Fit DEVICE_H_FRAC of height, capped by side pad, and
  // float it slightly high so the name sits in a roomy bottom-left band.
  let destH = IG_H * DEVICE_H_FRAC;
  let destW = destH * playerAspect;
  const maxW = IG_W - SIDE_PAD * 2;
  if (destW > maxW) { destW = maxW; destH = destW / playerAspect; }
  const destX = (IG_W - destW) / 2;
  const destY = (IG_H - destH) / 2 - IG_H * 0.03; // nudge up → bigger bottom margin

  const name = skinName(skinId);
  const blurb = skinBlurb(skinId);

  // ── TOP-LEFT: whisper-thin brand line — logomark + "skeuo/fm · <skin>" ────────
  const topY = LABEL_PAD + 8;
  let bx = LABEL_PAD;
  ctx.textBaseline = "middle";
  if (logo) {
    const ls = 19;
    ctx.globalAlpha = 0.9;
    ctx.drawImage(logo, bx, topY - ls / 2, ls, ls);
    ctx.globalAlpha = 1;
    bx += ls + 12;
  }
  ctx.font = `500 21px ${MONO}`;
  ctx.fillStyle = "rgba(232,236,226,0.8)";
  ctx.fillText("skeuo", bx, topY);
  const sw = ctx.measureText("skeuo").width;
  ctx.fillStyle = "rgba(157,255,77,0.8)";
  ctx.fillText("/fm", bx + sw, topY);
  const fw = ctx.measureText("/fm").width;
  ctx.fillStyle = DIM;
  ctx.fillText(`   ·   ${name.toLowerCase()}`, bx + sw + fw, topY);

  // ── TOP-RIGHT: tiny, dim tag ──────────────────────────────────────────────────
  ctx.font = `400 19px ${MONO}`;
  ctx.fillStyle = "rgba(108,116,102,0.8)";
  ctx.textAlign = "right";
  ctx.fillText("[ skeuomorphic player ]", IG_W - LABEL_PAD, topY);
  ctx.textAlign = "left";

  // ── BOTTOM-LEFT: small name (sans) + one dim caption line. Nothing else. ──────
  ctx.textBaseline = "alphabetic";
  const capY = IG_H - LABEL_PAD - 2;
  if (blurb) {
    ctx.font = `400 21px ${MONO}`;
    ctx.fillStyle = "rgba(108,116,102,0.92)";
    const oneLine = wrapLines(ctx, blurb, IG_W - LABEL_PAD * 2, 1)[0] ?? "";
    ctx.fillText(oneLine, LABEL_PAD, capY);
  }
  ctx.font = `600 42px ${SANS}`;
  if ("letterSpacing" in ctx) (ctx as unknown as { letterSpacing: string }).letterSpacing = "-0.5px";
  ctx.fillStyle = INK;
  ctx.fillText(name, LABEL_PAD, capY - 32);
  if ("letterSpacing" in ctx) (ctx as unknown as { letterSpacing: string }).letterSpacing = "0px";

  return { destX, destY, destW, destH };
}

export interface ExportResult {
  blob: Blob;
  width: number;
  height: number;
  frames: number;
  samples: ImageData[];
}

// ── shared compositor ─────────────────────────────────────────────────────────
// Builds the 1080×1920 output canvas and a `composite()` that, per frame, redraws
// the IG chrome (backdrop + margin labels) then paints the LIVE player DOM tree
// into the device box via the direct DOM compositor (NO modern-screenshot).
interface Compositor {
  outCanvas: HTMLCanvasElement;
  outCtx: CanvasRenderingContext2D;
  outW: number;
  outH: number;
  composite: () => void;
  dispose: () => void;
}

async function buildCompositor(
  el: HTMLElement,
  skinId: string,
  logo: HTMLImageElement | null,
  willReadFrequently = true,
): Promise<Compositor> {
  // decode every <img> + CSS background sprite once so the first frame is complete
  await preloadAssets(el);
  await nextFrame();

  const aspect = el.offsetWidth / el.offsetHeight || 1024 / 1536;

  const out = document.createElement("canvas");
  out.width = IG_W; out.height = IG_H;
  const outCtx = out.getContext("2d", { willReadFrequently })!;
  outCtx.imageSmoothingEnabled = true;
  outCtx.imageSmoothingQuality = "high";

  const composite = () => {
    const box = drawIgChrome(outCtx, skinId, aspect, logo);
    const playerRect = el.getBoundingClientRect();
    const scale = box.destW / (playerRect.width || box.destW);
    const m: Mapping = {
      rootLeft: playerRect.left,
      rootTop: playerRect.top,
      scale,
      destX: box.destX,
      destY: box.destY,
    };
    outCtx.save();
    // clip the device draw to its box so nothing spills into the margins
    outCtx.beginPath();
    outCtx.rect(box.destX - 2, box.destY - 2, box.destW + 4, box.destH + 4);
    outCtx.clip();
    paintTree(outCtx, el, m);
    outCtx.restore();
  };

  return { outCanvas: out, outCtx, outW: IG_W, outH: IG_H, composite, dispose: () => {} };
}

// ── animated GIF ──────────────────────────────────────────────────────────────
export async function recordPlayerGif(
  el: HTMLElement,
  onProgress?: (p: ExportProgress) => void,
  skinId?: string,
): Promise<ExportResult> {
  const logo = await loadLogo();
  const comp = await buildCompositor(el, resolveSkinId(el, skinId), logo);
  const { outCtx, outW, outH } = comp;

  const worker = new Worker(new URL("./gifWorker.ts", import.meta.url), { type: "module" });

  const frameBuffers: ArrayBuffer[] = [];
  const samples: ImageData[] = [];
  const interval = DURATION_MS / FRAME_COUNT;
  const t0 = performance.now();
  for (let i = 0; i < FRAME_COUNT; i++) {
    const target = t0 + i * interval;
    while (performance.now() < target) await nextFrame();
    comp.composite();
    const rgba = outCtx.getImageData(0, 0, outW, outH).data;
    frameBuffers.push(new Uint8ClampedArray(rgba).buffer);
    onProgress?.({ phase: "capturing", pct: ((i + 1) / FRAME_COUNT) * 0.7 });
  }
  comp.dispose();

  const midIdx = Math.floor(frameBuffers.length / 2);
  for (const idx of [0, midIdx, frameBuffers.length - 1]) {
    const b = frameBuffers[idx];
    if (b) samples.push(new ImageData(new Uint8ClampedArray(b.slice(0)), outW, outH));
  }

  const blob = await new Promise<Blob>((resolve, reject) => {
    worker.onmessage = (e: MessageEvent<ProgressMsg | DoneMsg>) => {
      const msg = e.data;
      if (msg.type === "progress") {
        onProgress?.({ phase: "encoding", pct: 0.7 + (msg.current / msg.total) * 0.3 });
      } else if (msg.type === "done") {
        resolve(new Blob([msg.gif], { type: "image/gif" }));
      }
    };
    worker.onerror = (err) => { worker.terminate(); reject(err); };
    worker.postMessage(
      { type: "encode", width: outW, height: outH, delay: FRAME_DELAY, frames: frameBuffers },
      frameBuffers,
    );
  });
  worker.terminate();
  onProgress?.({ phase: "done", pct: 1 });

  return { blob, width: outW, height: outH, frames: FRAME_COUNT, samples };
}

// ── deterministic, flicker-free VIDEO ─────────────────────────────────────────
const VIDEO_MS = 3000;
const VIDEO_FPS = 30;

export interface VideoResult {
  blob: Blob;
  mimeType: string;
  ext: "mp4" | "webm";
  width: number;
  height: number;
  durationMs: number;
}

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
  for (const c of candidates) if (supports && MediaRecorder.isTypeSupported(c.mimeType)) return c;
  return { mimeType: "video/webm", ext: "webm" };
}

export async function recordPlayerVideo(
  el: HTMLElement,
  onProgress?: (p: ExportProgress) => void,
  skinId?: string,
): Promise<VideoResult> {
  const logo = await loadLogo();
  const { mimeType, ext } = pickVideoMime();
  const comp = await buildCompositor(el, resolveSkinId(el, skinId), logo, false);
  const { outCanvas, outW, outH } = comp;

  comp.composite();
  const stream = outCanvas.captureStream(0);
  const track = stream.getVideoTracks()[0] as CanvasCaptureMediaStreamTrack | undefined;
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 12_000_000 });
  const chunks: BlobPart[] = [];
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  const done = new Promise<void>((resolve) => { recorder.onstop = () => resolve(); });
  recorder.start();
  track?.requestFrame();

  const frameInterval = 1000 / VIDEO_FPS;
  const totalFrames = Math.round(VIDEO_MS / frameInterval);
  const t0 = performance.now();
  for (let i = 1; i <= totalFrames; i++) {
    const target = t0 + i * frameInterval;
    while (performance.now() < target) await nextFrame();
    comp.composite();
    track?.requestFrame();
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

// ── crisp full-res PNG still ──────────────────────────────────────────────────
export interface SnapshotResult { blob: Blob; file: File; width: number; height: number; }

export async function snapshotPlayerPng(el: HTMLElement, skinId: string): Promise<SnapshotResult> {
  const logo = await loadLogo();
  const comp = await buildCompositor(el, skinId || resolveSkinId(el), logo);
  comp.composite();
  const blob = await new Promise<Blob>((resolve, reject) =>
    comp.outCanvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png"),
  );
  comp.dispose();
  const file = new File([blob], `skeuo-${skinId}.png`, { type: "image/png" });
  return { blob, file, width: IG_W, height: IG_H };
}

// resolve the skin id for labels: prefer the explicit id passed from the Share
// modal; only fall back to [data-skin] (which is the STYLE id, not always the
// skin id) when none was provided.
function resolveSkinId(el: HTMLElement, fallback = ""): string {
  return fallback || el.getAttribute("data-skin") || el.dataset.skin || "";
}

// ── downloads ─────────────────────────────────────────────────────────────────
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
export function downloadVideo(blob: Blob, skinId: string, ext: "mp4" | "webm") {
  downloadBlob(blob, `skeuo-${skinId}.${ext}`);
}
export function downloadGif(blob: Blob, skinId: string) {
  downloadBlob(blob, `skeuo-${skinId}.gif`);
}
export function downloadPng(blob: Blob, skinId: string) {
  downloadBlob(blob, `skeuo-${skinId}.png`);
}
