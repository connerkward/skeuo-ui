// Headless capture harness for the skeuo-ui IG-story export pages.
//
//   node capture.mjs hero    <outDir> <skin1,skin2,...> [paramStr] [secs] [name]
//   node capture.mjs mg      <outDir> <scene>           [paramStr] [secs] [name]
//   node capture.mjs grid|sprites|fan|center|scatter <outDir> [skins|-] [paramStr]
//
// VIDEO is captured by DETERMINISTIC FRAME-STEPPING, not real-time recording:
// CDP virtual time freezes the page clock and advances it exactly 1/fps per
// frame, screenshotting each step. Every frame is fully rendered regardless of
// how heavy the scene is, so there are ZERO dropped frames → no stutter, ever —
// and screenshots are @2x (sharp) with no grey. JPEG keeps it ~105ms/frame.
import pw from "/Users/conner/.npm/_npx/9833c18b2d85bc59/node_modules/playwright/index.js";
const { chromium } = pw;
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const CHROME = "/Users/conner/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const BASE = "http://localhost:5210/export.html";
const W = 1080, H = 1920;
const FPS = 30;            // deterministic output framerate
const WARMUP_MS = Number(process.env.CAP_WARMUP) || 900;  // virtual time before frame 0; lower it (CAP_WARMUP) to catch a one-shot intro like fan-in's fly-in

const [, , CMD, OUT = "/tmp/skeuo-ig", ARG3 = "", PARAMS = "", SECS = "8", OUTNAME = ""] = process.argv;
mkdirSync(OUT, { recursive: true });
const tmp = join(OUT, `_tmp-${process.pid}`); mkdirSync(tmp, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const qp = (extra) => [PARAMS, extra].filter(Boolean).join("&");

const browser = await chromium.launch({
  executablePath: CHROME,
  args: [
    "--autoplay-policy=no-user-gesture-required", "--force-color-profile=srgb",
    "--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=metal",
    "--enable-features=Metal", "--disable-frame-rate-limit",
  ],
});

// ── high-res still (@2x poster) ──────────────────────────────────────────────
async function still(url, outPath, settleMs = 2600) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.goto(url, { waitUntil: "networkidle" });
  await p.waitForSelector(".player .frame-layer", { timeout: 15000 }).catch(() => {});
  await sleep(settleMs);
  await p.screenshot({ path: outPath });
  await ctx.close();
  console.log("still  ✓", outPath);
}

// ── deterministic frame-stepped capture (the smooth pipeline) ────────────────
async function captureFrames(url, secs, waitSel) {
  const dir = join(tmp, `fr-${Date.now()}`); mkdirSync(dir, { recursive: true });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector(waitSel, { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready).catch(() => {});
  const cdp = await ctx.newCDPSession(page);
  const step = (budget) => new Promise(async (res) => {
    cdp.once("Emulation.virtualTimeBudgetExpired", res);
    await cdp.send("Emulation.setVirtualTimePolicy", { policy: "advance", budget });
  });
  await cdp.send("Emulation.setVirtualTimePolicy", { policy: "pause" });
  await step(WARMUP_MS);
  const N = Math.round(secs * FPS), frameMs = 1000 / FPS;
  for (let i = 0; i < N; i++) {
    await step(frameMs);
    await page.screenshot({ path: join(dir, `f${String(i).padStart(5, "0")}.jpg`), type: "jpeg", quality: 92, animations: "allow" });
  }
  await ctx.close();
  return { dir, n: N };
}

// frames → H.264 + 15fps gif. CAP_MAXRES=1 keeps the native 2× resolution
// (2160×3840 — the max-quality Instagram source) instead of downscaling to 1080.
function encodeFrames(dir, base) {
  const MAXRES = process.env.CAP_MAXRES === "1";
  const mp4 = `${base}.mp4`, gif = `${base}.gif`, pal = join(tmp, "pal.png");
  const SRC = ["-framerate", String(FPS), "-i", join(dir, "f%05d.jpg")];
  const SHARP = MAXRES ? "unsharp=5:5:0.4:5:5:0.0" : "scale=1080:1920:flags=lanczos,unsharp=5:5:0.7:5:5:0.0";
  const GIFVF = "fps=15,scale=1080:1920:flags=lanczos";   // gif stays light regardless
  execFileSync("ffmpeg", ["-y", ...SRC, "-vf", SHARP,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow",
    "-movflags", "+faststart", "-an", mp4], { stdio: "ignore" });
  console.log("mp4    ✓", mp4);
  execFileSync("ffmpeg", ["-y", ...SRC, "-vf",
    `${GIFVF},palettegen=stats_mode=diff`, pal], { stdio: "ignore" });
  execFileSync("ffmpeg", ["-y", ...SRC, "-i", pal,
    "-lavfi", `${GIFVF}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3`, gif], { stdio: "ignore" });
  console.log("gif    ✓", gif);
  rmSync(dir, { recursive: true, force: true });
}

// ── dispatch ─────────────────────────────────────────────────────────────────
if (CMD === "hero") {
  for (const skin of ARG3.split(",").filter(Boolean)) {
    const url = `${BASE}?${qp(`mode=hero&skin=${skin}`)}`;
    await still(url, join(OUT, `hero-${skin}-1080x1920@2x.png`));
    const { dir } = await captureFrames(url, Number(SECS), ".player .frame-layer");
    encodeFrames(dir, join(OUT, `hero-${skin}-1080x1920`));
  }
} else if (CMD === "mg") {
  const scene = ARG3 || "streams";
  const url = `${BASE}?${qp(`mode=mg&scene=${scene}`)}`;
  const { dir } = await captureFrames(url, Number(SECS), ".device");
  encodeFrames(dir, join(OUT, `${OUTNAME || `mg-${scene}`}-1080x1920`));
} else if (["grid", "sprites", "fan", "center", "scatter"].includes(CMD)) {
  const extra = ARG3 && ARG3 !== "-" ? `skins=${ARG3}` : "";
  const name = OUTNAME || CMD;
  await still(`${BASE}?${qp([`mode=${CMD}`, extra].filter(Boolean).join("&"))}`,
    join(OUT, `${name}-1080x1920@2x.png`), CMD === "sprites" ? 1500 : 3200);
}

await browser.close();
rmSync(tmp, { recursive: true, force: true });
console.log("\nDONE →", OUT);
