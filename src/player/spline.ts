import type { Pt } from "../template/schema";

/* Catmull-rom spline through normalized control points, sampled to a dense
   polyline with cumulative arc-length. Shared by the seek thumb (Composite) and
   the freeform "ribbon" visualizer (Visualizer) so both ride identical geometry.
   Value is ARC-LENGTH so motion along the curve is monotonic. */
export type Spline = { pts: Pt[]; cum: number[]; len: number };

export function buildSpline(path: Pt[]): Spline {
  const ctrl = path.length >= 2 ? path : [{ x: 0.04, y: 0.5 }, { x: 0.96, y: 0.5 }];
  const out: Pt[] = [];
  const SEG = 24;
  for (let i = 0; i < ctrl.length - 1; i++) {
    const p0 = ctrl[i - 1] ?? ctrl[i], p1 = ctrl[i], p2 = ctrl[i + 1], p3 = ctrl[i + 2] ?? ctrl[i + 1];
    for (let s = 0; s < SEG; s++) {
      const t = s / SEG, t2 = t * t, t3 = t2 * t;
      out.push({
        x: 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
        y: 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3),
      });
    }
  }
  out.push(ctrl[ctrl.length - 1]);
  const cum = [0];
  for (let i = 1; i < out.length; i++) cum.push(cum[i - 1] + Math.hypot(out[i].x - out[i - 1].x, out[i].y - out[i - 1].y));
  return { pts: out, cum, len: cum[cum.length - 1] || 1 };
}

// point on the spline at arc-length fraction v in [0,1]
export function splineAt(sp: Spline, v: number): Pt {
  const target = Math.max(0, Math.min(1, v)) * sp.len;
  let i = 1; while (i < sp.cum.length && sp.cum[i] < target) i++;
  const a = sp.pts[i - 1], b = sp.pts[i] ?? a;
  const seg = (sp.cum[i] ?? sp.len) - sp.cum[i - 1] || 1;
  const t = (target - sp.cum[i - 1]) / seg;
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}

// unit tangent of the spline at arc-length fraction v (for perpendicular bars)
export function splineTangent(sp: Spline, v: number): Pt {
  const e = 0.004;
  const a = splineAt(sp, Math.max(0, v - e)), b = splineAt(sp, Math.min(1, v + e));
  const dx = b.x - a.x, dy = b.y - a.y, m = Math.hypot(dx, dy) || 1;
  return { x: dx / m, y: dy / m };
}

// nearest arc-length fraction to a normalized pointer (monotonic seek)
export function splineProject(sp: Spline, px: number, py: number): number {
  let best = 0, bd = Infinity;
  for (let i = 0; i < sp.pts.length; i++) {
    const d = (sp.pts[i].x - px) ** 2 + (sp.pts[i].y - py) ** 2;
    if (d < bd) { bd = d; best = i; }
  }
  return sp.cum[best] / sp.len;
}
