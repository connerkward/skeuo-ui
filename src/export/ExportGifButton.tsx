import { useState } from "react";
import { recordPlayerGif, downloadGif, type ExportProgress } from "./exportGif";
import "./exportGif.css";

// Floating bottom-right button that records the live .player as an animated GIF.
export function ExportGifButton({ skinId }: { skinId: string }) {
  const [busy, setBusy] = useState(false);
  const [pct, setPct] = useState(0);

  const onClick = async () => {
    if (busy) return;
    const el = document.querySelector<HTMLElement>(".stage .player");
    if (!el) return;
    setBusy(true);
    setPct(0);
    try {
      const { blob } = await recordPlayerGif(el, (p: ExportProgress) => setPct(p.pct));
      downloadGif(blob, skinId);
    } catch (err) {
      console.error("[export-gif] failed", err);
    } finally {
      setBusy(false);
      setPct(0);
    }
  };

  const label = busy
    ? `Recording… ${Math.round(pct * 100)}%`
    : "Export GIF";

  return (
    <button className="export-gif-btn" onClick={onClick} disabled={busy} title="Record this skin as an animated GIF">
      <span className="dot" />
      <span>{label}</span>
    </button>
  );
}
