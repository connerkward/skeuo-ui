// useSpotify — the connect-&-control hook. Owns OAuth lifecycle, polls real
// playback, and exposes:
//   • a `status` for the <SpotifyConnect/> UI (configured / connecting / linked)
//   • a `drive: SpotifyDrive | null` that usePlayer consumes to REPLACE the local
//     WebAudio engine with real Spotify control when connected.
//
// When `drive` is non-null the skin's transport drives the user's real Spotify
// playback (active device, or the in-page SDK device when "play here" is on),
// and the screens reflect the real current track / progress / volume / playlist.
// When `drive` is null the existing local demo engine runs unchanged.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  beginLogin, clearTokens, getAccessToken, handleRedirectCallback,
  hasTokens, isConfigured,
} from "./auth";
import * as api from "./api";
import { NoActiveDeviceError, type PlaybackState, type SimplifiedPlaylist, type SpotifyTrack } from "./api";
import { initWebPlaybackSDK, type SdkHandle } from "./sdk";
import type { Track } from "../player/data";
import { isTauri, awaitDesktopCallback } from "../platform";

// The interface usePlayer reads when Spotify-connected. All transport methods
// are fire-and-forget against the Web API; reflected state comes from polling.
export interface SpotifyDrive {
  // reflected, real-time-ish state
  track: Track;          // current track in the player's own shape
  tracks: Track[];       // chosen playlist's tracks (playlist screen)
  trackIdx: number;      // index of current track within `tracks` (-1 if not in list)
  playing: boolean;
  elapsedSec: number;    // real progress
  durationSec: number;   // real track length
  volume: number;        // 0..1
  shuffle: boolean;
  repeatMode: number;    // 0 off · 1 one · 2 all (mapped from Spotify states)
  deviceName: string | null;
  // transport → Spotify Web API
  play: () => void;
  pause: () => void;
  next: () => void;
  prev: () => void;
  seekTo: (frac: number) => void;   // 0..1 of duration
  setVolume: (v: number) => void;   // 0..1
  toggleShuffle: () => void;
  cycleRepeat: () => void;
  selectTrack: (i: number) => void; // play track i of the chosen playlist
}

export type SpotifyStatus =
  | "unconfigured"   // no VITE_SPOTIFY_CLIENT_ID
  | "disconnected"   // configured, not logged in
  | "connecting"     // OAuth round-trip / first poll in flight
  | "connected"      // linked, controlling a device
  | "error";

// Module-level one-shot guard: React 19 StrictMode double-invokes mount effects,
// but an OAuth `code` is single-use — exchanging it twice fails. This promise
// ensures handleRedirectCallback runs exactly once per page load no matter how
// many times the effect fires.
let redirectHandled: Promise<{ exchanged: boolean; error?: string }> | null = null;
function handleRedirectOnce() {
  if (!redirectHandled) {
    redirectHandled = handleRedirectCallback()
      .then((exchanged) => ({ exchanged }))
      .catch((e: Error) => ({ exchanged: false, error: e.message }));
  }
  return redirectHandled;
}

const REPEAT_TO_NUM: Record<PlaybackState["repeat_state"], number> = { off: 0, track: 1, context: 2 };
const NUM_TO_REPEAT: Record<number, PlaybackState["repeat_state"]> = { 0: "off", 1: "track", 2: "context" };

function toTrack(t: SpotifyTrack): Track {
  return {
    artist: t.artists.map((a) => a.name).join(", ") || "Unknown",
    title: t.name,
    seconds: Math.round(t.duration_ms / 1000),
  };
}

export function useSpotify() {
  const [status, setStatus] = useState<SpotifyStatus>(
    isConfigured() ? "disconnected" : "unconfigured",
  );
  const [error, setError] = useState<string | null>(null);
  const [playback, setPlayback] = useState<PlaybackState | undefined>(undefined);
  const [playlists, setPlaylists] = useState<SimplifiedPlaylist[]>([]);
  const [chosenPlaylistId, setChosenPlaylistId] = useState<string | null>(null);
  const [playlistTracksRaw, setPlaylistTracksRaw] = useState<SpotifyTrack[]>([]);
  const [playHere, setPlayHere] = useState(false);     // in-page SDK device toggle
  const [deviceName, setDeviceName] = useState<string | null>(null);

  const sdkRef = useRef<SdkHandle | null>(null);
  const sdkDeviceIdRef = useRef<string | null>(null);
  // local optimistic progress so the clock ticks smoothly between polls
  const localProgress = useRef<{ ms: number; at: number; playing: boolean }>({ ms: 0, at: Date.now(), playing: false });

  const connected = status === "connected" || status === "connecting";

  // ---- 1. handle the OAuth redirect on mount ------------------------------
  // Uses a module-level one-shot (handleRedirectOnce) so StrictMode's double
  // mount can't double-exchange the single-use `code` or lose the result.
  useEffect(() => {
    if (!isConfigured()) return;
    let cancelled = false;
    void (async () => {
      const { exchanged, error: redirErr } = await handleRedirectOnce();
      if (cancelled) return;
      if (redirErr) { setError(redirErr); setStatus("error"); return; }
      if (exchanged || hasTokens()) {
        const t = await getAccessToken(); // verify the token works
        if (!cancelled) setStatus(t ? "connecting" : "disconnected");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ---- 2. poll playback while connected -----------------------------------
  const refresh = useCallback(async () => {
    try {
      const pb = await api.getPlaybackState();
      setPlayback(pb);
      setDeviceName(pb?.device?.name ?? null);
      if (pb?.progress_ms != null) {
        localProgress.current = { ms: pb.progress_ms, at: Date.now(), playing: pb.is_playing };
      }
      setStatus("connected");
      setError(null);
    } catch (e) {
      if (e instanceof NoActiveDeviceError) {
        // linked but nothing is playing anywhere — still "connected", just idle
        setPlayback(undefined);
        setStatus("connected");
      } else {
        setError((e as Error).message);
      }
    }
  }, []);

  useEffect(() => {
    if (!connected) return;
    void refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [connected, refresh]);

  // ---- 3. load the user's playlists once linked ---------------------------
  useEffect(() => {
    if (status !== "connected") return;
    let live = true;
    void (async () => {
      try {
        const pls = await api.getMyPlaylists(40);
        if (!live) return;
        setPlaylists(pls);
        setChosenPlaylistId((cur) => cur ?? pls[0]?.id ?? null);
      } catch { /* non-fatal: playlist screen falls back to current track */ }
    })();
    return () => { live = false; };
  }, [status]);

  // ---- 4. load the chosen playlist's tracks -------------------------------
  useEffect(() => {
    if (!chosenPlaylistId) { setPlaylistTracksRaw([]); return; }
    let live = true;
    void (async () => {
      try {
        const ts = await api.getPlaylistTracks(chosenPlaylistId, 60);
        if (live) setPlaylistTracksRaw(ts);
      } catch { /* leave previous */ }
    })();
    return () => { live = false; };
  }, [chosenPlaylistId]);

  // ---- 5. "play here": init / tear down the in-page SDK device ------------
  useEffect(() => {
    if (status !== "connected") return;
    if (playHere && !sdkRef.current) {
      let live = true;
      void (async () => {
        try {
          const handle = await initWebPlaybackSDK("skeuo-ui", (kind, msg) => {
            setError(`${kind}: ${msg}`);
            // premium/account failures: drop back to active-device control
            if (kind === "account_error" || kind === "authentication_error") setPlayHere(false);
          });
          if (!live) { handle.disconnect(); return; }
          sdkRef.current = handle;
          sdkDeviceIdRef.current = handle.deviceId;
          // move playback onto this tab and start it
          await api.transferPlayback(handle.deviceId, true);
          void refresh();
        } catch (e) {
          setError((e as Error).message);
          setPlayHere(false); // graceful degrade to active device
        }
      })();
      return () => { live = false; };
    }
    if (!playHere && sdkRef.current) {
      sdkRef.current.disconnect();
      sdkRef.current = null;
      sdkDeviceIdRef.current = null;
    }
  }, [playHere, status, refresh]);

  useEffect(() => () => { sdkRef.current?.disconnect(); }, []);

  // ---- public actions -----------------------------------------------------
  const login = useCallback(() => {
    setStatus("connecting");
    if (isTauri()) {
      // Desktop: Spotify rejects custom-scheme redirects, so we open the system
      // browser and catch the code on a 127.0.0.1 loopback. Bind the listener
      // BEFORE opening the browser so the redirect can't beat us to it.
      void (async () => {
        try {
          const cb = awaitDesktopCallback();
          await beginLogin();
          const url = await cb;
          await handleRedirectCallback(url);
          const t = await getAccessToken();
          setStatus(t ? "connected" : "disconnected");
        } catch (e) { setError((e as Error).message); setStatus("error"); }
      })();
      return;
    }
    void beginLogin().catch((e) => { setError((e as Error).message); setStatus("error"); });
  }, []);

  const logout = useCallback(() => {
    sdkRef.current?.disconnect();
    sdkRef.current = null;
    clearTokens();
    setPlayback(undefined);
    setPlaylists([]);
    setPlayHere(false);
    setStatus(isConfigured() ? "disconnected" : "unconfigured");
  }, []);

  // optimistic wrapper: run the API call, then re-poll shortly after so the UI
  // catches up even if the call is slow (Spotify's state is eventually consistent).
  const act = useCallback((fn: () => Promise<unknown>) => {
    fn().catch((e) => setError((e as Error).message)).finally(() => {
      setTimeout(() => { void refresh(); }, 350);
    });
  }, [refresh]);

  // Spotify transport targets the user's ACTIVE device. If none is active
  // (Spotify open but idle, just launched, or only running elsewhere) the API
  // 404s and the button appears to "do nothing". This runs the action, and on a
  // no-device error finds an available device, transfers playback to it, and
  // retries — so the widget's play/skip work even when nothing's playing yet.
  const withDevice = useCallback(async (run: (deviceId?: string) => Promise<unknown>) => {
    try {
      await run();
    } catch (e) {
      if (!(e instanceof NoActiveDeviceError)) throw e;
      const devices = await api.getDevices();
      const dev = devices.find((d) => d.is_active && d.id) ?? devices.find((d) => d.id);
      if (!dev?.id) throw new Error("No Spotify device found — open Spotify on your phone or computer, then press play.");
      await api.transferPlayback(dev.id, false);
      await run(dev.id);
    }
  }, []);

  // ---- build the drive object consumed by usePlayer -----------------------
  const item = playback?.item ?? null;
  const playlistTracks = playlistTracksRaw.map(toTrack);
  // index of the playing track within the chosen playlist (so the list highlights)
  const trackIdx = item?.id
    ? playlistTracksRaw.findIndex((t) => t.id === item.id)
    : -1;

  // smooth elapsed between 3s polls
  const elapsedSec = (() => {
    const p = localProgress.current;
    const base = p.ms + (p.playing ? Date.now() - p.at : 0);
    return Math.max(0, Math.round(base / 1000));
  })();

  const drive: SpotifyDrive | null = status === "connected" ? {
    track: item ? toTrack(item) : { artist: "Spotify", title: deviceName ? "Ready — press play" : "No active device", seconds: 0 },
    tracks: playlistTracks.length ? playlistTracks : (item ? [toTrack(item)] : []),
    trackIdx,
    playing: !!playback?.is_playing,
    elapsedSec,
    durationSec: item ? Math.round(item.duration_ms / 1000) : 0,
    volume: (playback?.device?.volume_percent ?? 70) / 100,
    shuffle: !!playback?.shuffle_state,
    repeatMode: playback ? REPEAT_TO_NUM[playback.repeat_state] : 0,
    deviceName,
    play: () => act(() => withDevice((id) => api.play(id ? { deviceId: id } : undefined))),
    pause: () => act(() => api.pause()),
    next: () => act(() => withDevice((id) => api.next(id))),
    prev: () => act(() => withDevice((id) => api.previous(id))),
    seekTo: (frac) => {
      const dur = item?.duration_ms ?? 0;
      act(() => api.seek(frac * dur));
    },
    setVolume: (v) => act(() => api.setVolume(v * 100)),
    toggleShuffle: () => act(() => api.setShuffle(!playback?.shuffle_state)),
    cycleRepeat: () => {
      const cur = playback ? REPEAT_TO_NUM[playback.repeat_state] : 0;
      act(() => api.setRepeat(NUM_TO_REPEAT[(cur + 1) % 3]));
    },
    selectTrack: (i) => {
      const t = playlistTracksRaw[i];
      if (!t) return;
      // play from the chosen playlist context at this offset when possible,
      // transferring to a device first if none is active
      act(() => withDevice((id) => chosenPlaylistId
        ? api.play({ deviceId: id, contextUri: `spotify:playlist:${chosenPlaylistId}`, offset: i })
        : api.play({ deviceId: id, uris: [t.uri] })));
    },
  } : null;

  return {
    status, error, drive,
    deviceName,
    // UI controls
    login, logout,
    playHere, setPlayHere,
    playlists, chosenPlaylistId, setChosenPlaylistId,
    isConfigured: isConfigured(),
  };
}

export type SpotifyHook = ReturnType<typeof useSpotify>;
