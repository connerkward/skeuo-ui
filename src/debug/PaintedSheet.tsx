// PAINTED sheet — the 4th Template Studio panel. Click to paint the CURRENT template
// via the real shipping FAL pipeline (POST /api/generate → combinedBlueprint → FAL
// image-edit paint), streaming stages (blueprint → paint) and showing the finished
// combined painted sheet (device + control strip, 9:16). One paid FAL call per click.
import { useState } from "react";
import { postGenerate } from "../generate/postGenerate";
import type { Region } from "../template/schema";

export default function PaintedSheet({ regions, prompt }: { regions: Region[]; prompt: string }) {
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [paintUrl, setPaintUrl] = useState("");   // final combined painted sheet
  const [liveUrl, setLiveUrl] = useState("");     // latest streamed stage image (blueprint→paint)
  const [msg, setMsg] = useState("");

  const gen = async () => {
    if (busy) return;
    setBusy(true); setPaintUrl(""); setLiveUrl(""); setStage(""); setMsg("sending to FAL…");
    const t0 = performance.now();
    try {
      const res = await postGenerate(
        { prompt, variant: "capsule", regions },
        (ev) => { setStage(ev.stage); setLiveUrl(ev.url); setMsg(`${ev.stage}…`); },
      );
      if (res.status === "done") {
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
  return (
    <div className="tsCanvas bp">
      <div className="tsCap">PAINTED sheet <span>{busy ? `(${stage || "…"})` : show ? "(FAL)" : "(click to paint · FAL)"}</span></div>
      <div className="tsBP" onClick={() => void gen()} title="click to paint this blueprint via the FAL API (one paid generation)"
        style={{ cursor: busy ? "wait" : "pointer", background: "#15151c", display: "flex", alignItems: "center", justifyContent: "center" }}>
        {show
          ? <img src={show} alt="painted sheet"
              onError={(e) => { const el = e.currentTarget; if (!el.dataset.retried) { el.dataset.retried = "1"; setTimeout(() => { el.src = show + (show.includes("?") ? "&r=1" : "?r=1"); }, 600); } }}
              style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain" }} />
          : <div style={{ color: "#66666f", fontSize: 12, textAlign: "center", padding: 16, lineHeight: 1.5 }}>▶ click to paint<br />this blueprint via FAL</div>}
        {busy && <div style={{ position: "absolute", inset: 0, background: "rgba(10,10,16,.5)", display: "flex", alignItems: "center", justifyContent: "center", color: "#7fe0a0", fontSize: 12 }}>{msg || stage}</div>}
      </div>
      <div style={{ fontSize: 11, marginTop: 4, minHeight: 14, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: msg.startsWith("✓") ? "#7fe0a0" : msg.startsWith("error") ? "#ff8a8a" : "#9a9aa6" }}>{msg}</div>
    </div>
  );
}
