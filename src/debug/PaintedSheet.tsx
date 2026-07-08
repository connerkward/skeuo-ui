// PAINTED sheet — the 4th Template Studio panel. Click to paint the CURRENT template
// via the real shipping FAL pipeline (POST /api/generate → combinedBlueprint → FAL
// image-edit paint), streaming stages (blueprint → paint) and showing the finished
// combined painted sheet. One paid FAL call per click.
//
// JOINT paint+mask (default on): the same $ generation returns a two-panel canvas
// (LEFT paint, RIGHT colour-keyed region mask). The REAL shipping extraction
// (maskAlign.extractMaskRegions — the exact code finishCutoutFull runs) is executed
// here and surfaced as a labeled, TOGGLEABLE overlay: dashed = the raw mask blob,
// solid = the snap-X-refined placement box, Δ = the snap delta in % of panel width.
import { useEffect, useState, type CSSProperties } from "react";
import { postGenerate } from "../generate/postGenerate";
import { fetchPaintCanvas, splitJointPanels } from "../generate/cutoutClient";
import { extractMaskRegions, type MaskAlignResult } from "../generate/maskAlign";
import type { GenerateDone } from "../generate/api";
import type { MaskKey } from "../generate/blueprint";
import type { Region } from "../template/schema";

export default function PaintedSheet({ regions, prompt }: { regions: Region[]; prompt: string }) {
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [paintUrl, setPaintUrl] = useState("");   // final combined painted sheet
  const [liveUrl, setLiveUrl] = useState("");     // latest streamed stage image (blueprint→paint)
  const [msg, setMsg] = useState("");
  const [withMask, setWithMask] = useState(true); // JOINT paint+mask request (same $; +mask panel)
  const [done, setDone] = useState<GenerateDone | null>(null);
  // mask extraction output + its keys (for colours/labels), and the overlay toggle
  const [maskViz, setMaskViz] = useState<{ out: MaskAlignResult; keys: MaskKey[] } | null>(null);
  const [showMask, setShowMask] = useState(true);

  const gen = async () => {
    if (busy) return;
    setBusy(true); setPaintUrl(""); setLiveUrl(""); setStage(""); setDone(null); setMaskViz(null);
    setMsg("sending to FAL…");
    const t0 = performance.now();
    try {
      const res = await postGenerate(
        { prompt, variant: "capsule", regions, maskPanel: withMask },
        (ev) => { setStage(ev.stage); setLiveUrl(ev.url); setMsg(`${ev.stage}…`); },
      );
      if (res.status === "done") {
        setDone(res);
        setPaintUrl(res.paintUrl || res.frameUrl || "");
        const secs = Math.round((performance.now() - t0) / 100) / 10;
        setMsg(`✓ ${secs}s · ${res.model}${res.seed != null ? ` · seed ${res.seed}` : ""}`);
      } else if (res.status === "error") {
        setMsg("error: " + res.error);
      } else {
        setMsg("pending async job — see ?pipeline");
      }
    } catch (e) { setMsg("error: " + (e instanceof Error ? e.message : String(e))); }
    finally { setBusy(false); }
  };

  // Prefer the streamed FAL result URL (fully written on the CDN → decodes immediately)
  // over the freshly-stored LOCAL path, which can race the dev server's file write on
  // first load and cache a decode failure (naturalWidth 0). onError retries once with a
  // cache-bust so the local-path fallback recovers after the write flushes.
  const show = liveUrl || paintUrl;
  const joint = !!done?.layout?.maskPanel;

  // Run the REAL mask extraction on the finished joint generation (same code path as
  // finishCutoutFull): decode → split at w//2 → correlate blobs by colour → snap-X.
  useEffect(() => {
    const lay = done?.layout;
    const src = liveUrl || paintUrl;
    if (!done || !lay?.maskPanel || !lay.maskKeys?.length || !src) { setMaskViz(null); return; }
    let alive = true;
    (async () => {
      try {
        const jointCanvas = await fetchPaintCanvas(src);
        const { paint, mask } = splitJointPanels(jointCanvas);
        const out = extractMaskRegions(paint, mask, lay.maskKeys!, lay.devFrac);
        if (alive) setMaskViz({ out, keys: lay.maskKeys! });
      } catch (e) { console.warn("mask extraction failed", e); }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done, paintUrl]);

  // one overlay box, positioned over the LEFT panel of the (1:1) joint image:
  // panel-normalized x maps to [0, 50%] of the full canvas; y maps 1:1.
  const box = (b: [number, number, number, number], style: CSSProperties, label?: string) => (
    <div style={{
      position: "absolute", left: `${b[0] * 50}%`, top: `${b[1] * 100}%`,
      width: `${b[2] * 50}%`, height: `${b[3] * 100}%`, pointerEvents: "none", ...style,
    }}>
      {label && <span style={{
        position: "absolute", left: 0, top: -13, font: "700 9px ui-monospace,monospace",
        color: "#fff", background: "rgba(10,10,16,.78)", padding: "0 4px", borderRadius: 3, whiteSpace: "nowrap",
      }}>{label}</span>}
    </div>
  );

  const overlay = maskViz && showMask && (
    <>
      <div style={{ position: "absolute", top: 4, left: 4, zIndex: 2, background: "rgba(10,10,16,.72)", color: "#7fe0a0", fontSize: 8.5, fontWeight: 700, padding: "1px 5px", borderRadius: 4, pointerEvents: "none" }}>
        ◉ studio overlay · not in the FAL image — dashed = raw mask blob · solid = snapped placement · Δ = snap (% width)
      </div>
      {maskViz.keys.map((k) => {
        const reg = maskViz.out.regions[k.id];
        if (!reg) return null;
        const dx = reg.maskDevice && reg.device
          ? (reg.device[0] + reg.device[2] / 2) - (reg.maskDevice[0] + reg.maskDevice[2] / 2)
          : null;
        return (
          <span key={k.id}>
            {reg.maskDevice && box(reg.maskDevice, { border: `1.5px dashed ${k.color}`, opacity: 0.75 })}
            {reg.device && box(reg.device, { border: `2px solid ${k.color}` },
              `${k.id}${dx != null ? ` Δ${(dx * 100).toFixed(2)}%` : reg.maskDevice ? "" : " (template fallback)"}`)}
          </span>
        );
      })}
      {Object.entries(maskViz.out.cells).map(([bind, b]) => {
        const key = maskViz.keys.find((k) => k.cells.includes(bind));
        return <span key={bind}>{box(b, { border: `1.5px dotted ${key?.color ?? "#fff"}` }, bind)}</span>;
      })}
    </>
  );

  return (
    <div className="tsCanvas bp">
      <div className="tsCap" style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
          PAINTED sheet <span>{busy ? `(${stage || "…"})` : show ? "(FAL)" : "(click to paint · FAL)"}</span>
        </span>
        <label title="joint paint+mask: the SAME paid generation also returns a colour-keyed region mask (right panel, 1:1 4K)"
          style={{ marginLeft: "auto", flex: "0 0 auto", display: "flex", alignItems: "center", gap: 3, fontSize: 10, color: "#8a8a96", cursor: "pointer" }}>
          <input type="checkbox" checked={withMask} onChange={(e) => setWithMask(e.target.checked)} style={{ margin: 0 }} />mask
        </label>
        {maskViz && (
          <button onClick={() => setShowMask((v) => !v)} title="toggle the mask-extraction overlay — labeled boxes are studio annotations, NOT part of the FAL image"
            style={{ flex: "0 0 auto", background: showMask ? "#243524" : "#15151c", color: showMask ? "#7fe0a0" : "#8a8a96", border: "1px solid #2a2a34", borderRadius: 5, padding: "1px 7px", cursor: "pointer", fontSize: 10, fontWeight: 600, whiteSpace: "nowrap" }}>
            {showMask ? "◉" : "◯"} regions
          </button>
        )}
      </div>
      <div className="tsFit">
      <div className="tsBP" onClick={() => void gen()} title="click to paint this blueprint via the FAL API (one paid generation)"
        style={{ cursor: busy ? "wait" : "pointer", background: "#15151c", display: "flex", alignItems: "center", justifyContent: "center", ...(joint ? { aspectRatio: "1 / 1" } : {}) }}>
        {show
          ? <img src={show} alt="painted sheet"
              onError={(e) => { const el = e.currentTarget; if (!el.dataset.retried) { el.dataset.retried = "1"; setTimeout(() => { el.src = show + (show.includes("?") ? "&r=1" : "?r=1"); }, 600); } }}
              style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain" }} />
          : <div style={{ color: "#66666f", fontSize: 12, textAlign: "center", padding: 16, lineHeight: 1.5 }}>▶ click to paint<br />this blueprint via FAL</div>}
        {overlay}
        {busy && <div style={{ position: "absolute", inset: 0, background: "rgba(10,10,16,.5)", display: "flex", alignItems: "center", justifyContent: "center", color: "#7fe0a0", fontSize: 12 }}>{msg || stage}</div>}
      </div></div>
      <div style={{ fontSize: 11, marginTop: 4, minHeight: 14, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: msg.startsWith("✓") ? "#7fe0a0" : msg.startsWith("error") ? "#ff8a8a" : "#9a9aa6" }}>{msg}</div>
    </div>
  );
}
