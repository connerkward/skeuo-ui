// Bake skin THUMBNAILS that include the live-rendered controls (buttons, knobs,
// dials, screen) — not just the bare frame art. The old thumbs were a plain
// resize of frame.png, which has EMPTY control wells, so the gallery minis looked
// hollow. Here we load the real <Composite> for each skin, hide ONLY the
// visualizer canvas (the gallery/mobile overlay their own live spectrum on top,
// so a baked one would double up), and screenshot the player on a transparent
// background → 256-wide WebP, same path the old thumbs used.
//
//   node scripts/bake-thumbs.mjs [port] [skin1,skin2,...]
//
// Requires the dev server running (npm run dev). With no skin list it bakes every
// public/skins/<id>/ that has a frame.png.
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { readdirSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const PORT = process.argv[2] || "5173";
const ONLY = (process.argv[3] || "").split(",").filter(Boolean);
const BASE = `http://127.0.0.1:${PORT}/`;
const SKINS_DIR = "public/skins";
const TMP = "/tmp/bake-thumbs";
mkdirSync(TMP, { recursive: true });

const ids = (ONLY.length ? ONLY : readdirSync(SKINS_DIR))
  .filter((id) => existsSync(join(SKINS_DIR, id, "frame.png")));

console.log(`baking ${ids.length} thumbnails from ${BASE} …`);

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2 });
let ok = 0, fail = 0;
for (const id of ids) {
  const page = await ctx.newPage();
  try {
    await page.goto(`${BASE}?skin=${encodeURIComponent(id)}`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForSelector(".player .frame-layer", { timeout: 15000 });
    await page.waitForTimeout(1400);                       // let sprites + screen settle
    // GUARD: the app falls back to the first skin when ?skin= names an unknown /
    // hidden id, and re-syncs the URL to whatever actually rendered. If it didn't
    // load the skin we asked for, skip it — never overwrite its thumb with another.
    const got = await page.evaluate(() => new URL(location.href).searchParams.get("skin"));
    if (got !== id) { process.stdout.write(`  – ${id} (skipped: resolved to ${got})\n`); await page.close(); continue; }
    // isolate the player: hide the app chrome (so nothing bleeds into the
    // transparent areas of the player box) and the live visualizer canvas (the
    // gallery/mobile overlay their own spectrum, so a baked one would double up)
    await page.addStyleTag({ content: `
      .topbar, .gallery, .stage-meta, .stage::before, .stage::after { display: none !important; }
      .stage { box-shadow: none !important; background: transparent !important; }
      .player canvas { visibility: hidden !important; }
    ` });
    await page.waitForTimeout(150);
    const el = await page.$(".player");
    const png = join(TMP, `${id}.png`);
    await el.screenshot({ path: png, omitBackground: true });
    execFileSync("magick", [png, "-resize", "256x", "-quality", "84",
      "-define", "webp:method=6", join(SKINS_DIR, id, "thumb.webp")]);
    ok++; process.stdout.write(`  ✓ ${id}\n`);
  } catch (e) {
    fail++; process.stdout.write(`  ✗ ${id} — ${e.message.split("\n")[0]}\n`);
  } finally {
    await page.close();
  }
}
await browser.close();
console.log(`done: ${ok} baked, ${fail} failed`);
