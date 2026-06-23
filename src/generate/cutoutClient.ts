// Browser-side cutout — the second half of the single-pass sprite-sheet pipeline.
//
// /api/generate (the CF Pages Function) can't run the cutout itself: background
// removal + per-control sprite cutting is pure-JS/CPU that trips the Function CPU
// ceiling → CF 1102. So the Worker returns the RAW COMBINED paint (device body on
// top + a sprite strip of bare controls below) plus a `layout` (needsCutout +
// paintUrl + layout). Here we:
//   1. decode the combined paint to a canvas;
//   2. crop the DEVICE region (top `devFrac`) and POST it to /api/cutout, which
//      runs fal BiRefNet SERVER-SIDE (FAL_KEY never reaches the browser) and
//      returns the transparent device PNG → upload as frame.png;
//   3. cut each control sprite from its strip cell by geometry (ellipse for
//      button/knob/toggle, rounded-rect for slider, slightly inset to avoid the
//      white halo) → upload each as sprites/<bind>.png.
// The app then sizes each control sprite to its OWN template region rect, so the
// bigger play region gets the bigger play button (placement is NOT baked in; we
// only cut clean per-control sprites).
//
// LEGACY/DEMO FALLBACK: when no `layout` is provided (old callers) or the paint is
// a data: URL (offline demo, no R2), we key out the white background with the
// shared pure-JS cutoutAlpha — the original behavior — instead of calling fal.
import { cutoutAlpha, DEVICE_FRAC, type BlueprintLayout, type SpriteKind } from "./blueprint";
import { apiUrl } from "../platform";

// Decode raw image bytes into something drawable, robustly across engines.
// createImageBitmap is the fast path, but in real WKWebView (the iOS app + macOS
// widget) it has historically been the flakier decoder — it can reject a blob that
// an <img> decodes without issue (seen as "The source image could not be decoded"
// on desktop while the same paint decodes fine on the web and in headless WebKit).
// So fall back to an <img> element, which sniffs the magic bytes and is the
// battle-tested decode path. If BOTH fail, throw an error carrying the real state
// (status, served type, byte length, magic) so an otherwise-opaque failure names
// its own cause next time instead of just "could not be decoded".
type Decoded = { src: CanvasImageSource; W: number; H: number; release: () => void };
async function decodePaint(buf: ArrayBuffer, res: Response): Promise<Decoded> {
  const bytes = new Uint8Array(buf);
  const blob = new Blob([buf]); // no forced type — let each decoder sniff the bytes
  let e1: unknown;
  try {
    const bmp = await createImageBitmap(blob);
    return { src: bmp, W: bmp.width, H: bmp.height, release: () => bmp.close?.() };
  } catch (e) { e1 = e; }
  try {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.src = url;
    await img.decode(); // fully decodes into memory; safe to revoke after drawImage
    return { src: img, W: img.naturalWidth, H: img.naturalHeight, release: () => URL.revokeObjectURL(url) };
  } catch (e2) {
    const magic = Array.from(bytes.slice(0, 8)).map((b) => b.toString(16).padStart(2, "0")).join(" ");
    const ct = res.headers.get("content-type") ?? "?";
    throw new Error(
      `paint undecodable (HTTP ${res.status}, type ${ct}, ${bytes.length}B, magic [${magic || "empty"}]; ` +
      `createImageBitmap: ${e1 instanceof Error ? e1.message : String(e1)}; ` +
      `img: ${e2 instanceof Error ? e2.message : String(e2)})`);
  }
}

// Fetch + decode the combined paint to a full-size canvas, with retries. The paint
// can be momentarily unavailable right after generation (the two-step write window,
// a CDN edge that hasn't filled, or dev static-serving lag) and come back as a
// non-image (a 404 page or the SPA index.html); a few short retries turn that
// transient into a success instead of a hard "could not be decoded".
async function fetchPaintCanvas(paintUrl: string): Promise<HTMLCanvasElement> {
  let decoded: Decoded | undefined;
  let lastErr: unknown;
  for (let attempt = 0; attempt < 3 && !decoded; attempt++) {
    if (attempt) await new Promise((r) => setTimeout(r, 400 * attempt));
    try {
      const res = await fetch(apiUrl(paintUrl), { cache: "no-store" });
      if (!res.ok) throw new Error(`fetch paint → ${res.status}`);
      decoded = await decodePaint(await res.arrayBuffer(), res);
    } catch (e) { lastErr = e; }
  }
  if (!decoded) throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
  const { src, W, H, release } = decoded;
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) { release(); throw new Error("no 2d canvas context"); }
  ctx.drawImage(src, 0, 0);
  release();
  return canvas;
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("canvas.toBlob failed"))), "image/png"));
}

// ---- LEGACY/DEMO: pure-JS white-key cutout of the whole paint (no fal) ----------
// Key out the near-white background of the (already cropped) device, keeping the
// largest connected component with internal holes filled. Used only when there is
// no layout (old caller) or no server to call (data: URL demo).
function whiteKeyCanvas(canvas: HTMLCanvasElement): Blob | Promise<Blob> {
  const W = canvas.width, H = canvas.height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("no 2d canvas context");
  const img = ctx.getImageData(0, 0, W, H);
  const rgba = new Uint8Array(img.data.buffer, img.data.byteOffset, img.data.byteLength);
  const alpha = cutoutAlpha(rgba, W, H);
  for (let i = 0; i < W * H; i++) img.data[i * 4 + 3] = alpha[i];
  ctx.putImageData(img, 0, 0);
  return canvasToBlob(canvas);
}

// ---- device region crop --------------------------------------------------------
// The device is the TOP `devFrac` of the combined paint. Returns a fresh canvas.
function cropDevice(paint: HTMLCanvasElement, devFrac: number): HTMLCanvasElement {
  const W = paint.width;
  const devH = Math.max(1, Math.round(paint.height * devFrac));
  const out = document.createElement("canvas");
  out.width = W; out.height = devH;
  const ctx = out.getContext("2d");
  if (!ctx) throw new Error("no 2d canvas context");
  ctx.drawImage(paint, 0, 0, W, devH, 0, 0, W, devH);
  return out;
}

// ---- per-control sprite cut (port of /tmp/A_post_v3.py cut()) -------------------
// Crop the cell from the combined paint, then mask to the control's shape (ellipse
// for button/knob/toggle, rounded-rect for slider), slightly inset (1px) to avoid
// the white edge halo. cellRect is normalized to the FULL combined image.
function cutSprite(
  paint: HTMLCanvasElement,
  cellRect: [number, number, number, number],
  kind: SpriteKind,
): HTMLCanvasElement {
  const W = paint.width, H = paint.height;
  const [nx, ny, nw, nh] = cellRect;
  const cx = nx * W, cy = ny * H, cw = nw * W, ch = nh * H;
  // The painted control sits CENTERED in its cell. Crop a centered SQUARE (round
  // controls) or a centered thin band (slider) — NOT the full (tall) cell, or the
  // inscribed ellipse becomes a stretched oval and the round button looks crushed.
  let sw: number, sh: number;
  if (kind === "slider") { sw = cw * 0.92; sh = Math.min(ch, cw * 0.34); }
  else { sw = sh = Math.min(cw, ch) * 0.92; }
  const sx = Math.round(cx + (cw - sw) / 2), sy = Math.round(cy + (ch - sh) / 2);
  const ow = Math.max(1, Math.round(sw)), oh = Math.max(1, Math.round(sh));

  const out = document.createElement("canvas");
  out.width = ow; out.height = oh;
  const ctx = out.getContext("2d");
  if (!ctx) throw new Error("no 2d canvas context");

  // clip to the control shape (inset 1px), then draw the centered crop through it.
  ctx.beginPath();
  if (kind === "slider") {
    roundRectPath(ctx, 1, 1, ow - 2, oh - 2, Math.min((ow - 2) / 2, (oh - 2) / 2));
  } else {
    ctx.ellipse(ow / 2, oh / 2, Math.max(0, ow / 2 - 1), Math.max(0, oh / 2 - 1), 0, 0, Math.PI * 2);
  }
  ctx.closePath();
  ctx.clip();
  ctx.drawImage(paint, sx, sy, ow, oh, 0, 0, ow, oh);
  return out;
}

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  const rr = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
}

// ---- /api/cutout — server-side BiRefNet on the device crop ----------------------
async function serverCutout(deviceCanvas: HTMLCanvasElement): Promise<Blob> {
  const png = await canvasToBlob(deviceCanvas);
  const r = await fetch(apiUrl("/api/cutout"), {
    method: "POST", headers: { "Content-Type": "image/png" }, body: png,
  });
  if (!r.ok) {
    const err = (await r.json().catch(() => null)) as { error?: string } | null;
    throw new Error(err?.error ?? `cutout → ${r.status}`);
  }
  return r.blob();
}

// ---- finalize uploads ----------------------------------------------------------
// Upload the cut device frame. /api/finalize/<id> is write-once + gated on a prior
// generation. Returns the public frame URL.
export async function uploadFrame(id: string, frame: Blob): Promise<string> {
  const r = await fetch(apiUrl(`/api/finalize/${encodeURIComponent(id)}`), {
    method: "POST", headers: { "Content-Type": "image/png" }, body: frame,
  });
  const out = (await r.json().catch(() => null)) as { frameUrl?: string; error?: string } | null;
  if (!r.ok || !out?.frameUrl) throw new Error(out?.error ?? `finalize → ${r.status}`);
  return out.frameUrl;
}

// Upload one per-control sprite. /api/finalize/<id>/sprites/<bind> is write-once.
export async function uploadSprite(id: string, bind: string, sprite: Blob): Promise<string> {
  const r = await fetch(
    apiUrl(`/api/finalize/${encodeURIComponent(id)}/sprites/${encodeURIComponent(bind)}`),
    { method: "POST", headers: { "Content-Type": "image/png" }, body: sprite },
  );
  const out = (await r.json().catch(() => null)) as { spriteUrl?: string; error?: string } | null;
  if (!r.ok || !out?.spriteUrl) throw new Error(out?.error ?? `finalize sprite → ${r.status}`);
  return out.spriteUrl;
}

export interface FinishResult {
  frameUrl: string;        // public (absolute on native) device frame URL
  sprites: boolean;        // true once per-skin sprites were cut + uploaded
  spriteUrls: Record<string, string>; // bind → public sprite URL
}

// Full client half of a single-pass generation, returning the rich FinishResult
// (frameUrl + which per-skin sprites now exist). `finishCutout` below wraps this to
// the legacy `Promise<string>` shape the existing callers consume; new callers that
// want the sprite info should call this directly.
//
// Crops + background-removes the device (top devFrac, via /api/cutout → BiRefNet),
// cuts each control sprite from its cell by geometry, uploads frame.png + each
// sprites/<bind>.png. `layout` carries devFrac + the strip cells. When omitted (old
// caller) or the paint is a data: URL (offline demo, no server), falls back to the
// LEGACY pure-JS white-key cutout of the whole paint — no device/sprite split.
export async function finishCutoutFull(
  id: string,
  paintUrl: string,
  durableFrameUrl: string,
  layout?: BlueprintLayout,
): Promise<FinishResult> {
  const paint = await fetchPaintCanvas(paintUrl);
  const isData = paintUrl.startsWith("data:");

  // LEGACY / DEMO: no layout, or a data: URL with no server to call → crop the
  // device region (top devFrac — DEVICE_FRAC when no layout) and white-key it in
  // pure JS (original behavior, sans the fal call). No sprite split. We still crop
  // the device off the combined paint so the strip controls don't bleed into frame.
  if (!layout || isData) {
    const devFrac = layout?.devFrac ?? DEVICE_FRAC;
    const deviceCanvas = cropDevice(paint, devFrac);
    const frame = await whiteKeyCanvas(deviceCanvas);
    if (isData) return { frameUrl: URL.createObjectURL(frame), sprites: false, spriteUrls: {} };
    await uploadFrame(id, frame);
    return { frameUrl: apiUrl(durableFrameUrl), sprites: false, spriteUrls: {} };
  }

  // 1. device frame: crop the top devFrac, BiRefNet via /api/cutout, upload.
  const deviceCanvas = cropDevice(paint, layout.devFrac);
  const frameBlob = await serverCutout(deviceCanvas);
  await uploadFrame(id, frameBlob);

  // 2. each control sprite: geometric cut from its cell, upload. Best-effort per
  //    sprite — a single failed sprite shouldn't sink the whole skin (the app
  //    falls back to the donor sprite for any bind that is missing).
  const spriteUrls: Record<string, string> = {};
  for (const cell of layout.cells) {
    try {
      const spriteCanvas = cutSprite(paint, cell.cellRect, cell.kind);
      const blob = await canvasToBlob(spriteCanvas);
      spriteUrls[cell.bind] = await uploadSprite(id, cell.bind, blob);
    } catch { /* skip this sprite; app falls back to donor for this bind */ }
  }

  return {
    frameUrl: apiUrl(durableFrameUrl),
    sprites: Object.keys(spriteUrls).length > 0,
    spriteUrls,
  };
}

// Back-compat wrapper: the existing Create panel/wizard call
// `finishCutout(id, paintUrl, frameUrl)` and use the returned frameUrl string.
// Keep that exact signature + return type so those (other-team) files compile and
// run unchanged; the optional 4th `layout` arg opts into the device+sprite split.
// When a caller passes the layout (from GenerateDone.layout), the per-skin sprites
// are cut + uploaded as a side effect and discoverable at
// /api/asset/skins/<id>/sprites/<bind>.png (GenerateDone.sprites).
export async function finishCutout(
  id: string,
  paintUrl: string,
  durableFrameUrl: string,
  layout?: BlueprintLayout,
): Promise<string> {
  const out = await finishCutoutFull(id, paintUrl, durableFrameUrl, layout);
  return out.frameUrl;
}
