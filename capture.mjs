// Headless capture harness for the skeuo-ui IG-story export pages.
// Chromium launches with autoplay allowed so the WebAudio spectrum runs live.
//
//   node capture.mjs hero    <outDir> <skin1,skin2,...> [paramStr] [secs]
//   node capture.mjs grid    <outDir> [skins|-]         [paramStr]
//   node capture.mjs sprites <outDir> [skins|-]         [paramStr]
//
// paramStr = extra URL query, e.g. "ts=1.1&mg=56&cols=2&gap=20".
// hero → 1080×1920 @2x still + full-fps mp4 + 12fps gif.
// grid/sprites → 1080×1920 @2x still (live spectra animate in the still).
import pw from "/Users/conner/.npm/_npx/9833c18b2d85bc59/node_modules/playwright/index.js";
const { chromium } = pw;
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const CHROME = "/Users/conner/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const BASE = "http://localhost:5210/export.html";
const W = 1080, H = 1920;

const [, , CMD, OUT = "/tmp/skeuo-ig", ARG3 = "", PARAMS = "", SECS = "8"] = process.argv;
mkdirSync(OUT, { recursive: true });
const tmp = join(OUT, "_tmp"); mkdirSync(tmp, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const qp = (extra) => [PARAMS, extra].filter(Boolean).join("&");

const browser = await chromium.launch({
  executablePath: CHROME,
  args: ["--autoplay-policy=no-user-gesture-required", "--force-color-profile=srgb"],
});

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

async function record(url, secs) {
  const ctx = await browser.newContext({
    viewport: { width: W, height: H }, deviceScaleFactor: 1,
    recordVideo: { dir: tmp, size: { width: W, height: H } },
  });
  const p = await ctx.newPage();
  const video = p.video();            // exact handle for THIS page's recording
  await p.goto(url, { waitUntil: "networkidle" });
  await p.waitForSelector(".player .frame-layer", { timeout: 15000 }).catch(() => {});
  await sleep(secs * 1000);
  await p.close();                    // finalizes the webm
  const webm = await video.path();    // no guessing — the precise file
  await ctx.close();
  return webm;
}

// PREROLL = seconds trimmed from the head (the blank period before React paints
// + fonts load); we record PREROLL extra and seek past it so the clip opens on a
// fully-rendered, already-animating frame.
const PREROLL = 2.0;
function transcode(webm, base, secs) {
  const mp4 = `${base}.mp4`, gif = `${base}.gif`, pal = join(tmp, "pal.png");
  const ss = ["-ss", String(PREROLL), "-t", String(secs)];
  execFileSync("ffmpeg", ["-y", ...ss, "-i", webm, "-vf", "scale=1080:1920:flags=lanczos",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow",
    "-movflags", "+faststart", "-an", mp4], { stdio: "ignore" });
  console.log("mp4    ✓", mp4);
  execFileSync("ffmpeg", ["-y", ...ss, "-i", webm,
    "-vf", "fps=12,scale=720:1280:flags=lanczos,palettegen=stats_mode=diff", pal], { stdio: "ignore" });
  execFileSync("ffmpeg", ["-y", ...ss, "-i", webm, "-i", pal,
    "-lavfi", "fps=12,scale=720:1280:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3", gif],
    { stdio: "ignore" });
  console.log("gif    ✓", gif);
}

if (CMD === "hero") {
  for (const skin of ARG3.split(",").filter(Boolean)) {
    const url = `${BASE}?${qp(`mode=hero&skin=${skin}`)}`;
    await still(url, join(OUT, `hero-${skin}-1080x1920@2x.png`));
    const webm = await record(url, Number(SECS) + PREROLL);
    transcode(webm, join(OUT, `hero-${skin}-1080x1920`), Number(SECS));
  }
} else if (CMD === "grid") {
  const extra = ARG3 && ARG3 !== "-" ? `skins=${ARG3}` : "";
  await still(`${BASE}?${qp(["mode=grid", extra].filter(Boolean).join("&"))}`, join(OUT, `grid-1080x1920@2x.png`), 3000);
} else if (CMD === "sprites") {
  const extra = ARG3 && ARG3 !== "-" ? `skins=${ARG3}` : "";
  await still(`${BASE}?${qp(["mode=sprites", extra].filter(Boolean).join("&"))}`, join(OUT, `sprites-1080x1920@2x.png`), 1500);
}

await browser.close();
rmSync(tmp, { recursive: true, force: true });
console.log("\nDONE →", OUT);
