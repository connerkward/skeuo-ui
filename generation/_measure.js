// Capture, per skin: a screenshot of the player + the LIVE bounding boxes of the
// actually-rendered controls (normalized to the player), so alignment is judged
// from real DOM positions, not template rects. Returns JSON; screenshots land in
// .playwright-mcp/m-<i>.png. Re-run each iteration to re-measure.
async (page) => {
  await page.evaluate(() => { const cb=document.querySelector('.wire-toggle-row input[type=checkbox]'); if(cb&&cb.checked)cb.click(); });
  const n = await page.evaluate(() => document.querySelectorAll('button.style-btn').length);
  const all = [];
  for (let i = 0; i < n; i++) {
    const name = await page.evaluate((idx) => {
      const b=[...document.querySelectorAll('button.style-btn')][idx]; b.click();
      return b.textContent.trim().split('✦')[0].trim();
    }, i);
    await page.waitForTimeout(200);
    await page.evaluate(() => { const p=[...document.querySelectorAll('button.tbtn')].find(b=>b.title==='play'); if(p)p.click(); });
    await page.waitForTimeout(380);
    await page.locator('.player').screenshot({ path: `.playwright-mcp/m-${String(i).padStart(2,'0')}.png` });
    const boxes = await page.evaluate(() => {
      const P = document.querySelector('.player'); const pr = P.getBoundingClientRect();
      const tag = (e) => {
        const c = ' '+(e.className||'')+' ';
        if (e.matches('button.tbtn')) return 'btn';
        if (/sk-slider-arc/.test(c)) return 'seek';
        if (/sk-slider-h/.test(c)) return 'seek';
        if (/sk-slider-v/.test(c)) return 'eq';
        if (/(^| )knob|sp-knob( |$)/.test(c) && !/img|ptr/.test(c)) return 'knob';
        if (/flip-switch|sk-switch|toggle/.test(c)) return 'switch';
        return null;
      };
      const out = [];
      for (const e of P.querySelectorAll('button.tbtn, [class*="slider"], [class*="knob"], [class*="switch"], [class*="flip"], [class*="toggle"]')) {
        const t = tag(e); if (!t) continue;
        const r = e.getBoundingClientRect(); if (r.width<2||r.height<2) continue;
        out.push({ t, x:+((r.left-pr.left)/pr.width).toFixed(4), y:+((r.top-pr.top)/pr.height).toFixed(4),
                   w:+(r.width/pr.width).toFixed(4), h:+(r.height/pr.height).toFixed(4) });
      }
      return out;
    });
    all.push({ i, name, boxes });
  }
  return JSON.stringify(all);
}
