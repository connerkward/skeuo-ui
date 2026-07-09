// record_social.mjs — stepped frame-by-frame capture of pbrtest3/social.html
// (1080x1920 9:16 social cut, 30 fps, ~20 s). Same discipline as record_pbr.mjs:
// the recorder owns the clock (?freeze= kills the page rAF), sets the full
// light/knob/press/zoom state per frame inside the REAL renderer iframe, calls
// draw(t), screenshots. ?bpm=128 beat-locks the ember pulse + viz bars.
//
// choreography (20 s @ 30 fps = 600 frames), all eased — catmull-rom spline
// through waypoints for the light path (no linear moves, no teleports):
//   A 0.0–8.0   scripted light path: sweeps in, RAKES ACROSS BOTH TOP SKULLS
//               (low light height so the relief pops), arcs over the ember
//               spikes and body, lands near the knob
//   B 8.0–12.0  volume knob sweep −140°→140° (eased), light orbits the knob so
//               the highlight travels on the brushed cap
//   C 12.0–16.5 play press (button physically depresses) → visualizer bars leap
//               on the 128-BPM grid, spilling light on the bezel; shuffle
//               switch flicks ON at 15.4 (the fixed vertical lever)
//   D 16.5–20.0 glass close-up: eased zoom into the twin glass panes, light
//               ping-pongs so the reflection streak moves across the glass
//
// usage: node record_social.mjs <serverURL> <framesRoot>
import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { join } from "path";

const BASE = process.argv[2];
const OUT = process.argv[3];
const AR11 = process.env.AR === "1x1";       // AR=1x1 -> 1080x1080 feed cut, same choreography
const dir = join(OUT, AR11 ? "frames-social-1x1" : "frames-social-9x16");
mkdirSync(dir, { recursive: true });

const FPS = 30, DUR = 20;
const BPM = 128;
const T0 = 2.8125;                       // 6 whole beats @128 -> frame 0 lands ON a beat (mid-glow)
const ease = (u) => 0.5 - 0.5 * Math.cos(Math.PI * Math.min(1, Math.max(0, u)));

// --- light path: catmull-rom through (time, lx, ly, h) waypoints -------------
const WP = [
  [-0.8, 0.62, 0.06, 0.40],   // lead-in (off-frame feel: high + right)
  [ 0.0, 0.46, 0.12, 0.34],   // frame 0: already sweeping
  [ 1.3, 0.24, 0.175, 0.15],  // SKULL top-left — raking
  [ 2.4, 0.50, 0.13, 0.22],   // crest over the transport cluster
  [ 3.5, 0.76, 0.175, 0.15],  // SKULL top-right — raking
  [ 4.8, 0.86, 0.42, 0.20],   // right ember spikes
  [ 6.0, 0.52, 0.56, 0.30],   // arc across the body
  [ 7.0, 0.20, 0.42, 0.22],   // left ember ridge
  [ 8.0, 0.58, 0.38, 0.26],   // hand-off toward the knob
];
function catmull(ts) {
  let i = 1;
  while (i < WP.length - 2 && WP[i + 1][0] < ts) i++;
  const [p0, p1, p2, p3] = [WP[i - 1], WP[i], WP[i + 1], WP[Math.min(i + 2, WP.length - 1)]];
  const u = Math.min(1, Math.max(0, (ts - p1[0]) / (p2[0] - p1[0])));
  const out = [];
  for (let k = 1; k <= 3; k++) {
    const a = p1[k], b = p2[k];
    const m1 = (b - p0[k]) / (p2[0] - p0[0]) * (p2[0] - p1[0]);
    const m2 = (p3[k] - a) / (p3[0] - p1[0]) * (p2[0] - p1[0]);
    const u2 = u * u, u3 = u2 * u;
    out.push((2 * u3 - 3 * u2 + 1) * a + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * b + (u3 - u2) * m2);
  }
  return out;   // [lx, ly, h]
}

const KNOB = { x: 0.7088, y: 0.4766 };
const GLASS = { x: 0.54, y: 0.715 };

function stateAt(sec) {
  const s = { k: 0, press: 0, playing: false, shuffle: false, zx: 0, zy: 0, zs: 0 };
  if (sec < 8) {                    // A — spline light path over the skulls
    [s.lx, s.ly, s.h] = catmull(sec);
  } else if (sec < 12) {            // B — knob sweep, light orbits the knob
    const u = (sec - 8) / 4, th = Math.PI * (1.15 - 1.3 * ease(u));
    s.lx = KNOB.x + 0.16 * Math.cos(th); s.ly = KNOB.y - 0.13 * Math.sin(th); s.h = 0.20;
    s.k = -140 + 280 * ease(u);
  } else {                          // C+D share knob end-state
    s.k = 140;
    if (sec < 16.5) {               // C — play press, beat bars, light drifts to viz
      // park at (0.46, 0.56): above the glass panes — directly over them blows out white
      const u = ease((sec - 12) / 4.5);
      s.lx = KNOB.x + 0.16 * Math.cos(Math.PI * -0.15) - (KNOB.x + 0.16 * Math.cos(Math.PI * -0.15) - 0.46) * u;
      s.ly = KNOB.y + 0.13 * Math.sin(Math.PI * 0.15) + (0.56 - KNOB.y - 0.13 * Math.sin(Math.PI * 0.15)) * u;
      s.h = 0.20 + 0.08 * u;
      s.press = sec < 12.2 ? 0 : sec < 12.45 ? ease((sec - 12.2) / 0.25) : Math.max(0, 1 - ease((sec - 12.45) / 0.3));
      s.playing = sec >= 12.45;
      s.shuffle = sec >= 15.4;
    } else {                        // D — glass close-up, moving reflection
      const u = (sec - 16.5) / 3.5;
      s.playing = true; s.shuffle = true;
      const zi = ease(Math.min(1, u * 2.2));           // zoom eases in over ~1.6 s
      // zs=1 with zx,zy=0.5 is identity; ease centre + scale together (no jump)
      s.zx = 0.5 + (GLASS.x - 0.5) * zi; s.zy = 0.5 + (GLASS.y - 0.5) * zi; s.zs = 1 + 1.35 * zi;
      // light ping-pongs the empirically-good diagonal ABOVE the panes (record_pbr
      // seg D: directly over glass = white blowout, this band = visible moving streak)
      const pp = 0.5 - 0.5 * Math.cos(2 * Math.PI * 1.5 * u);   // smooth ping-pong
      s.lx = 0.38 + 0.18 * pp; s.ly = 0.52 + 0.08 * pp; s.h = 0.25;
    }
  }
  return s;
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1080, height: AR11 ? 1080 : 1920 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });

await page.goto(`${BASE}/pbrtest3/social.html?freeze=${T0}&bpm=${BPM}${AR11 ? "&ar=1x1" : ""}`);
const frame = () => page.frames().find((f) => f.url().includes("pbrtest3/index.html"));
await page.waitForFunction(() => {
  const f = document.getElementById("demo");
  return f && f.contentDocument && f.contentDocument.title === "pbrtest3 ready";
}, null, { timeout: 60_000, polling: 200 });
await frame().evaluate(() => { resize(); });   // after chrome-hiding CSS -> full 1080px stage

const t0 = Date.now();
// PROBE=1 -> only a handful of representative frames (draw(t) is deterministic
// per-frame under ?bpm, so skipping frames is safe for a layout check)
const FRAMES = process.env.PROBE
  ? [0, 40, 105, 200, 290, 340, 372, 462, 530, 585]
  : Array.from({ length: DUR * FPS }, (_, i) => i);
for (const n of FRAMES) {
  const sec = n / FPS;
  const s = stateAt(sec);
  await frame().evaluate(([t, s]) => {
    state.lx = s.lx; state.ly = s.ly; state.h = s.h;
    state.knob = s.k * Math.PI / 180;
    state.playing = s.playing;
    state.zoom = [s.zx, s.zy, s.zs];
    if (s.press > 0) { PRESS.id = 36; PRESS.amt = s.press; PRESS.target = s.press; }
    else { PRESS.amt = 0; PRESS.target = 0; }
    if (s.shuffle !== state.shuffle) {
      state.shuffle = s.shuffle;
      upload("uTog", s.shuffle ? togOn : togOff, gl.RGBA);
    }
    draw(t);
  }, [T0 + sec, s]);
  await page.screenshot({ path: join(dir, String(n).padStart(5, "0") + ".png"), scale: "css" });
  if (n % 150 === 0) console.log(`frame ${n}/${DUR * FPS}  ${((Date.now() - t0) / 1000) | 0}s elapsed`);
}
await ctx.close();
await browser.close();
console.log(`social-${AR11 ? "1x1" : "9x16"}: ${DUR * FPS} frames (${DUR}s @ ${FPS}fps) captured in ${((Date.now() - t0) / 1000) | 0}s` +
  (errs.length ? `  PAGE ERRORS: ${errs.join(" | ")}` : ""));
if (errs.length) process.exitCode = 1;
