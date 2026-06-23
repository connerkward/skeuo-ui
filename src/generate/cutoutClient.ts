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
import { cutoutAlpha, DEVICE_FRAC, type BlueprintLayout, type BlueprintCell, type SpriteKind } from "./blueprint";
import type { Template } from "../template/schema";
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
export async function fetchPaintCanvas(paintUrl: string): Promise<HTMLCanvasElement> {
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
export function cropDevice(paint: HTMLCanvasElement, devFrac: number): HTMLCanvasElement {
  const W = paint.width;
  const devH = Math.max(1, Math.round(paint.height * devFrac));
  const out = document.createElement("canvas");
  out.width = W; out.height = devH;
  const ctx = out.getContext("2d");
  if (!ctx) throw new Error("no 2d canvas context");
  ctx.drawImage(paint, 0, 0, W, devH, 0, 0, W, devH);
  return out;
}

// The control STRIP is the BOTTOM (1 - devFrac) of the combined paint.
export function cropStrip(paint: HTMLCanvasElement, devFrac: number): HTMLCanvasElement {
  const W = paint.width, H = paint.height;
  const sy = Math.round(H * devFrac), sh = Math.max(1, H - sy);
  const out = document.createElement("canvas");
  out.width = W; out.height = sh;
  const ctx = out.getContext("2d");
  if (!ctx) throw new Error("no 2d canvas context");
  ctx.drawImage(paint, 0, sy, W, sh, 0, 0, W, sh);
  return out;
}

export async function blobToCanvas(blob: Blob): Promise<HTMLCanvasElement> {
  const bmp = await createImageBitmap(blob);
  const c = document.createElement("canvas");
  c.width = bmp.width; c.height = bmp.height;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  if (!ctx) { bmp.close?.(); throw new Error("no 2d canvas context"); }
  ctx.drawImage(bmp, 0, 0); bmp.close?.();
  return c;
}

// Keep ONLY the connected alpha component nearest the canvas centre (the target control
// is centred in its cell); zero every other component. This drops NEIGHBOUR fragments
// that bleed across the cell boundary and stray glyphs/label bits, which is exactly the
// "picked up the neighbour" failure. 4-connectivity BFS on alpha>40.
function keepCenterComponent(c: HTMLCanvasElement): void {
  const W = c.width, H = c.height, N = W * H;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  if (!ctx || N < 4) return;
  const img = ctx.getImageData(0, 0, W, H), d = img.data;
  const op = (i: number) => d[i * 4 + 3] > 40;
  const label = new Int32Array(N).fill(-1), stack = new Int32Array(N);
  const comps: { id: number; size: number; cx: number; cy: number }[] = [];
  for (let s = 0; s < N; s++) {
    if (!op(s) || label[s] !== -1) continue;
    const id = comps.length; let head = 0, tail = 0, size = 0, sx = 0, sy = 0;
    stack[tail++] = s; label[s] = id;
    while (head < tail) {
      const p = stack[head++]; size++; const x = p % W, y = (p / W) | 0; sx += x; sy += y;
      if (x > 0 && op(p - 1) && label[p - 1] === -1) { label[p - 1] = id; stack[tail++] = p - 1; }
      if (x < W - 1 && op(p + 1) && label[p + 1] === -1) { label[p + 1] = id; stack[tail++] = p + 1; }
      if (y > 0 && op(p - W) && label[p - W] === -1) { label[p - W] = id; stack[tail++] = p - W; }
      if (y < H - 1 && op(p + W) && label[p + W] === -1) { label[p + W] = id; stack[tail++] = p + W; }
    }
    comps.push({ id, size, cx: sx / size, cy: sy / size });
  }
  if (comps.length <= 1) return;
  // score = distance-to-centre minus a size bonus → prefer the big, centred control over
  // a small edge-hugging neighbour fragment. Ignore specks (<1% area).
  const ccx = W / 2, ccy = H / 2;
  let best = -1, bestScore = Infinity;
  for (const k of comps) {
    if (k.size < N * 0.01) continue;
    const score = Math.hypot(k.cx - ccx, k.cy - ccy) - Math.sqrt(k.size) * 0.6;
    if (score < bestScore) { bestScore = score; best = k.id; }
  }
  if (best < 0) return;
  for (let i = 0; i < N; i++) if (label[i] !== best) d[i * 4 + 3] = 0;
  ctx.putImageData(img, 0, 0);
}

// Cut one control from the BiRefNet-isolated (transparent-background) strip: crop the
// cell sub-rect, drop neighbour/stray components, then trim to alpha bounds → tight sprite.
export function cutFromTransparentStrip(
  strip: HTMLCanvasElement, sx: number, sy: number, sw: number, sh: number,
): HTMLCanvasElement | null {
  const W = strip.width, H = strip.height;
  const ix = Math.max(0, Math.round(sx)), iy = Math.max(0, Math.round(sy));
  const iw = Math.min(W - ix, Math.round(sw)), ih = Math.min(H - iy, Math.round(sh));
  if (iw < 2 || ih < 2) return null;
  // 1. crop the cell sub-rect into its own canvas
  const cell = document.createElement("canvas");
  cell.width = iw; cell.height = ih;
  const cctx = cell.getContext("2d", { willReadFrequently: true });
  if (!cctx) return null;
  cctx.drawImage(strip, ix, iy, iw, ih, 0, 0, iw, ih);
  // 2. keep only the centre control component (drop neighbours / stray glyphs)
  keepCenterComponent(cell);
  // 3. trim to the remaining non-transparent bounds
  const d = cctx.getImageData(0, 0, iw, ih).data;
  let minx = iw, miny = ih, maxx = -1, maxy = -1;
  for (let y = 0; y < ih; y++) for (let x = 0; x < iw; x++) {
    if (d[(y * iw + x) * 4 + 3] > 16) { if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y; }
  }
  if (maxx < minx || maxy < miny) return null;
  const ow = maxx - minx + 1, oh = maxy - miny + 1;
  const out = document.createElement("canvas");
  out.width = ow; out.height = oh;
  out.getContext("2d")!.drawImage(cell, minx, miny, ow, oh, 0, 0, ow, oh);
  return out;
}

// PER-SPRITE SEGMENTATION (primary path): instead of slicing fixed grid cells, label ALL
// connected alpha components on the WHOLE BiRefNet-matted strip and assign each to the
// nearest expected control cell by centroid-x. Each control sprite = the union of the
// component(s) nearest its cell, cropped tight to those components' pixels only. This uses
// where controls ACTUALLY landed (robust to off-centre paint) and unions a multi-part
// control (knob + pointer dot); a cell that captures no component returns null so the
// caller falls back to the grid crop. `strip` is the matted bottom strip; cellRect is
// normalized to the FULL combined image, so a cell's centre-x in strip pixels is
// (cellRect.x + cellRect.w/2) * strip.width.
export function segmentStripByComponents(
  strip: HTMLCanvasElement,
  cells: BlueprintCell[],
): Record<string, HTMLCanvasElement | null> {
  const out: Record<string, HTMLCanvasElement | null> = {};
  for (const c of cells) out[c.bind] = null;
  const W = strip.width, H = strip.height, N = W * H;
  const ctx = strip.getContext("2d", { willReadFrequently: true });
  if (!ctx || N < 4 || !cells.length) return out;
  const d = ctx.getImageData(0, 0, W, H).data;
  const op = (i: number) => d[i * 4 + 3] > 40;
  // 1. label connected components (4-connectivity BFS) with bbox + centroid-x
  const label = new Int32Array(N).fill(-1), stack = new Int32Array(N);
  const comps: { id: number; size: number; cx: number; minx: number; miny: number; maxx: number; maxy: number }[] = [];
  for (let s = 0; s < N; s++) {
    if (!op(s) || label[s] !== -1) continue;
    const id = comps.length; let head = 0, tail = 0, size = 0, sx = 0;
    let minx = W, miny = H, maxx = 0, maxy = 0;
    stack[tail++] = s; label[s] = id;
    while (head < tail) {
      const p = stack[head++]; size++; const x = p % W, y = (p / W) | 0; sx += x;
      if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y;
      if (x > 0 && op(p - 1) && label[p - 1] === -1) { label[p - 1] = id; stack[tail++] = p - 1; }
      if (x < W - 1 && op(p + 1) && label[p + 1] === -1) { label[p + 1] = id; stack[tail++] = p + 1; }
      if (y > 0 && op(p - W) && label[p - W] === -1) { label[p - W] = id; stack[tail++] = p - W; }
      if (y < H - 1 && op(p + W) && label[p + W] === -1) { label[p + W] = id; stack[tail++] = p + W; }
    }
    comps.push({ id, size, cx: sx / size, minx, miny, maxx, maxy });
  }
  // 2. drop specks (<0.3% of strip area) — stray glyph bits / matte noise — and order L→R
  const real = comps.filter((c) => c.size >= N * 0.003).sort((a, b) => a.cx - b.cx);
  if (!real.length) return out;
  // 3. assign components to cells. The painter paints the N controls left-to-right in the
  // SAME order as the cells, so when the counts MATCH (the common case) order-based mapping
  // (blob i → cell i) is exact and never cross-assigns the way nearest-x can when a control
  // is painted slightly off-centre. Only when the counts DIFFER (the painter dropped/merged
  // a control, or matte noise) do we fall back to best-effort nearest-cell; cells that then
  // capture nothing return null and the caller uses the grid crop.
  const assigned: number[][] = cells.map(() => []);
  if (real.length === cells.length) {
    real.forEach((c, i) => assigned[i].push(c.id));
  } else {
    const cellCx = cells.map((c) => (c.cellRect[0] + c.cellRect[2] / 2) * W);
    for (const c of real) {
      let best = 0, bestD = Infinity;
      for (let j = 0; j < cellCx.length; j++) {
        const dd = Math.abs(c.cx - cellCx[j]);
        if (dd < bestD) { bestD = dd; best = j; }
      }
      assigned[best].push(c.id);
    }
  }
  // 4. per cell: union the assigned components' bbox, copy ONLY their pixels → tight sprite
  for (let j = 0; j < cells.length; j++) {
    const ids = assigned[j];
    if (!ids.length) continue;                 // null → caller falls back to grid crop
    const idset = new Set(ids);
    let minx = W, miny = H, maxx = 0, maxy = 0;
    for (const id of ids) {
      const c = real[real.findIndex((r) => r.id === id)];
      if (c.minx < minx) minx = c.minx; if (c.maxx > maxx) maxx = c.maxx;
      if (c.miny < miny) miny = c.miny; if (c.maxy > maxy) maxy = c.maxy;
    }
    const ow = maxx - minx + 1, oh = maxy - miny + 1;
    if (ow < 2 || oh < 2) continue;
    const o = document.createElement("canvas"); o.width = ow; o.height = oh;
    const octx = o.getContext("2d"); if (!octx) continue;
    const od = octx.createImageData(ow, oh);
    for (let y = 0; y < oh; y++) {
      for (let x = 0; x < ow; x++) {
        const si = (miny + y) * W + (minx + x);
        if (idset.has(label[si])) {
          const di = (y * ow + x) * 4;
          od.data[di] = d[si * 4]; od.data[di + 1] = d[si * 4 + 1];
          od.data[di + 2] = d[si * 4 + 2]; od.data[di + 3] = d[si * 4 + 3];
        }
      }
    }
    octx.putImageData(od, 0, 0);
    out[cells[j].bind] = o;
  }
  return out;
}

// ---- per-control sprite cut (port of /tmp/A_post_v3.py cut()) -------------------
// Crop the cell from the combined paint, then mask to the control's shape (ellipse
// for button/knob/toggle, rounded-rect for slider), slightly inset (1px) to avoid
// the white edge halo. cellRect is normalized to the FULL combined image.
// Bounding box of the painted control inside a strip cell: the largest run of
// non-white, non-transparent pixels. Background in the strip is white; the control
// is the colored content. Returns paint-pixel coords, or null if the cell looks empty.
export function detectCellContent(
  paint: HTMLCanvasElement, cx: number, cy: number, cw: number, ch: number,
): { x: number; y: number; w: number; h: number } | null {
  const ctx = paint.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  const ix = Math.max(0, Math.round(cx)), iy = Math.max(0, Math.round(cy));
  const iw = Math.min(paint.width - ix, Math.round(cw)), ih = Math.min(paint.height - iy, Math.round(ch));
  if (iw < 3 || ih < 3) return null;
  let d: Uint8ClampedArray;
  try { d = ctx.getImageData(ix, iy, iw, ih).data; } catch { return null; }
  let minx = iw, miny = ih, maxx = -1, maxy = -1, n = 0;
  for (let y = 0; y < ih; y++) {
    for (let x = 0; x < iw; x++) {
      const i = (y * iw + x) * 4;
      if (d[i + 3] < 24) continue;                       // transparent → background
      if (d[i] > 234 && d[i + 1] > 234 && d[i + 2] > 234) continue;  // near-white → background
      n++;
      if (x < minx) minx = x; if (x > maxx) maxx = x;
      if (y < miny) miny = y; if (y > maxy) maxy = y;
    }
  }
  // need a real blob (not a few stray pixels) covering a sane fraction of the cell
  if (maxx <= minx || maxy <= miny || n < 0.02 * iw * ih) return null;
  return { x: ix + minx, y: iy + miny, w: maxx - minx + 1, h: maxy - miny + 1 };
}

export function cutSprite(
  paint: HTMLCanvasElement,
  cellRect: [number, number, number, number],
  kind: SpriteKind,
): HTMLCanvasElement {
  const W = paint.width, H = paint.height;
  const [nx, ny, nw, nh] = cellRect;
  const cx = nx * W, cy = ny * H, cw = nw * W, ch = nh * H;

  // DETECT the control inside its cell rather than assuming it's centered. The model
  // doesn't reliably center each control in its blueprint cell — it often paints it
  // left/offset on the white strip gap, so a fixed centered crop grabbed control +
  // white → a white crescent. Find the bbox of non-white content in the cell and
  // center the crop on THAT. Falls back to the centered cell crop if nothing found
  // (e.g. a white/silver control whose pixels read as background).
  const bbox = detectCellContent(paint, cx, cy, cw, ch);

  let sw: number, sh: number, sx: number, sy: number;
  if (kind === "slider") {
    // crop TIGHT around the painted thumb/grip (the content bbox + 12%), NOT a wide
    // band — the strip part is the small slider thumb the renderer rides on the track.
    if (bbox) {
      sw = bbox.w * 1.12; sh = bbox.h * 1.12;
      sx = Math.round(bbox.x + bbox.w / 2 - sw / 2); sy = Math.round(bbox.y + bbox.h / 2 - sh / 2);
    } else {
      sw = cw * 0.5; sh = ch * 0.4;
      sx = Math.round(cx + (cw - sw) / 2); sy = Math.round(cy + (ch - sh) / 2);
    }
  } else if (bbox) {
    // round control: square centered on the detected control, sized to its larger
    // extent (+10% margin) so the circle clip contains the whole control — no white gap.
    const side = Math.max(bbox.w, bbox.h) * 1.1;
    sw = sh = side;
    sx = Math.round(bbox.x + bbox.w / 2 - side / 2);
    sy = Math.round(bbox.y + bbox.h / 2 - side / 2);
  } else {
    sw = sh = Math.min(cw, ch) * 0.92;
    sx = Math.round(cx + (cw - sw) / 2); sy = Math.round(cy + (ch - sh) / 2);
  }
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
export async function serverCutout(deviceCanvas: HTMLCanvasElement, model?: string): Promise<Blob> {
  const png = await canvasToBlob(deviceCanvas);
  const url = model ? `/api/cutout?model=${encodeURIComponent(model)}` : "/api/cutout";
  const r = await fetch(apiUrl(url), {
    method: "POST", headers: { "Content-Type": "image/png" }, body: png,
  });
  if (!r.ok) {
    const err = (await r.json().catch(() => null)) as { error?: string } | null;
    throw new Error(err?.error ?? `cutout → ${r.status}`);
  }
  return r.blob();
}

// A control cut "failed" if it's nearly empty (BiRefNet eroded a low-contrast control
// away — e.g. white-on-white) — too few opaque pixels to be a real control.
function cutLooksFailed(c: HTMLCanvasElement | null): boolean {
  if (!c || c.width < 4 || c.height < 4) return true;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  if (!ctx) return true;
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  let n = 0; for (let i = 0; i < c.width * c.height; i++) if (d[i * 4 + 3] > 40) n++;
  return n / (c.width * c.height) < 0.10;
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
  template?: Template;     // the input blueprint template (deterministic socket positions, as-is)
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
  template?: Template,
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

  // 1b. PLACEMENT = the blueprint/socket positions, AS-IS. The deterministic template
  //     rects ARE the load-bearing truth (per ai-image-coords-rule). We do NOT run a VLM
  //     snap here: in this architecture the controls are painted in the bottom STRIP and
  //     the device has EMPTY sockets, so sending the device frame to gpt-4o locates only
  //     the displays/screens that ARE on the body and snaps controls to garbage — worse
  //     than the known-good blueprint coords. So keep the blueprint template unchanged.
  const snapped = template;

  // 2. control sprites: BiRefNet-isolate the WHOLE strip ONCE (the same rembg model used
  //    for the device), giving a transparent-background strip, then cut each control by
  //    its cell + trim to alpha. This yields true-shape sprites with no halo, no imposed
  //    ellipse, and no text/divider bleed — background-agnostic (any strip colour). Falls
  //    back to the geometric cut if the BiRefNet strip pass fails.
  const spriteUrls: Record<string, string> = {};
  const W = paint.width, H = paint.height;
  const syOrig = Math.round(H * layout.devFrac), stripHOrig = Math.max(1, H - syOrig);
  const strip = cropStrip(paint, layout.devFrac);
  const cutFrom = (ts: HTMLCanvasElement, cellRect: [number, number, number, number]) => {
    const fx = ts.width / W, fy = ts.height / stripHOrig;
    const [nx, ny, nw, nh] = cellRect;
    return cutFromTransparentStrip(ts, nx * W * fx, (ny * H - syOrig) * fy, nw * W * fx, nh * H * fy);
  };
  // Use the HEAVY BiRefNet model by default (segments low-contrast controls best) — no
  // light-first pass. (Per request: heavy every time, even before any contrast tune.)
  let tstrip: HTMLCanvasElement | null = null;
  try { tstrip = await blobToCanvas(await serverCutout(strip, "General Use (Heavy)")); } catch { tstrip = null; }
  // PRIMARY: connected-component segmentation of the whole matted strip (assign each blob
  // to the nearest control cell, union per cell). Robust to off-centre paint + multi-part
  // controls; uses where controls actually landed, not an assumed grid.
  const sprites: Record<string, HTMLCanvasElement | null> =
    tstrip ? segmentStripByComponents(tstrip, layout.cells) : {};
  // Upload: prefer the component-segmented sprite; fall back to the per-cell grid crop, then
  // the geometric cut, if a control captured no component / looks failed.
  for (const cell of layout.cells) {
    try {
      let sprite = sprites[cell.bind] ?? null;
      if (cutLooksFailed(sprite)) sprite = tstrip ? cutFrom(tstrip, cell.cellRect) : null;
      if (cutLooksFailed(sprite)) sprite = cutSprite(paint, cell.cellRect, cell.kind);
      if (!sprite) continue;
      spriteUrls[cell.bind] = await uploadSprite(id, cell.bind, await canvasToBlob(sprite));
    } catch { /* skip this sprite; app falls back to donor for this bind */ }
  }

  return {
    frameUrl: apiUrl(durableFrameUrl),
    sprites: Object.keys(spriteUrls).length > 0,
    spriteUrls,
    template: snapped,
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
