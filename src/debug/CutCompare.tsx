// DEV-ONLY head-to-head: per-control masking, VLM vs SAM (vs baseline + flood-key).
// Mounted on ?cutcompare (optionally &id=<substr>). Runs the REAL endpoints
// (/api/segment = fal SAM-3.1, /api/maskvlm = gpt-4o polygon) on the saved strip,
// applies each mask browser-side, and shows every cut full-res on a checker so the
// masking quality can be judged head-to-head. Per label-overlays-rule each tile is
// labeled (bind · kind · method · px).
import { useEffect, useState } from "react";
import { fetchPaintCanvas, cutSprite, detectCellContent } from "../generate/cutoutClient";
import type { BlueprintLayout } from "../generate/blueprint";
import type { Template, Region } from "../template/schema";

// Border flood-key: sample the cell's background color from its corners, BFS-flood
// from the borders removing pixels close to that bg color → alpha. Background-agnostic
// (white/pink/cyan/purple strips all work), keeps the control's TRUE shape, and keeps
// internal light regions (e.g. a stop icon's white square) since they aren't border-
// connected. No model. tol = color distance tolerance.
function floodKeyBorder(cv: HTMLCanvasElement, tol = 42): HTMLCanvasElement {
  const W = cv.width, H = cv.height;
  const ctx = cv.getContext("2d", { willReadFrequently: true })!;
  const img = ctx.getImageData(0, 0, W, H); const d = img.data;
  // bg color = median of the 4 corners
  const corners = [[0, 0], [W - 1, 0], [0, H - 1], [W - 1, H - 1]].map(([x, y]) => { const i = (y * W + x) * 4; return [d[i], d[i + 1], d[i + 2]]; });
  const med = (k: number) => corners.map((c) => c[k]).sort((a, b) => a - b)[1];
  const br = med(0), bg = med(1), bb = med(2);
  const isBg = (i: number) => Math.abs(d[i] - br) + Math.abs(d[i + 1] - bg) + Math.abs(d[i + 2] - bb) < tol;
  const out = new Uint8Array(W * H); // 1 = background-connected-to-border
  const stack: number[] = [];
  const push = (x: number, y: number) => { if (x < 0 || y < 0 || x >= W || y >= H) return; const p = y * W + x; if (out[p]) return; if (!isBg(p * 4)) return; out[p] = 1; stack.push(p); };
  for (let x = 0; x < W; x++) { push(x, 0); push(x, H - 1); }
  for (let y = 0; y < H; y++) { push(0, y); push(W - 1, y); }
  while (stack.length) { const p = stack.pop()!; const x = p % W, y = (p / W) | 0; push(x + 1, y); push(x - 1, y); push(x, y + 1); push(x, y - 1); }
  for (let p = 0; p < W * H; p++) if (out[p]) d[p * 4 + 3] = 0;
  ctx.putImageData(img, 0, 0);
  return cv;
}

type Cv = HTMLCanvasElement;
const METHODS = ["current", "flood-key", "VLM-poly", "SAM"] as const;
type Method = (typeof METHODS)[number];

interface Tile { bind: string; kind: string; method: Method; url: string; w: number; h: number; note?: string }
interface GenCmp { id: string; prompt: string; stripUrl: string; tiles: Tile[]; error?: string }

function mk(w: number, h: number): Cv { const c = document.createElement("canvas"); c.width = Math.max(1, w | 0); c.height = Math.max(1, h | 0); return c; }
function crop(src: Cv, x: number, y: number, w: number, h: number): Cv {
  const c = mk(w, h); c.getContext("2d")!.drawImage(src, x, y, w, h, 0, 0, w, h); return c;
}
// crop a canvas down to its non-transparent bounds (alpha>16)
function tightAlpha(src: Cv): Cv {
  const ctx = src.getContext("2d", { willReadFrequently: true })!;
  const { width: W, height: H } = src;
  const d = ctx.getImageData(0, 0, W, H).data;
  let x0 = W, y0 = H, x1 = -1, y1 = -1;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (d[(y * W + x) * 4 + 3] > 16) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  }
  if (x1 < x0 || y1 < y0) return src;
  return crop(src, x0, y0, x1 - x0 + 1, y1 - y0 + 1);
}
// apply a white-on-black mask image's luminance as the alpha of `base`
function applyLumaMask(base: Cv, mask: HTMLImageElement): Cv {
  const { width: W, height: H } = base;
  const m = mk(W, H); const mc = m.getContext("2d", { willReadFrequently: true })!;
  mc.drawImage(mask, 0, 0, W, H); const md = mc.getImageData(0, 0, W, H).data;
  const out = mk(W, H); const oc = out.getContext("2d", { willReadFrequently: true })!;
  oc.drawImage(base, 0, 0); const od = oc.getImageData(0, 0, W, H); const o = od.data;
  for (let i = 0; i < W * H; i++) {
    const lum = (md[i * 4] + md[i * 4 + 1] + md[i * 4 + 2]) / 3;
    o[i * 4 + 3] = lum > 110 ? o[i * 4 + 3] : 0;
  }
  oc.putImageData(od, 0, 0); return out;
}
function polyCut(base: Cv, pts: [number, number][]): Cv {
  const { width: W, height: H } = base;
  const out = mk(W, H); const ctx = out.getContext("2d")!;
  ctx.beginPath();
  pts.forEach(([nx, ny], i) => { const x = nx * W, y = ny * H; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.closePath(); ctx.clip(); ctx.drawImage(base, 0, 0);
  return out;
}
const dataUrl = (c: Cv) => c.toDataURL("image/png");

async function loadImg(url: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => { const im = new Image(); im.crossOrigin = "anonymous"; im.onload = () => res(im); im.onerror = rej; im.src = url; });
}

async function processGen(id: string, emit: (g: GenCmp) => void): Promise<void> {
  const base = `/generated/${id}`;
  const [layout, template, meta] = await Promise.all([
    fetch(`${base}-layout.json`).then((r) => r.json() as Promise<BlueprintLayout>),
    fetch(`${base}-template.json`).then((r) => r.json() as Promise<Template>),
    fetch(`${base}-meta.json`).then((r) => r.json()).catch(() => ({})),
  ]);
  const paint = await fetchPaintCanvas(`${base}-paint.png`);
  const W = paint.width, H = paint.height;
  const splitY = Math.round(H * layout.devFrac);
  const stripH = H - splitY;
  const strip = crop(paint, 0, splitY, W, stripH);

  const cells = layout.cells;
  const regById = new Map(template.regions.map((r) => [r.id, r] as const));
  // strip-local pixel boxes (flood-key) + full-image pixel boxes (SAM via imageUrl)
  const boxes = cells.map((c) => {
    const [nx, ny, nw, nh] = c.cellRect;
    const x0 = nx * W, y0 = ny * H - splitY, x1 = (nx + nw) * W, y1 = (ny + nh) * H - splitY;
    return { x_min: Math.max(0, x0), y_min: Math.max(0, y0), x_max: Math.min(W, x1), y_max: Math.min(stripH, y1) };
  });
  // SAM boxes (full-paint px) must be TIGHT to the control, not the whole cell — a
  // background-dominated box makes SAM segment the background. Use detectCellContent's
  // non-white bbox (padded) when found; else a centered shrink of the control band.
  const samBoxes = cells.map((c) => {
    const [nx, ny, nw, nh] = c.cellRect;
    const cx = nx * W, cy = ny * H, cw = nw * W, ch = nh * H;
    const bb = detectCellContent(paint, cx, cy, cw, ch);
    if (bb) {
      const pad = 0.08;
      return {
        x_min: Math.max(0, bb.x - bb.w * pad), y_min: Math.max(0, bb.y - bb.h * pad),
        x_max: Math.min(W, bb.x + bb.w * (1 + pad)), y_max: Math.min(H, bb.y + bb.h * (1 + pad)),
      };
    }
    // fallback (e.g. white-on-white): centered 64%×88% of the control band
    const mx = cx + cw / 2, my = cy + ch / 2, bw = cw * 0.64, bh = ch * 0.88;
    return { x_min: mx - bw / 2, y_min: my - bh / 2, x_max: mx + bw / 2, y_max: my + bh / 2 };
  });

  const tiles: Tile[] = [];
  const prompt = (meta as { prompt?: string }).prompt ?? id;
  const stripUrl = dataUrl(strip);
  const snap = () => emit({ id, prompt, stripUrl, tiles: [...tiles] });
  snap(); // section appears immediately

  // --- current (geometric ellipse/rect clip on full paint) — instant ---
  cells.forEach((c) => {
    try { const sc = cutSprite(paint, c.cellRect, c.kind); tiles.push({ bind: c.bind, kind: c.kind, method: "current", url: dataUrl(sc), w: sc.width, h: sc.height }); }
    catch { tiles.push({ bind: c.bind, kind: c.kind, method: "current", url: "", w: 0, h: 0, note: "fail" }); }
  });
  snap();

  // --- flood-key (border color-key on the strip cell, no model, bg-agnostic) — instant ---
  cells.forEach((c, i) => {
    try {
      const b = boxes[i]; const cw = Math.round(b.x_max - b.x_min), ch = Math.round(b.y_max - b.y_min);
      const cell = crop(strip, Math.round(b.x_min), Math.round(b.y_min), cw, ch);
      const t = tightAlpha(floodKeyBorder(cell));
      tiles.push({ bind: c.bind, kind: c.kind, method: "flood-key", url: dataUrl(t), w: t.width, h: t.height });
    } catch { tiles.push({ bind: c.bind, kind: c.kind, method: "flood-key", url: "", w: 0, h: 0, note: "fail" }); }
  });
  snap();

  // --- SAM (fal-ai/sam-3-1 box-prompt on the FULL paint via imageUrl) ---
  try {
    const r = await fetch("/api/segment", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ imageUrl: `${base}-paint.png`, boxes: samBoxes }),
    });
    const { masks, error } = await r.json();
    if (error) throw new Error(error);
    for (let i = 0; i < cells.length; i++) {
      const c = cells[i]; const mk2 = masks?.[i];
      if (!mk2?.maskUrl) { tiles.push({ bind: c.bind, kind: c.kind, method: "SAM", url: "", w: 0, h: 0, note: "no mask" }); continue; }
      try {
        const mimg = await loadImg(mk2.maskUrl);
        const masked = applyLumaMask(paint, mimg);   // mask is full-paint sized
        const t = tightAlpha(masked);
        tiles.push({ bind: c.bind, kind: c.kind, method: "SAM", url: dataUrl(t), w: t.width, h: t.height, note: `conf ${(mk2.score ?? 0).toFixed(2)}` });
      } catch { tiles.push({ bind: c.bind, kind: c.kind, method: "SAM", url: "", w: 0, h: 0, note: "apply fail" }); }
    }
  } catch (e) {
    cells.forEach((c) => tiles.push({ bind: c.bind, kind: c.kind, method: "SAM", url: "", w: 0, h: 0, note: `err: ${String(e).slice(0, 40)}` }));
  }
  snap();

  // --- VLM-poly (gpt-4o tight polygon on the strip) ---
  try {
    const controls = cells.map((c) => { const r = regById.get(c.bind) as Region | undefined; return { bind: c.bind, kind: c.kind, label: r?.label }; });
    const r = await fetch("/api/maskvlm", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ imageDataUrl: dataUrl(strip), controls }),
    });
    const { polys, error } = await r.json();
    if (error) throw new Error(error);
    const byBind = new Map<string, [number, number][]>((polys ?? []).map((p: { bind: string; points: [number, number][] }) => [p.bind, p.points]));
    cells.forEach((c) => {
      const pts = byBind.get(c.bind);
      if (!pts) { tiles.push({ bind: c.bind, kind: c.kind, method: "VLM-poly", url: "", w: 0, h: 0, note: "no poly" }); return; }
      try { const t = tightAlpha(polyCut(strip, pts)); tiles.push({ bind: c.bind, kind: c.kind, method: "VLM-poly", url: dataUrl(t), w: t.width, h: t.height, note: `${pts.length}pts` }); }
      catch { tiles.push({ bind: c.bind, kind: c.kind, method: "VLM-poly", url: "", w: 0, h: 0, note: "cut fail" }); }
    });
  } catch (e) {
    cells.forEach((c) => tiles.push({ bind: c.bind, kind: c.kind, method: "VLM-poly", url: "", w: 0, h: 0, note: `err: ${String(e).slice(0, 40)}` }));
  }
  snap();
}

const CHECKER = "conic-gradient(#3a3a3a 90deg,#2a2a2a 0 180deg,#3a3a3a 0 270deg,#2a2a2a 0) 0 0/18px 18px";

// Per-method explainer shown at the top of the page (the user asked each column be explained).
const METHOD_INFO: { key: Method; color: string; tag: string; how: string; verdict: string }[] = [
  {
    key: "current", color: "#cccccc", tag: "shipping (geometric)",
    how: "Finds the non-white bbox inside each strip cell, then FORCES a clip shape — an ellipse for round controls, a rounded-rect for sliders — and crops a square around it.",
    verdict: "✗ Imposes a fake shape and keeps the strip background in the square's corners → the white halo. This is the bug being replaced.",
  },
  {
    key: "flood-key", color: "#7CC4FF", tag: "no model · instant · free",
    how: "Samples the cell's background colour from its corners, then flood-fills inward from the borders removing every pixel close to that colour. Whatever's left is the control's real silhouette; transparent everywhere else.",
    verdict: "✓ Cuts the TRUE shape, no halo, background-agnostic (white/pink/cyan strips). Keeps internal light areas (e.g. a stop ■) since they aren't border-connected. Fails only if the control colour ≈ background colour.",
  },
  {
    key: "VLM-poly", color: "#FFC04D", tag: "gpt-4o · the 'mask in the VLM pass' arm",
    how: "Asks gpt-4o to TRACE a tight silhouette polygon (8–20 points) for each control, then cuts by that polygon. This is the 'add masking to the second VLM/slot pass' option.",
    verdict: "✗ VLMs can't do precise geometry — returns crude flat blobs, sometimes traces the label text. Not viable for masking (matches the known noisy-VLM failure mode).",
  },
  {
    key: "SAM", color: "#7CFF4F", tag: "fal sam-3-1 · box-prompt segmentation",
    how: "Box-prompts SAM-3.1 with a CONTENT-TIGHT box per control (from detectCellContent, else a centered shrink — NOT the whole cell). SAM returns a per-pixel mask; applied as alpha + tight-crop.",
    verdict: "✓ With a tight box: clean control masks, conf ~0.95. (The earlier 'halo' was MY bug — a background-dominated cell box made SAM segment the white background. Fixed.) Minor edge residue remains on white-on-white; otherwise on par with flood-key, at the cost of a fal call per control.",
  },
];

export default function CutCompare() {
  const [gens, setGens] = useState<GenCmp[]>([]);
  const [busy, setBusy] = useState(true);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let live = true; setBusy(true);
    (async () => {
      const all = (await fetch("/api/dev/gens").then((r) => r.json())).ids as string[];
      const q = new URLSearchParams(location.search);
      const filter = q.get("id");
      const n = Number(q.get("n") || "1");
      const ids = (filter ? all.filter((x) => x.includes(filter)) : all).slice(0, Math.max(1, n));
      const map = new Map<string, GenCmp>();
      const order = ids.slice();
      const emit = (g: GenCmp) => { if (!live) return; map.set(g.id, g); setGens(order.map((i) => map.get(i)).filter(Boolean) as GenCmp[]); };
      for (const id of ids) {
        try { await processGen(id, emit); } catch (e) { emit({ id, prompt: id, stripUrl: "", tiles: [], error: String(e) }); }
      }
      if (live) setBusy(false);
    })();
    return () => { live = false; };
  }, [nonce]);

  return (
    <div style={{ background: "#0d0e10", color: "#eee", minHeight: "100vh", padding: "16px clamp(12px,3vw,40px)", font: "13px ui-monospace, Menlo, monospace" }}>
      <div style={{ display: "flex", gap: 16, alignItems: "baseline", flexWrap: "wrap", marginBottom: 14 }}>
        <h1 style={{ fontSize: 19, margin: 0 }}>Masking head-to-head — VLM-poly vs SAM</h1>
        <button onClick={() => setNonce((n) => n + 1)} style={{ background: "#23262b", color: "#eee", border: "1px solid #3a3d42", borderRadius: 6, padding: "5px 12px", cursor: "pointer", font: "inherit" }}>↻ re-run</button>
        <span style={{ opacity: 0.6 }}>{busy ? "running SAM + gpt-4o…" : `${gens.length} skin(s)`}</span>
        <span style={{ opacity: 0.6 }}>columns: current (geom clip) · flood-key (no model) · VLM-poly (gpt-4o) · <b style={{ color: "#7CFF4F" }}>SAM</b></span>
        <span style={{ opacity: 0.5 }}>?id=&lt;substr&gt; &amp; ?n=&lt;count&gt;</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10, marginBottom: 18 }}>
        {METHOD_INFO.map((m) => (
          <div key={m.key} style={{ border: `1px solid ${m.color}40`, borderLeft: `3px solid ${m.color}`, borderRadius: 8, padding: "9px 11px", background: "#141619" }}>
            <div style={{ color: m.color, fontWeight: 700, marginBottom: 2 }}>{m.key}</div>
            <div style={{ opacity: 0.5, fontSize: 11, marginBottom: 6 }}>{m.tag}</div>
            <div style={{ fontSize: 11.5, lineHeight: 1.45, opacity: 0.85, marginBottom: 6 }}>{m.how}</div>
            <div style={{ fontSize: 11.5, lineHeight: 1.45, color: m.verdict.startsWith("✓") ? "#9ff58a" : m.verdict.startsWith("✗") ? "#ff8a8a" : "#ffd27a" }}>{m.verdict}</div>
          </div>
        ))}
      </div>
      {gens.map((g) => {
        const binds = [...new Set(g.tiles.map((t) => t.bind))];
        const get = (bind: string, m: Method) => g.tiles.find((t) => t.bind === bind && t.method === m);
        return (
          <section key={g.id} style={{ border: "1px solid #2a2c30", borderRadius: 10, marginBottom: 22, overflow: "hidden" }}>
            <header style={{ background: "#16181b", padding: "8px 12px", display: "flex", gap: 14, flexWrap: "wrap" }}>
              <b>{g.prompt}</b>{g.error && <span style={{ color: "#ff6b6b" }}>ERR {g.error}</span>}
            </header>
            <div style={{ padding: 12, display: "grid", gridTemplateColumns: "120px 1fr", gap: 14, alignItems: "start" }}>
              <div>
                <div style={{ opacity: 0.55, marginBottom: 5 }}>strip</div>
                {g.stripUrl && <img src={g.stripUrl} style={{ width: "100%", borderRadius: 5, background: "#000" }} />}
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ borderCollapse: "collapse", width: "100%" }}>
                  <thead><tr><th style={th}>control</th>{METHODS.map((m) => <th key={m} style={{ ...th, color: m === "SAM" ? "#7CFF4F" : "#ccc" }}>{m}</th>)}</tr></thead>
                  <tbody>
                    {binds.map((bind) => (
                      <tr key={bind}>
                        <td style={{ ...td, whiteSpace: "nowrap" }}><b>{bind}</b><br /><span style={{ opacity: 0.5 }}>{get(bind, "current")?.kind}</span></td>
                        {METHODS.map((m) => { const t = get(bind, m); return (
                          <td key={m} style={td}>
                            <div style={{ width: 96, height: 96, margin: "0 auto", display: "grid", placeItems: "center", background: CHECKER, borderRadius: 5 }}>
                              {t?.url ? <img src={t.url} style={{ maxWidth: "90%", maxHeight: "90%" }} /> : <span style={{ color: "#ff6b6b", fontSize: 10 }}>{t?.note || "—"}</span>}
                            </div>
                            <div style={{ fontSize: 10, opacity: 0.55, textAlign: "center", marginTop: 3 }}>{t?.w ? `${t.w}×${t.h}` : ""} {t?.url ? (t?.note || "") : ""}</div>
                          </td>
                        ); })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        );
      })}
    </div>
  );
}
const th: React.CSSProperties = { textAlign: "center", padding: "4px 8px", borderBottom: "1px solid #2a2c30", fontSize: 11, opacity: 0.8 };
const td: React.CSSProperties = { padding: "6px 8px", borderBottom: "1px solid #1c1e22", verticalAlign: "top", textAlign: "center" };
