// LIVE PAINT — a collapsible drawer for the Template Studio that paints the CURRENT
// combined blueprint in real time (<~3s) using a LOCAL, warm sidecar:
// SD1.5 + LCM-LoRA (few-step, CFG-free) + ControlNet(canny) + TAESD tiny-VAE, on MPS.
// In-software, no cloud, no ComfyUI. (generation/paint_server.py)
//
// Rasterizes the blueprint SVG → feeds it as the ControlNet control image. Everything
// is a live lookdev control: cond-scale, steps, seed, resolution, auto-paint-on-edit.
// Mounts with one line: <LivePaintPanel combinedSvg={combined?.svg} theme={prompt} />
import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_SERVER = "http://localhost:8788";
const round8 = (n: number) => Math.max(8, Math.round(n / 8) * 8);

type Health = { ready?: boolean; loading?: boolean; device?: string; dtype?: string; base?: string; controlnet?: string; error?: string | null };
type GenResult = { image?: string; control_preview?: string; seed?: number; timing_ms?: number; error?: string; loading?: boolean; size?: [number, number] };

// Rasterize an SVG string to a PNG data URL at the blueprint's native size (1024x1820).
// The sidecar resizes it down to the paint resolution — this is just a clean source.
function svgToPng(svg: string, w: number, h: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = w; c.height = h;
      const ctx = c.getContext("2d");
      if (!ctx) { URL.revokeObjectURL(url); reject(new Error("no 2d ctx")); return; }
      ctx.fillStyle = "#808082"; ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      resolve(c.toDataURL("image/png"));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("svg raster failed")); };
    img.src = url;
  });
}

const lbl: React.CSSProperties = { display: "flex", flexDirection: "column", fontSize: 12, color: "#b8b8c4", gap: 3 };
const val: React.CSSProperties = { color: "#7fe0a0", fontWeight: 700 };
const field: React.CSSProperties = { background: "#15151c", color: "#e8e8ee", border: "1px solid #2a2a34", borderRadius: 6, padding: "5px 8px", fontSize: 12, width: "100%", boxSizing: "border-box" };

export default function LivePaintPanel({ combinedSvg, theme }: { combinedSvg: string | null | undefined; theme: string }) {
  const [open, setOpen] = useState(false);
  const [server, setServer] = useState(DEFAULT_SERVER);
  const [health, setHealth] = useState<Health>({});
  const [prompt, setPrompt] = useState("");
  const [neg, setNeg] = useState("text, watermark, ui mockup, blurry, low quality, duplicated");
  const [scale, setScale] = useState(0.8);           // ControlNet conditioning strength
  const [steps, setSteps] = useState(4);             // LCM few-step
  const [guidance, setGuidance] = useState(1.0);     // LCM: ~1, CFG-free
  const [resW, setResW] = useState(448);             // paint width (9:16 → height auto)
  const [cannyLo, setCannyLo] = useState(80);
  const [cannyHi, setCannyHi] = useState(180);
  const [seed, setSeed] = useState(1234);
  const [lockSeed, setLockSeed] = useState(false);
  const [auto, setAuto] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GenResult | null>(null);
  const [msg, setMsg] = useState("");
  const debTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!prompt && theme) setPrompt(`${theme}, finished tactile product render, glossy sculpted controls molded into the housing, studio lighting, flat neutral background, no text`);
  }, [theme, prompt]);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch(`${server}/health`);
        const h = await r.json();
        if (alive) setHealth(h);
      } catch { if (alive) setHealth({ error: "sidecar unreachable — start generation/paint_server.py" }); }
    };
    tick();
    const iv = window.setInterval(tick, 2500);
    return () => { alive = false; window.clearInterval(iv); };
  }, [open, server]);

  const paint = useCallback(async () => {
    if (!combinedSvg) { setMsg("no blueprint"); return; }
    setBusy(true); setMsg("rasterizing blueprint…");
    try {
      const control = await svgToPng(combinedSvg, 1024, 1820);
      const width = round8(resW), height = round8((resW * 16) / 9);
      setMsg("painting…");
      const body = {
        prompt, negative_prompt: neg, control_image: control,
        controlnet_conditioning_scale: scale, steps, guidance,
        seed: lockSeed ? seed : null, canny_low: cannyLo, canny_high: cannyHi, width, height,
      };
      const r = await fetch(`${server}/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d: GenResult = await r.json();
      if (d.error) { setMsg(d.error); }
      else {
        setResult(d);
        if (!lockSeed && typeof d.seed === "number") setSeed(d.seed);
        setMsg(`✓ ${d.timing_ms}ms · seed ${d.seed} · ${d.size?.join("×")}`);
      }
    } catch (e) { setMsg("error: " + (e instanceof Error ? e.message : String(e))); }
    finally { setBusy(false); }
  }, [combinedSvg, prompt, neg, scale, steps, guidance, lockSeed, seed, cannyLo, cannyHi, resW, server]);

  // auto-paint (debounced) on blueprint change
  useEffect(() => {
    if (!open || !auto || !combinedSvg || busy) return;
    if (debTimer.current) window.clearTimeout(debTimer.current);
    debTimer.current = window.setTimeout(() => { void paint(); }, 700);
    return () => { if (debTimer.current) window.clearTimeout(debTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combinedSvg, auto, open]);

  const ready = health.ready === true;
  const statusColor = health.error ? "#ff6a6a" : ready ? "#3ce07f" : "#f5c451";
  const statusText = health.error ? "error" : ready ? `ready · ${health.device} · ${health.dtype}` : health.loading ? "loading model…" : "connecting…";

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} title="Live real-time paint of the current blueprint (SD1.5 · LCM · ControlNet, local)"
        style={{ position: "fixed", right: 14, bottom: 52, zIndex: 50, background: "#1c1c26", color: "#e8e8ee", border: "1px solid #3a3a48", borderRadius: 10, padding: "9px 14px", cursor: "pointer", fontSize: 13, boxShadow: "0 4px 18px rgba(0,0,0,.4)" }}>
        🎨 Live Paint
      </button>
    );
  }

  return (
    <div style={{ position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 50, width: "min(440px, 100vw)", background: "#0e0e14", borderLeft: "1px solid #26262f", boxShadow: "-8px 0 30px rgba(0,0,0,.5)", display: "flex", flexDirection: "column", overflowY: "auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderBottom: "1px solid #1e1e26", position: "sticky", top: 0, background: "#0e0e14", zIndex: 1 }}>
        <b style={{ fontSize: 14 }}>🎨 Live Paint</b>
        <span style={{ fontSize: 10.5, color: statusColor, marginLeft: 4 }}>● {statusText}</span>
        <button onClick={() => setOpen(false)} style={{ marginLeft: "auto", background: "transparent", color: "#8a8a96", border: "1px solid #33333f", borderRadius: 6, padding: "3px 9px", cursor: "pointer", fontSize: 12 }}>✕</button>
      </div>

      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        {/* RESULT */}
        <div style={{ position: "relative", width: "100%", aspectRatio: "9/16", background: "#15151c", border: "1px solid #2a2a34", borderRadius: 10, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {result?.image
            ? <img src={result.image} alt="paint" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
            : <span style={{ color: "#66666f", fontSize: 12, textAlign: "center", padding: 20 }}>the current blueprint, painted in real time, appears here</span>}
          {busy && <div style={{ position: "absolute", inset: 0, background: "rgba(10,10,16,.55)", display: "flex", alignItems: "center", justifyContent: "center", color: "#7fe0a0", fontSize: 12 }}>{msg || "painting…"}</div>}
          {result?.control_preview && <img src={result.control_preview} alt="control" title="ControlNet input (canny of the blueprint)" style={{ position: "absolute", left: 8, bottom: 8, width: 56, border: "1px solid #3a3a48", borderRadius: 4, opacity: 0.9 }} />}
        </div>
        <div style={{ fontSize: 11, color: msg.startsWith("✓") ? "#7fe0a0" : "#9a9aa6", minHeight: 14 }}>{msg}</div>

        <button onClick={() => void paint()} disabled={busy || !ready}
          style={{ background: busy || !ready ? "#23232c" : "#1f6f3f", color: "#fff", border: "1px solid #2f8f52", borderRadius: 8, padding: "9px", cursor: busy || !ready ? "default" : "pointer", fontSize: 14, fontWeight: 600, opacity: busy || !ready ? 0.6 : 1 }}>
          {busy ? "painting…" : "▶ Paint blueprint"}
        </button>

        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#b8b8c4" }}>
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
          auto-paint on blueprint edit (debounced)
        </label>

        <label style={lbl}>prompt (material / style)
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} style={{ ...field, resize: "vertical", fontFamily: "inherit" }} />
        </label>
        <label style={lbl}>negative
          <input value={neg} onChange={(e) => setNeg(e.target.value)} style={field} />
        </label>

        <label style={lbl}>resolution (width, 9:16) <b style={val}>{round8(resW)}×{round8((resW * 16) / 9)}</b> <span style={{ fontSize: 10, color: "#66666f" }}>(smaller = faster)</span>
          <input type="range" min={320} max={576} step={32} value={resW} onChange={(e) => setResW(+e.target.value)} /></label>
        <label style={lbl}>controlnet scale <b style={val}>{scale.toFixed(2)}</b>
          <input type="range" min={0} max={1.5} step={0.05} value={scale} onChange={(e) => setScale(+e.target.value)} /></label>
        <label style={lbl}>steps <b style={val}>{steps}</b> <span style={{ fontSize: 10, color: "#66666f" }}>(LCM: 2–6)</span>
          <input type="range" min={1} max={8} step={1} value={steps} onChange={(e) => setSteps(+e.target.value)} /></label>
        <label style={lbl}>guidance <b style={val}>{guidance.toFixed(1)}</b> <span style={{ fontSize: 10, color: "#66666f" }}>(LCM → ~1)</span>
          <input type="range" min={0} max={3} step={0.5} value={guidance} onChange={(e) => setGuidance(+e.target.value)} /></label>
        <div style={{ display: "flex", gap: 10 }}>
          <label style={{ ...lbl, flex: 1 }}>canny lo <b style={val}>{cannyLo}</b>
            <input type="range" min={0} max={255} value={cannyLo} onChange={(e) => setCannyLo(+e.target.value)} /></label>
          <label style={{ ...lbl, flex: 1 }}>canny hi <b style={val}>{cannyHi}</b>
            <input type="range" min={0} max={255} value={cannyHi} onChange={(e) => setCannyHi(+e.target.value)} /></label>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <label style={{ ...lbl, flex: 1 }}>seed
            <input type="number" value={seed} onChange={(e) => setSeed(+e.target.value)} style={field} /></label>
          <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#b8b8c4", paddingBottom: 6 }}>
            <input type="checkbox" checked={lockSeed} onChange={(e) => setLockSeed(e.target.checked)} /> lock</label>
          <button onClick={() => setSeed(Math.floor(Math.random() * 1e9))} style={{ ...field, width: "auto", cursor: "pointer", paddingBottom: 6 }}>🎲</button>
        </div>

        <label style={lbl}>sidecar
          <input value={server} onChange={(e) => setServer(e.target.value)} style={field} /></label>
        {health.error && <div style={{ fontSize: 11, color: "#ff8a8a", lineHeight: 1.5 }}>{health.error}<br /><code style={{ color: "#c8c8d2" }}>generation/.venv-zimage/bin/python generation/paint_server.py</code></div>}
        <div style={{ fontSize: 10.5, color: "#5a5a64", lineHeight: 1.5 }}>{health.base} · {health.controlnet}</div>
      </div>
    </div>
  );
}
