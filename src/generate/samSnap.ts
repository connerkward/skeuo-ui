// Prior-guided SAM-3.1 snap — the ALIGN pass, ported from generation/sam_snap.py.
//
// WHY: the painter places controls/screens NEAR the blueprint sockets but not pixel-on,
// so the template rects (used to overlay live controls + render the screen/visualizer)
// land off the painted features → "everything outside bounds". Eyeballing or darkness
// heuristics are unreliable; SAM-3.1 is a real segmentation model. Each control's rect is
// fed to SAM as a (gap-clamped) BOX PROMPT; SAM segments the actual painted control there
// and returns a tight normalized box + score. We snap when confident + the move is
// plausible, keep the prior when unsure, and structurally refit evenly-spaced rows
// (transport buttons, EQ bands). Robust on a dark socket OR a bright painted knob.
//
// One SAM call per skin (all box prompts batched). Server-side only (FAL_KEY).

const SAM_URL = "https://queue.fal.run/fal-ai/sam-3-1/image";
const PAD = 0.6;        // expand the box prompt to tolerate drift…
const PAD_GAP = 0.45;   // …but never past this fraction of the gap to a neighbour (dense rows)
const MIN_SCORE = 0.55; // below this, keep the prior
const SAM_W = 1024, SAM_H = 1536; // device aspect (2:3); box prompts are in these pixels

// Snappable kinds: controls AND displays. Including "display" is the key for the
// visualizer/marquee alignment — SAM box-prompts the painted screen glass and snaps the
// region onto it, so live content stops landing off the actual screen.
const CTRL = new Set(["button", "toggle", "knob", "slider-h", "slider-v", "slider-arc", "slider-path", "display"]);

interface Rect { x: number; y: number; w: number; h: number }
interface Region { kind: string; bind?: string; id?: string; rect: Rect; [k: string]: unknown }
interface Det { cx: number; cy: number; w: number; h: number; score: number }

// per-control pad: PAD×size, clamped to PAD_GAP×(gap to nearest neighbour) so dense rows
// (EQ) don't grow into each other and get merged by SAM.
function adaptivePads(rects: Rect[]): [number, number][] {
  return rects.map((a, i) => {
    let gx = 1.0, gy = 1.0;
    rects.forEach((b, j) => {
      if (i === j) return;
      if (!(a.y + a.h < b.y || b.y + b.h < a.y)) { // shares a row
        const gap = Math.abs((b.x + b.w / 2) - (a.x + a.w / 2)) - (a.w + b.w) / 2;
        if (gap >= -0.01) gx = Math.min(gx, Math.max(0, gap));
      }
      if (!(a.x + a.w < b.x || b.x + b.w < a.x)) { // shares a column
        const gap = Math.abs((b.y + b.h / 2) - (a.y + a.h / 2)) - (a.h + b.h) / 2;
        if (gap >= -0.01) gy = Math.min(gy, Math.max(0, gap));
      }
    });
    return [Math.min(a.w * PAD, PAD_GAP * gx), Math.min(a.h * PAD, PAD_GAP * gy)];
  });
}

// box prompt in the IMAGE's ACTUAL pixel space (SAM interprets box_prompts as image
// pixels — using a fixed size when the upload is a different size makes every prompt land
// in the wrong place → nothing detected).
function padBox(rc: Rect, [px, py]: [number, number], W: number, H: number): [number, number, number, number] {
  const x0 = Math.max(0, rc.x - px), y0 = Math.max(0, rc.y - py);
  const x1 = Math.min(1, rc.x + rc.w + px), y1 = Math.min(1, rc.y + rc.h + py);
  return [Math.round(x0 * W), Math.round(y0 * H), Math.round(x1 * W), Math.round(y1 * H)];
}

// PNG dimensions from the IHDR header (bytes 16–24), no decode.
function pngDims(b: Uint8Array): { w: number; h: number } | null {
  if (b.length < 24 || b[0] !== 0x89 || b[1] !== 0x50) return null;
  const rd = (o: number) => ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0;
  return { w: rd(16), h: rd(20) };
}

function plausible(rc: Rect, d: Det | null): boolean {
  if (!d || d.score < MIN_SCORE) return false;
  const pcx = rc.x + rc.w / 2, pcy = rc.y + rc.h / 2;
  const move = Math.hypot(d.cx - pcx, d.cy - pcy);
  if (move > Math.max(rc.w, rc.h) * 1.2) return false;     // wandered more than ~one control away
  const aw = d.w / rc.w, ah = d.h / rc.h;
  return aw > 0.4 && aw < 2.6 && ah > 0.4 && ah < 2.6;     // size sanity
}

// Upload image bytes to fal storage → a fal-reachable URL (needed when the source isn't
// publicly fetchable by fal, e.g. a localhost /api/asset in dev). Mirrors sam_snap.py upload().
export async function uploadToFal(falKey: string, bytes: Uint8Array): Promise<string> {
  const init = await fetchJson("https://rest.alpha.fal.ai/storage/upload/initiate", {
    method: "POST",
    headers: { Authorization: `Key ${falKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ file_name: "snap.png", content_type: "image/png" }),
  });
  await fetch(init.upload_url as string, { method: "PUT", headers: { "Content-Type": "image/png" }, body: bytes as unknown as ArrayBuffer });
  return init.file_url as string;
}

async function fetchJson(url: string, init?: RequestInit): Promise<Record<string, unknown>> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`SAM ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const t = (await r.text()).trim();
  return t ? JSON.parse(t) : {};
}

// one SAM call: a box prompt per control. Returns dets aligned to the ctrl order.
async function detect(falKey: string, imageUrl: string, ctrl: Region[], W: number, H: number): Promise<(Det | null)[]> {
  const pads = adaptivePads(ctrl.map((r) => r.rect));
  const boxes = ctrl.map((r, i) => padBox(r.rect, pads[i], W, H));
  const payload = {
    image_url: imageUrl,
    box_prompts: boxes.map((b) => ({ x_min: b[0], y_min: b[1], x_max: b[2], y_max: b[3] })),
    include_boxes: true, include_scores: true,
    return_multiple_masks: true, max_masks: boxes.length, apply_mask: false,
  };
  const auth = { Authorization: `Key ${falKey}`, "Content-Type": "application/json" };
  const sub = await fetchJson(SAM_URL, { method: "POST", headers: auth, body: JSON.stringify(payload) });
  const statusUrl = sub.status_url as string, responseUrl = sub.response_url as string;
  const t0 = Date.now();
  for (;;) {
    const st = await fetchJson(statusUrl, { headers: { Authorization: `Key ${falKey}` } });
    if (st.status === "COMPLETED") break;
    if (st.status === "FAILED" || st.status === "ERROR" || Date.now() - t0 > 120_000) throw new Error(`SAM status ${st.status}`);
    await new Promise((r) => setTimeout(r, 1500));
  }
  const res = await fetchJson(responseUrl, { headers: { Authorization: `Key ${falKey}` } });
  const out: (Det | null)[] = new Array(ctrl.length).fill(null);
  for (const m of (res.metadata as Array<Record<string, unknown>>) ?? []) {
    const i = m.index as number;
    if (i == null || i < 0 || i >= ctrl.length) continue;
    const b = m.box as number[]; // [cx,cy,w,h] normalized
    out[i] = { cx: b[0], cy: b[1], w: b[2], h: b[3], score: (m.score as number) ?? 0 };
  }
  return out;
}

// least-squares slope/intercept for cx ≈ a*pos + b over the "good" (snapped) members
function lineFit(pos: number[], xs: number[]): [number, number] {
  const n = pos.length, sx = pos.reduce((s, v) => s + v, 0), sy = xs.reduce((s, v) => s + v, 0);
  const sxx = pos.reduce((s, v) => s + v * v, 0), sxy = pos.reduce((s, v, i) => s + v * xs[i], 0);
  const d = n * sxx - sx * sx || 1;
  const a = (n * sxy - sx * sy) / d;
  return [a, (sy - a * sx) / n];
}
const median = (a: number[]) => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

// Snap each control's rect to SAM (when confident), then structurally refit
// evenly-spaced rows (transport buttons, EQ bands) so a missed member is interpolated.
// Returns a NEW regions array with corrected rects (only CTRL kinds change).
// snap controls, and ONLY the live screen among displays (visualizer/cd/albumart) — NOT
// small text displays (marquee/time/playlist), whose box prompts overlap neighbours and
// mis-snap onto a button; their layout position is reliable, so keep it.
const BIG_SCREEN = new Set(["visualizer", "cd", "albumart"]);
function snappable(r: Region): boolean {
  if (!CTRL.has(r.kind)) return false;
  if (r.kind === "display") return BIG_SCREEN.has(String((r as { dynamicType?: string }).dynamicType ?? ""));
  return true;
}

export async function snapRegions(falKey: string, imageUrl: string, regions: Region[], imgW = SAM_W, imgH = SAM_H): Promise<{ regions: Region[]; snapped: number; total: number }> {
  const ctrl = regions.filter(snappable);
  if (!ctrl.length) return { regions, snapped: 0, total: 0 };
  const det = await detect(falKey, imageUrl, ctrl, imgW, imgH);
  const newRects: Rect[] = [];
  const flags: ("snap" | "keep" | "refit")[] = [];
  ctrl.forEach((r, i) => {
    const d = det[i];
    if (plausible(r.rect, d) && d) {
      // POSITION-ONLY: move the rect's CENTER onto SAM's detection, but KEEP the prior
      // size. Never let detection resize a control — that made knobs/buttons different
      // sizes (ai-image-coords-rule). The blueprint sizes are the load-bearing truth.
      newRects.push({ x: d.cx - r.rect.w / 2, y: d.cy - r.rect.h / 2, w: r.rect.w, h: r.rect.h }); flags.push("snap");
    } else { newRects.push({ ...r.rect }); flags.push("keep"); }
  });

  const refitRow = (pred: (r: Region) => boolean) => {
    const idx = ctrl.map((r, i) => [r, i] as const).filter(([r]) => pred(r)).map(([, i]) => i);
    if (idx.length < 3) return;
    const order = [...idx].sort((a, b) => ctrl[a].rect.x - ctrl[b].rect.x);
    const good = order.map((i) => flags[i] === "snap");
    if (good.filter(Boolean).length < 2) return;
    const gPos: number[] = [], gXs: number[] = [];
    order.forEach((i, k) => { if (good[k]) { gPos.push(k); gXs.push(newRects[i].x + newRects[i].w / 2); } });
    const [a, b] = lineFit(gPos, gXs);
    const gi = order.filter((_, k) => good[k]);
    const cyMed = median(gi.map((i) => newRects[i].y + newRects[i].h / 2));
    order.forEach((i, k) => {
      if (flags[i] === "snap") return;
      // POSITION-ONLY refit: interpolate the row position; KEEP this control's prior size.
      const cx = a * k + b, pw = ctrl[i].rect.w, ph = ctrl[i].rect.h;
      newRects[i] = { x: cx - pw / 2, y: cyMed - ph / 2, w: pw, h: ph };
      flags[i] = "refit";
    });
  };
  refitRow((r) => r.bind === "eqBand");
  refitRow((r) => r.kind === "button" && ["prev", "play", "pause", "stop", "next"].includes(r.bind ?? ""));

  let ci = 0;
  const out = regions.map((r) => {
    if (!snappable(r)) return r;
    const nr = newRects[ci++];
    return { ...r, rect: { x: +nr.x.toFixed(4), y: +nr.y.toFixed(4), w: +nr.w.toFixed(4), h: +nr.h.toFixed(4) } };
  });
  return { regions: out, snapped: flags.filter((f) => f === "snap").length, total: ctrl.length };
}

// Full align from a SERVER-FETCHABLE image URL: fetch the bytes, read true dims, upload to
// fal storage (fal can't fetch localhost; even in prod this is robust), then snap. Used by
// both /api/snap (CF) and the dev plugin so the logic lives in one place.
export async function snapFromUrl(falKey: string, fetchUrl: string, regions: Region[]): Promise<{ regions: Region[]; snapped: number; total: number }> {
  const r = await fetch(fetchUrl);
  if (!r.ok) throw new Error(`fetch image ${r.status}`);
  const bytes = new Uint8Array(await r.arrayBuffer());
  const dims = pngDims(bytes) ?? { w: SAM_W, h: SAM_H };
  const falUrl = await uploadToFal(falKey, bytes);
  return snapRegions(falKey, falUrl, regions, dims.w, dims.h);
}
