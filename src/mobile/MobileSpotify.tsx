// MobileSpotify — the connect-&-control affordance for the mobile / iOS shell.
//
// The desktop sidebar has room for the full <SpotifyConnect/> panel; the phone
// doesn't, and connecting is the ONE thing that must be effortless here (audio
// playback runs through the user's real Spotify). So the top bar carries a single
// status pill:
//   • not linked  → "Connect Spotify", one tap calls login() (no menu in the way)
//   • linked      → device/status, one tap opens a bottom sheet (mode · playlist ·
//                   disconnect), reusing the same <SpotifyConnect/> body.
// The pill's dot mirrors the live OAuth status color.

import { useState } from "react";
import type { SpotifyHook } from "../spotify/useSpotify";
import { SpotifyConnect } from "../spotify/SpotifyConnect";

export function MobileSpotify({ sp, mode, setMode }: {
  sp: SpotifyHook;
  mode: "local" | "spotify";
  setMode: (m: "local" | "spotify") => void;
}) {
  const [sheet, setSheet] = useState(false);
  const { status, isConfigured, deviceName, login } = sp;
  const linked = status === "connected" || status === "connecting";

  const label =
    status === "connecting" ? "Linking…"
    : status === "connected" ? (deviceName ?? "Spotify")
    : "Connect Spotify";

  // Not configured (no client id) → open the sheet so the warning is visible.
  // Configured + not linked → straight to login (the easy path the goal wants).
  // Linked → sheet for mode / playlist / disconnect.
  const onTap = () => {
    if (!isConfigured || linked) { setSheet(true); return; }
    login();
  };

  return (
    <>
      <button
        className={`m-sp-pill ${linked ? "linked" : "idle"}`}
        onClick={onTap}
        aria-label={linked ? "Spotify options" : "Connect Spotify"}
      >
        <span className="m-sp-dot" data-status={status} />
        <span className="m-sp-label">{label}</span>
      </button>

      {sheet && (
        <div className="m-sheet-scrim" onPointerDown={(e) => e.target === e.currentTarget && setSheet(false)}>
          <div className="m-sheet" role="dialog" aria-label="Spotify">
            <div className="m-sheet-grip" />
            <SpotifyConnect sp={sp} mode={mode} onMode={setMode} />
            <button className="m-sheet-done" onClick={() => setSheet(false)}>Done</button>
          </div>
        </div>
      )}
    </>
  );
}
