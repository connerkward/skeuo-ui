// observe_drive — headless driver for observe12.py ([[skin-observation-rule]]).
// Loads the served player, screenshots the #phone stage, exercises the REAL handlers
// (seek jump, toggle click, knob pointer-drag, button click), screenshots again.
// Usage: node observe_drive.mjs <playerUrl> <outDir>
import { chromium } from 'playwright';
import path from 'node:path';

const [url, out] = process.argv.slice(2);
const b = await chromium.launch();
const pg = await b.newPage({ viewport: { width: 900, height: 1100 } });
await pg.goto(url);
await pg.waitForFunction("document.querySelectorAll('#phone .pbtn').length > 0", { timeout: 20000 });
await pg.waitForTimeout(2500); // sprite decode + seat
const phone = pg.locator('#phone');
await phone.screenshot({ path: path.join(out, 'full.png') });

await pg.evaluate('window.__seek && window.__seek(0.55)');
// dispatch DOM clicks — model layouts can overlap control divs, making strict pointer
// clicks flaky ("<other pbtn> intercepts pointer events"); the players' handlers are
// plain 'click' listeners, so el.click() exercises the same real code path.
const tog = pg.locator('#phone .ptog');
if (await tog.count()) await tog.first().evaluate(e => e.click());
const knob = pg.locator('#phone .pknob');
if (await knob.count()) {
  const bb = await knob.first().boundingBox();
  const cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;
  await pg.mouse.move(cx, cy); await pg.mouse.down();
  await pg.mouse.move(cx, cy - 40, { steps: 8 }); await pg.mouse.up();
}
const btn = pg.locator('#phone .pbtn');
if (await btn.count()) await btn.first().evaluate(e => e.click());
await pg.waitForTimeout(400);
await phone.screenshot({ path: path.join(out, 'after.png') });
await b.close();
console.log('[observe_drive] wrote full.png + after.png');
