// record_pbr.mjs — stepped frame-by-frame demo capture of pbrtest2 (the
// emissive self-lighting PBR page). The page's draw(t) is a pure function of
// (state, t) and its WebGL context keeps the drawing buffer, so the recorder
// owns the clock: ?freeze= disables the page's own rAF loop, and each output
// frame sets the light/knob state directly (exactly what the pointermove and
// slider handlers set) and calls draw(t) with t advancing 1/30 s — fully
// deterministic, no wall-clock, no dropped frames. Screenshots are taken at
// deviceScaleFactor 2 and downscaled to the 1920×1080 CSS viewport (crisp).
//
// segments (34 s total @ 30 fps):
//   A 0–8 s    hero: emissive pulse (ember flicker), light in a gentle drift
//   B 8–18 s   pointer light sweeps two full orbits around the faceplate
//   C 18–26 s  knob (independent cut part) rotates −150°→150°, light parked
//   D 26–34 s  glass close-up: light orbits the glass — dynamic vs baked reflection
//
// usage: node record_pbr.mjs <serverURL> <framesRoot>
import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { join } from "path";

const BASE = process.argv[2];
const OUT = process.argv[3];
const dir = join(OUT, "frames-demo-emissive");
mkdirSync(dir, { recursive: true });

const FPS = 30, DUR = 34, T0 = 2.5;           // T0 = the page's default freezeT
const ease = (u) => 0.5 - 0.5 * Math.cos(Math.PI * u);

// per-frame script: seg → { lx, ly, k(deg), glass(bool: scrolled to close-up) }
function stateAt(sec) {
  if (sec < 8) {          // A — emissive pulse, gentle light drift
    const u = sec / 8;
    return { lx: 0.5 + 0.08 * Math.cos(2 * Math.PI * u), ly: 0.30 + 0.05 * Math.sin(2 * Math.PI * u), k: 0, glass: false };
  }
  if (sec < 18) {         // B — two full light orbits
    const u = (sec - 8) / 10, th = 2 * Math.PI * 2 * u - Math.PI / 2;
    return { lx: 0.5 + 0.40 * Math.cos(th), ly: 0.5 + 0.40 * Math.sin(th), k: 0, glass: false };
  }
  if (sec < 26) {         // C — knob sweep, light parked upper-left
    const u = (sec - 18) / 8;
    return { lx: 0.32, ly: 0.22, k: -150 + 300 * ease(u), glass: false };
  }
  {                       // D — glass close-up: light ping-pongs along the
    // empirically-probed "good band" diagonal (0.38,0.52)↔(0.56,0.60), where
    // the reflection streak on the glass is visible AND moving. Probed on the
    // real page: the gzA/gzB extremes read near-black, directly over the glass
    // blows out white — this diagonal is the band in between.
    const u = (sec - 26) / 8, s = 0.5 + 0.5 * Math.sin(2 * Math.PI * 2 * u);
    return { lx: 0.38 + 0.18 * s, ly: 0.52 + 0.08 * s, k: 150, glass: true };
  }
}

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });

// freeze= kills the page's own rAF loop; we call draw(t) ourselves
await page.goto(`${BASE}/pbrtest2/index.html?skin=diablo&freeze=${T0}`);
await page.waitForFunction(() => document.title === "pbrtest2 ready", null, { timeout: 60_000, polling: 200 });
// framing: whole player visible in the 1080p viewport, composition centered
await page.addStyleTag({ content: `
  .stage { max-width: 700px; }
  .wrap, .glasswrap { justify-content: center; }
  ::-webkit-scrollbar { display: none; }
` });
await page.evaluate(() => { resize(); window.scrollTo(0, 0); });

const t0 = Date.now();
let scrolledGlass = false;
for (let n = 0; n < DUR * FPS; n++) {
  const sec = n / FPS;
  const s = stateAt(sec);
  if (s.glass !== scrolledGlass) {
    scrolledGlass = s.glass;
    await page.evaluate((g) => {
      if (g) document.querySelector(".glasswrap").scrollIntoView({ block: "center" });
      else window.scrollTo(0, 0);
    }, s.glass);
  }
  await page.evaluate(([t, lx, ly, kdeg]) => {
    state.lx = lx; state.ly = ly; state.k = kdeg * Math.PI / 180;
    // mirror the knob slider UI so the on-screen control matches the render
    const el = document.getElementById("k"); el.value = kdeg;
    document.getElementById("vK").textContent = Math.round(kdeg) + "°";
    draw(t);
  }, [T0 + sec, s.lx, s.ly, s.k]);
  await page.screenshot({ path: join(dir, String(n).padStart(5, "0") + ".png"), scale: "css" });
}
await ctx.close();
await browser.close();
console.log(`demo-emissive: ${DUR * FPS} frames (${DUR}s @ ${FPS}fps) captured in ${((Date.now() - t0) / 1000) | 0}s` +
  (errs.length ? `  PAGE ERRORS: ${errs.join(" | ")}` : ""));
if (errs.length) process.exitCode = 1;
