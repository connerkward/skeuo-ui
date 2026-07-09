// record.mjs — drive capture.html through Playwright's built-in video recording.
// One context per (panel × aspect), viewport = exact output size, records ≥2 full
// animation loops (loop end detected via the caption returning to PHASE 1 — robust
// to whatever rAF rate the recorder achieves). Emits .webm; convert.sh turns them
// into H.264 mp4 + poster PNGs.
//
// usage: node record.mjs <serverURL> <outDir> [panel ...]
import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { join } from "path";

const BASE = process.argv[2];                 // e.g. http://localhost:54731
const OUT = process.argv[3];
const ONLY = process.argv.slice(4);
mkdirSync(OUT, { recursive: true });

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

const browser = await chromium.launch();
for (const p of PANELS) {
  for (const a of ASPECTS) {
    const name = `${p.anim}-${a.tag}`;
    const t0 = Date.now();
    const ctx = await browser.newContext({
      viewport: { width: a.w, height: a.h },
      deviceScaleFactor: 1,
      recordVideo: { dir: OUT, size: { width: a.w, height: a.h } },
    });
    const page = await ctx.newPage();
    const errs = [];
    page.on("pageerror", (e) => errs.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });

    await page.goto(`${BASE}/animexport/capture.html?anim=${p.anim}&aspect=${a.tag}`);
    // interval polling everywhere — the page throttles rAF to 60Hz for pacing,
    // so rAF-based polling must not be relied on
    await page.waitForFunction(() => window.__ready, null, { polling: 100 });
    await page.evaluate(() => window.__start());
    // animation actually running = its phase caption is on screen
    await page.waitForFunction(
      (id) => /^PHASE/.test(document.getElementById(id)?.textContent || ""),
      `anim-${p.anim}-cap`, { timeout: 30_000, polling: 200 });
    // ≥2 full loops (loop 3 has begun), generous cap for slow recording rAF
    await page.waitForFunction(() => window.__loops >= 2,
      null, { timeout: Math.max(120_000, p.loopSec * 2 * 4 * 1000), polling: 500 });
    await page.waitForTimeout(400);           // small tail

    const video = page.video();
    await ctx.close();                        // finalizes the webm
    await video.saveAs(join(OUT, `${name}.webm`));
    console.log(`${name}.webm  ${(Date.now() - t0) / 1000 | 0}s recorded` +
      (errs.length ? `  PAGE ERRORS: ${errs.join(" | ")}` : ""));
    if (errs.length) process.exitCode = 1;
  }
}
await browser.close();
