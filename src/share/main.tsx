import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import ShareApp from "./ShareApp";

// Standalone entry for the per-skin share page (skeuo.fm/share?id=<id>). It is a
// SEPARATE Vite entry from the main app so a shared link loads a small, focused
// player surface — not the whole studio. The player CSS + skin palettes come from
// ShareApp's own "../skins/all" import (same bundle the app and widget use).
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ShareApp />
  </StrictMode>,
);
