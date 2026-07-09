// explainer_anim — LIVE canvas animations of the gen12 placement algorithms,
// running the REAL math on the REAL artifacts (paints, masks, BiRefNet mattes/cuts
// + regions.json), not a canned cartoon.
//
//  Panel 1 (knob seat)   = extract12.py circle_fit() + matte-hole-centroid snap:
//    mini-Hough sweep over candidate circles (dy/dx step 3 within ±0.5·r0, r step 3 in
//    [0.7,1.3]·r0, 72 ring samples) scored by mean gradient magnitude; best ring locks
//    the RADIUS; the fit CENTRE then snaps to the matte alpha-hole centroid (the
//    regions.json `seat`, which extract12 computed exactly that way).
//  Panel 2 (seek travel) = extract12.py's LEVEL-AWARE coverage-span [travel] block:
//    per-column median of max(R,G,B) through the groove band (box-smoothed); base span =
//    the slot's MASK CELL (never walked inside — baked-handle-proof); from each cell edge
//    walk OUTWARD while columns stay clearly below the PER-SIDE local body plateau
//    (recessed at any depth — dark channel or lighter stepped trough) or are a bright
//    bezel rim; stop on a short sustained near-body run, a sustained bright run, or the
//    designed backdrop COLOUR (distance-from-BGC); clamp ±12% of cell width; span (±2%
//    margin) becomes the thumb travel. The loop ENDS on a green "SHIPPED ✓" beat that
//    checks the recomputed span against the live regions.json travel (⚠ if they drift).
//  Panel 3 (slot angle)  = extract12.py _pca_angle(): the toggle slot's mask pixels
//    (device band ONLY — (assign==idx)&(YY<devFrac·H)) as a point cloud; principal-axis
//    search (trial axis + variance meter) → eigen lock (success). Then two BANNER-
//    LABELLED asides: a red "OLD BUG (fixed)" re-enactment (strip-cell pixels flash in
//    → combined axis = slot→strip diagonal), the green "FIX" (device-only), an amber
//    "SAFETY GATE" demo (near-round knob blob → refuse rotation, by design) — and the
//    loop ENDS on a green "SHIPPED ✓" hold that recomputes the full rot decision
//    (slot − part axis, cardinal snap, gates) and verifies it against live regions.json.
//  Panel 4 (state align) = extract12.py silhouette state-registration: scale the ON
//    cut's alpha to the OFF bbox, slide it over a (dx,dy)∈[-12,12]² grid maximising
//    silhouette IoU (heat-trail + live meter), lock at max → regions.json stateAlign;
//    then the two real cuts swap in place with the housing static.
//
// Plain canvas + requestAnimationFrame; no build step, no deps. Loops forever.
// A shared speed control (#animctl: 0.25×–4× + pause) scales every panel's clock;
// each panel registers a restart in RESTARTS (wired to its ⟲ button).
(function () {
  "use strict";
  // Exemplar skins chosen where each algorithm's interesting path actually fires,
  // AND whose CURRENT shipped regions.json is demonstrably correct (the panels re-run
  // the real math on the live served assets, so a regenerated exemplar can silently
  // invalidate the narrative — validate after every batch regen):
  //  · steam-porthole: the vol knob's fit-centre → hole-centroid snap is visible,
  //    and its shuffle cuts differ enough that state-registration is non-trivial.
  //  · wc-goldshield: a CLEAN dark groove whose pointed end caps the mask cell
  //    UNDERSHOOTS — the outward walks extend ~50px past both cell edges through the
  //    below-body recess and stop cleanly on body; the shipped travel lands exactly on
  //    the visual tips (recompute == regions.json to 1e-5, verified on the paint crop).
  //    (wmp-quicksilver, the previous exemplar, over-walks LEFT into the neighbouring
  //    knob's shadow — shipped travel_lo sits ~78px onto the body, so the thumb's left
  //    extreme visibly hangs off the slot; ps1-crunchy has a BAKED handle in the slot.)
  //  · n64-cutscene: the shuffle slot is strongly VERTICAL (elong 2.9 → axis real),
  //    its strip cells drag the combined axis to a +48° garbage diagonal (the old-bug
  //    re-enactment shows a REAL failure), and its vol knob blob is near-round
  //    (elong 1.0 → the safety gate fires). (diablo-gothic, the previous exemplar,
  //    was regenerated 2026-07-09: its slot blob now reads elong 1.86 < the 2.0 gate
  //    and its strip cells sit directly below → no garbage contrast. Unsuitable.)
  const KNOB_SKIN = "assets-steam-porthole";
  const TRAVEL_SKIN = "assets-wc-goldshield";
  const PCA_SKIN = "assets-n64-cutscene";
  const IOU_SKIN = "assets-steam-porthole";

  // ── shared speed control ────────────────────────────────────────────────────
  // Every panel advances its clock by adv() per rAF tick instead of a hard ++,
  // so one control bar scales all four animations (pause ⇒ adv()=0: still drawn,
  // frozen in place).
  const SPEED = { mult: 1, paused: false };
  const adv = () => (SPEED.paused ? 0 : SPEED.mult);
  const RESTARTS = {};   // canvas id → reset fn (per-panel ⟲ button)
  (function wireControls() {
    const bar = document.getElementById("animctl");
    if (bar) {
      bar.querySelectorAll("button[data-sp]").forEach((b) => {
        b.addEventListener("click", () => {
          SPEED.mult = parseFloat(b.dataset.sp);
          bar.querySelectorAll("button[data-sp]").forEach((x) => x.classList.toggle("on", x === b));
        });
      });
      const p = document.getElementById("anim-pause");
      if (p) p.addEventListener("click", () => {
        SPEED.paused = !SPEED.paused;
        p.classList.toggle("on", SPEED.paused);
        p.textContent = SPEED.paused ? "▶ resume" : "⏸ pause";
      });
    }
    document.querySelectorAll(".arst").forEach((b) => {
      b.addEventListener("click", () => { const f = RESTARTS[b.dataset.anim]; if (f) f(); });
    });
  })();

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
  // full-width banner strip across the canvas top — used to UNAMBIGUOUSLY frame a
  // phase as history ("OLD BUG (fixed)"), shipped fix, safety demo, or final success,
  // so a re-enacted failure can never be mistaken for the algorithm failing live.
  // Drawn along the BOTTOM edge (over the legend/footer strip) so it never covers
  // the live crop/stage pixels the phase is actually about.
  function banner(ctx, W, H, txt, bg, fg) {
    ctx.fillStyle = bg; ctx.fillRect(0, H - 32, W, 32);
    ctx.fillStyle = fg;
    let fs = 15;                                   // auto-fit: never clip the banner text
    do { ctx.font = "bold " + fs + "px ui-monospace,monospace"; fs--; }
    while (fs > 9 && ctx.measureText(txt).width > W - 16);
    ctx.textAlign = "center"; ctx.fillText(txt, W / 2, H - 11); ctx.textAlign = "left";
  }

  // ── init: each panel fetches its exemplar skin's real artifacts ─────────────
  Promise.all([
    fetch(KNOB_SKIN + "/regions.json").then((r) => r.json()),
    loadImg(KNOB_SKIN + "/paint.png"),
    loadImg(KNOB_SKIN + "_biref/global-matte.png"),
  ]).then(([reg, paint, matte]) => {
    try { knobAnim(reg, paint, matte, paint.naturalWidth, paint.naturalHeight); }
    catch (e) { fail("anim-knob", e); }
  }).catch((e) => fail("anim-knob", e));

  Promise.all([
    fetch(TRAVEL_SKIN + "/regions.json").then((r) => r.json()),
    fetch(TRAVEL_SKIN + "/results.json").then((r) => r.json()),   // backdrop colour for cdist
    loadImg(TRAVEL_SKIN + "/paint.png"),
    loadImg(TRAVEL_SKIN + "_biref/seek.png"),
  ]).then(([reg, res, paint, thumbImg]) => {
    try { travelAnim(reg, res, paint, thumbImg, paint.naturalWidth, paint.naturalHeight); }
    catch (e) { fail("anim-travel", e); }
  }).catch((e) => fail("anim-travel", e));

  Promise.all([
    fetch(PCA_SKIN + "/regions.json").then((r) => r.json()),
    loadImg(PCA_SKIN + "/mask.png"),
    loadImg(PCA_SKIN + "/paint.png"),
    loadImg(PCA_SKIN + "_biref/shuffle_off.png"),   // part axis (rot is RELATIVE to it)
  ]).then(([reg, mask, paint, partImg]) => {
    try { pcaAnim(reg, mask, paint, partImg); }
    catch (e) { fail("anim-pca", e); }
  }).catch((e) => fail("anim-pca", e));

  Promise.all([
    fetch(IOU_SKIN + "/regions.json").then((r) => r.json()),
    loadImg(IOU_SKIN + "_biref/shuffle_off.png"),
    loadImg(IOU_SKIN + "_biref/shuffle_on.png"),
  ]).then(([reg, offImg, onImg]) => {
    try { iouAnim(reg, offImg, onImg); }
    catch (e) { fail("anim-iou", e); }
  }).catch((e) => fail("anim-iou", e));

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
    let phase, pt, ci, cif, best, curr, maxSeen;
    function reset() {
      phase = "sweep"; pt = 0; ci = 0; cif = 0;
      best = { s: 0, dx: 0, dy: 0, r: r0 }; curr = null; maxSeen = 1e-6;
    }
    reset();
    RESTARTS["anim-knob"] = reset;

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
      const a = adv();
      ctx.fillStyle = "#0d0f14"; ctx.fillRect(0, 0, W, H);
      ctx.drawImage(paint, cropX, cropY, cropS, cropS, DX, DY, D, D);
      ctx.strokeStyle = "#3a4a63"; ctx.strokeRect(DX, DY, D, D);
      ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
      ctx.fillText("vol knob crop · real paint px", DX, DY - 5);

      if (phase === "sweep") {
        cif = Math.min(cands.length, cif + CHUNK * a);
        for (; ci < cif; ci++) {
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
        pt += a;
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
        pt += a;
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
        if (phase === "hold" && pt > 110) reset();   // loop
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
  function travelAnim(reg, res, paint, thumbImg, GW, GH) {
    const canvas = document.getElementById("anim-travel");
    if (!canvas) return;
    const W = 760, H = 470; canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");

    const seek = reg.regions.seek;
    const b = seek.device, mb = seek.maskDevice || b, storedTv = seek.travel;
    const BGC = res.backdrop;                        // designed backdrop colour (results.json)
    // EXACT window construction from extract12.py's LEVEL-AWARE [travel] block
    const cyp = (b[1] + b[3] / 2) * GH;
    const hh = Math.max(6, Math.round(b[3] * GH * 0.30));
    const by0 = Math.round(cyp - hh), by1 = Math.round(cyp + hh);
    const ux0 = Math.min(b[0], mb[0]), ux1 = Math.max(b[0] + b[2], mb[0] + mb[2]);
    const pad = Math.round((ux1 - ux0) * GW * 0.40);
    const bx0 = Math.max(0, Math.round(ux0 * GW) - pad);
    const bx1 = Math.min(GW, Math.round(ux1 * GW) + pad);
    const NC = bx1 - bx0;

    // med[x] = median over band rows of per-pixel max(R,G,B), box-smoothed (7)
    // cdist[x] = median over band rows of max-channel |rgb − backdrop|
    const off = document.createElement("canvas"); off.width = NC; off.height = by1 - by0;
    const octx = off.getContext("2d", { willReadFrequently: true });
    octx.drawImage(paint, bx0, by0, NC, by1 - by0, 0, 0, NC, by1 - by0);
    const data = octx.getImageData(0, 0, NC, by1 - by0).data;
    const rows = by1 - by0;
    const medRaw = new Float64Array(NC), cdist = new Float64Array(NC);
    const colv = new Float64Array(rows), cdv = new Float64Array(rows);
    for (let x = 0; x < NC; x++) {
      for (let y = 0; y < rows; y++) {
        const j = (y * NC + x) * 4;
        colv[y] = Math.max(data[j], data[j + 1], data[j + 2]);
        cdv[y] = Math.max(Math.abs(data[j] - BGC[0]), Math.abs(data[j + 1] - BGC[1]), Math.abs(data[j + 2] - BGC[2]));
      }
      medRaw[x] = percentile(colv, 50);
      cdist[x] = percentile(cdv, 50);
    }
    const med = new Float64Array(NC);                // np.convolve(·, ones(7)/7, "same")
    for (let x = 0; x < NC; x++) {
      let s = 0;
      for (let k = x - 3; k <= x + 3; k++) if (k >= 0 && k < NC) s += medRaw[k];
      med[x] = s / 7;
    }
    const dx0 = Math.max(0, Math.round(b[0] * GW) - bx0);
    const dx1 = Math.min(NC, Math.round((b[0] + b[2]) * GW) - bx0);
    let mx0 = Math.max(0, Math.round(mb[0] * GW) - bx0);
    let mx1 = Math.min(NC, Math.round((mb[0] + mb[2]) * GW) - bx0);
    if (mx1 <= mx0) { mx0 = dx0; mx1 = dx1; }
    const cw = Math.max(1, mx1 - mx0);
    const bgd = Math.max(BGC[0], BGC[1], BGC[2]);
    const Dfloor = percentile(med.slice(mx0, mx1), 10);   // darkest fraction of the CELL
    const fw = Math.max(30, Math.trunc(cw * 0.20));       // per-side flank window
    const bodyOf = (arr) => {                             // local plateau, recess+backdrop excluded
      const fl = Array.from(arr).filter((v) => v > bgd + 25 && v > Dfloor + 15);
      return fl.length >= 8 ? percentile(fl, 50) : null;
    };
    const bodyGlob = bodyOf(med) ?? percentile(med, 85);
    const bodyL = bodyOf(med.slice(Math.max(0, mx0 - 4 - fw), Math.max(0, mx0 - 4))) ?? bodyGlob;
    const bodyR = bodyOf(med.slice(mx1 + 4, mx1 + 4 + fw)) ?? bodyGlob;
    const belowOf = (body) => body - Math.max(14, 0.22 * Math.max(0, body - Dfloor));
    const rimcap = Math.max(8, Math.trunc(cw * 0.06));    // TOTAL bright budget per walk
    const stopcap = Math.max(6, Math.trunc(cw * 0.02));

    // outward walk from a CELL EDGE with a per-step trace:
    // state ∈ recess|rim|body|stop-body|stop-rim|stop-backdrop
    // rrun is CUMULATIVE (never reset): a real bezel is ONE contiguous bright band; a bright
    // carved frame alternating with shadow seams would ride rim→recess→rim forever otherwise.
    function walk(edge, step, body) {
      const below = belowOf(body), rimhi = body + 20;
      const trace = []; let x = edge + step, last = edge, nrun = 0, rrun = 0;
      while (x >= 0 && x < NC) {
        if (cdist[x] < 30) { trace.push({ x, st: "stop-backdrop" }); break; }
        if (med[x] < below) { last = x; nrun = 0; trace.push({ x, st: "recess" }); }
        else if (med[x] > rimhi) {
          last = x; rrun++; nrun = 0; trace.push({ x, st: "rim" });
          if (rrun > rimcap) { trace[trace.length - 1].st = "stop-rim"; break; }
        } else {
          nrun++; trace.push({ x, st: "body" });
          if (nrun > stopcap) { trace[trace.length - 1].st = "stop-body"; break; }
        }
        x += step;
      }
      return { trace, last };
    }
    const L = walk(mx0, -1, bodyL), R = walk(mx1 - 1, +1, bodyR);
    let lo = bx0 + L.last, hi = bx0 + R.last;
    const gx0 = Math.round(b[0] * GW), gx1 = Math.round((b[0] + b[2]) * GW);
    if (hi - lo < 0.5 * (gx1 - gx0)) { lo = gx0; hi = gx1; }   // collapse guard (same as extract12)
    lo = Math.max(lo, bx0 + mx0 - Math.trunc(0.12 * cw));      // clamp: mask cell ±12%
    hi = Math.min(hi, bx0 + mx1 + Math.trunc(0.12 * cw));
    const M = Math.trunc((hi - lo) * 0.02);
    const tvLo = Math.max(0, lo - M), tvHi = Math.min(GW, hi + M);

    // display geometry: strip crop on top (taller band for context), chart below
    const CX = 10, CY = 18, CW = 740, CH = 150;
    const srcH = Math.round(NC * CH / CW);                    // preserve aspect
    const srcY = Math.round(cyp - srcH / 2);
    const X = (col) => CX + col * (CW / NC);                  // band col → canvas x
    const XY = (py) => CY + (py - srcY) * (CH / srcH);        // paint y → canvas y
    const PH_X = 10, PH_Y = 248, PH_W = 740, PH_H = 150;      // profile chart
    const YV = (v) => PH_Y + PH_H - (v / 255) * PH_H;

    const STC = { recess: "#5af", rim: "#fd5", body: "#9aa",
                  "stop-body": "#f55", "stop-rim": "#fa0", "stop-backdrop": "#f0f" };
    // thumb draw size (aspect-true, height ≈ groove for a readable slide)
    const kx = CW / NC;
    const thumbH = 54, thumbW = thumbH * thumbImg.naturalWidth / thumbImg.naturalHeight;

    let phase, pt, wi;
    function reset() { phase = "profile"; pt = 0; wi = 0; }
    reset();
    RESTARTS["anim-travel"] = reset;
    const WALK_FRAMES = 150;                                   // both walkers finish together
    const perFrameL = L.trace.length / WALK_FRAMES, perFrameR = R.trace.length / WALK_FRAMES;

    function cellShade() {                                     // the mask cell = base span
      ctx.fillStyle = "#5a7cff18";
      ctx.fillRect(X(mx0), CY, X(mx1) - X(mx0), CH);
      ctx.fillRect(X(mx0), PH_Y, X(mx1) - X(mx0), PH_H);
      ctx.strokeStyle = "#5a7cff66";
      for (const mx of [mx0, mx1]) {
        ctx.beginPath(); ctx.moveTo(X(mx), CY); ctx.lineTo(X(mx), PH_Y + PH_H); ctx.stroke();
      }
      ctx.fillStyle = "#7a9cff"; ctx.font = "10px ui-monospace,monospace";
      ctx.fillText("mask cell (model's slot declaration — walks start at its edges)", X(mx0) + 4, PH_Y + PH_H + 12);
    }
    function thresholds() {                                    // PER-SIDE body + below lines
      const segs = [[PH_X, X(mx0), bodyL, "L"], [X(mx1), PH_X + PH_W, bodyR, "R"]];
      for (const [xa, xb, body, tag] of segs) {
        const below = belowOf(body);
        ctx.strokeStyle = "#ccbb9966"; ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(xa, YV(body)); ctx.lineTo(xb, YV(body)); ctx.stroke();
        ctx.strokeStyle = "#55aaff66";
        ctx.beginPath(); ctx.moveTo(xa, YV(below)); ctx.lineTo(xb, YV(below)); ctx.stroke();
        ctx.setLineDash([]);
        ctx.font = "10px ui-monospace,monospace";
        ctx.fillStyle = "#cb9";
        ctx.fillText(`body ${tag} ${body.toFixed(0)}`, tag === "L" ? xa + 2 : xb - 74, YV(body) - 3);
        ctx.fillStyle = "#5af";
        ctx.fillText(`below < ${below.toFixed(0)}`, tag === "L" ? xa + 2 : xb - 74, YV(below) + 11);
      }
    }
    function curve(color) {
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
      if (!trace.length) return;
      const i = Math.min(trace.length, Math.max(1, Math.round(n))) - 1;
      const t = trace[i];
      ctx.strokeStyle = STC[t.st]; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(X(t.x), CY); ctx.lineTo(X(t.x), CY + CH); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(X(t.x), YV(med[t.x]) - 8); ctx.lineTo(X(t.x), YV(med[t.x]) + 8); ctx.stroke();
      ctx.fillStyle = STC[t.st]; ctx.font = "10px ui-monospace,monospace";
      ctx.fillText(lbl + " · " + t.st, X(t.x) - 20, CY + CH + 12);
    }

    function frame() {
      const a = adv();
      ctx.fillStyle = "#0d0f14"; ctx.fillRect(0, 0, W, H);
      // crop band
      ctx.drawImage(paint, bx0, srcY, NC, srcH, CX, CY, CW, CH);
      ctx.strokeStyle = "#3a4a63"; ctx.strokeRect(CX, CY, CW, CH);
      ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
      ctx.fillText("seek slot crop · real paint px (groove band ±" + hh + "px sampled)", CX, CY - 6);
      // groove-band guides
      ctx.strokeStyle = "#5a7cff44";
      ctx.strokeRect(CX, XY(by0), CW, XY(by1) - XY(by0));
      // chart frame
      ctx.strokeStyle = "#2a3345"; ctx.strokeRect(PH_X, PH_Y, PH_W, PH_H);
      ctx.fillStyle = "#8a90a0"; ctx.fillText("per-column MEDIAN luminance (max RGB, smoothed) — the profile the walkers read", PH_X, PH_Y - 6);
      cellShade();
      thresholds();
      curve("#3d4658");

      if (phase === "profile") {
        pt += a;
        cap("anim-travel", "PHASE 1/5 · profile: median of max(R,G,B) per column through the groove band (box-smoothed 7px). Base span = the slot's MASK CELL (shaded) — never walked inside, so a baked handle can't derail anything. Body plateau per SIDE from the flanking band (dashed) — extract12.py [travel]");
        if (pt > 50) { phase = "walk"; pt = 0; wi = 0; }
      } else if (phase === "walk") {
        wi += a;
        tracePaint(L.trace, wi * perFrameL); tracePaint(R.trace, wi * perFrameR);
        walker(L.trace, wi * perFrameL, "◀"); walker(R.trace, wi * perFrameR, "▶");
        cap("anim-travel", "PHASE 2/5 · walk OUTWARD from both cell edges: clearly-below-LOCAL-body (blue — dark channel OR lighter stepped trough) and bright bezel rim (yellow) both count as slot; a short sustained near-body run (red), sustained bright (orange), or backdrop COLOUR (magenta, |rgb−BGC|) is the DESIGNED stop — the end of the slot found");
        if (wi >= WALK_FRAMES + 20) { phase = "span"; pt = 0; }
      } else {
        // keep the full coloured trace visible
        tracePaint(L.trace, L.trace.length); tracePaint(R.trace, R.trace.length);
        walker(L.trace, L.trace.length, "◀"); walker(R.trace, R.trace.length, "▶");
        const t = phase === "span" ? ease(Math.min(1, pt / 40)) : 1;
        pt += a;
        // travel bar grows out from the cell to the clamped ±2%-padded span
        const cl = X(mx0), cr = X(mx1);
        const xl = cl + (X(tvLo - bx0) - cl) * t, xr = cr + (X(tvHi - bx0) - cr) * t;
        const barY = CY + CH + 22;
        ctx.fillStyle = "#5f7"; ctx.fillRect(xl, barY, xr - xl, 6);
        ctx.fillRect(xl, barY - 4, 2, 14); ctx.fillRect(xr - 2, barY - 4, 2, 14);
        ctx.fillStyle = "#8fa"; ctx.font = "10px ui-monospace,monospace";
        ctx.fillText(`travel = [${(tvLo / GW).toFixed(4)}, ${(tvHi / GW).toFixed(4)}] (cell ∪ walked caps, clamped ±12% of cell, ±2% margin)`, xl, barY + 20);
        // cross-check ticks: the travel extract12 actually shipped in regions.json
        for (const v of storedTv) {
          const xx = X(v * GW - bx0);
          ctx.strokeStyle = "#fff"; ctx.beginPath(); ctx.moveTo(xx, barY - 7); ctx.lineTo(xx, barY + 13); ctx.stroke();
        }
        ctx.fillStyle = "#cdd3dd"; ctx.fillText("white ticks = regions.json travel (shipped)", PH_X + PH_W - 262, barY + 31);
        if (phase === "span") {
          cap("anim-travel", "PHASE 3/5 · span snap: travel = mask cell ∪ walked end caps, clamped to ±12% of the cell width, + 2% margin; white ticks are the values extract12 shipped in regions.json — they coincide");
          if (pt > 70) { phase = "slide"; pt = 0; }
        } else if (phase === "slide") {
          // thumb slides end-to-end: x0 = travel[0], x1 = travel[1] − thumbW (consumer clamp)
          const x0c = X(tvLo - bx0), x1c = X(tvHi - bx0) - thumbW;
          const u = Math.min(1, pt / 170);
          const uu = u < 0.5 ? ease(u * 2) : ease(2 - u * 2);      // there and back
          const tx = x0c + (x1c - x0c) * uu;
          ctx.drawImage(thumbImg, tx, CY + CH / 2 - thumbH / 2, thumbW, thumbH);
          ctx.strokeStyle = "#5f7"; ctx.strokeRect(tx, CY + CH / 2 - thumbH / 2, thumbW, thumbH);
          cap("anim-travel", "PHASE 4/5 · coverage: the real cut thumb (BiRefNet seek.png) slides x∈[travel₀, travel₁−thumbW] — its extremes visually COVER the slot ends incl. the end caps the mask cell undershot");
          if (pt > 170) { phase = "success"; pt = 0; }
        } else if (phase === "success") {
          // SUCCESS BEAT (loop always ends here): park the thumb mid-slot and verify the
          // LIVE recompute against the shipped regions.json travel — an honest check, not
          // an assertion: if the served assets drift, this turns into an amber warning.
          const x0c = X(tvLo - bx0), x1c = X(tvHi - bx0) - thumbW;
          const tx = (x0c + x1c) / 2;
          ctx.drawImage(thumbImg, tx, CY + CH / 2 - thumbH / 2, thumbW, thumbH);
          ctx.strokeStyle = "#5f7"; ctx.strokeRect(tx, CY + CH / 2 - thumbH / 2, thumbW, thumbH);
          const okL = Math.abs(tvLo / GW - storedTv[0]) < 0.005;
          const okR = Math.abs(tvHi / GW - storedTv[1]) < 0.005;
          if (okL && okR) {
            banner(ctx, W, H, "✓ SHIPPED RESULT — recomputed travel = regions.json [" +
              storedTv[0].toFixed(4) + ", " + storedTv[1].toFixed(4) + "] · slot covered end-to-end",
              "#0d2f1a", "#5f7");
            cap("anim-travel", "PHASE 5/5 · shipped ✓ — the live recompute equals the regions.json travel extract12 shipped (" + storedTv[0].toFixed(4) + " – " + storedTv[1].toFixed(4) + "); the thumb's extremes cover the slot end-to-end. Loop restarts.");
          } else {
            banner(ctx, W, H, "⚠ RECOMPUTE ≠ SHIPPED regions.json — served assets drifted; re-run extract12.py",
              "#332008", "#fd5");
            cap("anim-travel", "PHASE 5/5 · ⚠ MISMATCH: live recompute [" + (tvLo / GW).toFixed(4) + ", " + (tvHi / GW).toFixed(4) + "] ≠ shipped [" + storedTv[0].toFixed(4) + ", " + storedTv[1].toFixed(4) + "] — the served paint/regions pair is stale; re-run extract12.py on this skin");
          }
          if (pt > 120) reset();
        }
      }
      // legend (suppressed during the success beat — the banner owns the bottom strip)
      if (phase !== "success") {
        ctx.font = "10px ui-monospace,monospace";
        const leg = [["below local body (trough)", "#5af"], ["bright bezel rim", "#fd5"], ["near-body", "#9aa"],
                     ["STOP: sustained body", "#f55"], ["STOP: sustained bright", "#fa0"], ["STOP: backdrop colour", "#f0f"]];
        let lx = 12;
        for (const [name, c] of leg) {
          ctx.fillStyle = c; ctx.fillRect(lx, H - 20, 8, 8);
          ctx.fillStyle = "#8a90a0"; ctx.fillText(name, lx + 11, H - 12);
          lx += ctx.measureText(name).width + 34;
        }
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ════════════════════════════════════════════════════════════════════════════
  // Panel 3 — device-only PCA slot rotation + elongation gate (shuffle slot)
  // Re-runs extract12.py's mask-colour assignment and _pca_angle() covariance math
  // on the real diablo-gothic mask, at native resolution.
  // ════════════════════════════════════════════════════════════════════════════
  function pcaAnim(reg, mask, paint, partImg) {
    const canvas = document.getElementById("anim-pca");
    if (!canvas) return;
    const W = 760, H = 470; canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");
    const MW = mask.naturalWidth, MH = mask.naturalHeight;
    const DEVF = reg.devFrac, devY = DEVF * MH;

    // part's own principal axis from the biref OFF cut's alpha (α>30), same math as
    // extract12's _pca_angle on the part — rot shipped is slot MINUS part, not absolute.
    function alphaPCA(img) {
      const c = document.createElement("canvas");
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      const cc = c.getContext("2d", { willReadFrequently: true });
      cc.drawImage(img, 0, 0);
      const d = cc.getImageData(0, 0, c.width, c.height).data;
      let n = 0, sx = 0, sy = 0, sxx = 0, sxy = 0, syy = 0;
      for (let y = 0, i = 3; y < c.height; y++) for (let x = 0; x < c.width; x++, i += 4)
        if (d[i] > 30) { n++; sx += x; sy += y; sxx += x * x; sxy += x * y; syy += y * y; }
      if (n < 200) return null;
      const mx = sx / n, my = sy / n;
      const Sxx = sxx / n - mx * mx, Sxy = sxy / n - mx * my, Syy = syy / n - my * my;
      const T = Sxx + Syy, D2 = Sxx * Syy - Sxy * Sxy;
      const l1 = (T + Math.sqrt(Math.max(0, T * T - 4 * D2))) / 2, l2 = T - l1;
      let vx = Sxy, vy = l1 - Sxx;
      if (Math.abs(vx) < 1e-9 && Math.abs(vy) < 1e-9) { vx = 1; vy = 0; }
      let ang = Math.atan2(vy, vx) * 180 / Math.PI;
      if (ang > 90) ang -= 180; else if (ang < -90) ang += 180;
      return { ang, elong: Math.sqrt(l1 / Math.max(1e-9, l2)) };
    }
    const partSt = alphaPCA(partImg);

    // ── mask-colour assignment, EXACT extract12 rule:
    //    sat = (max-min)>55 & max>90 ; assign = argmin dist to key colours if min<95
    const keys = reg.keys, names = Object.keys(keys);
    const KR = names.map((n) => keys[n][0]), KG = names.map((n) => keys[n][1]), KB = names.map((n) => keys[n][2]);
    const SI = names.indexOf("shuffle"), VI = names.indexOf("vol");
    const offc = document.createElement("canvas"); offc.width = MW; offc.height = MH;
    const octx = offc.getContext("2d", { willReadFrequently: true });
    octx.drawImage(mask, 0, 0);
    const md = octx.getImageData(0, 0, MW, MH).data;

    // moments accumulators per group + strided display samples
    function grp() { return { n: 0, sx: 0, sy: 0, sxx: 0, sxy: 0, syy: 0, pts: [] }; }
    const SD = grp(), SS = grp(), VD = grp();               // shuffle-device, shuffle-strip, vol-device
    const STRIDE = { SD: 21, SS: 43, VD: 23 };
    for (let y = 0, i = 0; y < MH; y++) {
      for (let x = 0; x < MW; x++, i += 4) {
        const r = md[i], g = md[i + 1], b = md[i + 2];
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
        if (mx - mn <= 55 || mx <= 90) continue;            // sat filter
        let bi = -1, bd = 1e18;
        for (let c = 0; c < KR.length; c++) {
          const dr = r - KR[c], dg = g - KG[c], db = b - KB[c];
          const d2 = dr * dr + dg * dg + db * db;
          if (d2 < bd) { bd = d2; bi = c; }
        }
        if (bd >= 9025) continue;                            // dist < 95 (squared)
        let G = null, tag = null;
        if (bi === SI) { G = y < devY ? SD : SS; tag = y < devY ? "SD" : "SS"; }
        else if (bi === VI && y < devY) { G = VD; tag = "VD"; }
        if (!G) continue;
        G.n++; G.sx += x; G.sy += y; G.sxx += x * x; G.sxy += x * y; G.syy += y * y;
        if (G.n % STRIDE[tag] === 0) G.pts.push(x, y);
      }
    }
    // central covariance + eigen decomposition (same math as np.linalg.eigh on the 2×2)
    function stats(...gs) {
      let n = 0, sx = 0, sy = 0, sxx = 0, sxy = 0, syy = 0;
      for (const g of gs) { n += g.n; sx += g.sx; sy += g.sy; sxx += g.sxx; sxy += g.sxy; syy += g.syy; }
      const mx = sx / n, my = sy / n;
      const Sxx = sxx / n - mx * mx, Sxy = sxy / n - mx * my, Syy = syy / n - my * my;
      const T = Sxx + Syy, D = Sxx * Syy - Sxy * Sxy;
      const l1 = (T + Math.sqrt(Math.max(0, T * T - 4 * D))) / 2, l2 = T - l1;
      // major eigenvector, then extract12's wrap to (-90, 90]
      let vx = Sxy, vy = l1 - Sxx;
      if (Math.abs(vx) < 1e-9 && Math.abs(vy) < 1e-9) { vx = 1; vy = 0; }
      let ang = Math.atan2(vy, vx) * 180 / Math.PI;
      if (ang > 90) ang -= 180; else if (ang < -90) ang += 180;
      return { n, mx, my, Sxx, Sxy, Syy, l1, l2, ang, elong: Math.sqrt(l1 / Math.max(1e-9, l2)) };
    }
    const stSlot = stats(SD), stBoth = stats(SD, SS), stVol = stats(VD);
    // full shipped rot decision, EXACT extract12 [angle] rule: elongation gate on BOTH
    // blobs, relative angle, wrap to (−90,90], snap near-cardinal to exact 0/±90.
    let rotShip;
    if (!partSt || stSlot.elong < 2.0 || partSt.elong < 2.0) {
      rotShip = { rot: 0, why: "gate" };
    } else {
      let rr = stSlot.ang - partSt.ang;
      rr = ((rr + 90) % 180 + 180) % 180 - 90;
      if (Math.abs(rr) <= 20) rr = 0; else if (Math.abs(rr - 90) <= 20) rr = 90;
      else if (Math.abs(rr + 90) <= 20) rr = -90;
      rotShip = { rot: rr, why: "pca" };
    }
    const shippedAngle = (reg.regions.shuffle || {}).angle;   // absent = 0° shipped
    const shipOk = Math.abs((shippedAngle === undefined ? 0 : shippedAngle) - rotShip.rot) < 0.15;
    const varAt = (st, th) => {  // variance of projections onto trial axis θ — the search meter
      const c = Math.cos(th), s = Math.sin(th);
      return c * c * st.Sxx + 2 * c * s * st.Sxy + s * s * st.Syy;
    };

    // ── views (mask px rects) the left stage lerps between ─────────────────────
    function bboxView(mb, padF) {
      const bw = mb[2] * MW, bh = mb[3] * MH;
      const cx = (mb[0] + mb[2] / 2) * MW, cy = (mb[1] + mb[3] / 2) * MH;
      const w = bw * padF, h = bh * (1 + (padF - 1) * 0.55);
      return { x: cx - w / 2, y: cy - h / 2, w, h };
    }
    const V_SLOT = bboxView(reg.regions.shuffle.maskDevice, 2.4);
    const V_VOL = bboxView(reg.regions.vol.maskDevice, 2.0);
    const V_FULL = { x: 0, y: 0, w: MW, h: MH };
    let view = { ...V_SLOT };
    const SX = 12, SY = 16, SW = 320, SH = 436;              // left stage box
    function proj() {                                        // current mask-px → canvas transform
      const s = Math.min(SW / view.w, SH / view.h);
      const ox = SX + (SW - view.w * s) / 2, oy = SY + (SH - view.h * s) / 2;
      return { s, ox, oy, X: (x) => ox + (x - view.x) * s, Y: (y) => oy + (y - view.y) * s };
    }
    const lerpView = (A, B, t) => { view.x = A.x + (B.x - A.x) * t; view.y = A.y + (B.y - A.y) * t; view.w = A.w + (B.w - A.w) * t; view.h = A.h + (B.h - A.h) * t; };

    const RX = 352, RW = 396;                                 // right column
    function meterBar(y, name, val, vmax, color, note) {
      ctx.fillStyle = "#9ab"; ctx.font = "11px ui-monospace,monospace"; ctx.fillText(name, RX, y - 5);
      ctx.fillStyle = "#161a22"; ctx.fillRect(RX, y, RW - 110, 12);
      ctx.fillStyle = color; ctx.fillRect(RX, y, Math.max(0, Math.min(1, val / vmax)) * (RW - 110), 12);
      ctx.fillStyle = "#cdd3dd"; ctx.fillText(note, RX + RW - 104, y + 10);
    }
    function axisLine(P, st, ang, color, len, wdt) {
      const c = Math.cos(ang * Math.PI / 180), s = Math.sin(ang * Math.PI / 180);
      ctx.strokeStyle = color; ctx.lineWidth = wdt || 2;
      ctx.beginPath();
      ctx.moveTo(P.X(st.mx - c * len), P.Y(st.my - s * len));
      ctx.lineTo(P.X(st.mx + c * len), P.Y(st.my + s * len));
      ctx.stroke(); ctx.lineWidth = 1;
    }
    function drawPts(P, pts, color, upto, size) {
      ctx.fillStyle = color;
      const n = Math.min(pts.length, (upto === undefined ? pts.length : upto * 2));
      for (let i = 0; i < n; i += 2) ctx.fillRect(P.X(pts[i]) - (size || 1), P.Y(pts[i + 1]) - (size || 1), (size || 1) * 2, (size || 1) * 2);
    }
    function stage(P, title) {
      ctx.save();
      ctx.beginPath(); ctx.rect(SX, SY, SW, SH); ctx.clip();
      ctx.drawImage(paint, view.x, view.y, view.w, view.h, P.ox, P.oy, view.w * P.s, view.h * P.s);
      ctx.globalCompositeOperation = "screen";               // mask blobs glow over the paint
      ctx.globalAlpha = 0.55;
      ctx.drawImage(mask, view.x, view.y, view.w, view.h, P.ox, P.oy, view.w * P.s, view.h * P.s);
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
      // devFrac line (device band above, sprite strip below)
      const dy = P.Y(devY);
      if (dy > SY && dy < SY + SH) {
        ctx.strokeStyle = "#fd5"; ctx.setLineDash([5, 4]);
        ctx.beginPath(); ctx.moveTo(SX, dy); ctx.lineTo(SX + SW, dy); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = "#fd5"; ctx.font = "10px ui-monospace,monospace";
        ctx.fillText("devFrac — sprite STRIP below", SX + 6, dy + 12);
      }
      ctx.restore();
      ctx.strokeStyle = "#3a4a63"; ctx.strokeRect(SX, SY, SW, SH);
      ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
      ctx.fillText(title, SX, SY - 5);
    }

    const SEARCH_F = 240;                                    // trial-axis sweep frames at 1×
    let phase, pt, bestTh, bestVar;
    function reset() { phase = "cloud"; pt = 0; bestTh = 0; bestVar = -1; view = { ...V_SLOT }; }
    reset();
    RESTARTS["anim-pca"] = reset;

    function frame() {
      const a = adv();
      ctx.fillStyle = "#0d0f14"; ctx.fillRect(0, 0, W, H);
      const P = proj();

      if (phase === "cloud") {
        pt += a;
        stage(P, "shuffle slot · real mask px over paint");
        const reveal = Math.min(1, pt / 70);
        drawPts(P, SD.pts, "#7df", Math.floor((SD.pts.length / 2) * reveal));
        ctx.fillStyle = "#cdd3dd"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText("mask-colour assignment (extract12):", RX, 40);
        ctx.fillStyle = "#8a90a0";
        ctx.fillText("sat: (max−min)>55 & max>90", RX, 60);
        ctx.fillText("assign = argmin ‖px − key‖ if <95", RX, 76);
        ctx.fillText(`shuffle DEVICE px (y < devFrac·H): ${SD.n.toLocaleString()}`, RX, 96);
        ctx.fillStyle = "#7df"; ctx.fillText("point cloud = the slot's own pixels", RX, 116);
        cap("anim-pca", "PHASE 1/7 · point cloud: the toggle slot's mask pixels, DEVICE band only — (assign==idx) & (YY < devFrac·H) — extract12.py _pca_angle() input");
        if (pt > 90) { phase = "search"; pt = 0; }
      } else if (phase === "search") {
        pt += a;
        stage(P, "shuffle slot · principal-axis search");
        drawPts(P, SD.pts, "#7df");
        const th = Math.min(180, (pt / SEARCH_F) * 180) * Math.PI / 180;
        const v = varAt(stSlot, th);
        if (v > bestVar) { bestVar = v; bestTh = th; }
        axisLine(P, stSlot, bestTh * 180 / Math.PI, "#5f7", view.h * 0.5, 1.6);
        axisLine(P, stSlot, th * 180 / Math.PI, "#f55", view.h * 0.45, 2);
        meterBar(56, "variance along TRIAL axis (live)", v, stSlot.l1, "#f55", (v / stSlot.l1 * 100).toFixed(0) + "%");
        meterBar(96, "variance along BEST axis so far", bestVar, stSlot.l1, "#5f7", (bestVar / stSlot.l1 * 100).toFixed(0) + "%");
        ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText(`trial θ = ${(th * 180 / Math.PI).toFixed(0)}°   best θ = ${(bestTh * 180 / Math.PI).toFixed(0)}°`, RX, 130);
        ctx.fillText("(the real code solves this in closed form:", RX, 152);
        ctx.fillText(" eigenvector of the 2×2 covariance — this", RX, 166);
        ctx.fillText(" sweep is that same variance surface)", RX, 180);
        cap("anim-pca", "PHASE 2/7 · axis search: rotate a trial axis through the cloud's centroid; variance of the projections peaks along the slot's long direction — PCA's major eigenvector");
        if (pt > SEARCH_F + 25) { phase = "lock"; pt = 0; }
      } else if (phase === "lock") {
        pt += a;
        stage(P, "shuffle slot · major axis LOCKED");
        drawPts(P, SD.pts, "#7df");
        axisLine(P, stSlot, stSlot.ang, "#5f7", view.h * 0.52, 2.6);
        ctx.fillStyle = "#5f7"; ctx.font = "12px ui-monospace,monospace";
        ctx.fillText(`slot axis = ${stSlot.ang.toFixed(1)}°  (vertical)`, RX, 50);
        meterBar(84, "elongation √(λmax/λmin) — gate ≥ 2.0", stSlot.elong, 5, "#5f7", stSlot.elong.toFixed(2));
        const gx = RX + (2.0 / 5) * (RW - 110);
        ctx.strokeStyle = "#fd5"; ctx.beginPath(); ctx.moveTo(gx, 78); ctx.lineTo(gx, 102); ctx.stroke();
        ctx.fillStyle = "#fd5"; ctx.font = "10px ui-monospace,monospace"; ctx.fillText("gate 2.0", gx - 20, 112);
        ctx.fillStyle = "#cdd3dd"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText(`elongation ${stSlot.elong.toFixed(2)} ≥ 2.0 → axis TRUSTED`, RX, 136);
        ctx.fillStyle = "#8a90a0";
        if (partSt) {
          ctx.fillText(`part's own axis (OFF cut alpha): ${partSt.ang.toFixed(1)}°`, RX, 158);
          ctx.fillText(`→ relative rot ≈ ${(((stSlot.ang - partSt.ang + 90) % 180 + 180) % 180 - 90).toFixed(1)}°, snapped to`, RX, 172);
        } else {
          ctx.fillText("part axis unavailable → rot defaults 0", RX, 158);
          ctx.fillText("→ relative rot ≈ 0, snapped to", RX, 172);
        }
        ctx.fillText("cardinal → no rotation shipped. Only true", RX, 186);
        ctx.fillText("diagonals (>20° off-cardinal) rotate.", RX, 200);
        cap("anim-pca", "PHASE 3/7 · lock ✓: eigen angle " + stSlot.ang.toFixed(1) + "°, elongation " + stSlot.elong.toFixed(2) + " passes the ≥2.0 gate. rot = slot − part axis, wrapped and snapped to cardinal — extract12.py [angle]. Next: a replay of the OLD bug this code fixed.");
        if (pt > 130) { phase = "smear"; pt = 0; }
      } else if (phase === "smear") {
        pt += a;
        const t = ease(Math.min(1, pt / 55));
        lerpView(V_SLOT, V_FULL, t);
        stage(P, "OLD BUG replay · strip cells included in the blob");
        drawPts(P, SD.pts, "#7df");
        const flash = 0.55 + 0.4 * Math.sin(pt / 5);
        ctx.globalAlpha = Math.min(1, t * 1.5) * flash;
        drawPts(P, SS.pts, "#f55");
        ctx.globalAlpha = 1;
        if (t > 0.6) {
          axisLine(P, stBoth, stBoth.ang, "#f55", view.h * 0.5, 2.4);
          ctx.fillStyle = "#f55"; ctx.font = "12px ui-monospace,monospace";
          ctx.fillText(`combined axis = ${stBoth.ang > 0 ? "+" : ""}${stBoth.ang.toFixed(1)}°  — GARBAGE`, RX, 50);
          meterBar(84, "elongation (combined cloud)", stBoth.elong, 5, "#f55", stBoth.elong.toFixed(2));
          ctx.fillStyle = "#cdd3dd"; ctx.font = "11px ui-monospace,monospace";
          ctx.fillText("the strip's OFF/ON reference cells share", RX, 120);
          ctx.fillText("the slot's guide colour — include them and", RX, 134);
          ctx.fillText("the \"major axis\" is just the line from the", RX, 148);
          ctx.fillText("slot to the strip. Elongation even looks", RX, 162);
          ctx.fillText("STRONGER (" + stBoth.elong.toFixed(1) + ") — the gate can't save you.", RX, 176);
          ctx.fillStyle = "#f88";
          ctx.fillText("a vertical slot reading " + stBoth.ang.toFixed(0) + "° would rotate", RX, 200);
          ctx.fillText("the part diagonally — the bug we fixed.", RX, 214);
        }
        banner(ctx, W, H, "⚠ HISTORY — THE OLD BUG (ALREADY FIXED) · re-enacted for contrast, not the shipping code", "#3a0f12", "#f88");
        cap("anim-pca", "PHASE 4/7 · OLD BUG replay (fixed in extract12.py): the sprite-strip cells (below devFrac) share the slot's mask colour; including them smears the cloud and the axis becomes the slot→strip diagonal (" + stBoth.ang.toFixed(1) + "°). This is HISTORY — the fix is next.");
        if (pt > 170) { phase = "fixup"; pt = 0; }
      } else if (phase === "fixup") {
        pt += a;
        const t = ease(Math.min(1, pt / 55));
        lerpView(V_FULL, V_SLOT, t);
        stage(P, "THE FIX (shipped) · device band only");
        drawPts(P, SD.pts, "#7df");
        ctx.globalAlpha = (1 - t) * 0.35;
        drawPts(P, SS.pts, "#f55");
        ctx.globalAlpha = 1;
        axisLine(P, stSlot, stSlot.ang, "#5f7", view.h * 0.52, 2.4);
        ctx.fillStyle = "#5f7"; ctx.font = "12px ui-monospace,monospace";
        ctx.fillText(`device-only axis = ${stSlot.ang.toFixed(1)}° again`, RX, 50);
        ctx.fillStyle = "#cdd3dd"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText("the fix (extract12.py):", RX, 84);
        ctx.fillStyle = "#8fa";
        ctx.fillText("(assign == idx) & (YY < DEVF·MH)", RX, 104);
        ctx.fillStyle = "#8a90a0";
        ctx.fillText("# DEVICE slot only (exclude strip cells!)", RX, 122);
        banner(ctx, W, H, "✓ THE FIX — SHIPPING CODE: device-only pixels (assign==idx) & (YY < devFrac·H)", "#0d2f1a", "#5f7");
        cap("anim-pca", "PHASE 5/7 · the fix (shipping in extract12.py): mask the blob to the device band before PCA — strip cells excluded, the axis is the slot's own again");
        if (pt > 110) { phase = "gate"; pt = 0; bestVar = -1; bestTh = 0; view = { ...V_VOL }; }
      } else if (phase === "gate") {
        pt += a;
        stage(P, "elongation gate · vol knob blob (near-round)");
        drawPts(P, VD.pts, "#d9f");
        const th = (pt / 90) * Math.PI;                       // keep spinning — no peak to find
        const v = varAt(stVol, th);
        axisLine(P, stVol, th * 180 / Math.PI, "#f55", view.h * 0.4, 2);
        meterBar(56, "variance along TRIAL axis (live)", v, stVol.l1, "#f55", (v / stVol.l1 * 100).toFixed(0) + "%");
        ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText("…the meter barely moves as the axis spins:", RX, 92);
        ctx.fillText("a round blob has no preferred direction.", RX, 106);
        meterBar(140, "elongation √(λmax/λmin) — gate ≥ 2.0", stVol.elong, 5, "#f55", stVol.elong.toFixed(2));
        const gx = RX + (2.0 / 5) * (RW - 110);
        ctx.strokeStyle = "#fd5"; ctx.beginPath(); ctx.moveTo(gx, 134); ctx.lineTo(gx, 158); ctx.stroke();
        ctx.fillStyle = "#fd5"; ctx.font = "10px ui-monospace,monospace"; ctx.fillText("gate 2.0", gx - 20, 168);
        if (pt > 120) {
          ctx.fillStyle = "#fd5"; ctx.font = "12px ui-monospace,monospace";
          ctx.fillText(`elongation ${stVol.elong.toFixed(2)} < 2.0 → axis is NOISE`, RX, 196);
          ctx.fillText("→ NO ROTATION applied (CORRECT refusal)", RX, 214);
          ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
          ctx.fillText("(myst once read +71° of pure noise off a", RX, 236);
          ctx.fillText(" ragged blob — this gate is why it can't now)", RX, 250);
        }
        banner(ctx, W, H, "SAFETY GATE DEMO — refusing to rotate a round blob is the CORRECT, designed behaviour", "#33270a", "#fd5");
        cap("anim-pca", "PHASE 6/7 · safety-gate demo (by design): a near-round blob (vol knob, elongation " + stVol.elong.toFixed(2) + ") keeps a flat variance meter — its axis is meaningless, so extract12 correctly refuses to rotate: \"elongation too weak → no rotation\"");
        if (pt > 240) { phase = "ship"; pt = 0; view = { ...V_SLOT }; }
      } else if (phase === "ship") {
        // FINAL SUCCESS HOLD — every loop ends here: the correct locked axis plus the
        // full shipped rot decision, verified live against regions.json (⚠ on drift).
        pt += a;
        stage(P, "shuffle slot · SHIPPED result");
        drawPts(P, SD.pts, "#7df");
        axisLine(P, stSlot, stSlot.ang, "#5f7", view.h * 0.52, 2.6);
        ctx.fillStyle = "#cdd3dd"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText(`slot axis ${stSlot.ang.toFixed(1)}°  elong ${stSlot.elong.toFixed(2)}` + (stSlot.elong >= 2 ? " ✓ real" : " (weak)"), RX, 56);
        if (partSt)
          ctx.fillText(`part axis ${partSt.ang.toFixed(1)}°  elong ${partSt.elong.toFixed(2)}` + (partSt.elong < 2 ? " → squat" : ""), RX, 74);
        ctx.fillStyle = "#8a90a0";
        ctx.fillText(rotShip.why === "gate"
          ? "elongation gate → NO rotation (the safe call:"
          : "rot = slot − part, wrapped + cardinal-snapped:", RX, 96);
        ctx.fillText(rotShip.why === "gate"
          ? " slot is cardinal + part upright, nothing to rotate)"
          : ` → ${rotShip.rot.toFixed(1)}° applied to the part`, RX, 112);
        const shippedTxt = shippedAngle === undefined ? "none (= 0°)" : shippedAngle + "°";
        if (shipOk) {
          ctx.fillStyle = "#5f7"; ctx.font = "13px ui-monospace,monospace";
          ctx.fillText(`✓ SHIPPED  regions.json angle: ${shippedTxt}`, RX, 148);
          ctx.fillText(`  recomputed decision ${rotShip.rot.toFixed(0)}° — MATCH`, RX, 168);
          banner(ctx, W, H, "✓ SHIPPED RESULT — recomputed rotation " + rotShip.rot.toFixed(0) + "° = regions.json (angle: " + shippedTxt + ")", "#0d2f1a", "#5f7");
          cap("anim-pca", "PHASE 7/7 · shipped ✓ — device-only axis " + stSlot.ang.toFixed(1) + "° (elong " + stSlot.elong.toFixed(2) + "), rot decision " + rotShip.rot.toFixed(0) + "° matches the live regions.json (angle: " + shippedTxt + "). Loop restarts.");
        } else {
          ctx.fillStyle = "#fd5"; ctx.font = "13px ui-monospace,monospace";
          ctx.fillText(`⚠ MISMATCH  regions.json angle: ${shippedTxt}`, RX, 148);
          ctx.fillText(`  recomputed decision ${rotShip.rot.toFixed(0)}°`, RX, 168);
          banner(ctx, W, H, "⚠ RECOMPUTE ≠ SHIPPED regions.json — served assets drifted; re-run extract12.py", "#332008", "#fd5");
          cap("anim-pca", "PHASE 7/7 · ⚠ MISMATCH: recomputed rot " + rotShip.rot.toFixed(0) + "° ≠ shipped regions.json angle (" + shippedTxt + ") — the served mask/regions pair is stale; re-run extract12.py on this skin");
        }
        if (pt > 150) reset();
      }
      if (phase !== "smear" && phase !== "fixup" && phase !== "gate" && phase !== "ship") {
        ctx.fillStyle = "#6a7080"; ctx.font = "10px ui-monospace,monospace";
        ctx.fillText("LIVE — real covariance math on the real mask px · loops", RX, H - 12);
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ════════════════════════════════════════════════════════════════════════════
  // Panel 4 — silhouette-IoU switch state registration (shuffle OFF/ON cuts)
  // Re-runs extract12.py's state-registration: scale ON→OFF bbox, search
  // (dx,dy)∈[-12,12]² for max silhouette IoU → regions.json stateAlign.
  // ════════════════════════════════════════════════════════════════════════════
  function iouAnim(reg, offImg, onImg) {
    const canvas = document.getElementById("anim-iou");
    if (!canvas) return;
    const W = 760, H = 450; canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");
    const sa = (reg.regions.shuffle || {}).stateAlign;       // what extract12 shipped

    // alpha>30 bool silhouettes (exact extract12 threshold)
    function alphaOf(img) {
      const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
      const cc = c.getContext("2d", { willReadFrequently: true });
      cc.drawImage(img, 0, 0);
      const d = cc.getImageData(0, 0, c.width, c.height).data;
      const a = new Uint8Array(c.width * c.height);
      for (let i = 0, j = 3; i < a.length; i++, j += 4) a[i] = d[j] > 30 ? 1 : 0;
      return { a, w: c.width, h: c.height };
    }
    function bbox(A) {
      let x0 = A.w, y0 = A.h, x1 = -1, y1 = -1;
      for (let y = 0; y < A.h; y++) for (let x = 0; x < A.w; x++) if (A.a[y * A.w + x]) {
        if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
      return [x0, y0, x1 - x0 + 1, y1 - y0 + 1];
    }
    const OFF = alphaOf(offImg), ON = alphaOf(onImg);
    const [ox, oy, ow, oh] = bbox(OFF), [nx, ny, nw, nh] = bbox(ON);
    // offb = OFF bbox crop; onb = ON bbox crop nearest-resized to (ow,oh)
    const offb = new Uint8Array(ow * oh), onb = new Uint8Array(ow * oh);
    let cntOff = 0, cntOn = 0;
    for (let y = 0; y < oh; y++) for (let x = 0; x < ow; x++) {
      const v = OFF.a[(oy + y) * OFF.w + (ox + x)];
      offb[y * ow + x] = v; cntOff += v;
      const sx2 = Math.min(nw - 1, Math.floor((x + 0.5) * nw / ow));
      const sy2 = Math.min(nh - 1, Math.floor((y + 0.5) * nh / oh));
      const u = ON.a[(ny + sy2) * ON.w + (nx + sx2)];
      onb[y * ow + x] = u; cntOn += u;
    }
    // IoU under integer shift (dx,dy) — identical to extract12's 3×-canvas overlap
    function iouAtShift(dx, dy) {
      let inter = 0;
      const yA = Math.max(0, dy), yB = Math.min(oh, oh + dy);
      const xA = Math.max(0, dx), xB = Math.min(ow, ow + dx);
      for (let y = yA; y < yB; y++) {
        const r0 = y * ow, r1 = (y - dy) * ow - dx;
        for (let x = xA; x < xB; x++) inter += offb[r0 + x] & onb[r1 + x];
      }
      return inter / (cntOff + cntOn - inter);
    }
    // candidate scan order = extract12's (dy outer, dx inner), -12..12
    const cands = [];
    for (let dy = -12; dy <= 12; dy++) for (let dx = -12; dx <= 12; dx++) cands.push([dx, dy]);
    const ious = new Float64Array(cands.length).fill(-1);
    const scaleX = ow / nw, scaleY = oh / nh;

    // tinted silhouettes for the stage (colour = state)
    function tint(img, color) {
      const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
      const cc = c.getContext("2d");
      cc.drawImage(img, 0, 0); cc.globalCompositeOperation = "source-in";
      cc.fillStyle = color; cc.fillRect(0, 0, c.width, c.height);
      return c;
    }
    const offT = tint(offImg, "#8fa8c0"), onT = tint(onImg, "#f7923c");

    // display geometry: stage left (OFF-frame px × ds), heat grid right
    const ds = Math.min(440 / ow, 250 / oh);
    const STX = 16, STY = 108, STW = ow * ds, STH = oh * ds;
    const HGX = 512, HGY = 96, CELL = 8, HGW = 25 * CELL;     // (dx,dy) ∈ [-12,12]²
    const IOU_LO = 0.80;                                      // meter/heat floor (worst ≈ .82)
    function heatColor(v) {
      const t = Math.max(0, Math.min(1, (v - IOU_LO) / (1 - IOU_LO)));
      const r = Math.round(30 + 225 * t), g = Math.round(40 + 180 * t * t), b = Math.round(80 - 40 * t);
      return `rgb(${r},${g},${b})`;
    }

    const SEARCH_F = 280, perFrame = cands.length / SEARCH_F;
    let phase, pt, cif, ci, best;
    function reset() { phase = "cuts"; pt = 0; ci = 0; cif = 0; best = { iou: -1, dx: 0, dy: 0 }; ious.fill(-1); }
    reset();
    RESTARTS["anim-iou"] = reset;

    function heatGrid() {
      ctx.fillStyle = "#8a90a0"; ctx.font = "10px ui-monospace,monospace";
      ctx.fillText("tried offsets — IoU heat  (dx →, dy ↓)", HGX, HGY - 8);
      ctx.strokeStyle = "#2a3345"; ctx.strokeRect(HGX - 1, HGY - 1, HGW + 2, HGW + 2);
      for (let i = 0; i < cands.length; i++) {
        if (ious[i] < 0) continue;
        const [dx, dy] = cands[i];
        ctx.fillStyle = heatColor(ious[i]);
        ctx.fillRect(HGX + (dx + 12) * CELL, HGY + (dy + 12) * CELL, CELL - 1, CELL - 1);
      }
      // best marker
      if (best.iou > 0) {
        ctx.strokeStyle = "#5f7"; ctx.lineWidth = 2;
        ctx.strokeRect(HGX + (best.dx + 12) * CELL - 1, HGY + (best.dy + 12) * CELL - 1, CELL + 1, CELL + 1);
        ctx.lineWidth = 1;
      }
    }
    function iouMeter(v, y, name, color) {
      const MX = HGX, MW2 = HGW;
      ctx.fillStyle = "#9ab"; ctx.font = "11px ui-monospace,monospace"; ctx.fillText(name, MX, y - 5);
      ctx.fillStyle = "#161a22"; ctx.fillRect(MX, y, MW2, 12);
      const t = Math.max(0, (v - IOU_LO) / (1 - IOU_LO));
      ctx.fillStyle = color; ctx.fillRect(MX, y, Math.min(1, t) * MW2, 12);
      ctx.fillStyle = "#cdd3dd"; ctx.fillText((v * 100).toFixed(1) + "%", MX + MW2 - 46, y + 10);
    }
    function stageFrame(title) {
      ctx.strokeStyle = "#3a4a63"; ctx.strokeRect(STX - 1, STY - 1, STW + 2, STH + 2);
      ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
      ctx.fillText(title, STX, STY - 6);
    }

    function frame() {
      const a = adv();
      ctx.fillStyle = "#0d0f14"; ctx.fillRect(0, 0, W, H);

      if (phase === "cuts") {
        pt += a;
        // the two real cuts, side by side, then their silhouettes
        const tw = 200, th = tw * offImg.naturalHeight / offImg.naturalWidth;
        ctx.drawImage(offImg, 30, 26, tw, th);
        ctx.drawImage(onImg, 270, 26, tw, th);
        ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText("shuffle_off.png (BiRefNet cut)", 30, 20);
        ctx.fillText("shuffle_on.png", 270, 20);
        ctx.strokeStyle = "#3a4a63"; ctx.strokeRect(30, 26, tw, th); ctx.strokeRect(270, 26, tw, th);
        const rv = Math.min(1, pt / 60);
        ctx.globalAlpha = rv;
        ctx.drawImage(offT, 30, 26 + th + 24, tw, th);
        ctx.drawImage(onT, 270, 26 + th + 24, tw, th);
        ctx.globalAlpha = 1;
        ctx.fillStyle = "#8fa8c0"; ctx.fillText("OFF silhouette (α>30)", 30, 26 + th + 20);
        ctx.fillStyle = "#f7923c"; ctx.fillText("ON silhouette (α>30)", 270, 26 + th + 20);
        ctx.fillStyle = "#cdd3dd";
        ctx.fillText(`bboxes: OFF ${ow}×${oh}px · ON ${nw}×${nh}px — cut frames differ,`, 30, 26 + th * 2 + 60);
        ctx.fillText("so centring the raw cuts would make the housing JUMP between states.", 30, 26 + th * 2 + 76);
        cap("anim-iou", "PHASE 1/4 · the two real shuffle cuts: BiRefNet trims each state slightly differently (" + nw + "×" + nh + " vs " + ow + "×" + oh + "). Align by SILHOUETTE, not by cut frame — extract12.py state-registration");
        if (pt > 110) { phase = "search"; pt = 0; }
      } else if (phase === "search" || phase === "lock") {
        if (phase === "search") {
          cif = Math.min(cands.length, cif + perFrame * a);
          for (; ci < cif; ci++) {
            const [dx, dy] = cands[ci];
            const v = iouAtShift(dx, dy);
            ious[ci] = v;
            if (v > best.iou) best = { iou: v, dx, dy };
          }
        } else pt += a;
        const done = phase === "lock" || ci >= cands.length;
        const [cdx, cdy] = done ? [best.dx, best.dy] : cands[Math.max(0, ci - 1)];
        stageFrame("OFF frame · ON silhouette sliding over (dx,dy)");
        ctx.globalAlpha = 0.85;
        ctx.drawImage(offT, ox, oy, ow, oh, STX, STY, STW, STH);
        // ON drawn scaled to OFF bbox (the ow/nw × oh/nh resize), shifted by candidate
        ctx.globalAlpha = 0.6;
        ctx.drawImage(onT, nx, ny, nw, nh, STX + cdx * ds, STY + cdy * ds, STW, STH);
        ctx.globalAlpha = 1;
        heatGrid();
        const curIou = done ? best.iou : (ious[Math.max(0, ci - 1)] >= 0 ? ious[Math.max(0, ci - 1)] : 0);
        iouMeter(curIou, HGY + HGW + 34, done ? "IoU — LOCKED at max" : "IoU — current offset (live)", done ? "#5f7" : "#f7923c");
        iouMeter(Math.max(0, best.iou), HGY + HGW + 74, "IoU — best so far", "#5f7");
        ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText(`offset (${cdx},${cdy})  ·  tried ${Math.min(ci, cands.length)}/${cands.length}`, HGX, HGY + HGW + 96);
        ctx.fillText(`ON scaled to OFF bbox: ×(${scaleX.toFixed(4)}, ${scaleY.toFixed(4)})`, STX, STY + STH + 18);
        if (phase === "search") {
          cap("anim-iou", "PHASE 2/4 · registration search: the ON silhouette (scaled to the OFF bbox) slides over every (dx,dy) ∈ [−12,12]²; silhouette IoU scored per offset — extract12.py [state-align]");
          if (ci >= cands.length) { phase = "lock"; pt = 0; }
        } else {
          ctx.fillStyle = "#5f7"; ctx.font = "12px ui-monospace,monospace";
          ctx.fillText(`LOCK  d=(${best.dx},${best.dy})  IoU=${(best.iou * 100).toFixed(2)}%`, STX, STY + STH + 40);
          ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
          if (sa) ctx.fillText(`regions.json stateAlign: d=(${sa.dx},${sa.dy}) scale=(${sa.scaleX},${sa.scaleY}) IoU=${sa.iou} — matches`, STX, STY + STH + 58);
          cap("anim-iou", "PHASE 3/4 · lock: max-IoU offset becomes regions.json stateAlign (scale + dx,dy in OFF-frame px) — the shipped values, recomputed live");
          if (pt > 110) { phase = "swap"; pt = 0; }
        }
      } else if (phase === "swap") {
        pt += a;
        stageFrame("player runtime · states swap IN PLACE");
        const onState = Math.floor(pt / 55) % 2 === 1;
        // OFF-frame ghost stays put — the housing reference
        ctx.globalAlpha = 0.18;
        ctx.drawImage(offT, ox, oy, ow, oh, STX, STY, STW, STH);
        ctx.globalAlpha = 1;
        if (!onState) {
          ctx.drawImage(offImg, ox, oy, ow, oh, STX, STY, STW, STH);
        } else {
          // ON rendered through stateAlign: scaled to OFF bbox, shifted by (dx,dy)
          ctx.drawImage(onImg, nx, ny, nw, nh, STX + best.dx * ds, STY + best.dy * ds, STW, STH);
        }
        ctx.strokeStyle = "#5f7"; ctx.setLineDash([4, 4]);
        ctx.strokeRect(STX, STY, STW, STH); ctx.setLineDash([]);
        ctx.fillStyle = "#5f7"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText("housing static (dashed) — only the rocker changes", STX, STY + STH + 18);
        ctx.fillStyle = onState ? "#f7923c" : "#8fa8c0"; ctx.font = "13px ui-monospace,monospace";
        ctx.fillText(onState ? "STATE: ON" : "STATE: OFF", STX, STY - 24);
        heatGrid();
        iouMeter(best.iou, HGY + HGW + 34, "registered IoU", "#5f7");
        ctx.fillStyle = "#8a90a0"; ctx.font = "11px ui-monospace,monospace";
        ctx.fillText("without stateAlign the whole switch would", HGX, HGY + HGW + 66);
        ctx.fillText("jump a few px on every click — with it the", HGX, HGY + HGW + 80);
        ctx.fillText("housing coincides and only the lever moves.", HGX, HGY + HGW + 94);
        cap("anim-iou", "PHASE 4/4 · payoff: the real cuts swap in place through stateAlign — the fixed housing coincides across states (IoU " + (best.iou * 100).toFixed(1) + "%), so the toggle reads as ONE object with a moving rocker");
        if (pt > 260) reset();
      }
      ctx.fillStyle = "#6a7080"; ctx.font = "10px ui-monospace,monospace";
      ctx.fillText("LIVE — real silhouette IoU on the real BiRefNet cuts · loops", 16, H - 12);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
})();
