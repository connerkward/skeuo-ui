// explainer_anim — LIVE canvas animations of the two gen12 placement algorithms,
// running the REAL math on the REAL artifacts (steam-porthole paint + BiRefNet matte
// + regions.json), not a canned cartoon.
//
//  Panel 1 (knob seat)   = extract12.py circle_fit() + matte-hole-centroid snap:
//    mini-Hough sweep over candidate circles (dy/dx step 3 within ±0.5·r0, r step 3 in
//    [0.7,1.3]·r0, 72 ring samples) scored by mean gradient magnitude; best ring locks
//    the RADIUS; the fit CENTRE then snaps to the matte alpha-hole centroid (the
//    regions.json `seat`, which extract12 computed exactly that way).
//  Panel 2 (seek travel) = extract12.py's coverage-span [travel] block: per-column
//    median of max(R,G,B) through the groove band; walk outward from the slot centre
//    through dark recess AND bright bezel rim, stop on sustained-bright body (brun>cap)
//    or near-black backdrop; span (±2% margin) becomes the thumb travel.
//
// Plain canvas + requestAnimationFrame; no build step. Loops forever.
(function () {
  "use strict";
  const SKIN = "assets-steam-porthole";

  const loadImg = (src) => new Promise((res, rej) => {
    const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = src;
  });
  // numpy-style linear-interpolation percentile (matches np.percentile default)
  function percentile(arr, p) {
    const a = Float64Array.from(arr).sort();
    const idx = (p / 100) * (a.length - 1);
    const lo = Math.floor(idx), hi = Math.ceil(idx);
    return a[lo] + (a[hi] - a[lo]) * (idx - lo);
  }
  const ease = (t) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

  // ── shared init: fetch regions + images once ────────────────────────────────
  Promise.all([
    fetch(SKIN + "/regions.json").then((r) => r.json()),
    loadImg(SKIN + "/paint.png"),
    loadImg(SKIN + "_biref/global-matte.png"),
    loadImg(SKIN + "_biref/seek.png"),
  ]).then(([reg, paint, matte, thumbImg]) => {
    const GW = paint.naturalWidth, GH = paint.naturalHeight;
    try { knobAnim(reg, paint, matte, GW, GH); } catch (e) { fail("anim-knob", e); }
    try { travelAnim(reg, paint, thumbImg, GW, GH); } catch (e) { fail("anim-travel", e); }
  }).catch((e) => { fail("anim-knob", e); fail("anim-travel", e); });

  function fail(id, e) {
    const cap = document.getElementById(id + "-cap");
    if (cap) cap.textContent = "animation failed to load: " + e;
    console.error(id, e);
  }
  function cap(id, txt) {
    const el = document.getElementById(id + "-cap");
    if (el) el.textContent = txt;
  }

  // ════════════════════════════════════════════════════════════════════════════
  // Panel 1 — gradient circle-fit → matte-hole centroid seat (vol knob)
  // ════════════════════════════════════════════════════════════════════════════
  function knobAnim(reg, paint, matte, GW, GH) {
    const canvas = document.getElementById("anim-knob");
    if (!canvas) return;
    const W = 720, H = 430; canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");

    const vol = reg.regions.vol;
    const mb = vol.maskDevice;                       // the bbox circle_fit() receives
    const seat = vol.seat;                           // extract12's FINAL seat (hole centroid + fit r)
    const cx0 = (mb[0] + mb[2] / 2) * GW, cy0 = (mb[1] + mb[3] / 2) * GH;
    const r0 = (mb[2] * GW + mb[3] * GH) / 4;
    const seatPx = { x: seat[0] * GW, y: seat[1] * GH, r: seat[2] * GW };

    // crop window (covers the full search extent: centre ±0.5·r0, r ≤ 1.3·r0)
    const half = Math.ceil(r0 * 2.0);
    const cropX = Math.round(cx0 - half), cropY = Math.round(cy0 - half), cropS = half * 2;
    // native-res offscreen crop → luminance → gradient magnitude (np.gradient equiv)
    const off = document.createElement("canvas"); off.width = cropS; off.height = cropS;
    const octx = off.getContext("2d", { willReadFrequently: true });
    octx.drawImage(paint, cropX, cropY, cropS, cropS, 0, 0, cropS, cropS);
    const px = octx.getImageData(0, 0, cropS, cropS).data;
    const lum = new Float32Array(cropS * cropS);
    for (let i = 0, j = 0; i < lum.length; i++, j += 4)
      lum[i] = 0.299 * px[j] + 0.587 * px[j + 1] + 0.114 * px[j + 2];  // PIL "L"
    const gmag = new Float32Array(cropS * cropS);
    for (let y = 0; y < cropS; y++) for (let x = 0; x < cropS; x++) {
      const gx = (lum[y * cropS + Math.min(cropS - 1, x + 1)] - lum[y * cropS + Math.max(0, x - 1)]) / (x > 0 && x < cropS - 1 ? 2 : 1);
      const gy = (lum[Math.min(cropS - 1, y + 1) * cropS + x] - lum[Math.max(0, y - 1) * cropS + x]) / (y > 0 && y < cropS - 1 ? 2 : 1);
      gmag[y * cropS + x] = Math.hypot(gx, gy);
    }

    // candidate list, EXACT parameterisation + nested order of circle_fit()
    const ANG = 72, ca = [], sa = [];
    for (let a = 0; a < ANG; a++) { ca.push(Math.cos(2 * Math.PI * a / ANG)); sa.push(Math.sin(2 * Math.PI * a / ANG)); }
    const cands = [];
    const dspan = Math.trunc(r0 * 0.5);
    for (let dy = -dspan; dy <= dspan; dy += 3)
      for (let dx = -dspan; dx <= dspan; dx += 3)
        for (let r = r0 * 0.7; r < r0 * 1.3; r += 3) cands.push([dx, dy, r]);
    // circle centre in crop-local coords is (half+dx, half+dy)
    function score(dx, dy, r) {
      let s = 0, n = 0;
      for (let a = 0; a < ANG; a++) {
        const x = Math.trunc(half + dx + r * ca[a]), y = Math.trunc(half + dy + r * sa[a]);
        if (x >= 0 && x < cropS && y >= 0 && y < cropS) { s += gmag[y * cropS + x]; n++; }
      }
      return n < 60 ? -1 : s / n;
    }

    // display geometry: crop square left, meter column right
    const D = 400, DX = 12, DY = 16, k = D / cropS;
    const cx = (x) => DX + (x - cropX) * k, cy = (y) => DY + (y - cropY) * k;   // paint px → canvas

    const SWEEP_S = 3.2, CHUNK = Math.max(1, Math.ceil(cands.length / (SWEEP_S * 60)));
    let phase = "sweep", pt = 0, ci = 0;
    let best = { s: 0, dx: 0, dy: 0, r: r0 }, curr = null, maxSeen = 1e-6;

    function ring(pcx, pcy, r, color, dash, width) {
      ctx.beginPath(); ctx.setLineDash(dash || []); ctx.lineWidth = width || 1.6;
      ctx.strokeStyle = color; ctx.arc(cx(pcx), cy(pcy), r * k, 0, 7); ctx.stroke(); ctx.setLineDash([]);
    }
    function dot(pcx, pcy, color, r) {
      ctx.beginPath(); ctx.fillStyle = color; ctx.arc(cx(pcx), cy(pcy), r || 3.5, 0, 7); ctx.fill();
    }
    function label(x, y, txt, color) {
      ctx.font = "11px ui-monospace,monospace"; const w = ctx.measureText(txt).width;
      ctx.fillStyle = "#000000cc"; ctx.fillRect(x - 3, y - 10, w + 6, 14);
      ctx.fillStyle = color; ctx.fillText(txt, x, y + 1);
    }
    function meter(y, name, val, color) {
      const MX = 430, MW = 268;
      ctx.fillStyle = "#9ab"; ctx.font = "11px ui-monospace,monospace"; ctx.fillText(name, MX, y - 5);
      ctx.fillStyle = "#161a22"; ctx.fillRect(MX, y, MW, 12);
      ctx.fillStyle = color; ctx.fillRect(MX, y, Math.max(0, Math.min(1, val / maxSeen)) * MW, 12);
      ctx.fillStyle = "#cdd3dd"; ctx.fillText(val.toFixed(1), MX + MW - 44, y + 10);
    }

    function frame() {
      ctx.fillStyle = "#0d0f14"; ctx.fillRect(0, 0, W, H);
      ctx.drawImage(paint, cropX, cropY, cropS, cropS, DX, DY, D, D);
      ctx.strokeStyle = "#3a4a63"; ctx.strokeRect(DX, DY, D, D);
      ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
      ctx.fillText("vol knob crop · real paint px", DX, DY - 5);

      if (phase === "sweep") {
        for (let n = 0; n < CHUNK && ci < cands.length; n++, ci++) {
          const [dx, dy, r] = cands[ci];
          const s = score(dx, dy, r);
          curr = { s, dx, dy, r };
          if (s > maxSeen) maxSeen = s;
          if (s > best.s) best = { s, dx, dy, r };
        }
        if (curr) {
          ring(cx0 + best.dx, cy0 + best.dy, best.r, "#5f7", [], 2);
          ring(cx0 + curr.dx, cy0 + curr.dy, curr.r, "#f55", [5, 4], 1.4);
          label(DX + 6, DY + D - 24, "candidate (dx,dy,r sweep)", "#f88");
          label(DX + 6, DY + D - 8, "best-so-far ring", "#5f7");
          meter(60, "edge score — candidate (mean |∇| on ring)", curr.s, "#f55");
          meter(100, "edge score — best", best.s, "#5f7");
          ctx.fillStyle = "#8a90a0";
          ctx.fillText(`candidates scored ${ci}/${cands.length}`, 430, 136);
          ctx.fillText(`best r=${best.r.toFixed(0)}px  centre Δ=(${best.dx},${best.dy})px`, 430, 152);
        }
        cap("anim-knob", "PHASE 1/3 · mini-Hough sweep: score every candidate circle (centre ±½r₀ step 3, r 0.7–1.3·r₀ step 3) by mean gradient magnitude along its 72-point ring — extract12.py circle_fit()");
        if (ci >= cands.length) { phase = "lock"; pt = 0; }
      } else if (phase === "lock") {
        pt++;
        const pulse = 1 + 0.04 * Math.sin(pt / 4);
        ring(cx0 + best.dx, cy0 + best.dy, best.r * pulse, "#5f7", [], 2.6);
        dot(cx0 + best.dx, cy0 + best.dy, "#f55", 4);
        label(cx(cx0 + best.dx) + 8, cy(cy0 + best.dy) - 8, "fit centre (glare-biased)", "#f88");
        meter(60, "edge score — best (LOCKED)", best.s, "#5f7");
        ctx.fillStyle = "#5f7"; ctx.font = "12px ui-monospace,monospace";
        ctx.fillText(`RADIUS LOCKED  r=${best.r.toFixed(0)}px`, 430, 100);
        ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText(`(regions.json seat r=${seatPx.r.toFixed(0)}px)`, 430, 118);
        cap("anim-knob", "PHASE 2/3 · best ring locks: the socket rim is the strongest edge, so the RADIUS is trustworthy — but the centre drifts toward the glary side");
        if (pt > 55) { phase = "snap"; pt = 0; }
      } else if (phase === "snap" || phase === "hold") {
        const t = phase === "snap" ? ease(Math.min(1, pt / 70)) : 1;
        pt++;
        // matte fades in: the alpha-hole (empty socket) shows as a gap in the white body
        ctx.save(); ctx.globalAlpha = 0.45 * t;
        ctx.drawImage(matte, cropX, cropY, cropS, cropS, DX, DY, D, D);
        ctx.restore();
        const fx = cx0 + best.dx, fy = cy0 + best.dy;
        const ix = fx + (seatPx.x - fx) * t, iy = fy + (seatPx.y - fy) * t;
        ring(ix, iy, best.r, "#5f7", [], 2.4);
        dot(fx, fy, "#f5555588", 3.5);                       // where the fit centre was
        dot(seatPx.x, seatPx.y, "#fd5", 4);                  // matte-hole centroid target
        dot(ix, iy, "#5f7", 4);                              // the sliding seat centre
        ctx.strokeStyle = "#fd5"; ctx.setLineDash([3, 3]); ctx.beginPath();
        ctx.moveTo(cx(fx), cy(fy)); ctx.lineTo(cx(seatPx.x), cy(seatPx.y)); ctx.stroke(); ctx.setLineDash([]);
        label(cx(seatPx.x) + 8, cy(seatPx.y) + 14, "matte-hole CENTROID", "#fd5");
        label(DX + 6, DY + D - 8, "BiRefNet global-matte (45%): empty socket = HOLE", "#9ab");
        ctx.fillStyle = "#cdd3dd"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText("SNAP: keep the fit RADIUS,", 430, 70);
        ctx.fillText("take the CENTRE from the", 430, 86);
        ctx.fillText("matte hole's centroid —", 430, 102);
        ctx.fillText("geometry, immune to glare.", 430, 118);
        ctx.fillStyle = "#5f7";
        ctx.fillText(`seat = (${seatPx.x.toFixed(0)}, ${seatPx.y.toFixed(0)}) r=${best.r.toFixed(0)}px`, 430, 146);
        cap("anim-knob", "PHASE 3/3 · seat snap: fit centre slides to the BiRefNet matte alpha-hole centroid (regions.json seat) — extract12.py [circle-fit] + hole-centroid override");
        if (phase === "snap" && pt > 70) { phase = "hold"; pt = 0; }
        if (phase === "hold" && pt > 110) {   // loop
          phase = "sweep"; pt = 0; ci = 0; best = { s: 0, dx: 0, dy: 0, r: r0 }; curr = null;
        }
      }
      // static footer inside canvas
      ctx.fillStyle = "#6a7080"; ctx.font = "10px ui-monospace,monospace";
      ctx.fillText("LIVE — real gradient math on the real crop · loops", 430, H - 12);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ════════════════════════════════════════════════════════════════════════════
  // Panel 2 — coverage-span seek travel (column median-luminance walk)
  // ════════════════════════════════════════════════════════════════════════════
  function travelAnim(reg, paint, thumbImg, GW, GH) {
    const canvas = document.getElementById("anim-travel");
    if (!canvas) return;
    const W = 760, H = 440; canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");

    const seek = reg.regions.seek;
    const b = seek.device, storedTv = seek.travel;   // extract12's shipped travel span
    // EXACT window construction from extract12.py's [travel] block
    const cyp = (b[1] + b[3] / 2) * GH;
    const hh = Math.max(6, Math.round(b[3] * GH * 0.30));
    const by0 = Math.round(cyp - hh), by1 = Math.round(cyp + hh);
    const pad = Math.round(b[2] * GW * 0.40);
    const bx0 = Math.max(0, Math.round(b[0] * GW) - pad);
    const bx1 = Math.min(GW, Math.round((b[0] + b[2]) * GW) + pad);
    const NC = bx1 - bx0;

    // med[x] = median over band rows of per-pixel max(R,G,B)
    const off = document.createElement("canvas"); off.width = NC; off.height = by1 - by0;
    const octx = off.getContext("2d", { willReadFrequently: true });
    octx.drawImage(paint, bx0, by0, NC, by1 - by0, 0, 0, NC, by1 - by0);
    const data = octx.getImageData(0, 0, NC, by1 - by0).data;
    const rows = by1 - by0;
    const med = new Float64Array(NC);
    const colv = new Float64Array(rows);
    for (let x = 0; x < NC; x++) {
      for (let y = 0; y < rows; y++) {
        const j = (y * NC + x) * 4;
        colv[y] = Math.max(data[j], data[j + 1], data[j + 2]);
      }
      med[x] = percentile(colv, 50);
    }
    const dx0 = Math.max(0, Math.round(b[0] * GW) - bx0);
    const dx1 = Math.min(NC, Math.round((b[0] + b[2]) * GW) - bx0);
    const ctr = (dx0 + dx1) >> 1;
    const Dfloor = percentile(med.slice(dx0, dx1), 15);
    const bgd = percentile(med, 2);
    const recess = Dfloor + 22, rim = Dfloor + 70;
    const capRun = Math.max(8, Math.trunc((dx1 - dx0) * 0.06));

    // _walk with a per-step trace: state ∈ recess|rim|mid|stop-body|stop-backdrop
    function walk(step) {
      const trace = []; let x = ctr, last = ctr, brun = 0;
      while (x >= 0 && x < NC) {
        if (med[x] <= bgd + 8) { trace.push({ x, st: "stop-backdrop" }); break; }
        if (med[x] < recess) { last = x; brun = 0; trace.push({ x, st: "recess" }); }
        else if (med[x] > rim) {
          last = x; brun++; trace.push({ x, st: "rim" });
          if (brun > capRun) { trace[trace.length - 1].st = "stop-body"; break; }
        } else { brun = 0; trace.push({ x, st: "mid" }); }
        x += step;
      }
      return { trace, last };
    }
    const L = walk(-1), R = walk(+1);
    let lo = bx0 + L.last, hi = bx0 + R.last;
    const gx0 = Math.round(b[0] * GW), gx1 = Math.round((b[0] + b[2]) * GW);
    if (hi - lo < 0.5 * (gx1 - gx0)) { lo = gx0; hi = gx1; }   // collapse guard (same as extract12)
    const M = Math.trunc((hi - lo) * 0.02);
    const tvLo = Math.max(0, lo - M), tvHi = Math.min(GW, hi + M);

    // display geometry: strip crop on top (taller band for context), chart below
    const CX = 10, CY = 18, CW = 740, CH = 150;
    const srcH = Math.round(NC * CH / CW);                    // preserve aspect
    const srcY = Math.round(cyp - srcH / 2);
    const X = (col) => CX + col * (CW / NC);                  // band col → canvas x
    const XY = (py) => CY + (py - srcY) * (CH / srcH);        // paint y → canvas y
    const PH_X = 10, PH_Y = 205, PH_W = 740, PH_H = 150;      // profile chart
    const YV = (v) => PH_Y + PH_H - (v / 255) * PH_H;

    const STC = { recess: "#5af", rim: "#fd5", mid: "#9aa", "stop-body": "#f55", "stop-backdrop": "#f0f" };
    // thumb draw size (aspect-true, height ≈ groove for a readable slide)
    const kx = CW / NC;
    const thumbH = 54, thumbW = thumbH * thumbImg.naturalWidth / thumbImg.naturalHeight;

    let phase = "profile", pt = 0, wi = 0;
    const WALK_FRAMES = 150;                                   // both walkers finish together
    const perFrameL = L.trace.length / WALK_FRAMES, perFrameR = R.trace.length / WALK_FRAMES;

    function thresholds() {
      for (const [v, name, c] of [[recess, `recess < ${recess.toFixed(0)}`, "#5af"],
                                  [rim, `rim > ${rim.toFixed(0)}`, "#fd5"],
                                  [bgd + 8, `backdrop ≤ ${(bgd + 8).toFixed(0)}`, "#f0f"]]) {
        ctx.strokeStyle = c + "66"; ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(PH_X, YV(v)); ctx.lineTo(PH_X + PH_W, YV(v)); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = c; ctx.font = "10px ui-monospace,monospace"; ctx.fillText(name, PH_X + PH_W - 118, YV(v) - 3);
      }
    }
    function curve(color, upTo) {
      ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath();
      for (let x = 0; x < NC; x++) { const X1 = X(x), Y1 = YV(med[x]); x ? ctx.lineTo(X1, Y1) : ctx.moveTo(X1, Y1); }
      ctx.stroke();
    }
    function tracePaint(trace, n) {
      for (let i = 0; i < Math.min(n, trace.length); i++) {
        const t = trace[i];
        ctx.fillStyle = STC[t.st];
        ctx.fillRect(X(t.x), YV(med[t.x]) - 1.5, Math.max(1, kx), 3);      // on the chart
        ctx.globalAlpha = 0.5; ctx.fillRect(X(t.x), CY, Math.max(1, kx), 5); ctx.globalAlpha = 1;  // tick strip on crop
      }
    }
    function walker(trace, n, lbl) {
      const i = Math.min(trace.length, Math.max(1, Math.round(n))) - 1;
      const t = trace[i];
      ctx.strokeStyle = STC[t.st]; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(X(t.x), CY); ctx.lineTo(X(t.x), CY + CH); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(X(t.x), YV(med[t.x]) - 8); ctx.lineTo(X(t.x), YV(med[t.x]) + 8); ctx.stroke();
      ctx.fillStyle = STC[t.st]; ctx.font = "10px ui-monospace,monospace";
      ctx.fillText(lbl + (t.st.startsWith("stop") ? " · " + t.st : " · " + t.st), X(t.x) - 20, CY + CH + 12);
    }

    function frame() {
      ctx.fillStyle = "#0d0f14"; ctx.fillRect(0, 0, W, H);
      // crop band
      ctx.drawImage(paint, bx0, srcY, NC, srcH, CX, CY, CW, CH);
      ctx.strokeStyle = "#3a4a63"; ctx.strokeRect(CX, CY, CW, CH);
      ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
      ctx.fillText("seek slot crop · real paint px (groove band ±" + hh + "px sampled)", CX, CY - 6);
      // groove-band guides + centre
      ctx.strokeStyle = "#5a7cff44";
      ctx.strokeRect(CX, XY(by0), CW, XY(by1) - XY(by0));
      ctx.strokeStyle = "#8a90a0"; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(X(ctr), CY); ctx.lineTo(X(ctr), PH_Y + PH_H); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = "#8a90a0"; ctx.fillText("centre", X(ctr) - 17, PH_Y + PH_H + 12);
      // chart frame
      ctx.strokeStyle = "#2a3345"; ctx.strokeRect(PH_X, PH_Y, PH_W, PH_H);
      ctx.fillStyle = "#8a90a0"; ctx.fillText("per-column MEDIAN luminance (max RGB) — the profile the walker reads", PH_X, PH_Y - 6);
      thresholds();
      curve("#3d4658");

      if (phase === "profile") {
        pt++;
        cap("anim-travel", "PHASE 1/4 · profile: median of max(R,G,B) per column through the groove band; floors from percentiles → recess/rim/backdrop thresholds — extract12.py [travel]");
        if (pt > 50) { phase = "walk"; pt = 0; wi = 0; }
      } else if (phase === "walk") {
        wi++;
        tracePaint(L.trace, wi * perFrameL); tracePaint(R.trace, wi * perFrameR);
        walker(L.trace, wi * perFrameL, "◀"); walker(R.trace, wi * perFrameR, "▶");
        cap("anim-travel", "PHASE 2/4 · walk outward BOTH ways from centre: dark recess (blue) and bright bezel rim (yellow) both count as slot; sustained-bright body (red, brun>cap) or near-black backdrop stops the walk");
        if (wi >= WALK_FRAMES + 20) { phase = "span"; pt = 0; }
      } else {
        // keep the full coloured trace visible
        tracePaint(L.trace, L.trace.length); tracePaint(R.trace, R.trace.length);
        walker(L.trace, L.trace.length, "◀"); walker(R.trace, R.trace.length, "▶");
        const t = phase === "span" ? ease(Math.min(1, pt / 40)) : 1;
        pt++;
        // travel bar grows out from centre to the ±2% padded span
        const c = X(ctr);
        const xl = c + (X(tvLo - bx0) - c) * t, xr = c + (X(tvHi - bx0) - c) * t;
        const barY = CY + CH + 22;
        ctx.fillStyle = "#5f7"; ctx.fillRect(xl, barY, xr - xl, 6);
        ctx.fillRect(xl, barY - 4, 2, 14); ctx.fillRect(xr - 2, barY - 4, 2, 14);
        ctx.fillStyle = "#8fa"; ctx.font = "10px ui-monospace,monospace";
        ctx.fillText(`travel = [${(tvLo / GW).toFixed(4)}, ${(tvHi / GW).toFixed(4)}] (walk span ± 2%)`, xl, barY + 20);
        // cross-check ticks: the travel extract12 actually shipped in regions.json
        for (const v of storedTv) {
          const xx = X(v * GW - bx0);
          ctx.strokeStyle = "#fff"; ctx.beginPath(); ctx.moveTo(xx, barY - 7); ctx.lineTo(xx, barY + 13); ctx.stroke();
        }
        ctx.fillStyle = "#cdd3dd"; ctx.fillText("white ticks = regions.json travel (shipped)", X(NC * 0.55), barY + 20);
        if (phase === "span") {
          cap("anim-travel", "PHASE 3/4 · span snap: travel = walked slot extent + 2% margin; white ticks are the values extract12 shipped in regions.json — they coincide");
          if (pt > 70) { phase = "slide"; pt = 0; }
        } else if (phase === "slide" || phase === "hold") {
          // thumb slides end-to-end: x0 = travel[0], x1 = travel[1] − thumbW (consumer clamp)
          const x0c = X(tvLo - bx0), x1c = X(tvHi - bx0) - thumbW;
          let u = phase === "slide" ? Math.min(1, pt / 170) : 1;
          const uu = u < 0.5 ? ease(u * 2) : ease(2 - u * 2);      // there and back
          const tx = x0c + (x1c - x0c) * uu;
          ctx.drawImage(thumbImg, tx, CY + CH / 2 - thumbH / 2, thumbW, thumbH);
          ctx.strokeStyle = "#5f7"; ctx.strokeRect(tx, CY + CH / 2 - thumbH / 2, thumbW, thumbH);
          cap("anim-travel", "PHASE 4/4 · coverage: the real cut thumb (BiRefNet seek.png) slides x∈[travel₀, travel₁−thumbW] — its extremes visually COVER the slot ends incl. bezel rims");
          if (phase === "slide" && pt > 170) { phase = "hold"; pt = 0; }
          if (phase === "hold" && pt > 60) { phase = "profile"; pt = 0; }
        }
      }
      // legend
      ctx.font = "10px ui-monospace,monospace";
      const leg = [["dark recess", "#5af"], ["bright bezel rim", "#fd5"], ["mid (rim slope)", "#9aa"],
                   ["STOP: sustained-bright body", "#f55"], ["STOP: backdrop", "#f0f"]];
      let lx = 12;
      for (const [name, c] of leg) {
        ctx.fillStyle = c; ctx.fillRect(lx, H - 20, 8, 8);
        ctx.fillStyle = "#8a90a0"; ctx.fillText(name, lx + 11, H - 12);
        lx += ctx.measureText(name).width + 34;
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
})();
