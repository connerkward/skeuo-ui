// ── direct DOM → canvas compositor (prod-safe; NO modern-screenshot) ──────────
//
// WHY THIS EXISTS: the old exporter rasterized each frame with modern-screenshot's
// `domToCanvas`. On the MINIFIED PRODUCTION bundle that silently returns a blank
// (grey) canvas — it does not throw — so every exported frame was grey except the
// separately-drawn watermark. It only worked in `npm run dev`. (Confirmed: live
// gif=125KB / video=27KB, only the watermark visible.)
//
// THE FIX (this module): never touch modern-screenshot. Walk the live player DOM
// and draw each element DIRECTLY onto a 2D canvas by reading `getBoundingClientRect`
// (relative to the player's rect) + `getComputedStyle`. Every drawable is taint-free
// and identical in dev and prod:
//   • <img>            → ctx.drawImage (same-origin, decoded) — frame, sprites, switches
//   • <canvas>         → ctx.drawImage live each frame — the spectrum visualizer (motion)
//   • CSS background    → solid color rect + background-image (sprite/gradient)
//   • text nodes        → ctx.fillText with the element's computed font/color, clipped
//   • <svg>            → serialize → rasterize (cached) → drawImage (eq-curve, sliders)
// Painter's order = DOM order; opacity + overflow-clip + border-radius respected.

export interface Mapping {
  // player element rect in screen px (captured once, the coordinate origin)
  rootLeft: number;
  rootTop: number;
  // screen-px → output-px scale (uniform; player is drawn into a fixed dest box)
  scale: number;
  // output-px offset of the player's top-left within the larger IG canvas
  destX: number;
  destY: number;
}

// map a screen-space rect to output-canvas px
function mapRect(r: DOMRect, m: Mapping) {
  return {
    x: m.destX + (r.left - m.rootLeft) * m.scale,
    y: m.destY + (r.top - m.rootTop) * m.scale,
    w: r.width * m.scale,
    h: r.height * m.scale,
  };
}

// parse "rgb(a)(...)" → [r,g,b,a]; returns null for transparent/none.
function parseColor(c: string): [number, number, number, number] | null {
  const m = c.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(",").map((s) => parseFloat(s));
  const a = p.length > 3 ? p[3] : 1;
  if (a <= 0) return null;
  return [p[0], p[1], p[2], a];
}

// approximate a CSS gradient by its representative (last) color stop — these only
// appear on tiny EQ/volume fills, so a flat fill is visually indistinguishable.
function gradientColor(bg: string): string | null {
  const cols = bg.match(/rgba?\([^)]+\)|#[0-9a-fA-F]{3,8}/g);
  return cols && cols.length ? cols[cols.length - 1] : null;
}

// extract url("...") from a background-image value
function bgUrl(bg: string): string | null {
  const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
  return m ? m[1] : null;
}

// max of the (possibly 4) border-radius values, in px, scaled to output
function radiusPx(cs: CSSStyleDeclaration, scale: number, maxR: number): number {
  const r = parseFloat(cs.borderTopLeftRadius) || 0;
  return Math.min(r * scale, maxR);
}

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

// ── image cache: keep decoded <img>/sprite/svg bitmaps so per-frame drawImage is
//    cheap (no re-decode). Keyed by URL or svg markup. ──────────────────────────
const imgCache = new Map<string, HTMLImageElement | "pending" | "error">();
function getImg(url: string): HTMLImageElement | null {
  const hit = imgCache.get(url);
  if (hit instanceof HTMLImageElement) return hit;
  if (hit === undefined) {
    imgCache.set(url, "pending");
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => imgCache.set(url, img);
    img.onerror = () => imgCache.set(url, "error");
    img.src = url;
  }
  return null;
}

// preload every <img> currently in the tree + every CSS background-image url, so
// the FIRST composited frame already has them decoded (avoids a blank first frame).
export async function preloadAssets(root: HTMLElement): Promise<void> {
  const urls = new Set<string>();
  for (const el of root.querySelectorAll<HTMLElement>("*")) {
    if (el instanceof HTMLImageElement && el.src) urls.add(el.src);
    const bg = getComputedStyle(el).backgroundImage;
    const u = bg && bg !== "none" ? bgUrl(bg) : null;
    if (u) urls.add(u);
  }
  await Promise.all(
    [...urls].map(
      (u) =>
        new Promise<void>((res) => {
          const cached = imgCache.get(u);
          if (cached instanceof HTMLImageElement) return res();
          const img = new Image();
          img.crossOrigin = "anonymous";
          img.onload = () => { imgCache.set(u, img); res(); };
          img.onerror = () => { imgCache.set(u, "error"); res(); };
          img.src = u;
        }),
    ),
  );
}

// background-size: cover/contain/percent → dest geometry for a drawImage into box
function drawBgImage(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  bx: number, by: number, bw: number, bh: number,
  cs: CSSStyleDeclaration,
) {
  const size = cs.backgroundSize;
  let dw = bw, dh = bh, dx = bx, dy = by;
  if (size === "cover" || size === "contain") {
    const ir = img.naturalWidth / img.naturalHeight;
    const br = bw / bh;
    const fill = size === "cover" ? ir < br : ir > br;
    if (fill) { dw = bw; dh = bw / ir; } else { dh = bh; dw = bh * ir; }
    dx = bx + (bw - dw) / 2;
    dy = by + (bh - dh) / 2;
  } else {
    // percentage pair like "118% 118%" or "100% 100%": scale box by those factors,
    // honoring background-position (center for the molded faces).
    const parts = size.split(" ");
    const pw = parts[0]?.endsWith("%") ? parseFloat(parts[0]) / 100 : 1;
    const ph = (parts[1] ?? parts[0])?.endsWith("%") ? parseFloat(parts[1] ?? parts[0]) / 100 : pw;
    dw = bw * pw; dh = bh * ph;
    const pos = cs.backgroundPosition.split(" ");
    const fx = pos[0]?.endsWith("%") ? parseFloat(pos[0]) / 100 : 0.5;
    const fy = (pos[1] ?? pos[0])?.endsWith("%") ? parseFloat(pos[1] ?? pos[0]) / 100 : fx;
    dx = bx + (bw - dw) * fx;
    dy = by + (bh - dh) * fy;
  }
  ctx.drawImage(img, dx, dy, dw, dh);
}

// rasterize an <svg> element to a cached bitmap (eq-curve, freeform sliders). The
// markup is the cache key so the tiny dynamic ones still update when they change.
const svgCache = new Map<string, HTMLImageElement | "pending">();
function getSvgImg(svg: SVGElement): HTMLImageElement | null {
  const w = Math.max(1, Math.round(svg.getBoundingClientRect().width));
  const h = Math.max(1, Math.round(svg.getBoundingClientRect().height));
  const clone = svg.cloneNode(true) as SVGElement;
  clone.setAttribute("width", String(w));
  clone.setAttribute("height", String(h));
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const markup = new XMLSerializer().serializeToString(clone);
  const hit = svgCache.get(markup);
  if (hit instanceof HTMLImageElement) return hit;
  if (hit === undefined) {
    svgCache.set(markup, "pending");
    const img = new Image();
    img.onload = () => svgCache.set(markup, img);
    img.onerror = () => svgCache.set(markup, "error" as never);
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(markup);
  }
  return null;
}

// is there at least one direct text-node child with visible text?
function ownText(el: HTMLElement): string {
  let s = "";
  for (const n of el.childNodes) if (n.nodeType === Node.TEXT_NODE) s += n.textContent ?? "";
  return s.trim();
}

// ── the recursive painter ─────────────────────────────────────────────────────
export function paintTree(ctx: CanvasRenderingContext2D, el: HTMLElement, m: Mapping) {
  const cs = getComputedStyle(el);
  if (cs.display === "none" || cs.visibility === "hidden") return;
  const opacity = parseFloat(cs.opacity);
  if (opacity <= 0) return;

  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    // zero-size container can still have visible descendants? no — skip subtree.
    return;
  }
  const { x, y, w, h } = mapRect(rect, m);

  ctx.save();
  if (opacity < 1) ctx.globalAlpha = opacity;

  // clip when the element clips its overflow (marquee window, screens, rounded imgs)
  const clips = cs.overflow !== "visible";
  const rad = radiusPx(cs, m.scale, Math.min(w, h) / 2);
  if (clips) {
    roundRectPath(ctx, x, y, w, h, rad);
    ctx.clip();
  }

  // 1) background color
  const bgc = parseColor(cs.backgroundColor);
  if (bgc) {
    ctx.save();
    ctx.globalAlpha = (opacity < 1 ? opacity : 1) * bgc[3];
    ctx.fillStyle = `rgb(${bgc[0]},${bgc[1]},${bgc[2]})`;
    roundRectPath(ctx, x, y, w, h, rad);
    ctx.fill();
    ctx.restore();
  }

  // 2) background image (sprite url OR gradient approximation)
  const bg = cs.backgroundImage;
  if (bg && bg !== "none") {
    const u = bgUrl(bg);
    if (u) {
      const img = getImg(u);
      if (img && img.naturalWidth > 0) drawBgImage(ctx, img, x, y, w, h, cs);
    } else {
      const gc = gradientColor(bg);
      if (gc) {
        const c = parseColor(gc);
        if (c) {
          ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${c[3]})`;
          roundRectPath(ctx, x, y, w, h, rad);
          ctx.fill();
        }
      }
    }
  }

  // 3) element-type draws
  if (el instanceof HTMLImageElement) {
    if (el.complete && el.naturalWidth > 0) {
      try { ctx.drawImage(el, x, y, w, h); } catch { /* tainted? skip */ }
    } else {
      const img = getImg(el.src);
      if (img) ctx.drawImage(img, x, y, w, h);
    }
  } else if (el instanceof HTMLCanvasElement) {
    if (el.width > 0 && el.height > 0) {
      try { ctx.drawImage(el, x, y, w, h); } catch { /* skip */ }
    }
  } else if (el instanceof SVGElement) {
    const img = getSvgImg(el);
    if (img && img.naturalWidth > 0) ctx.drawImage(img, x, y, w, h);
  } else {
    // 4) own text (leaf text not inside an svg). Recurse into children for nested.
    const txt = ownText(el);
    if (txt) drawText(ctx, el, cs, x, y, w, h, m);
  }

  // 5) recurse children (skip into svg — already rasterized whole)
  if (!(el instanceof SVGElement) && !(el instanceof HTMLImageElement) && !(el instanceof HTMLCanvasElement)) {
    for (const child of el.children) {
      if (child instanceof HTMLElement || child instanceof SVGElement) {
        paintTree(ctx, child as HTMLElement, m);
      }
    }
  }

  ctx.restore();
}

// draw an element's own text with its computed font/color/alignment, clipped to box
function drawText(
  ctx: CanvasRenderingContext2D,
  el: HTMLElement,
  cs: CSSStyleDeclaration,
  x: number, y: number, w: number, h: number,
  m: Mapping,
) {
  const txt = ownText(el);
  if (!txt) return;
  const col = parseColor(cs.color);
  if (!col) return;
  const fontPx = (parseFloat(cs.fontSize) || 12) * m.scale;
  const family = cs.fontFamily || "monospace";
  const weight = cs.fontWeight || "400";
  ctx.save();
  // clip text to its own box so it never bleeds (marquee already clipped by parent)
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.font = `${weight} ${fontPx}px ${family}`;
  ctx.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${col[3]})`;
  ctx.textBaseline = "middle";
  const align = cs.textAlign;
  let tx = x;
  if (align === "center") { ctx.textAlign = "center"; tx = x + w / 2; }
  else if (align === "right" || align === "end") { ctx.textAlign = "right"; tx = x + w; }
  else { ctx.textAlign = "left"; tx = x; }
  // vertical: single line centered in the box (good enough for these LCD read-outs)
  ctx.fillText(txt, tx, y + h / 2);
  ctx.restore();
}
