// record.mjs — stepped FRAME-BY-FRAME capture of capture.html (NO Playwright
// recordVideo — that path re-encodes at viewport scale and ships soft, starved
// video; it is banned for canvas content). The page runs with ?stepped=1 so the
// recorder owns the animation clock: each captured frame advances the page's
// rAF queue exactly 2 ticks (2 × 1000/60 ms = 33.33 ms of designed time), then
// grabs a lossless viewport PNG at the exact output resolution. convert.sh
// encodes the numbered PNGs with libx264 crf15.
//
// usage: node record.mjs <serverURL> <framesRoot> [panel ...]
import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { join } from "path";

const BASE = process.argv[2];                 // e.g. http://localhost:54731
const OUT = process.argv[3];                  // frames root (transient)
const ONLY = process.argv.slice(4);
mkdirSync(OUT, { recursive: true });

const FPS = 30, TICKS_PER_FRAME = 2;          // panels are designed at 60Hz
const PANELS = [
  { anim: "knob",   loopSec: 8 },
  { anim: "travel", loopSec: 10 },
  { anim: "pca",    loopSec: 18 },
  { anim: "iou",    loopSec: 14 },
].filter((p) => !ONLY.length || ONLY.includes(p.anim));
const ASPECTS = [
  { tag: "16x9", w: 1920, h: 1080 },
  { tag: "3x4",  w: 1080, h: 1440 },
];
const TAIL = 15;                              // frames after loop 2 completes

const browser = await chromium.launch();
for (const p of PANELS) {
  for (const a of ASPECTS) {
    const name = `${p.anim}-${a.tag}`;
    const dir = join(OUT, `frames-${name}`);
    mkdirSync(dir, { recursive: true });
    const t0 = Date.now();
    const ctx = await browser.newContext({
      viewport: { width: a.w, height: a.h },
      deviceScaleFactor: 1,
    });
    const page = await ctx.newPage();
    const errs = [];
    page.on("pageerror", (e) => errs.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });

    await page.goto(`${BASE}/animexport/capture.html?anim=${p.anim}&aspect=${a.tag}&stepped=1`);
    await page.waitForFunction(() => window.__ready, null, { polling: 100 });
    await page.evaluate(() => window.__start());
    // the panel draws only once its artifact images load (async, real time) —
    // pump one tick per poll until its first phase caption is on screen
    await page.waitForFunction((id) => {
      window.__tick(1);
      return /^PHASE/.test(document.getElementById(id)?.textContent || "");
    }, `anim-${p.anim}-cap`, { timeout: 60_000, polling: 100 });

    // frame loop: step 33.33ms → screenshot, until ≥2 full loops (+ tail)
    const maxFrames = FPS * p.loopSec * 2 * 3 + 600;   // generous safety cap
    let n = 0, done = -1;
    while (n < maxFrames) {
      // __loops read is one frame stale by design (MutationObserver microtask
      // timing) — harmless, the tail more than covers it
      const loops = await page.evaluate((k) => { window.__tick(k); return window.__loops; }, TICKS_PER_FRAME);
      await page.screenshot({ path: join(dir, String(n).padStart(5, "0") + ".png") });
      n++;
      if (done < 0 && loops >= 2) done = n;
      if (done >= 0 && n >= done + TAIL) break;
    }
    await ctx.close();
    const complete = done >= 0;
    console.log(`${name}: ${n} frames (${(n / FPS).toFixed(1)}s @ ${FPS}fps) captured in ${((Date.now() - t0) / 1000) | 0}s` +
      (complete ? "" : "  INCOMPLETE: 2 loops not reached") +
      (errs.length ? `  PAGE ERRORS: ${errs.join(" | ")}` : ""));
    if (!complete || errs.length) process.exitCode = 1;
  }
}
await browser.close();
