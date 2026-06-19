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

// Fetch the raw paint, key out the near-white background, return a PNG Blob of the
// cut RGBA frame (white → transparent, largest component kept, holes filled).
export async function cutoutPaintToFrame(paintUrl: string): Promise<Blob> {
  // apiUrl() makes paths absolute under the native shells (tauri:// origin) so the
  // cross-origin fetch hits skeuo.fm; on the web it stays same-origin. The asset
  // endpoint sends CORS headers so the fetched paint is readable into the canvas.
  const res = await fetch(apiUrl(paintUrl));
  if (!res.ok) throw new Error(`fetch paint → ${res.status}`);
  const bmp = await createImageBitmap(await res.blob());
  const W = bmp.width, H = bmp.height;
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) { bmp.close?.(); throw new Error("no 2d canvas context"); }
  ctx.drawImage(bmp, 0, 0);
  bmp.close?.();

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
