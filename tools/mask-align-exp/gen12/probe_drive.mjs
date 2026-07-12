// probe_drive.mjs — [[verification-recalibration]] scripted JS-state probe driver.
// docs/experiments/2026-07-11-verification-recalibration.md "Residual gaps": vision (VLM) can't
// reliably tell a DEAD control from a merely-static one. The ps1-crunchy "visualizer not
// working" review comment turned out to be a control that WAS drawing, just not visibly
// animating between two screenshots (idle already wobbles gently by design). The
// fallout-vault "prev button, shuffle button, failed to work" comment is the anchor case for
// a *different* failure mode this driver is built to catch: a hitbox/z-order defect where an
// overlapping sibling control silently swallows the click — two static screenshots can't tell
// "nothing happened because the handler is broken" from "nothing happened because the click
// never reached this element."
//
// So: every button/toggle interaction below is dispatched as a REAL page.mouse click at the
// control's own getBoundingClientRect() center — real hit-testing, not el.click(). Compare
// observe_drive.mjs (a *different* driver, owned by the vision pass), which deliberately uses
// el.click() to DODGE overlap flakiness for its own screenshot-diff purpose — the opposite
// choice, correct for THAT script's job (get a clean before/after frame pair) and wrong for
// this one (this script's whole point is to notice the overlap). Own throwaway
// chromium.launch() — no shared browser/profile with observe_drive.mjs or any other driver.
//
// Usage: node probe_drive.mjs <playerUrl> <regionsJsonPath> <outFile.json>
import { chromium } from 'playwright';
import fs from 'node:fs';

const [url, regionsPath, outFile] = process.argv.slice(2);
if (!url || !regionsPath || !outFile) {
  console.error('usage: node probe_drive.mjs <playerUrl> <regionsJsonPath> <outFile.json>');
  process.exit(1);
}

const regs = JSON.parse(fs.readFileSync(regionsPath, 'utf8'));
const roles = regs.roles || {};
const keyOf = (role) => Object.keys(roles).find((k) => roles[k] === role) || null;
const buttonKeys = Object.keys(roles).filter((k) => roles[k] === 'button');
const toggleKey = keyOf('toggle');
const knobKey = keyOf('knob');
const sliderKey = keyOf('slider');
const sliderVertical = sliderKey ? !!(regs.regions && regs.regions[sliderKey] && regs.regions[sliderKey].vertical) : false;

const results = {};
const evid = (alive, text) => ({ alive: !!alive, evidence: text });
// backgroundImage values are `url(data:image/png;base64,...)` — can run to hundreds of KB.
// Evidence strings must stay human-readable; truncate anything long instead of embedding it.
const trunc = (s, n = 40) => (s == null ? String(s) : s.length > n ? `${s.slice(0, n)}...(${s.length}ch)` : s);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 900, height: 1100 } });
const pageErrors = [];
page.on('pageerror', (e) => pageErrors.push(String((e && e.message) || e)));
page.on('console', (m) => { if (m.type() === 'error') pageErrors.push('console: ' + m.text()); });

let loadOk = true, loadErr = '';
try {
  await page.goto(url, { waitUntil: 'load', timeout: 20000 });
  await page.waitForFunction(
    "document.querySelectorAll('#phone .pbtn').length > 0 || document.querySelectorAll('#phone .pknob,#phone .pthumb,#phone .ptog').length > 0",
    { timeout: 20000 },
  );
  await page.waitForTimeout(2500); // sprite decode + seat (matches observe_drive.mjs)
} catch (e) {
  loadOk = false;
  loadErr = String((e && e.message) || e);
}

function writeOutAndExit(code) {
  fs.writeFileSync(outFile, JSON.stringify({ url, loadOk, loadErr, pageErrors, results }, null, 2));
  return browser.close().then(() => process.exit(code));
}

if (!loadOk) {
  // a harness failure must not read as "alive" — every control that would have been probed is
  // explicitly UNMEASURED-AS-DEAD, not silently absent from probe.json.
  const allKeys = [...buttonKeys, toggleKey, knobKey, sliderKey, 'visualizer'].filter(Boolean);
  for (const k of allKeys) results[k] = evid(false, `page failed to load/settle: ${loadErr}`);
  await writeOutAndExit(0);
}

// ---- shared state reader ----
const readState = () =>
  page.evaluate(() => {
    const hint = document.getElementById('hint');
    const queue = document.getElementById('queue');
    const btnDataM = {};
    document.querySelectorAll('#phone .pbtn').forEach((e) => { btnDataM[e.title] = e.dataset.m ?? null; });
    const tog = document.querySelector('#phone .ptog');
    const knobCap = document.querySelector('#phone .pknob .cap');
    const thumb = document.querySelector('#phone .pthumb');
    return {
      hint: hint ? hint.textContent : null,
      queueOpen: queue ? queue.classList.contains('open') : null,
      btnDataM,
      togBg: tog ? tog.style.backgroundImage : null,
      togLeft: tog ? tog.style.left : null,
      togTop: tog ? tog.style.top : null,
      togTransform: tog ? tog.style.transform : null,
      knobTransform: knobCap ? knobCap.style.transform : null,
      thumbLeft: thumb ? thumb.style.left : null,
      thumbTop: thumb ? thumb.style.top : null,
    };
  });

// ---- locate a control's on-screen center + whether a real click there would actually hit it
// (elementFromPoint) — this doubles as BOTH the click-target computation and the hitbox check.
const locateByTitle = (selector, title) =>
  page.evaluate(
    ({ selector, title }) => {
      const el = Array.from(document.querySelectorAll(selector)).find((e) => e.title === title);
      if (!el) return { found: false };
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return { found: true, zeroSize: true, rect: [r.x, r.y, r.width, r.height] };
      const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
      const hit = document.elementFromPoint(cx, cy);
      const hitClosest = hit ? hit.closest(selector) : null;
      const occluded = hitClosest !== el;
      return {
        found: true, zeroSize: false, cx, cy, occluded,
        occluderDesc: occluded ? (hit ? hit.title || hit.className || hit.tagName : 'nothing') : null,
      };
    },
    { selector, title },
  );

const locateFirst = (selector) =>
  page.evaluate((selector) => {
    const el = document.querySelector(selector);
    if (!el) return { found: false };
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return { found: true, zeroSize: true, rect: [r.x, r.y, r.width, r.height] };
    const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
    const hit = document.elementFromPoint(cx, cy);
    const hitClosest = hit ? hit.closest(selector) : null;
    const occluded = hitClosest !== el;
    return {
      found: true, zeroSize: false, cx, cy, occluded,
      occluderDesc: occluded ? (hit ? hit.title || hit.className || hit.tagName : 'nothing') : null,
    };
  }, selector);

// ======================= buttons (playpause handled below, combined with visualizer) =======================
for (const key of buttonKeys) {
  if (key === 'playpause') continue;
  try {
    const loc = await locateByTitle('#phone .pbtn', key);
    if (!loc.found) { results[key] = evid(false, `no .pbtn[title="${key}"] found in rendered DOM — control missing entirely`); continue; }
    if (loc.zeroSize) { results[key] = evid(false, `control rendered with zero-size hitbox rect=${JSON.stringify(loc.rect)}`); continue; }
    const before = await readState();
    await page.mouse.click(loc.cx, loc.cy);
    await page.waitForTimeout(150);
    const after = await readState();
    const occNote = loc.occluded
      ? ` [HITBOX WARNING: point (${loc.cx.toFixed(0)},${loc.cy.toFixed(0)}) resolved to ${loc.occluderDesc}, not "${key}" — a real click here hits the wrong control]`
      : '';
    if (key === 'queue') {
      const alive = before.queueOpen !== after.queueOpen;
      results[key] = evid(alive, `queue overlay open: ${before.queueOpen} -> ${after.queueOpen}${occNote}`);
    } else if (key === 'repeat') {
      const dm0 = before.btnDataM[key], dm1 = after.btnDataM[key];
      const hintChanged = before.hint !== after.hint && /^repeat:/.test(after.hint || '');
      const alive = dm0 !== dm1 || hintChanged;
      results[key] = evid(alive, `dataset.m: ${dm0} -> ${dm1}; hint: "${before.hint}" -> "${after.hint}"${occNote}`);
    } else {
      // shipped click handler default: hint.textContent = `${b} ▸` (build_player.py) — exact
      // match is the strongest signal; a hint change to something ELSE (e.g. a neighboring
      // control's own label) is the fallout-vault "prev...failed to work" shape: the click
      // landed on the wrong control.
      const expected = `${key} ▸`;
      const alive = after.hint === expected;
      const partial = !alive && before.hint !== after.hint;
      results[key] = evid(
        alive,
        alive
          ? `hint -> "${after.hint}" as expected${occNote}`
          : partial
            ? `hint changed but NOT to the expected value: "${before.hint}" -> "${after.hint}" (expected "${expected}")${occNote}`
            : `click had no observable effect: hint stayed "${before.hint}"${occNote}`,
      );
    }
  } catch (e) {
    results[key] = evid(false, `probe threw: ${(e && e.message) || e}`);
  }
}

// ======================= playpause + visualizer (combined: one click drives both) =======================
try {
  const vzExists = await page.evaluate(() => !!document.getElementById('viz'));

  const sampleCanvasActivity = (ms, stepMs = 100) =>
    page.evaluate(
      async ({ ms, stepMs }) => {
        const c = document.getElementById('viz');
        if (!c || !c.width || !c.height) return { total: 0, samples: 0 };
        const g = c.getContext('2d');
        const grab = () => g.getImageData(0, 0, c.width, c.height).data;
        let prev = grab(), total = 0, samples = 0;
        const t0 = performance.now();
        while (performance.now() - t0 < ms) {
          await new Promise((r) => setTimeout(r, stepMs));
          const cur = grab();
          let d = 0;
          for (let i = 0; i < cur.length; i += 4) d += Math.abs(cur[i] - prev[i]);
          total += d;
          samples++;
          prev = cur;
        }
        return { total, samples };
      },
      { ms, stepMs },
    );

  if (!vzExists) results['visualizer'] = evid(false, 'no #viz canvas element found in rendered DOM');

  const ppLoc = await locateByTitle('#phone .pbtn', 'playpause');
  if (!ppLoc.found) {
    results['playpause'] = evid(false, 'no .pbtn[title="playpause"] found in rendered DOM — control missing entirely');
    if (vzExists) results['visualizer'] = evid(false, 'cannot exercise playing-state: playpause control missing');
  } else if (ppLoc.zeroSize) {
    results['playpause'] = evid(false, `control rendered with zero-size hitbox rect=${JSON.stringify(ppLoc.rect)}`);
    if (vzExists) results['visualizer'] = evid(false, 'cannot exercise playing-state: playpause hitbox is zero-size');
  } else {
    const idle = vzExists ? await sampleCanvasActivity(600) : null;
    const before = await readState();
    await page.mouse.click(ppLoc.cx, ppLoc.cy);
    await page.waitForTimeout(150);
    const after = await readState();
    const occNote = ppLoc.occluded
      ? ` [HITBOX WARNING: point resolved to ${ppLoc.occluderDesc}, not "playpause"]`
      : '';
    const ppAlive = before.hint !== after.hint && /playing|paused/i.test(after.hint || '');
    results['playpause'] = evid(
      ppAlive,
      ppAlive
        ? `hint: "${before.hint}" -> "${after.hint}"${occNote}`
        : `no play/pause state transition observed: hint "${before.hint}" -> "${after.hint}"${occNote}`,
    );

    if (vzExists) {
      const playingActivity = await sampleCanvasActivity(600);
      const idleTotal = idle ? idle.total : 0;
      const playTotal = playingActivity ? playingActivity.total : 0;
      // ps1-crunchy lesson (docs/experiments/2026-07-11-verification-recalibration.md): idle
      // ALREADY wobbles gently by design (bars drift toward a low random band every frame), so
      // raw non-zero motion is not proof the canvas is actually driven by the 'playing' flag.
      // Require an absolute floor AND a clear multiple over THIS skin's own idle baseline
      // (accent color / bar count / canvas size vary per skin, so a per-skin relative check is
      // more robust than one fixed magic number alone). Calibrated against real skins in the
      // validation pass — see TODO.md / the commit that lands this file.
      const ABS_FLOOR = 4000;
      const REL_MARGIN = 2.5;
      const vzAlive = playTotal > ABS_FLOOR && playTotal > idleTotal * REL_MARGIN;
      results['visualizer'] = evid(
        vzAlive,
        `idle 600ms pixel-activity=${idleTotal.toFixed(0)}, playing 600ms pixel-activity=${playTotal.toFixed(0)} ` +
          `(need >${ABS_FLOOR} and >${REL_MARGIN}x idle)`,
      );
    }
  }
} catch (e) {
  if (!results['playpause']) results['playpause'] = evid(false, `probe threw: ${(e && e.message) || e}`);
  if (!results['visualizer']) results['visualizer'] = evid(false, `probe threw: ${(e && e.message) || e}`);
}

// ======================= toggle (shuffle) =======================
// `.pthumb[data-role="toggle"]` is a defensive selector for a NOT-YET-IMPLEMENTED "two-detent
// slider" toggle rendering mentioned in the recalibration spec — build_player.py only emits
// `.ptog` (sprite-swap) today, and regions.json carries no mode flag to detect (checked: no
// skin's toggle region has anything beyond device/angle/stateAlign). Rather than branch on a
// field that doesn't exist, the check below is a generic STYLE DIFF (bg/pos/transform) that
// is correct for either representation without modification — this comment + selector are the
// "detect which mode" hook the spec asks for; no dead per-mode branch is added ahead of need.
try {
  if (toggleKey) {
    const togLoc = await locateFirst('#phone .ptog, #phone .pthumb[data-role="toggle"]');
    if (!togLoc.found) {
      results[toggleKey] = evid(false, 'no toggle control rendered (neither .ptog sprite-swap nor a slider-style element found)');
    } else if (togLoc.zeroSize) {
      results[toggleKey] = evid(false, `control rendered with zero-size hitbox rect=${JSON.stringify(togLoc.rect)}`);
    } else {
      const before = await readState();
      await page.mouse.click(togLoc.cx, togLoc.cy);
      await page.waitForTimeout(150);
      const after = await readState();
      const occNote = togLoc.occluded
        ? ` [HITBOX WARNING: point resolved to ${togLoc.occluderDesc}, not the toggle]`
        : '';
      const changed =
        before.togBg !== after.togBg ||
        before.togLeft !== after.togLeft ||
        before.togTop !== after.togTop ||
        before.togTransform !== after.togTransform;
      results[toggleKey] = evid(
        changed,
        changed
          ? `state changed on click (bg ${before.togBg !== after.togBg ? 'DIFFERS' : 'same'}: "${trunc(before.togBg)}"->"${trunc(after.togBg)}", left ${before.togLeft}->${after.togLeft}, top ${before.togTop}->${after.togTop})${occNote}`
          : `no CSS state change after click: bg="${trunc(before.togBg)}", left=${before.togLeft}, top=${before.togTop}${occNote}`,
      );
    }
  }
} catch (e) {
  if (toggleKey) results[toggleKey] = evid(false, `probe threw: ${(e && e.message) || e}`);
}

// ======================= knob (vol) =======================
try {
  if (knobKey) {
    const knobLoc = await locateFirst('#phone .pknob');
    if (!knobLoc.found) {
      results[knobKey] = evid(false, 'no .pknob element found in rendered DOM');
    } else if (knobLoc.zeroSize) {
      results[knobKey] = evid(false, `control rendered with zero-size hitbox rect=${JSON.stringify(knobLoc.rect)}`);
    } else {
      const before = await readState();
      await page.mouse.move(knobLoc.cx, knobLoc.cy);
      await page.mouse.down();
      await page.mouse.move(knobLoc.cx, knobLoc.cy - 50, { steps: 8 });
      await page.mouse.up();
      await page.waitForTimeout(150);
      const after = await readState();
      const occNote = knobLoc.occluded
        ? ` [HITBOX WARNING: drag-start point resolved to ${knobLoc.occluderDesc}, not the knob]`
        : '';
      const changed = before.knobTransform !== after.knobTransform;
      results[knobKey] = evid(
        changed,
        changed
          ? `cap transform: "${before.knobTransform}" -> "${after.knobTransform}"${occNote}`
          : `no rotation change after a 50px drag: transform stayed "${before.knobTransform}"${occNote}`,
      );
    }
  }
} catch (e) {
  if (knobKey) results[knobKey] = evid(false, `probe threw: ${(e && e.message) || e}`);
}

// ======================= seek slider (value change + clamp at BOTH ends) =======================
try {
  if (sliderKey) {
    const thumbLoc = await locateFirst('#phone .pthumb');
    if (!thumbLoc.found) {
      results[sliderKey] = evid(false, 'no .pthumb element found in rendered DOM');
    } else if (thumbLoc.zeroSize) {
      results[sliderKey] = evid(false, `control rendered with zero-size hitbox rect=${JSON.stringify(thumbLoc.rect)}`);
    } else {
      const occNote = thumbLoc.occluded
        ? ` [HITBOX WARNING: drag-start point resolved to ${thumbLoc.occluderDesc}, not the thumb]`
        : '';
      const readPos = () =>
        page.evaluate((vert) => {
          const t = document.querySelector('#phone .pthumb');
          return vert ? t.style.top : t.style.left;
        }, sliderVertical);
      const thumbCenter = () =>
        page.evaluate(() => {
          const t = document.querySelector('#phone .pthumb');
          const r = t.getBoundingClientRect();
          return [r.x + r.width / 2, r.y + r.height / 2];
        });
      const dragTo = async (fromX, fromY, toX, toY) => {
        await page.mouse.move(fromX, fromY);
        await page.mouse.down();
        await page.mouse.move(toX, toY, { steps: 10 });
        await page.mouse.up();
        await page.waitForTimeout(120);
      };

      const initialPos = await readPos();
      const BIG = 3000; // huge overshoot forces the clamp regardless of the skin's own track length
      let [cx, cy] = [thumbLoc.cx, thumbLoc.cy];

      // drive to the MAX end, twice — 2nd overshoot landing on the SAME position as the 1st IS the clamp
      if (sliderVertical) await dragTo(cx, cy, cx, cy + BIG); else await dragTo(cx, cy, cx + BIG, cy);
      const maxPos1 = await readPos();
      [cx, cy] = await thumbCenter();
      if (sliderVertical) await dragTo(cx, cy, cx, cy + BIG * 2); else await dragTo(cx, cy, cx + BIG * 2, cy);
      const maxPos2 = await readPos();

      // drive to the MIN end, twice
      [cx, cy] = await thumbCenter();
      if (sliderVertical) await dragTo(cx, cy, cx, cy - BIG); else await dragTo(cx, cy, cx - BIG, cy);
      const minPos1 = await readPos();
      [cx, cy] = await thumbCenter();
      if (sliderVertical) await dragTo(cx, cy, cx, cy - BIG * 2); else await dragTo(cx, cy, cx - BIG * 2, cy);
      const minPos2 = await readPos();

      const moved = maxPos1 !== minPos1 && maxPos1 !== initialPos;
      const clampedAtMax = maxPos1 === maxPos2;
      const clampedAtMin = minPos1 === minPos2;
      const alive = moved && clampedAtMax && clampedAtMin;
      results[sliderKey] = evid(
        alive,
        `initial=${initialPos}, max-drag=${maxPos1} (re-overshoot=${maxPos2}, clamped=${clampedAtMax}), ` +
          `min-drag=${minPos1} (re-overshoot=${minPos2}, clamped=${clampedAtMin})${occNote}`,
      );
    }
  }
} catch (e) {
  if (sliderKey) results[sliderKey] = evid(false, `probe threw: ${(e && e.message) || e}`);
}

await writeOutAndExit(0);
