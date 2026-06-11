// Control audit — run inside the page (Playwright evaluate). Exercises EVERY
// interactive control on the CURRENT skin with assertions; returns
// { passes: [...], failures: [...] }. A skin is shippable only when failures
// is empty for it. Used by the pre-ship sweep (see README).
async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const passes = [], failures = [];
  const ok = (name) => passes.push(name);
  const bad = (name, why) => failures.push(`${name}: ${why}`);
  const pe = (el, type, x, y) => el.dispatchEvent(new PointerEvent(type, {
    clientX: x, clientY: y, bubbles: true, pointerId: 1, pointerType: 'touch' }));

  // ---- flip switches: state flips AND art swaps ----
  for (const sw of document.querySelectorAll('.flipsw')) {
    const name = `switch[${sw.title}]`;
    const before = sw.getAttribute('data-on');
    sw.click(); await wait(320);   // React render + 90ms art transition
    const after = sw.getAttribute('data-on');
    if (before === after) { bad(name, 'state did not flip'); continue; }
    const onImg = sw.querySelector('.sp-sw-img.on');
    if (onImg) {
      const op = getComputedStyle(onImg).opacity;
      if ((after === 'true') !== (op === '1')) { bad(name, 'sprite art did not swap'); continue; }
      if (!onImg.complete || onImg.naturalWidth === 0) { bad(name, 'sprite image failed to load'); continue; }
    }
    ok(name);
  }
  // restore EQ on so sliders are enabled
  const eqsw = [...document.querySelectorAll('.flipsw')].find(s => /^(ON|EQ)/.test(s.title) && s.getAttribute('data-on') === 'false');
  if (eqsw) { eqsw.click(); await wait(320); }

  // ---- segmented: each segment activates ----
  for (const segGroup of document.querySelectorAll('.segmented')) {
    const segs = [...segGroup.querySelectorAll('.seg')];
    for (const s of segs) {
      s.click(); await wait(80);
      if (s.getAttribute('data-active') !== 'true') { bad(`seg[${s.title}]`, 'did not activate'); }
      else ok(`seg[${s.title}]`);
    }
  }

  // ---- knobs: drag changes value; sprite rotates around well center ----
  for (const k of document.querySelectorAll('.knob')) {
    const name = `knob[${k.title.split(':')[0]}]`;
    const r = k.getBoundingClientRect();
    const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
    const v0 = parseInt(k.title.match(/(\d+)%/)?.[1] ?? '-1');
    const dir = v0 > 50 ? +60 : -60;            // drag toward the free end
    pe(k, 'pointerdown', cx, cy); pe(window, 'pointermove', cx, cy + dir); pe(window, 'pointerup', cx, cy + dir);
    await wait(120);
    const v1 = parseInt(k.title.match(/(\d+)%/)?.[1] ?? '-1');
    if (v0 === v1) { bad(name, `value stuck at ${v0}%`); continue; }
    const img = k.querySelector('.sp-knob-img');
    if (img) {
      const ir = img.getBoundingClientRect();
      const offC = Math.hypot((ir.x + ir.width / 2) - cx, (ir.y + ir.height / 2) - cy);
      if (offC > 3) { bad(name, `sprite center ${offC.toFixed(1)}px off well center (bad pivot)`); continue; }
      if (!img.complete || img.naturalWidth === 0) { bad(name, 'sprite failed to load'); continue; }
    }
    ok(name);
  }

  // ---- vertical sliders: full travel both ends ----
  const vss = [...document.querySelectorAll('.sk-slider-v')];
  for (let i = 0; i < vss.length; i++) {
    const s = vss[i]; const name = `slider-v[${i}]`;
    if (s.getAttribute('data-disabled') === 'true') { bad(name, 'disabled (EQ off?)'); continue; }
    const r = s.getBoundingClientRect(); const x = r.x + r.width / 2;
    const th = s.querySelector('.thumb');
    pe(s, 'pointerdown', x, r.top + 1); pe(window, 'pointerup', x, r.top + 1); await wait(80);
    const topPos = th.getBoundingClientRect();
    pe(s, 'pointerdown', x, r.bottom - 1); pe(window, 'pointerup', x, r.bottom - 1); await wait(80);
    const botPos = th.getBoundingClientRect();
    if (Math.abs(topPos.top - r.top) > 4) { bad(name, `thumb top short by ${(topPos.top - r.top).toFixed(1)}px`); continue; }
    if (Math.abs(botPos.bottom - r.bottom) > 4) { bad(name, `thumb bottom short by ${(r.bottom - botPos.bottom).toFixed(1)}px`); continue; }
    ok(name);
  }

  // ---- horizontal sliders: full travel (pause first: the seek thumb is
  // driven by the clock, which otherwise races the measurement) ----
  document.querySelector('.region button[title="pause"], .region button[title="Pause"]')?.click();
  await wait(150);
  const hss = [...document.querySelectorAll('.region .sk-slider-h')];
  for (let i = 0; i < hss.length; i++) {
    const s = hss[i]; const name = `slider-h[${i}]`;
    const r = s.getBoundingClientRect(); const y = r.y + r.height / 2;
    const th = s.querySelector('.thumb');
    pe(s, 'pointerdown', r.right - 1, y); pe(window, 'pointerup', r.right - 1, y); await wait(80);
    const right = th.getBoundingClientRect();
    pe(s, 'pointerdown', r.left + 1, y); pe(window, 'pointerup', r.left + 1, y); await wait(80);
    const left = th.getBoundingClientRect();
    if (Math.abs(right.right - r.right) > 4) { bad(name, `thumb right short by ${(r.right - right.right).toFixed(1)}px`); continue; }
    if (Math.abs(left.left - r.left) > 4) { bad(name, `thumb left short by ${(left.left - r.left).toFixed(1)}px`); continue; }
    ok(name);
  }

  // ---- transport buttons: next/prev change track; sprite faces load ----
  // shuffle must be OFF or prev cannot return to the original track
  const shsw = [...document.querySelectorAll('.flipsw')].find(s => /^SHUF/.test(s.title) && s.getAttribute('data-on') === 'true');
  if (shsw) { shsw.click(); await wait(320); }
  const cur = () => document.querySelector('.pl-row.current .pl-name')?.textContent;
  const btn = (t) => document.querySelector(`.region button[title="${t}"], .region button[title="${t.toLowerCase()}"]`);
  const before = cur();
  btn('Next')?.click() ?? btn('next')?.click(); await wait(150);
  if (cur() === before) bad('button[next]', 'track did not change'); else ok('button[next]');
  btn('Prev')?.click() ?? btn('prev')?.click(); await wait(150);
  if (cur() !== before) bad('button[prev]', 'did not return to original track'); else ok('button[prev]');
  for (const b of document.querySelectorAll('.tbtn.sp-btn')) {
    const bi = getComputedStyle(b).borderImageSource;
    if (bi && bi !== 'none' && !bi.includes('url')) bad(`button[${b.title}]`, 'sprite face missing');
  }

  // ---- playlist ----
  const rows = document.querySelectorAll('.pl-row');
  if (rows.length) {
    rows[Math.min(3, rows.length - 1)].click(); await wait(120);
    if (!rows[Math.min(3, rows.length - 1)].classList.contains('current')) bad('playlist', 'row select failed');
    else ok('playlist');
  }

  // ---- xy pad (if present) ----
  const xy = document.querySelector('.xy');
  if (xy) {
    const r = xy.getBoundingClientRect();
    pe(xy, 'pointerdown', r.x + r.width * 0.85, r.y + r.height * 0.2); pe(window, 'pointerup', 0, 0);
    await wait(100);
    const puck = xy.querySelector('.xy-puck');
    const pl = parseFloat(puck?.style.left ?? '0');
    if (Math.abs(pl - 85) > 6) bad('xy', `puck at ${pl}% expected ~85%`); else ok('xy');
  }

  return { passes, failures };
}
