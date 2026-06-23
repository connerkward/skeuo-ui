// Node test for spriteSheet.ts — decode the test PNGs (upng-js + pako, both dev
// deps already in node_modules), run the alignment pipeline, write the result,
// and assert every sprite_control matched a DISTINCT socket.
//
// Run:  node src/generate/spriteSheet.test.mjs
// (Node >= 22.6 strips TS types from the imported .ts module natively.)

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import UPNG from "upng-js";

import {
  alignSpriteSheet,
} from "./spriteSheet.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const MASKED = "/tmp/sheet-masked.png";
const COMBINED = "/tmp/sheet-out.png";
const LAYOUT = "/tmp/sheet-layout.json";
const RESULT = "/tmp/spritesheet-ts-result.png";

function decodePNG(file) {
  const buf = fs.readFileSync(file);
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const img = UPNG.decode(ab);
  const frames = UPNG.toRGBA8(img); // array of ArrayBuffers, one per frame
  const data = new Uint8ClampedArray(frames[0]);
  return { data, width: img.width, height: img.height };
}

function encodePNG(rgba, file) {
  const ab = UPNG.encode(
    [rgba.data.buffer.slice(rgba.data.byteOffset, rgba.data.byteOffset + rgba.data.byteLength)],
    rgba.width,
    rgba.height,
    0, // lossless
  );
  fs.writeFileSync(file, Buffer.from(ab));
}

function assert(cond, msg) {
  if (!cond) {
    console.error("ASSERT FAILED:", msg);
    process.exitCode = 1;
    throw new Error(msg);
  }
}

// ---------------------------------------------------------------------------

const layout = JSON.parse(fs.readFileSync(LAYOUT, "utf8"));
const masked = decodePNG(MASKED);
const combined = decodePNG(COMBINED);

console.log(
  `layout: W=${layout.W} H=${layout.H} DEV_H=${layout.DEV_H} ` +
    `sprites=[${layout.sprite_controls.join(",")}]`,
);
console.log(`masked   ${masked.width}x${masked.height}`);
console.log(`combined ${combined.width}x${combined.height}`);

const { frame, device, sprites, sockets, matches } = alignSpriteSheet(
  combined,
  masked,
  layout,
);

console.log(`device crop: ${device.width}x${device.height}`);
console.log(`detected ${sockets.length} sockets (screens filtered out):`);
for (const s of sockets) {
  console.log(
    `  socket @ (${s.cx.toFixed(0)},${s.cy.toFixed(0)}) r=${s.r.toFixed(0)} ` +
      `area=${s.area} aspect=${s.aspect.toFixed(2)}`,
  );
}

console.log("sprite cut sizes:");
for (const id of layout.sprite_controls) {
  const sp = sprites[id];
  console.log(`  ${id}: ${sp ? `${sp.w}x${sp.h}` : "MISSING"}`);
}

console.log("matches (bind -> socket center):");
const matchedIds = Object.keys(matches);
const socketKeys = new Set();
for (const id of layout.sprite_controls) {
  const m = matches[id];
  if (m) {
    const key = `${Math.round(m.cx)},${Math.round(m.cy)}`;
    socketKeys.add(key);
    console.log(`  ${id} -> (${m.cx.toFixed(0)}, ${m.cy.toFixed(0)}) r=${m.r.toFixed(0)}`);
  } else {
    console.log(`  ${id} -> UNMATCHED`);
  }
}

encodePNG(frame, RESULT);
console.log(`wrote result -> ${RESULT} (${frame.width}x${frame.height})`);

// ---- assertions ----
const wantN = layout.sprite_controls.length;

// every sprite-control was cut
for (const id of layout.sprite_controls) {
  assert(sprites[id] && sprites[id].w > 1 && sprites[id].h > 1, `sprite ${id} cut`);
}

// every sprite-control matched something
assert(
  matchedIds.length === wantN,
  `all ${wantN} sprite_controls matched (got ${matchedIds.length})`,
);

// matches are to DISTINCT sockets
assert(
  socketKeys.size === wantN,
  `each matched socket is distinct (got ${socketKeys.size} distinct of ${wantN})`,
);

console.log("\nALL ASSERTIONS PASSED");
