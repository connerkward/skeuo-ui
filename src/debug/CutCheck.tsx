// DEV-ONLY cut-inspection harness (mounted on ?cutcheck).
//
// Runs the REAL shipping cut functions (fetchPaintCanvas / detectCellContent /
// cutSprite from cutoutClient.ts — imported, NOT reimplemented) against the saved
// combined paints in public/generated/, so cut geometry can be iterated FAST
// without re-painting, and every cut is inspected full-res with labels.
//
// Per label-overlays-rule: every drawn box carries a legible label (bind · kind,
// + size). Per verify-outputs §7: this exercises the same cutSprite that ships;
// the FINAL proof is still the live Composite render of a generated skin.
import { useEffect, useState } from "react";
import { fetchPaintCanvas, detectCellContent, cutSprite } from "../generate/cutoutClient";
import type { BlueprintLayout } from "../generate/blueprint";
import type { Template } from "../template/schema";

interface CellResult {
  bind: string;
  kind: string;
  cellRect: [number, number, number, number];
  bbox: { x: number; y: number; w: number; h: number } | null;
  spriteUrl: string;
  spriteW: number;
  spriteH: number;
}

interface GenResult {
  id: string;
  prompt: string;
  model: string;
  paintW: number;
  paintH: number;
  paintAspect: number;
  devFrac: number;
  overlayUrl: string; // the combined paint with labeled cell + bbox overlays
  cells: CellResult[];
  error?: string;
}

const COL = {
  cell: "#19e0ff",   // cyan: the cellRect the cut samples from
  bbox: "#7CFF4F",   // lime: the detected content bbox
  dev: "#ff5bd0",    // magenta: the device/strip split line
};

async function processGen(id: string): Promise<GenResult> {
  const base = `/generated/${id}`;
  const [layout, , meta] = await Promise.all([
    fetch(`${base}-layout.json`).then((r) => r.json() as Promise<BlueprintLayout>),
    fetch(`${base}-template.json`).then((r) => r.json() as Promise<Template>),
    fetch(`${base}-meta.json`).then((r) => r.json()).catch(() => ({})),
  ]);
  const paint = await fetchPaintCanvas(`${base}-paint.png`);
  const W = paint.width, H = paint.height;

  // overlay canvas
  const ov = document.createElement("canvas");
  ov.width = W; ov.height = H;
  const ctx = ov.getContext("2d")!;
  ctx.drawImage(paint, 0, 0);

  // device/strip split line (devFrac of combined height)
  const splitY = Math.round(H * layout.devFrac);
  ctx.strokeStyle = COL.dev; ctx.lineWidth = 4; ctx.setLineDash([18, 12]);
  ctx.beginPath(); ctx.moveTo(0, splitY); ctx.lineTo(W, splitY); ctx.stroke();
  ctx.setLineDash([]);
  drawLabel(ctx, 12, splitY - 10, `device | strip  (devFrac ${layout.devFrac.toFixed(3)})`, COL.dev);

  const cells: CellResult[] = [];
  for (const cell of layout.cells) {
    const [nx, ny, nw, nh] = cell.cellRect;
    const cx = nx * W, cy = ny * H, cw = nw * W, ch = nh * H;
    // cell rect (cyan)
    ctx.strokeStyle = COL.cell; ctx.lineWidth = 3; ctx.strokeRect(cx, cy, cw, ch);
    // detected content bbox (lime) — REAL detectCellContent
    const bbox = detectCellContent(paint, cx, cy, cw, ch);
    if (bbox) {
      ctx.strokeStyle = COL.bbox; ctx.lineWidth = 3; ctx.strokeRect(bbox.x, bbox.y, bbox.w, bbox.h);
    }
    drawLabel(ctx, cx + 2, cy - 6, `${cell.bind} · ${cell.kind}`, COL.cell);

    // REAL cutSprite
    let spriteUrl = "", spriteW = 0, spriteH = 0;
    try {
      const sc = cutSprite(paint, cell.cellRect, cell.kind);
      spriteW = sc.width; spriteH = sc.height;
      spriteUrl = sc.toDataURL("image/png");
    } catch (e) { spriteUrl = ""; }

    cells.push({ bind: cell.bind, kind: cell.kind, cellRect: cell.cellRect, bbox, spriteUrl, spriteW, spriteH });
  }

  return {
    id,
    prompt: (meta as { prompt?: string }).prompt ?? id,
    model: (meta as { model?: string }).model ?? "?",
    paintW: W, paintH: H, paintAspect: W / H, devFrac: layout.devFrac,
    overlayUrl: ov.toDataURL("image/png"),
    cells,
  };
}

function drawLabel(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, color: string): void {
  ctx.font = "bold 22px ui-monospace, Menlo, monospace";
  const w = ctx.measureText(text).width;
  ctx.fillStyle = "rgba(0,0,0,0.78)";
  ctx.fillRect(x - 4, y - 22, w + 10, 28);
  ctx.fillStyle = color;
  ctx.fillText(text, x + 1, y);
}

export default function CutCheck() {
  const [ids, setIds] = useState<string[]>([]);
  const [results, setResults] = useState<GenResult[]>([]);
  const [busy, setBusy] = useState(true);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let live = true;
    setBusy(true);
    (async () => {
      const all = (await fetch("/api/dev/gens").then((r) => r.json())).ids as string[];
      // optional ?ids=a,b,c filter; else newest 8
      const filter = new URLSearchParams(location.search).get("ids");
      const ids = filter ? all.filter((x) => filter.split(",").some((f) => x.includes(f))) : all.slice(0, 8);
      if (!live) return;
      setIds(ids);
      const out: GenResult[] = [];
      for (const id of ids) {
        try { out.push(await processGen(id)); }
        catch (e) { out.push({ id, prompt: id, model: "?", paintW: 0, paintH: 0, paintAspect: 0, devFrac: 0, overlayUrl: "", cells: [], error: String(e) }); }
        if (live) setResults([...out]);
      }
      if (live) setBusy(false);
    })();
    return () => { live = false; };
  }, [nonce]);

  const ASPECT_OK = 9 / 16;

  return (
    <div style={{ background: "#0d0e10", color: "#eee", minHeight: "100vh", padding: "16px clamp(12px,3vw,40px)", font: "14px ui-monospace, Menlo, monospace" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, margin: 0 }}>Cut-check — real cutSprite on saved paints</h1>
        <button onClick={() => setNonce((n) => n + 1)} style={btn}>↻ re-run cut (HMR-safe)</button>
        <span style={{ opacity: 0.6 }}>{busy ? "processing…" : `${results.length} / ${ids.length} generations`}</span>
        <span style={{ opacity: 0.6 }}>
          legend: <b style={{ color: COL.cell }}>cellRect</b> · <b style={{ color: COL.bbox }}>detected bbox</b> · <b style={{ color: COL.dev }}>device|strip</b>
        </span>
      </div>

      {results.map((g) => (
        <section key={g.id} style={{ border: "1px solid #2a2c30", borderRadius: 10, marginBottom: 22, overflow: "hidden" }}>
          <header style={{ background: "#16181b", padding: "8px 12px", display: "flex", gap: 14, flexWrap: "wrap", alignItems: "baseline" }}>
            <b>{g.prompt}</b>
            <span style={{ opacity: 0.6 }}>{g.model}</span>
            <span style={{ color: Math.abs(g.paintAspect - ASPECT_OK) < 0.01 ? COL.bbox : "#ff6b6b" }}>
              paint {g.paintW}×{g.paintH} (aspect {g.paintAspect.toFixed(3)} {Math.abs(g.paintAspect - ASPECT_OK) < 0.01 ? "✓ 9:16" : "✗ NOT 9:16"})
            </span>
            {g.error && <span style={{ color: "#ff6b6b" }}>ERROR: {g.error}</span>}
          </header>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(280px, 1fr) 2fr", gap: 16, padding: 14, alignItems: "start" }}>
            {/* labeled overlay of the full combined paint */}
            <div>
              <div style={{ opacity: 0.6, marginBottom: 6 }}>combined paint + overlays</div>
              {g.overlayUrl && <img src={g.overlayUrl} alt="overlay" style={{ width: "100%", height: "auto", borderRadius: 6, background: "#000" }} />}
            </div>
            {/* each cut sprite, full-res, labeled */}
            <div>
              <div style={{ opacity: 0.6, marginBottom: 6 }}>cut sprites ({g.cells.length}) — full res, on checker</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10 }}>
                {g.cells.map((c, i) => (
                  <figure key={i} style={{ margin: 0, border: "1px solid #2a2c30", borderRadius: 6, overflow: "hidden", background: "#16181b" }}>
                    <div style={{ height: 130, display: "grid", placeItems: "center", background: "conic-gradient(#3a3a3a 90deg,#2a2a2a 0 180deg,#3a3a3a 0 270deg,#2a2a2a 0) 0 0/20px 20px" }}>
                      {c.spriteUrl
                        ? <img src={c.spriteUrl} alt={c.bind} style={{ maxWidth: "92%", maxHeight: "92%", imageRendering: "auto" }} />
                        : <span style={{ color: "#ff6b6b", fontSize: 11 }}>cut failed</span>}
                    </div>
                    <figcaption style={{ padding: "5px 7px", fontSize: 11, lineHeight: 1.35 }}>
                      <b>{c.bind}</b> · {c.kind}<br />
                      <span style={{ opacity: 0.6 }}>{c.spriteW}×{c.spriteH}px {c.bbox ? "· bbox✓" : "· no-bbox"}</span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}

const btn: React.CSSProperties = {
  background: "#23262b", color: "#eee", border: "1px solid #3a3d42",
  borderRadius: 6, padding: "5px 12px", cursor: "pointer", font: "inherit",
};
