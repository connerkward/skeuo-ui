// Web Playback SDK loader — turns THIS page into a Spotify Connect device so
// audio can play in the browser tab itself (Premium-only). We load the script
// on demand, create a Spotify.Player wired to our OAuth token, and resolve with
// the device_id once it's ready. Callers gate this behind a "play here" toggle
// and fall back to controlling the user's existing active device when the SDK
// errors out (no Premium, autoplay blocked, etc.).

import { getAccessToken } from "./auth";

// Minimal typings for the parts of the global SDK we touch (no @types dep).
interface SpotifyPlayer {
  connect(): Promise<boolean>;
  disconnect(): void;
  addListener(event: string, cb: (arg: unknown) => void): boolean;
  removeListener(event: string): boolean;
  activateElement?(): Promise<void>;
}
interface SpotifyNamespace {
  Player: new (opts: {
    name: string;
    getOAuthToken: (cb: (token: string) => void) => void;
    volume?: number;
  }) => SpotifyPlayer;
}
declare global {
  interface Window {
    Spotify?: SpotifyNamespace;
    onSpotifyWebPlaybackSDKReady?: () => void;
  }
}

const SDK_SRC = "https://sdk.scdn.co/spotify-player.js";
let sdkReady: Promise<void> | null = null;

function loadSdkScript(): Promise<void> {
  if (window.Spotify) return Promise.resolve();
  if (sdkReady) return sdkReady;
  sdkReady = new Promise<void>((resolve, reject) => {
    // The SDK calls this global when its script finishes initializing.
    window.onSpotifyWebPlaybackSDKReady = () => resolve();
    const el = document.createElement("script");
    el.src = SDK_SRC;
    el.async = true;
    el.onerror = () => reject(new Error("Failed to load Spotify Web Playback SDK"));
    document.head.appendChild(el);
  });
  return sdkReady;
}

export interface SdkHandle {
  player: SpotifyPlayer;
  deviceId: string;
  disconnect: () => void;
}

// Creates and connects the in-page player. Resolves once it's ready with a
// device_id. Rejects on init/account/authentication errors so the caller can
// fall back to active-device control.
export async function initWebPlaybackSDK(
  name = "skeuo-ui",
  onError?: (kind: string, message: string) => void,
): Promise<SdkHandle> {
  await loadSdkScript();
  const Spotify = window.Spotify;
  if (!Spotify) throw new Error("Spotify SDK namespace missing after load");

  const player = new Spotify.Player({
    name,
    volume: 0.7,
    getOAuthToken: (cb) => {
      // SDK asks for a token now and on every refresh — always hand it a fresh one.
      void getAccessToken().then((t) => { if (t) cb(t); });
    },
  });

  // surface the SDK's error channels (premium gate, auth, playback) to the UI
  for (const kind of ["initialization_error", "authentication_error", "account_error", "playback_error"]) {
    player.addListener(kind, (e) => onError?.(kind, (e as { message?: string })?.message ?? kind));
  }

  const deviceId = await new Promise<string>((resolve, reject) => {
    player.addListener("ready", (e) => resolve((e as { device_id: string }).device_id));
    player.addListener("not_ready", () => {/* device went offline; ignore here */});
    player.addListener("initialization_error", (e) => reject(new Error((e as { message?: string })?.message ?? "init error")));
    player.addListener("authentication_error", (e) => reject(new Error((e as { message?: string })?.message ?? "auth error")));
    player.addListener("account_error", () => reject(new Error("Spotify Premium is required to play in the browser")));
    player.connect().then((ok) => { if (!ok) reject(new Error("SDK player failed to connect")); });
  });

  return {
    player,
    deviceId,
    disconnect: () => { try { player.disconnect(); } catch { /* noop */ } },
  };
}
