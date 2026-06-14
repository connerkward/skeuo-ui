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

const [, , CMD, OUT = "/tmp/skeuo-ig", ARG3 = "", PARAMS = "", SECS = "8", OUTNAME = ""] = process.argv;
mkdirSync(OUT, { recursive: true });
// per-process tmp so parallel capture.mjs runs (same OUT) don't share pal.png
// or rmSync each other's scratch dir mid-flight
const tmp = join(OUT, `_tmp-${process.pid}`); mkdirSync(tmp, { recursive: true });
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

async function record(url, secs, waitSel = ".player .frame-layer") {
  // recordVideo.size MUST match the viewport, else Playwright places the page in
  // a corner and pads the rest GREY (and the 2× pixel load drops frames → choppy).
  // 1080×1920 @ DSF1 = full-frame, smooth, real-time; sharpness comes from the
  // encode (unsharp + low crf) in transcode(), not from oversizing the recorder.
  const ctx = await browser.newContext({
    viewport: { width: W, height: H }, deviceScaleFactor: 1,
    recordVideo: { dir: tmp, size: { width: W, height: H } },
  });
  const p = await ctx.newPage();
  const video = p.video();            // exact handle for THIS page's recording
  await p.goto(url, { waitUntil: "networkidle" });
  await p.waitForSelector(waitSel, { timeout: 15000 }).catch(() => {});
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
function transcode(webm, base, secs, preroll = PREROLL) {
  const mp4 = `${base}.mp4`, gif = `${base}.gif`, pal = join(tmp, "pal.png");
  const ss = ["-ss", String(preroll), "-t", String(secs)];
  // 1080×1920 native; a light unsharp recovers the VP8 softness without grey
  const SHARP = "unsharp=5:5:0.9:5:5:0.0";
  execFileSync("ffmpeg", ["-y", ...ss, "-i", webm, "-vf", SHARP,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "15", "-preset", "slow",
    "-movflags", "+faststart", "-an", mp4], { stdio: "ignore" });
  console.log("mp4    ✓", mp4);
  execFileSync("ffmpeg", ["-y", ...ss, "-i", webm,
    "-vf", `fps=15,${SHARP},scale=900:1600:flags=lanczos,palettegen=stats_mode=diff`, pal], { stdio: "ignore" });
  execFileSync("ffmpeg", ["-y", ...ss, "-i", webm, "-i", pal,
    "-lavfi", `fps=15,${SHARP},scale=900:1600:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3`, gif],
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
} else if (CMD === "mg") {
  // motion-graphics scene → smooth real-time mp4 + gif (no caption chrome)
  const scene = ARG3 || "streams";
  const url = `${BASE}?${qp(`mode=mg&scene=${scene}`)}`;
  const webm = await record(url, Number(SECS) + 1.2, ".mg-skin");
  transcode(webm, join(OUT, `${OUTNAME || `mg-${scene}`}-1080x1920`), Number(SECS), 1.2);
} else if (["grid", "sprites", "fan", "center", "scatter"].includes(CMD)) {
  // any non-hero mode → one hi-res still (live spectra animate in the still).
  // OUTNAME lets variations of the same mode coexist (e.g. center-pebble).
  const extra = ARG3 && ARG3 !== "-" ? `skins=${ARG3}` : "";
  const name = OUTNAME || CMD;
  await still(`${BASE}?${qp([`mode=${CMD}`, extra].filter(Boolean).join("&"))}`,
    join(OUT, `${name}-1080x1920@2x.png`), CMD === "sprites" ? 1500 : 3200);
}

await browser.close();
rmSync(tmp, { recursive: true, force: true });
console.log("\nDONE →", OUT);
