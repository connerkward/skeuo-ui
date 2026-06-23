// Browser-side alpha cutout — the second half of the deferred-cutout pipeline.
//
// /api/generate (the CF Pages Function) can't run the cutout itself: it is ~2s of
// pure-JS CPU (UPNG decode/encode + cutoutAlpha connected-components/flood-fill)
// and trips the Function CPU ceiling → CF 1102. So the Worker returns the RAW
// paint (needsCutout + paintUrl); here we key out the white background using the
// SAME shared cutoutAlpha, then upload the finished frame.png back to R2 via
// /api/finalize/<id>. The browser has no CPU limit, so the 2s is harmless.
//
// CORS: paintUrl is same-origin (/api/asset/…) or a data: URL, so drawing it to a
// canvas never taints it and getImageData works. (A cross-origin fal URL WOULD
// taint the canvas — that's why /api/generate routes the paint through our own R2.)
import { cutoutAlpha } from "./blueprint";
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

// Fetch the raw paint, key out the near-white background, return a PNG Blob of the
// cut RGBA frame (white → transparent, largest component kept, holes filled).
export async function cutoutPaintToFrame(paintUrl: string): Promise<Blob> {
  // apiUrl() makes paths absolute under the native shells (tauri:// origin) so the
  // cross-origin fetch hits skeuo.fm; on the web it stays same-origin. The asset
  // endpoint sends CORS headers so the fetched paint is readable into the canvas.
  //
  // Retry fetch+decode: the paint can be momentarily unavailable right after
  // generation — the two-step write window (Worker stores paint, then we read it),
  // a CDN edge that hasn't filled, or dev static-serving lag — and come back as a
  // non-image (a 404 page or the SPA index.html). A few short retries turn that
  // transient into a success instead of a hard "could not be decoded".
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

  const img = ctx.getImageData(0, 0, W, H);
  // a Uint8Array VIEW over the same buffer ImageData owns — read RGBA via the view,
  // write the computed alpha straight back into img.data (no copy).
  const rgba = new Uint8Array(img.data.buffer, img.data.byteOffset, img.data.byteLength);
  const alpha = cutoutAlpha(rgba, W, H);
  for (let i = 0; i < W * H; i++) img.data[i * 4 + 3] = alpha[i];
  ctx.putImageData(img, 0, 0);

  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("canvas.toBlob failed"))), "image/png"));
}

// Upload the cut frame to R2 so the skin is durable + shareable. Returns the public
// frame URL on success. /api/finalize is write-once and gated on a prior generation.
export async function uploadFrame(id: string, frame: Blob): Promise<string> {
  const r = await fetch(apiUrl(`/api/finalize/${encodeURIComponent(id)}`), {
    method: "POST", headers: { "Content-Type": "image/png" }, body: frame,
  });
  const out = (await r.json().catch(() => null)) as { frameUrl?: string; error?: string } | null;
  if (!r.ok || !out?.frameUrl) throw new Error(out?.error ?? `finalize → ${r.status}`);
  return out.frameUrl;
}

// Full client half of a generation when the server deferred the cutout. Returns the
// frameUrl to USE/PERSIST: the durable (absolute-on-native) R2 URL after upload, or
// — in the demo path (paintUrl is a data: URL, no R2) — an in-memory object URL of
// the cut frame. apiUrl() keeps the persisted URL reachable from the native shell.
export async function finishCutout(id: string, paintUrl: string, durableFrameUrl: string): Promise<string> {
  const frame = await cutoutPaintToFrame(paintUrl);
  if (paintUrl.startsWith("data:")) return URL.createObjectURL(frame); // demo: no R2 to upload to
  await uploadFrame(id, frame);
  return apiUrl(durableFrameUrl);
}
