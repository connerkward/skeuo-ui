// render_knob.mjs — throwaway isolated Playwright driver for the knob-zero closed-loop
// measurement. For one skin: loads the REAL served player.html (own chromium.launch(), not
// the shared browser), captures the .pknob .cap element at init (val=0.5, the page's default,
// no interaction needed) and, via real pointer drag through the SAME handlers the user drives,
// at min (val=0) and max (val=1). Screenshots are exact element-bbox crops at high
// deviceScaleFactor so the downstream angle detector sees real anti-aliased pixels, not a
// re-derived geometry.
// Usage: node render_knob.mjs <playerUrl> <outDir> <skinId>
import { chromium } from 'playwright';
import path from 'node:path';

const [url, out, sid] = process.argv.slice(2);
const b = await chromium.launch();
const pg = await b.newPage({ viewport: { width: 900, height: 1100 }, deviceScaleFactor: 4 });
await pg.goto(url);
await pg.waitForFunction("document.querySelector('#phone .pknob .cap') !== null", { timeout: 20000 });
await pg.waitForTimeout(1200); // sprite decode + seat

const cap = pg.locator('#phone .pknob .cap');
if (await cap.count() === 0) {
  console.log(JSON.stringify({ sid, error: 'no-knob' }));
  await b.close();
  process.exit(0);
}

// init — page default, val=0.5, no interaction
await cap.screenshot({ path: path.join(out, `${sid}-live-init.png`) });

// drag to min (val=0) / max (val=1) via the REAL pointer handlers, same mechanism as
// observe_drive.mjs's knob drag. val = sv + (sy - clientY)/160, sv starts at 0.5.
const knob = pg.locator('#phone .pknob');
const bb = await knob.boundingBox();
const cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;

async function dragTo(dyFromStart) {
  await pg.mouse.move(cx, cy);
  await pg.mouse.down();
  await pg.mouse.move(cx, cy + dyFromStart, { steps: 12 });
  await pg.mouse.up();
  await pg.waitForTimeout(120);
}

await dragTo(80); // val -> 0
await cap.screenshot({ path: path.join(out, `${sid}-live-min.png`) });
await dragTo(-160); // from val=0, move up 160 -> val=1
await cap.screenshot({ path: path.join(out, `${sid}-live-max.png`) });
// reset back toward init for cleanliness (not strictly needed, page is throwaway)

await b.close();
console.log(JSON.stringify({ sid, ok: true }));
