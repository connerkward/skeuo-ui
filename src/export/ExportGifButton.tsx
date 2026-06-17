import { useState } from "react";
import {
  recordPlayerGif,
  downloadGif,
  snapshotPlayerPng,
  downloadPng,
  type ExportProgress,
} from "./exportGif";
import "./exportGif.css";

// Floating bottom-right SHARE button. On a browser that supports sharing files
// (iOS Safari, Android Chrome) it opens the native share sheet with a short
// caption, the skin permalink, and a crisp high-res PNG of the player. On
// everything else (most desktops) it falls back to: copy the link to the
// clipboard AND download the PNG still (+ keep the GIF as an option).
//
// Exported as `ExportGifButton` for backwards compatibility with App.tsx's
// import — only the behaviour and label changed, not the mount point.

const shareUrl = (skinId: string) => `https://skeuo.fm/?skin=${encodeURIComponent(skinId)}`;
const shareText = (skinId: string) => `My ${skinId} skin on skeuo.fm — a skeuomorphic music player.`;

type Feedback = { kind: "ok"; msg: string } | null;

export function ExportGifButton({ skinId }: { skinId: string }) {
  const [busy, setBusy] = useState(false);
  const [pct, setPct] = useState(0);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const flash = (msg: string) => {
    setFeedback({ kind: "ok", msg });
    setTimeout(() => setFeedback(null), 2400);
  };

  const onClick = async () => {
    if (busy) return;
    const el = document.querySelector<HTMLElement>(".stage .player");
    if (!el) return;
    setBusy(true);
    setPct(0);
    try {
      // The primary artifact is a crisp full-res PNG still (sharper than the GIF).
      const { blob: pngBlob, file } = await snapshotPlayerPng(el, skinId);
      const url = shareUrl(skinId);
      const text = shareText(skinId);

      // ── native Web Share (mobile): share text + link + the PNG file ──────────
      const canShareFiles =
        typeof navigator !== "undefined" &&
        !!navigator.canShare &&
        navigator.canShare({ files: [file] });
      if (canShareFiles && navigator.share) {
        try {
          await navigator.share({ title: "skeuo.fm", text, url, files: [file] });
          flash("Shared ✓");
          return;
        } catch (err) {
          // user-cancelled share is not an error worth surfacing
          if ((err as DOMException)?.name === "AbortError") return;
          // otherwise fall through to the desktop fallback
        }
      }

      // ── desktop fallback: copy link to clipboard + download the crisp PNG ─────
      let copied = false;
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(url);
          copied = true;
        }
      } catch { /* clipboard blocked — still download the image */ }
      downloadPng(pngBlob, skinId);
      flash(copied ? "Link copied · PNG saved" : "PNG saved");
    } catch (err) {
      console.error("[share] failed", err);
      flash("Share failed");
    } finally {
      setBusy(false);
      setPct(0);
    }
  };

  // Hidden affordance: shift-click to grab the (now higher-quality) animated GIF
  // instead of the still. Keeps the existing GIF path reachable without a 2nd button.
  const onGif = async (e: React.MouseEvent) => {
    if (!e.shiftKey || busy) return;
    e.preventDefault();
    const el = document.querySelector<HTMLElement>(".stage .player");
    if (!el) return;
    setBusy(true);
    setPct(0);
    try {
      const { blob } = await recordPlayerGif(el, (p: ExportProgress) => setPct(p.pct));
      downloadGif(blob, skinId);
      flash("GIF saved");
    } catch (err) {
      console.error("[export-gif] failed", err);
      flash("GIF failed");
    } finally {
      setBusy(false);
      setPct(0);
    }
  };

  const label = feedback
    ? feedback.msg
    : busy
      ? pct > 0 ? `Rendering… ${Math.round(pct * 100)}%` : "Preparing…"
      : "Share";

  return (
    <button
      className="export-gif-btn"
      onClick={(e) => (e.shiftKey ? onGif(e) : onClick())}
      disabled={busy}
      title="Share this skin (shift-click for an animated GIF)"
    >
      {feedback ? (
        <span className="dot ok" />
      ) : (
        <ShareGlyph />
      )}
      <span>{label}</span>
    </button>
  );
}

// Minimal share glyph (three nodes + links), drawn inline so there's no asset dep.
function ShareGlyph() {
  return (
    <svg className="share-glyph" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <path d="M8.6 10.6 15.4 6.5M8.6 13.4 15.4 17.5" />
    </svg>
  );
}
