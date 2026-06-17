/* ============================================================
   geometry.ts — CAD curve / shape / repack math.

   Ported from scripts/.lookdev-detect/cad.html (a vanilla-JS prototype).
   All math here works in a normalized 0..1 unit square (the stage),
   so it is resolution-independent and maps straight onto the schema's
   normalized rects / paths. The editor renders these as SVG.
   ============================================================ */

export type V2 = { x: number; y: number };

/* ---- visualizer shapes (non-rectangular) ----------------------------------
   roundedPolygon and blob both return a list of points in unit space that the
   editor closes into an SVG path and stores on a display region as region.path
   (normalized in the region rect). ---------------------------------------- */

// n-gon with rounded corners, centered at (cx,cy), radius r, corner fraction cr.
// Returns an SVG path `d` string (absolute coords in the same unit space).
export function roundedPolygonPath(
  cx: number, cy: number, r: number, n: number, cr: number,
): string {
  const pts: V2[] = [];
  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    pts.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
  }
  const rr = r * cr;
  let d = "";
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n], pv = pts[(i - 1 + n) % n];
    const v1 = unit(a, pv), v2 = unit(a, b);
    const pA = { x: a.x + v1.x * rr, y: a.y + v1.y * rr };
    const pB = { x: a.x + v2.x * rr, y: a.y + v2.y * rr };
    d += i === 0 ? `M ${f(pA.x)} ${f(pA.y)} ` : `L ${f(pA.x)} ${f(pA.y)} `;
    d += `Q ${f(a.x)} ${f(a.y)} ${f(pB.x)} ${f(pB.y)} `;
  }
  return d + "Z";
}

// organic blob: 8 lobes with a deterministic seed (same as cad.html).
export function blobPath(cx: number, cy: number, r: number, seed = 3): string {
  const n = 8;
  const pts: V2[] = [];
  for (let i = 0; i < n; i++) {
    const a = (i * 2 * Math.PI) / n;
    const rr = r * (0.82 + 0.18 * Math.sin(i * 1.7 + seed));
    pts.push({ x: cx + rr * Math.cos(a), y: cy + rr * Math.sin(a) });
  }
  let d = `M ${f((pts[0].x + pts[n - 1].x) / 2)} ${f((pts[0].y + pts[n - 1].y) / 2)} `;
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n];
    d += `Q ${f(a.x)} ${f(a.y)} ${f((a.x + b.x) / 2)} ${f((a.y + b.y) / 2)} `;
  }
  return d + "Z";
}

// Sample a visualizer shape as a list of normalized points INSIDE a rect, so it
// can be stored as region.path (0..1 in the region's own box). Used by the
// "non-rectangular visualizer" export.
export function shapePointsInRect(
  shape: "circle" | "poly" | "blob", sides: number, corner: number,
): V2[] {
  // center of the rect, radius leaving a small margin
  const cx = 0.5, cy = 0.5, r = 0.46;
  if (shape === "circle") {
    const out: V2[] = [];
    for (let i = 0; i < 24; i++) {
      const a = (i * 2 * Math.PI) / 24;
      out.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
    }
    return out;
  }
  if (shape === "poly") {
    const pts: V2[] = [];
    for (let i = 0; i < sides; i++) {
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / sides;
      pts.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
    }
    // expand corners into a few points each so the spline reads as rounded
    const rr = r * corner;
    const out: V2[] = [];
    for (let i = 0; i < sides; i++) {
      const a = pts[i], b = pts[(i + 1) % sides], pv = pts[(i - 1 + sides) % sides];
      const v1 = unit(a, pv), v2 = unit(a, b);
      out.push({ x: a.x + v1.x * rr, y: a.y + v1.y * rr });
      out.push({ x: a.x + v2.x * rr, y: a.y + v2.y * rr });
    }
    return out;
  }
  // blob
  const n = 8, seed = 3, out: V2[] = [];
  for (let i = 0; i < n; i++) {
    const a = (i * 2 * Math.PI) / n;
    const rr = r * (0.82 + 0.18 * Math.sin(i * 1.7 + seed));
    out.push({ x: cx + rr * Math.cos(a), y: cy + rr * Math.sin(a) });
  }
  return out;
}

/* ---- transport button layout (grid vs along-curve) + repack --------------- */

export type Disc = { x: number; y: number; r: number };

// Distribute n button centers either in a horizontal grid row or along an arc,
// all in unit space. radius/size in unit fractions. Mirrors cad.html buttons().
export function layoutButtons(opts: {
  mode: "grid" | "curve";
  count: number;
  size: number;        // button diameter (unit fraction)
  center: V2;          // arc center (also grid vertical anchor reference)
  curveRadius: number; // unit fraction
  startDeg: number;
  endDeg: number;
  repack: boolean;
}): Disc[] {
  const { mode, count: n, size, center, curveRadius, startDeg, endDeg, repack } = opts;
  const r = size / 2;
  const out: Disc[] = [];
  if (mode === "grid") {
    const y = 0.66, span = 0.62, x0 = 0.5 - span / 2;
    for (let i = 0; i < n; i++)
      out.push({ x: x0 + span * (n === 1 ? 0.5 : i / (n - 1)), y, r });
  } else {
    const a0 = (startDeg * Math.PI) / 180, a1 = (endDeg * Math.PI) / 180;
    for (let i = 0; i < n; i++) {
      const t = n === 1 ? 0.5 : i / (n - 1);
      const a = a0 + (a1 - a0) * t;
      out.push({ x: center.x + curveRadius * Math.cos(a), y: center.y + curveRadius * Math.sin(a), r });
    }
  }
  if (repack) repackDiscs(out);
  return out;
}

// Iterative separation so no two discs overlap (gap of 0.006 unit, ~4px @720).
// Direct port of cad.html's repack loop.
export function repackDiscs(out: Disc[], gap = 0.006, iters = 60): void {
  const n = out.length;
  for (let iter = 0; iter < iters; iter++) {
    let moved = false;
    for (let i = 0; i < n; i++)
      for (let j = i + 1; j < n; j++) {
        const A = out[i], B = out[j];
        const dx = B.x - A.x, dy = B.y - A.y;
        const d = Math.hypot(dx, dy);
        const min = A.r + B.r + gap;
        if (d < min) {
          const push = (min - d) / 2;
          const ux = dx / (d || 1), uy = dy / (d || 1);
          A.x -= ux * push; A.y -= uy * push;
          B.x += ux * push; B.y += uy * push;
          moved = true;
        }
      }
    if (!moved) break;
  }
}

// overlap count among discs (for the live stat readout)
export function overlapCount(d: Disc[]): number {
  let n = 0;
  for (let i = 0; i < d.length; i++)
    for (let j = i + 1; j < d.length; j++)
      if (Math.hypot(d[i].x - d[j].x, d[i].y - d[j].y) < d[i].r + d[j].r) n++;
  return n;
}

/* ---- seek as a CAD arc ---------------------------------------------------- */

// Build an SVG arc `d` for a seek curve in unit space (center, radius, angles).
export function arcPath(cx: number, cy: number, r: number, a0Deg: number, a1Deg: number): string {
  const a0 = (a0Deg * Math.PI) / 180, a1 = (a1Deg * Math.PI) / 180;
  const sx = cx + r * Math.cos(a0), sy = cy + r * Math.sin(a0);
  const ex = cx + r * Math.cos(a1), ey = cy + r * Math.sin(a1);
  const large = Math.abs(a1Deg - a0Deg) > 180 ? 1 : 0;
  const sweep = a1Deg > a0Deg ? 1 : 0;
  return `M ${f(sx)} ${f(sy)} A ${f(r)} ${f(r)} 0 ${large} ${sweep} ${f(ex)} ${f(ey)}`;
}

/* ---- helpers -------------------------------------------------------------- */
function unit(from: V2, to: V2): V2 {
  const dx = to.x - from.x, dy = to.y - from.y, l = Math.hypot(dx, dy) || 1;
  return { x: dx / l, y: dy / l };
}
function f(n: number): string { return (n * 100).toFixed(3); }
