import { useState } from "react";
import { ShareModal } from "./ShareModal";
import "./exportGif.css";

// Floating bottom-right SHARE button. Clicking it now OPENS A MODAL with a live
// preview of exactly what will be shared (a crisp watermarked PNG of the current
// skin) plus options: native Share / copy link, Download PNG, and — on desktop —
// Download GIF and Download Video. It no longer shares immediately.
//
// Exported as `ExportGifButton` for backwards compatibility with App.tsx's
// import — only the behaviour changed, not the mount point or the export name.

export function ExportGifButton({ skinId }: { skinId: string }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        className="export-gif-btn"
        onClick={() => setOpen(true)}
        title="Share this skin"
      >
        <ShareGlyph />
        <span>Share</span>
      </button>
      {open && <ShareModal skinId={skinId} onClose={() => setOpen(false)} />}
    </>
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
