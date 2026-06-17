import { useEffect, useRef, useState } from "react";
import {
  snapshotPlayerPng,
  downloadPng,
  recordPlayerGif,
  downloadGif,
  recordPlayerVideo,
  downloadVideo,
  type ExportProgress,
} from "./exportGif";
import "./ShareModal.css";

// Share modal: opens from the floating bottom-right button. Shows a PNG preview of
// exactly what will be shared (watermark included) and a set of options — native
// Share / copy link, download PNG, download GIF, download Video. On-brand dark.
//
// The share LINK distinguishes generated skins (persisted in localStorage under
// "skeuo:skins") from built-in skins: generated → /share?id=<id>, built-in →
// /?skin=<id>. We read that store directly so App.tsx stays untouched.

function isGeneratedSkin(skinId: string): boolean {
  try {
    const raw = localStorage.getItem("skeuo:skins");
    if (!raw) return false;
    const arr = JSON.parse(raw) as Array<{ id?: string }>;
    return Array.isArray(arr) && arr.some((s) => s?.id === skinId);
  } catch {
    return false;
  }
}

const buildShareUrl = (skinId: string) =>
  isGeneratedSkin(skinId)
    ? `https://skeuo.fm/share?id=${encodeURIComponent(skinId)}`
    : `https://skeuo.fm/?skin=${encodeURIComponent(skinId)}`;

const shareText = (skinId: string) =>
  `My ${skinId} skin on skeuo.fm — a skeuomorphic music player.`;

// is this a desktop-width viewport (where GIF/Video make sense)?
const isDesktop = () =>
  typeof window !== "undefined" && window.matchMedia("(min-width: 700px)").matches;

type Job = "png" | "gif" | "video" | "share" | "copy" | null;

export function ShareModal({ skinId, onClose }: { skinId: string; onClose: () => void }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewErr, setPreviewErr] = useState(false);
  const [job, setJob] = useState<Job>(null);
  const [pct, setPct] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [desktop] = useState(isDesktop);
  const previewBlobRef = useRef<Blob | null>(null);
  const objUrlRef = useRef<string | null>(null);
  const url = buildShareUrl(skinId);

  // ── render the live preview PNG once on open ────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const el = document.querySelector<HTMLElement>(".stage .player");
    if (!el) { setPreviewErr(true); return; }
    snapshotPlayerPng(el, skinId)
      .then(({ blob }) => {
        if (cancelled) return;
        previewBlobRef.current = blob;
        const u = URL.createObjectURL(blob);
        objUrlRef.current = u;
        setPreviewUrl(u);
      })
      .catch(() => { if (!cancelled) setPreviewErr(true); });
    return () => {
      cancelled = true;
      if (objUrlRef.current) URL.revokeObjectURL(objUrlRef.current);
    };
  }, [skinId]);

  // ── esc to close ────────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const flash = (msg: string) => {
    setFeedback(msg);
    setTimeout(() => setFeedback((m) => (m === msg ? "" : m)), 2600);
  };

  const player = () => document.querySelector<HTMLElement>(".stage .player");

  // native share (mobile) — share the already-rendered preview PNG + link
  const onShare = async () => {
    if (job) return;
    setJob("share");
    try {
      let file: File | null = null;
      if (previewBlobRef.current) {
        file = new File([previewBlobRef.current], `skeuo-${skinId}.png`, { type: "image/png" });
      }
      const canShareFiles =
        !!navigator.canShare && !!file && navigator.canShare({ files: [file] });
      if (navigator.share) {
        await navigator.share(
          canShareFiles && file
            ? { title: "skeuo.fm", text: shareText(skinId), url, files: [file] }
            : { title: "skeuo.fm", text: shareText(skinId), url },
        );
        flash("Shared ✓");
      } else {
        // no Web Share at all → fall back to copying the link
        await copyLink();
      }
    } catch (err) {
      if ((err as DOMException)?.name !== "AbortError") flash("Share unavailable — link copied");
      if ((err as DOMException)?.name !== "AbortError") await copyLink(true);
    } finally {
      setJob(null);
    }
  };

  const copyLink = async (silent = false) => {
    if (job && !silent) return;
    if (!silent) setJob("copy");
    try {
      await navigator.clipboard.writeText(url);
      flash("Copied ✓");
    } catch {
      flash("Couldn't copy — select the link");
    } finally {
      if (!silent) setJob(null);
    }
  };

  const onPng = async () => {
    if (job) return;
    setJob("png");
    try {
      // reuse the already-rendered preview blob if we have it (sharp 1080px)
      const blob = previewBlobRef.current
        ?? (await snapshotPlayerPng(player()!, skinId)).blob;
      downloadPng(blob, skinId);
      flash("PNG saved");
    } catch {
      flash("PNG failed");
    } finally {
      setJob(null);
    }
  };

  const onGif = async () => {
    if (job) return;
    const el = player();
    if (!el) return;
    setJob("gif"); setPct(0);
    try {
      const { blob } = await recordPlayerGif(el, (p: ExportProgress) => setPct(p.pct));
      downloadGif(blob, skinId);
      flash("GIF saved");
    } catch {
      flash("GIF failed");
    } finally {
      setJob(null); setPct(0);
    }
  };

  const onVideo = async () => {
    if (job) return;
    const el = player();
    if (!el) return;
    setJob("video"); setPct(0);
    try {
      const { blob, ext } = await recordPlayerVideo(el, (p: ExportProgress) => setPct(p.pct));
      downloadVideo(blob, skinId, ext);
      flash(`Video saved (.${ext})`);
    } catch {
      flash("Video failed");
    } finally {
      setJob(null); setPct(0);
    }
  };

  const busy = (j: Job) => job === j;
  const progBar = (j: Job) =>
    busy(j) && pct > 0 ? (
      <div className="share-prog"><i style={{ width: `${Math.round(pct * 100)}%` }} /></div>
    ) : null;

  return (
    <div
      className="share-overlay"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="share-modal" role="dialog" aria-modal="true" aria-label="Share this skin">
        <button className="share-close" onClick={onClose} aria-label="Close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>

        <div className="share-head">
          <div>
            <h2 className="share-title">Share <span className="fm">skeuo.fm</span></h2>
            <p className="share-sub">{skinId}</p>
          </div>
        </div>

        <div className="share-preview">
          {previewUrl ? (
            <img src={previewUrl} alt={`Preview of the ${skinId} skin`} />
          ) : previewErr ? (
            <span className="share-preview-err">Couldn't render a preview — you can still share the link below.</span>
          ) : (
            <span className="share-spinner" aria-label="Rendering preview" />
          )}
        </div>

        <div className="share-link-row">
          <span className="url">{url}</span>
        </div>

        <div className="share-actions">
          <div className="share-row">
            <button className={`share-btn primary ${busy("share") ? "busy" : ""}`} onClick={onShare} disabled={!!job}>
              {busy("share") ? <span className="share-spin-sm" /> : <ShareIcon />}
              Share
            </button>
            <button className={`share-btn ${busy("copy") ? "busy" : ""}`} onClick={() => copyLink()} disabled={!!job}>
              {busy("copy") ? <span className="share-spin-sm" /> : <LinkIcon />}
              Copy link
            </button>
          </div>

          <button className={`share-btn ${busy("png") ? "busy" : ""}`} onClick={onPng} disabled={!!job}>
            {busy("png") ? <span className="share-spin-sm" /> : <ImageIcon />}
            Download PNG
          </button>

          {desktop && (
            <>
              <button className={`share-btn ${busy("gif") ? "busy" : ""}`} onClick={onGif} disabled={!!job}>
                {busy("gif") ? <span className="share-spin-sm" /> : <GifIcon />}
                Download GIF <span className="desktop-tag">desktop</span>
              </button>
              {progBar("gif")}

              <button className={`share-btn ${busy("video") ? "busy" : ""}`} onClick={onVideo} disabled={!!job}>
                {busy("video") ? <span className="share-spin-sm" /> : <VideoIcon />}
                Download Video <span className="desktop-tag">desktop</span>
              </button>
              {progBar("video")}
            </>
          )}
        </div>

        <div className="share-feedback" aria-live="polite">{feedback}</div>
      </div>
    </div>
  );
}

// ── inline icons (no asset deps) ───────────────────────────────────────────────
const ico = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
function ShareIcon() {
  return (
    <svg viewBox="0 0 24 24" {...ico}>
      <circle cx="18" cy="5" r="2.5" /><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="19" r="2.5" />
      <path d="M8.3 10.8 15.7 6.4M8.3 13.2 15.7 17.6" />
    </svg>
  );
}
function LinkIcon() {
  return (
    <svg viewBox="0 0 24 24" {...ico}>
      <path d="M9 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1" />
      <path d="M15 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1" />
    </svg>
  );
}
function ImageIcon() {
  return (
    <svg viewBox="0 0 24 24" {...ico}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.5" /><path d="m4 17 5-5 4 4 3-3 4 4" />
    </svg>
  );
}
function GifIcon() {
  return (
    <svg viewBox="0 0 24 24" {...ico}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M9 10.5H7.5a1.5 1.5 0 0 0 0 3H9v-1.2M12 10v4M16.5 10H14.5v4M14.5 12h1.6" />
    </svg>
  );
}
function VideoIcon() {
  return (
    <svg viewBox="0 0 24 24" {...ico}>
      <rect x="3" y="6" width="13" height="12" rx="2" />
      <path d="m16 10 5-3v10l-5-3z" />
    </svg>
  );
}
