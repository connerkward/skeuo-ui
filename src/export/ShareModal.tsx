import { useEffect, useRef, useState } from "react";
import {
  snapshotPlayerPng,
  downloadPng,
  recordPlayerGif,
  downloadGif,
  recordPlayerVideo,
  downloadVideo,
} from "./exportGif";
import { Composite, type RuntimeSkinView } from "../player/Composite";
import type { Template } from "../template/schema";
import type { SpotifyDrive } from "../spotify/useSpotify";
import "./ShareModal.css";

// Share modal: opens from the floating bottom-right button. It mounts a REAL,
// self-animating <Composite> of the current skin in the preview box (the same
// player the page renders — the spectrum sweeps, the marquee scrolls, the clock
// ticks). That live player is ALSO the export capture target, so the GIF/Video/
// PNG are exactly what the user sees (WYSIWYG).
//
// On open we PRE-GENERATE the GIF and the Video in the background and cache the
// Blobs in a module-level map keyed by skinId, so by the time the user clicks
// Download either is instant — and re-opening / re-downloading never regenerates.
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

// ── module-level export cache ─────────────────────────────────────────────────
// Keyed by skinId. Each entry holds the in-flight PROMISE (so a download click
// that lands before pre-gen finishes just awaits it) and, once resolved, the
// Blob (so re-clicks / re-opens are instant and never re-encode).
interface CachedExport {
  gifPromise?: Promise<Blob>;
  gif?: Blob;
  videoPromise?: Promise<{ blob: Blob; ext: "mp4" | "webm" }>;
  video?: Blob;
  videoExt?: "mp4" | "webm";
}
const exportCache = new Map<string, CachedExport>();

type Job = "png" | "gif" | "video" | "share" | "copy" | null;
type AssetState = "idle" | "preparing" | "ready" | "error";

interface ShareModalProps {
  skinId: string;
  template: Template;
  runtime?: RuntimeSkinView;
  spotifyDrive?: SpotifyDrive | null;
  onClose: () => void;
}

export function ShareModal({ skinId, template, runtime, spotifyDrive, onClose }: ShareModalProps) {
  const [job, setJob] = useState<Job>(null);
  const [feedback, setFeedback] = useState("");
  const [desktop] = useState(isDesktop);
  const [gifState, setGifState] = useState<AssetState>("idle");
  const [videoState, setVideoState] = useState<AssetState>("idle");
  const previewRef = useRef<HTMLDivElement>(null);
  const previewBlobRef = useRef<Blob | null>(null);
  const url = buildShareUrl(skinId);

  // the modal's OWN live player element — the capture target for every export.
  const player = () => previewRef.current?.querySelector<HTMLElement>(".player") ?? null;

  // ── kick off background pre-generation of GIF + Video on open ────────────────
  // We wait a couple of animation frames so the freshly-mounted <Composite> has
  // laid out (and its spectrum canvas exists) before we capture. Results land in
  // the module cache; re-opens reuse them and never regenerate.
  useEffect(() => {
    if (!desktop) return; // GIF/Video are desktop-only options
    let cancelled = false;
    let entry = exportCache.get(skinId);
    if (!entry) { entry = {}; exportCache.set(skinId, entry); }

    // GIF: already cached → ready; otherwise start (or reuse an in-flight) encode.
    if (entry.gif) {
      setGifState("ready");
    } else {
      setGifState("preparing");
      if (!entry.gifPromise) {
        entry.gifPromise = waitForPlayer(player)
          .then((el) => recordPlayerGif(el).then((r) => r.blob))
          .then((blob) => { entry!.gif = blob; return blob; });
      }
      entry.gifPromise
        .then(() => { if (!cancelled) setGifState("ready"); })
        .catch(() => { if (!cancelled) setGifState("error"); });
    }

    // Video: same pattern.
    if (entry.video) {
      setVideoState("ready");
    } else {
      setVideoState("preparing");
      if (!entry.videoPromise) {
        entry.videoPromise = waitForPlayer(player)
          .then((el) => recordPlayerVideo(el).then((r) => ({ blob: r.blob, ext: r.ext })))
          .then((r) => { entry!.video = r.blob; entry!.videoExt = r.ext; return r; });
      }
      entry.videoPromise
        .then(() => { if (!cancelled) setVideoState("ready"); })
        .catch(() => { if (!cancelled) setVideoState("error"); });
    }

    return () => { cancelled = true; };
  }, [skinId, desktop]);

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

  // native share (mobile) — share a fresh PNG snapshot of the live player + link
  const onShare = async () => {
    if (job) return;
    setJob("share");
    try {
      const el = await waitForPlayer(player).catch(() => null);
      let file: File | null = null;
      if (el) {
        const snap = await snapshotPlayerPng(el, skinId);
        previewBlobRef.current = snap.blob;
        file = snap.file;
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
      const el = await waitForPlayer(player);
      const { blob } = await snapshotPlayerPng(el, skinId);
      downloadPng(blob, skinId);
      flash("PNG saved");
    } catch {
      flash("PNG failed");
    } finally {
      setJob(null);
    }
  };

  // GIF: serve the cached blob if ready, otherwise AWAIT the in-flight pre-gen
  // (download-before-ready → wait then download). Never regenerates.
  const onGif = async () => {
    if (job) return;
    setJob("gif");
    try {
      const entry = exportCache.get(skinId);
      const blob = entry?.gif ?? (await entry?.gifPromise);
      if (!blob) throw new Error("no gif");
      downloadGif(blob, skinId);
      flash("GIF saved");
    } catch {
      flash("GIF failed");
    } finally {
      setJob(null);
    }
  };

  const onVideo = async () => {
    if (job) return;
    setJob("video");
    try {
      const entry = exportCache.get(skinId);
      let blob = entry?.video;
      let ext = entry?.videoExt;
      if (!blob && entry?.videoPromise) {
        const r = await entry.videoPromise;
        blob = r.blob; ext = r.ext;
      }
      if (!blob || !ext) throw new Error("no video");
      downloadVideo(blob, skinId, ext);
      flash(`Video saved (.${ext})`);
    } catch {
      flash("Video failed");
    } finally {
      setJob(null);
    }
  };

  const busy = (j: Job) => job === j;

  // button label reflects pre-gen state: "Preparing…" until the asset is cached,
  // then the normal download label (instant on click).
  const assetLabel = (base: string, state: AssetState) =>
    state === "preparing" ? "Preparing…" : state === "error" ? `${base} (retry)` : base;

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

        {/* LIVE animated preview — a real <Composite>, the same one on the page.
            It animates itself and is the export capture target. */}
        <div className="share-preview" ref={previewRef}>
          <Composite
            template={template}
            skinId={skinId}
            runtime={runtime}
            spotifyDrive={spotifyDrive}
          />
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
              <button
                className={`share-btn ${busy("gif") || gifState === "preparing" ? "busy" : ""}`}
                onClick={onGif}
                disabled={!!job || gifState === "preparing"}
              >
                {busy("gif") || gifState === "preparing" ? <span className="share-spin-sm" /> : <GifIcon />}
                {assetLabel("Download GIF", gifState)} <span className="desktop-tag">desktop</span>
              </button>

              <button
                className={`share-btn ${busy("video") || videoState === "preparing" ? "busy" : ""}`}
                onClick={onVideo}
                disabled={!!job || videoState === "preparing"}
              >
                {busy("video") || videoState === "preparing" ? <span className="share-spin-sm" /> : <VideoIcon />}
                {assetLabel("Download Video", videoState)} <span className="desktop-tag">desktop</span>
              </button>
            </>
          )}
        </div>

        <div className="share-feedback" aria-live="polite">{feedback}</div>
      </div>
    </div>
  );
}

// Resolve the modal's live .player element once it's READY to capture: mounted +
// laid out AND its skin frame image actually decoded. Capturing before the frame
// PNG loads yields a blank export (only the watermark) — so we wait for images,
// then a few rAFs so the spectrum <canvas> has painted at least one frame.
async function waitForPlayer(getEl: () => HTMLElement | null): Promise<HTMLElement> {
  const raf = () => new Promise<void>((r) => requestAnimationFrame(() => r()));
  let el: HTMLElement | null = null;
  for (let i = 0; i < 120; i++) {
    el = getEl();
    if (el && el.offsetWidth > 0 && el.offsetHeight > 0) break;
    await raf();
  }
  if (!el || !el.offsetWidth) throw new Error("player never mounted");
  // wait for every <img> in the player (the skin frame is the big one) to load
  const imgs = [...el.querySelectorAll("img")];
  await Promise.all(
    imgs.map((img) =>
      img.complete && img.naturalWidth > 0
        ? Promise.resolve()
        : img.decode().catch(
            () => new Promise<void>((res) => { img.onload = () => res(); img.onerror = () => res(); }),
          ),
    ),
  );
  await raf(); await raf(); await raf();   // let the spectrum canvas draw
  return el;
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
