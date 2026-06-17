import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import WorkshopEditor from "./WorkshopEditor";

// Standalone mount for /editor.html — the workshop authoring tool, isolated
// from the main App so it's testable on its own page.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <WorkshopEditor />
  </StrictMode>,
);
