import { useState } from "react";
import { ShareModal } from "./ShareModal";
import type { Template } from "../template/schema";
import type { RuntimeSkinView } from "../player/Composite";
import type { SpotifyDrive } from "../spotify/useSpotify";
import "./exportGif.css";

// Floating bottom-right SHARE button. Clicking it OPENS A MODAL with a LIVE,
// self-animating preview of exactly what will be shared (a real <Composite> of
// the current skin, the same one rendered on the page) plus options: native
// Share / copy link, Download PNG, and — on desktop — Download GIF and Download
// Video. The modal's own live player is the export CAPTURE TARGET (WYSIWYG).
//
// The skin props (template / runtime / spotifyDrive) are threaded through from
// App so the modal can mount its own identical <Composite> rather than scraping
// the page's DOM. Exported as `ExportGifButton` for backwards compatibility with
// App.tsx's import — only the behaviour changed, not the mount point or name.

interface Props {
  skinId: string;
  template: Template;
  runtime?: RuntimeSkinView;
  spotifyDrive?: SpotifyDrive | null;
}

export function ExportGifButton({ skinId, template, runtime, spotifyDrive }: Props) {
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
      {open && (
        <ShareModal
          skinId={skinId}
          template={template}
          runtime={runtime}
          spotifyDrive={spotifyDrive}
          onClose={() => setOpen(false)}
        />
      )}
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
