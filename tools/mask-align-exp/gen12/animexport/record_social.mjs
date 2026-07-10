// record_social.mjs — stepped frame-by-frame capture of pbrtest3/social.html
// (1080x1920 9:16 social cut, 30 fps, ~20 s). Same discipline as record_pbr.mjs:
// the recorder owns the clock (?freeze= kills the page rAF), sets the full
// light/knob/press/zoom state per frame inside the REAL renderer iframe, calls
// draw(t), screenshots.
//
// 2026-07-10 re-record (TODO.md "session close-out backlog" item 1, spec locked):
//   - lighting is ORGANIC firelight, not beat-locked. The 128-BPM clock from the
//     prior cut (0a8d7512) is a feature-flagged path in pbrtest3/index.html's
//     pulses()/drawViz() (?bpm=N) — we simply don't pass ?bpm= here, so the page's
//     own non-BPM branch runs: a multi-octave decaying-amplitude sine sum, a cheap
//     deterministic approximation of 1/f (pink-noise) ember flicker.
//   - choreography order is LOCKED: (1) press play FIRST, (2) light sweeps across
//     the skulls, (3) rotate the (right) knob, (4) zoom into the TOP region so the
//     skull motif AND the central play/pause emissive glow are both in frame.
//   - the second (left) knob added 2026-07-10 (pbrtest3/extract3.py) has no scripted
//     motion here — it sits at its default static angle (index.html ?knob2=,
//     default -20°) so both sockets simply read as filled/lived-in.
//
// choreography (20 s @ 30 fps = 600 frames), all eased — catmull-rom spline through
// waypoints for the light path (no linear moves, no teleports):
//   A 0.0–3.0   PRESS PLAY: light idles near the play/pause button, the button
//               physically depresses, visualizer bars go live, light eases off
//               toward the skull-sweep's entry point (no jump cut into B)
//   B 3.0–10.0  scripted light path: sweeps in, RAKES ACROSS BOTH TOP SKULLS (low
//               light height so the relief pops), arcs over the ember spikes/body
//   C 10.0–14.0 volume knob sweep −140°→140° (eased), light orbits the knob so the
//               highlight travels on the brushed cap; shuffle flicks ON at 13.4
//   D 14.0–20.0 TOP-REGION close-up: eased zoom into the skulls + play/pause
//               cluster, light lingers/drifts across it so the glow reads live
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
const T0 = 2.8125;                       // clock start offset (matches index.html's default freezeT band)
const ease = (u) => 0.5 - 0.5 * Math.cos(Math.PI * Math.min(1, Math.max(0, u)));

// --- computed from pbrtest3/diablo-meta3.json (2026-07-10 knob re-derivation) ------
const PLAY = { x: 0.5044, y: 0.3186 };    // playpause button centre (meta3 buttons[].rect)
const KNOB = { x: 0.6987, y: 0.4701 };    // right/original knob seat (re-derived from the paint)
const TOP = { x: 0.50, y: 0.235 };        // zoom centre: both skulls (y~0.17) + playpause (y~0.32)

// --- segment B light path: catmull-rom through (time, lx, ly, h) waypoints --------
const WP = [
  [ 2.20, 0.62, 0.06, 0.40],  // lead-in, continuous from segment A's hand-off
  [ 3.00, 0.46, 0.12, 0.34],  // frame start of B: already sweeping
  [ 4.30, 0.24, 0.175, 0.15], // SKULL top-left — raking
  [ 5.40, 0.50, 0.13, 0.22],  // crest over the transport cluster
  [ 6.50, 0.76, 0.175, 0.15], // SKULL top-right — raking
  [ 7.80, 0.86, 0.42, 0.20],  // right ember spikes
  [ 9.00, 0.52, 0.56, 0.30],  // arc across the body
  [10.00, 0.58, 0.38, 0.26],  // hand-off toward the knob
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

function stateAt(sec) {
  const s = { k: 0, press: 0, playing: false, shuffle: false, zx: 0, zy: 0, zs: 0 };

  if (sec < 3.0) {                              // A — press play first
    s.playing = sec >= 0.55;
    s.press = sec < 0.30 ? 0
      : sec < 0.55 ? ease((sec - 0.30) / 0.25)
      : Math.max(0, 1 - ease((sec - 0.55) / 0.30));
    // ease the light off PLAY toward B's entry waypoint (2.2, 0.62, 0.06, 0.40) —
    // no teleport at the A/B seam
    const u = ease(Math.min(1, Math.max(0, (sec - 0.85) / (2.20 - 0.85))));
    s.lx = PLAY.x + (0.62 - PLAY.x) * u;
    s.ly = PLAY.y + (0.06 - PLAY.y) * u;
    s.h = 0.24 + (0.40 - 0.24) * u;

  } else if (sec < 10.0) {                      // B — spline light path over the skulls
    s.playing = true;
    [s.lx, s.ly, s.h] = catmull(sec);

  } else if (sec < 14.0) {                      // C — knob sweep, light orbits the knob
    s.playing = true;
    const u = (sec - 10.0) / 4.0, th = Math.PI * (1.15 - 1.3 * ease(u));
    s.lx = KNOB.x + 0.16 * Math.cos(th); s.ly = KNOB.y - 0.13 * Math.sin(th); s.h = 0.20;
    s.k = -140 + 280 * ease(u);
    s.shuffle = sec >= 13.4;

  } else {                                      // D — top-region close-up (skulls + play/pause)
    s.playing = true; s.shuffle = true; s.k = 140;
    const u = (sec - 14.0) / 6.0;
    const zi = ease(Math.min(1, u * 2.0));               // zoom eases in over ~3 s, then holds
    // kept moderate (not the glass-close-up's 2.35 max) — the top region spans both
    // skulls (~0.10-0.90 wide); too tight crops the skull silhouettes out of frame
    s.zx = 0.5 + (TOP.x - 0.5) * zi; s.zy = 0.5 + (TOP.y - 0.5) * zi; s.zs = 1 + 0.65 * zi;
    // gentle ping-pong drift across the skull/play-pause band once zoomed in
    const pp = 0.5 - 0.5 * Math.cos(2 * Math.PI * 1.1 * u);
    s.lx = 0.30 + 0.40 * pp; s.ly = 0.16 + 0.12 * pp; s.h = 0.16;
  }
  return s;
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1080, height: AR11 ? 1080 : 1920 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });

// no ?bpm= -> pbrtest3/index.html's organic (non-beat-locked) pulse/viz branch runs
await page.goto(`${BASE}/pbrtest3/social.html?freeze=${T0}${AR11 ? "&ar=1x1" : ""}`);
const frame = () => page.frames().find((f) => f.url().includes("pbrtest3/index.html"));
await page.waitForFunction(() => {
  const f = document.getElementById("demo");
  return f && f.contentDocument && f.contentDocument.title === "pbrtest3 ready";
}, null, { timeout: 60_000, polling: 200 });
await frame().evaluate(() => { resize(); });   // after chrome-hiding CSS -> full 1080px stage

const t0 = Date.now();
// PROBE=1 -> only a handful of representative frames (draw(t) is deterministic
// per-frame, so skipping frames is safe for a layout/choreography check)
const FRAMES = process.env.PROBE
  ? [0, 10, 20, 40, 90, 150, 220, 310, 360, 420, 480, 540, 585]
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
