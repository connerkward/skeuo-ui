#!/usr/bin/env node
// playwright-capture — generic Playwright + CDP screencast driver for dailies.
//
// Captures a configured URL via headed chromium, drives a list of "scenes"
// (scripted page interactions), and writes JPEG frames + a scene-timestamps.json
// to a scratch dir under ~/Desktop/dailies-scratch/<stamp>/. The dir is then a
// valid queue item for encode-queue.sh.
//
// Usage:
//   node playwright-capture.js <config.json>
//   node playwright-capture.js <config.json> --scratch /custom/path
//
// Config schema (see central/skills/dailies/examples/ for working examples):
//   {
//     "url":      "http://localhost:4747/projects/bmw-research/smart-objects/",
//     "viewport": { "width": 1920, "height": 1080 },
//     "preload":  {                  // optional
//       "localStorage":   { "ckw-theme": "dark" },
//       "waitForSelector": ".smart-object-viewer canvas",
//       "waitForFonts":    true,
//       "settleMs":        1500
//     },
//     "scenes": [
//       { "slug": "fullpage-parallax-scroll",
//         "drive": [
//           { "action": "scroll-to-top" },
//           { "action": "raf-scroll", "from": 0, "to": "document", "durationMs": 22000 }
//         ]
//       },
//       { "slug": "viewport-3d-orbit",
//         "drive": [
//           { "action": "scroll-into-view", "selector": ".smart-object-viewer canvas" },
//           { "action": "wait", "ms": 800 },
//           { "action": "raf-orbit", "selector": ".smart-object-viewer canvas",
//             "dxPx": 380, "dyPx": 0, "durationMs": 6500 }
//         ]
//       },
//       { "slug": "viewport-3d-cinema-zoom",
//         "drive": [
//           { "action": "scroll-into-view", "selector": "[data-cinema-zoom]" },
//           { "action": "click", "selector": "[data-cinema-zoom]" },
//           { "action": "wait", "ms": 6200 }
//         ]
//       }
//     ]
//   }
//
// Action primitives (drive[]):
//   wait              { ms }
//   scroll-to-top     {}
//   scroll-into-view  { selector }
//   raf-scroll        { from?, to: "document"|number, durationMs }
//   raf-orbit         { selector, dxPx, dyPx, durationMs }     // mouse-drag inside selector
//   click             { selector }
//   hover             { selector }
//   keyboard          { key }   // e.g. "PageDown", "Escape"
//
// Requires: a Playwright install reachable via require(). Set NODE_PATH if needed:
//   NODE_PATH=$HOME/dev/punku-web/node_modules node playwright-capture.js …

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (e) {
  console.error('error: cannot require("playwright"). Set NODE_PATH to a Playwright install:');
  console.error('  NODE_PATH=$HOME/dev/punku-web/node_modules node playwright-capture.js …');
  process.exit(2);
}

const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('usage: node playwright-capture.js <config.json> [--scratch <dir>]');
  process.exit(2);
}
const configPath = args[0];
let scratchOverride = null;
for (let i = 1; i < args.length; i++) {
  if (args[i] === '--scratch') scratchOverride = args[++i];
}

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
if (!config.url) { console.error('config.url is required'); process.exit(2); }
if (!Array.isArray(config.scenes) || config.scenes.length === 0) {
  console.error('config.scenes must be a non-empty array');
  process.exit(2);
}

const viewport = Object.assign({ width: 1920, height: 1080 }, config.viewport || {});
const preload = config.preload || {};

function stamp() {
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

const scratchRoot = scratchOverride || path.join(os.homedir(), 'Desktop', 'dailies-scratch');
const scratchDir = path.join(scratchRoot, stamp());
const framesDir = path.join(scratchDir, 'frames');
fs.mkdirSync(framesDir, { recursive: true });
console.error(`scratch: ${scratchDir}`);

let frameCounter = 0;
const sceneTimestamps = [];

async function runScene(page, client, scene) {
  const startFrame = frameCounter;
  const wallStart = Date.now();
  console.error(`── scene: ${scene.slug} ──`);

  for (const step of scene.drive) {
    await runStep(page, step);
  }

  // Allow last frames to flush.
  await page.waitForTimeout(250);

  const wallMs = Date.now() - wallStart;
  const endFrame = frameCounter;
  const nFrames = endFrame - startFrame;
  const fps = nFrames > 0 ? +(nFrames / (wallMs / 1000)).toFixed(2) : 0;
  console.error(`   ${nFrames} frames, ${wallMs} ms, ${fps} fps`);
  sceneTimestamps.push({ slug: scene.slug, startFrame, frameCount: nFrames, fps, wallMs });
}

async function runStep(page, step) {
  switch (step.action) {
    case 'wait':
      await page.waitForTimeout(step.ms || 0);
      return;
    case 'scroll-to-top':
      await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }));
      await page.waitForTimeout(120);
      return;
    case 'scroll-into-view': {
      if (!step.selector) throw new Error('scroll-into-view requires selector');
      await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) throw new Error(`scroll-into-view: ${sel} not found`);
        el.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
      }, step.selector);
      await page.waitForTimeout(160);
      return;
    }
    case 'raf-scroll': {
      const dur = step.durationMs || 8000;
      const from = step.from != null ? step.from : 0;
      const to = step.to === 'document' ? null : step.to;
      await page.evaluate(({ dur, from, to }) => new Promise(res => {
        const maxY = to == null
          ? Math.max(0, document.documentElement.scrollHeight - window.innerHeight)
          : to;
        const start = performance.now();
        function tick(now) {
          const t = Math.min(1, (now - start) / dur);
          const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
          window.scrollTo(0, from + (maxY - from) * ease);
          if (t < 1) requestAnimationFrame(tick); else res();
        }
        requestAnimationFrame(tick);
      }), { dur, from, to });
      return;
    }
    case 'raf-orbit': {
      if (!step.selector) throw new Error('raf-orbit requires selector');
      const dur = step.durationMs || 6000;
      const dxPx = step.dxPx || 300;
      const dyPx = step.dyPx || 0;
      const box = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) throw new Error(`raf-orbit: ${sel} not found`);
        const r = el.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
      }, step.selector);
      const startX = box.x - dxPx / 2;
      const startY = box.y - dyPx / 2;
      const endX = box.x + dxPx / 2;
      const endY = box.y + dyPx / 2;
      await page.mouse.move(startX, startY);
      await page.mouse.down();
      const steps = Math.max(20, Math.floor(dur / 16));
      const t0 = Date.now();
      for (let i = 1; i <= steps; i++) {
        const tFrac = i / steps;
        const ease = tFrac < 0.5 ? 2 * tFrac * tFrac : 1 - Math.pow(-2 * tFrac + 2, 2) / 2;
        const x = startX + (endX - startX) * ease;
        const y = startY + (endY - startY) * ease;
        await page.mouse.move(x, y);
        const elapsed = Date.now() - t0;
        const want = (dur * i) / steps;
        if (want > elapsed) await page.waitForTimeout(want - elapsed);
      }
      await page.mouse.up();
      return;
    }
    case 'click':
      if (!step.selector) throw new Error('click requires selector');
      await page.click(step.selector);
      return;
    case 'hover':
      if (!step.selector) throw new Error('hover requires selector');
      await page.hover(step.selector);
      return;
    case 'keyboard':
      if (!step.key) throw new Error('keyboard requires key');
      await page.keyboard.press(step.key);
      return;
    default:
      throw new Error(`unknown action: ${step.action}`);
  }
}

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport, deviceScaleFactor: 2 });

  if (preload.localStorage && Object.keys(preload.localStorage).length) {
    const ls = preload.localStorage;
    await context.addInitScript((entries) => {
      for (const [k, v] of Object.entries(entries)) {
        try { localStorage.setItem(k, String(v)); } catch (_) {}
      }
    }, ls);
  }

  const page = await context.newPage();
  await page.goto(config.url, { waitUntil: 'load' });
  if (preload.waitForFonts) {
    await page.evaluate(() => document.fonts ? document.fonts.ready : null);
  }
  if (preload.waitForSelector) {
    await page.waitForSelector(preload.waitForSelector, { timeout: 30000 });
  }
  if (preload.settleMs) {
    await page.waitForTimeout(preload.settleMs);
  }

  const client = await context.newCDPSession(page);
  client.on('Page.screencastFrame', async (ev) => {
    const idx = frameCounter++;
    const out = path.join(framesDir, `frame-${String(idx).padStart(6, '0')}.jpg`);
    fs.writeFile(out, Buffer.from(ev.data, 'base64'), () => {});
    try { await client.send('Page.screencastFrameAck', { sessionId: ev.sessionId }); } catch (_) {}
  });

  await client.send('Page.startScreencast', {
    format: 'jpeg',
    quality: 95,
    everyNthFrame: 1,
  });

  try {
    for (const scene of config.scenes) {
      await runScene(page, client, scene);
    }
  } finally {
    try { await client.send('Page.stopScreencast'); } catch (_) {}
    await browser.close();
  }

  fs.writeFileSync(
    path.join(scratchDir, 'scene-timestamps.json'),
    JSON.stringify(sceneTimestamps, null, 2),
  );
  fs.writeFileSync(
    path.join(scratchDir, 'config-used.json'),
    JSON.stringify(config, null, 2),
  );

  console.error(`done. ${frameCounter} frames total → ${scratchDir}`);
  console.error('next: ~/dev/central/skills/dailies/encode-queue.sh encode');
})();
