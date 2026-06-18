// <SpotifyConnect/> — the connect-&-control panel for the sidebar.
//
// Renders the "Connect Spotify" button, the Spotify-vs-local mode switch, the
// "play here" (in-page SDK device) toggle, a playlist picker, and live status /
// error / device readout. All Spotify logic lives in useSpotify; this is pure UI.

import type { SpotifyHook } from "./useSpotify";
import { isMobileApp } from "../platform";

export function SpotifyConnect({ sp, mode, onMode }: {
  sp: SpotifyHook;
  mode: "local" | "spotify";
  onMode: (m: "local" | "spotify") => void;
}) {
  const { status, error, isConfigured, deviceName, playHere, setPlayHere,
          playlists, chosenPlaylistId, setChosenPlaylistId, login, logout } = sp;
  const linked = status === "connected" || status === "connecting";
  // "Play here" is the in-page Web Playback SDK device — it needs EME/Widevine,
  // which the iOS WKWebView doesn't provide, so hide it in the iOS app. There,
  // playback always runs on the user's active Spotify device (their phone's
  // Spotify app or any Connect target).
  const canPlayHere = !isMobileApp();

  return (
    <div className="sp-panel">
      <div className="sp-head">
        <span className="sp-dot" data-status={status} />
        <span className="sp-title">Spotify</span>
      </div>

      {!isConfigured && (
        <p className="sp-note sp-warn">
          Set <code>VITE_SPOTIFY_CLIENT_ID</code> in <code>.env.local</code> and
          restart the dev server to enable Spotify mode. See <code>.env.example</code>.
        </p>
      )}

      {/* mode switch — only meaningful once linked, but always visible so the
          local demo can be re-selected without disconnecting */}
      <div className="sp-mode" role="tablist" aria-label="Player source">
        <button role="tab" aria-selected={mode === "local"} className="sp-mode-btn"
          data-active={mode === "local"} onClick={() => onMode("local")}>
          Local demo
        </button>
        <button role="tab" aria-selected={mode === "spotify"} className="sp-mode-btn"
          data-active={mode === "spotify"} disabled={!linked}
          onClick={() => onMode("spotify")} title={linked ? "" : "Connect first"}>
          Spotify
        </button>
      </div>

      {!linked ? (
        <button className="sp-connect" disabled={!isConfigured} onClick={login}>
          Connect Spotify
        </button>
      ) : (
        <>
          <div className="sp-status">
            {status === "connecting" && <span>Linking…</span>}
            {status === "connected" && (
              <span>Linked{deviceName ? ` · ${deviceName}` : " · no active device"}</span>
            )}
          </div>

          {/* in-page SDK device (Premium) — desktop/web only (no EME on iOS) */}
          {canPlayHere && (
            <label className="sp-toggle">
              <input type="checkbox" checked={playHere} onChange={(e) => setPlayHere(e.target.checked)} />
              <span>Play here (this tab · Premium)</span>
            </label>
          )}

          {/* playlist picker → the playlist screen + selectTrack context */}
          {playlists.length > 0 && (
            <label className="sp-field">
              <span>Playlist screen</span>
              <select value={chosenPlaylistId ?? ""} onChange={(e) => setChosenPlaylistId(e.target.value)}>
                {playlists.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.tracks.total})</option>
                ))}
              </select>
            </label>
          )}

          <button className="sp-disconnect" onClick={logout}>Disconnect</button>
        </>
      )}

      {error && <p className="sp-note sp-err" title={error}>{error}</p>}
    </div>
  );
}
