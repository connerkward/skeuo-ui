// Offline smoke test: layouts → blueprint/mask SVG → PNG → composite.
// No fal calls. Verifies the rasterizer + compositor + layout math.
import { Resvg } from "@resvg/resvg-js";
import UPNG from "upng-js";
import { writeFileSync } from "node:fs";
import { regionsForVariant, LAYOUT_VARIANTS } from "../src/generate/layouts";
import { wellsOnlySvg, regionMaskSvg } from "../src/generate/blueprint";

const raster = (svg: string) => new Uint8Array(new Resvg(svg, { fitTo: { mode: "original" } }).render().asPng());
const toAB = (u: Uint8Array) => u.buffer.slice(u.byteOffset, u.byteOffset + u.byteLength) as ArrayBuffer;

for (const v of LAYOUT_VARIANTS) {
  const regs = regionsForVariant(v);
  const wells = raster(wellsOnlySvg(regs));
  const mask = raster(regionMaskSvg(regs));
  writeFileSync(`/tmp/smoke-${v}-wells.png`, wells);
  writeFileSync(`/tmp/smoke-${v}-mask.png`, mask);
  // composite a fake "paint" (solid blue) with the mask to prove alpha works
  const W = 1024, H = 1536;
  const paint = new Uint8Array(W * H * 4);
  for (let i = 0; i < W * H; i++) { paint[i * 4] = 40; paint[i * 4 + 1] = 90; paint[i * 4 + 2] = 200; paint[i * 4 + 3] = 255; }
  const paintPng = new Uint8Array(UPNG.encode([paint.buffer], W, H, 0));
  const p = UPNG.decode(toAB(paintPng)); const pr = new Uint8Array(UPNG.toRGBA8(p)[0]);
  const a = UPNG.decode(toAB(mask)); const ar = new Uint8Array(UPNG.toRGBA8(a)[0]);
  for (let i = 0; i < W * H; i++) pr[i * 4 + 3] = ar[i * 4];
  const out = new Uint8Array(UPNG.encode([pr.buffer], W, H, 0));
  writeFileSync(`/tmp/smoke-${v}-composite.png`, out);
  // count opaque pixels as a sanity metric
  let opaque = 0; for (let i = 0; i < W * H; i++) if (pr[i * 4 + 3] > 128) opaque++;
  console.log(`${v}: ${regs.length} regions, wells ${wells.length}B, mask opaque ${(100 * opaque / (W * H)).toFixed(1)}%`);
}
console.log("smoke ok → /tmp/smoke-*.png");
