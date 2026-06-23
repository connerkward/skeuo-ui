import { useCallback, useEffect, useState } from "react";

// Document Picture-in-Picture — float arbitrary DOM in an always-on-top OS
// window (Chrome/Edge 111+). The in-browser, zero-install equivalent of the
// Tauri desktop widget: a "Float" button detaches the running skin into a
// mini-player the user keeps visible over other tabs/apps.
//
// requestWindow() MUST be called from a user gesture (browser anti-abuse rule —
// it can't auto-fire on load). The skin's stylesheets are carried into the PiP
// document so it renders identically; the caller portals the live <Composite>
// into pipWindow.document.body, so the SAME React instance keeps driving the
// same audio engine (the window swap never remounts it).

// documentPictureInPicture isn't in the DOM lib types yet — declare what we use.
interface DocumentPictureInPicture {
  requestWindow(opts?: { width?: number; height?: number }): Promise<Window>;
  readonly window: Window | null;
}
declare global {
  interface Window {
    documentPictureInPicture?: DocumentPictureInPicture;
  }
}

// Clone every same-origin stylesheet into the PiP document so the skin looks
// identical. cssRules throws for cross-origin sheets → fall back to a <link>.
function carryStyles(dst: Window) {
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      const style = dst.document.createElement("style");
      style.textContent = Array.from(sheet.cssRules).map((r) => r.cssText).join("");
      dst.document.head.appendChild(style);
    } catch {
      if (sheet.href) {
        const link = dst.document.createElement("link");
        link.rel = "stylesheet";
        link.href = sheet.href;
        dst.document.head.appendChild(link);
      }
    }
  }
}

export interface DocPip {
  supported: boolean;
  pipWindow: Window | null;
  open: (opts?: { width?: number; height?: number }) => Promise<void>;
  close: () => void;
}

export function useDocumentPip(): DocPip {
  const supported =
    typeof window !== "undefined" && "documentPictureInPicture" in window;
  const [pipWindow, setPipWindow] = useState<Window | null>(null);

  const close = useCallback(() => pipWindow?.close(), [pipWindow]);

  const open = useCallback(
    async (opts?: { width?: number; height?: number }) => {
      if (!supported || pipWindow) {
        pipWindow?.focus();
        return;
      }
      // 2:3 player aspect (1024×1536) — keep the floating window matched to it.
      const win = await window.documentPictureInPicture!.requestWindow({
        width: opts?.width ?? 360,
        height: opts?.height ?? 540,
      });
      carryStyles(win);
      win.document.title = "skeuo.fm — mini player";
      win.document.body.classList.add("pip-body");
      // pagehide fires whether the user closes the OS window or we call close()
      win.addEventListener("pagehide", () => setPipWindow(null), { once: true });
      setPipWindow(win);
    },
    [supported, pipWindow],
  );

  // close the floating window if the host component unmounts
  useEffect(() => () => pipWindow?.close(), [pipWindow]);

  return { supported, pipWindow, open, close };
}
