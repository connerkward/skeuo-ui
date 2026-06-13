// Typed Spotify Web API client — every call shape the player needs.
//
// All requests go to https://api.spotify.com/v1 with a Bearer token from auth.ts.
// Transport mutations (play/pause/next/prev/seek/volume) target the user's ACTIVE
// device unless a device_id is supplied (used when we transfer to the in-page
// Web Playback SDK device). The 204 No-Content responses (typical for player
// mutations) are handled — we don't try to parse an empty body as JSON.

import { getAccessToken } from "./auth";

const BASE = "https://api.spotify.com/v1";

export class NoActiveDeviceError extends Error {
  constructor() {
    super("No active Spotify device");
    this.name = "NoActiveDeviceError";
  }
}

async function call<T>(
  path: string,
  init: RequestInit = {},
  parse = true,
): Promise<T> {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated with Spotify");
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  // 404 from a player mutation = "Device not found" / no active device
  if (res.status === 404) throw new NoActiveDeviceError();
  if (res.status === 204) return undefined as T; // No Content (idle / no playback)
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Spotify API ${res.status} ${path}: ${text}`);
  }
  if (!parse) return undefined as T;
  // some endpoints (e.g. /me/player when nothing is playing) return 204 above;
  // here we have a body
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) return undefined as T;
  return (await res.json()) as T;
}

// ---- types (only the fields we consume) -----------------------------------
export interface SpotifyImage { url: string; width: number | null; height: number | null }
export interface SpotifyArtist { name: string; id: string }
export interface SpotifyTrack {
  id: string | null;
  uri: string;
  name: string;
  duration_ms: number;
  artists: SpotifyArtist[];
  album: { name: string; images: SpotifyImage[] };
}
export interface SpotifyDevice {
  id: string | null;
  is_active: boolean;
  name: string;
  type: string;
  volume_percent: number | null;
}
export interface PlaybackState {
  device: SpotifyDevice | null;
  is_playing: boolean;
  progress_ms: number | null;
  shuffle_state: boolean;
  repeat_state: "off" | "track" | "context";
  item: SpotifyTrack | null;
}
export interface SimplifiedPlaylist {
  id: string;
  name: string;
  tracks: { total: number };
  images: SpotifyImage[];
}
export interface PlaylistTrackItem { track: SpotifyTrack | null }

export interface MeProfile { id: string; display_name: string | null; product: string }

// ---- reads ----------------------------------------------------------------
export function getMe(): Promise<MeProfile> {
  return call<MeProfile>("/me");
}

// Returns undefined when there is no active playback (Spotify sends 204).
export async function getPlaybackState(): Promise<PlaybackState | undefined> {
  return call<PlaybackState | undefined>("/me/player");
}

export async function getMyPlaylists(limit = 30): Promise<SimplifiedPlaylist[]> {
  const r = await call<{ items: SimplifiedPlaylist[] }>(`/me/playlists?limit=${limit}`);
  return r?.items ?? [];
}

export async function getPlaylistTracks(playlistId: string, limit = 50): Promise<SpotifyTrack[]> {
  const fields = "items(track(id,uri,name,duration_ms,artists(name,id),album(name,images)))";
  const r = await call<{ items: PlaylistTrackItem[] }>(
    `/playlists/${playlistId}/tracks?limit=${limit}&fields=${encodeURIComponent(fields)}`,
  );
  return (r?.items ?? []).map((i) => i.track).filter((t): t is SpotifyTrack => !!t);
}

export async function getDevices(): Promise<SpotifyDevice[]> {
  const r = await call<{ devices: SpotifyDevice[] }>("/me/player/devices");
  return r?.devices ?? [];
}

// ---- transport mutations --------------------------------------------------
// device_id is optional; omit to target the current active device.
const dq = (deviceId?: string) => (deviceId ? `?device_id=${deviceId}` : "");

export function play(opts?: { deviceId?: string; uris?: string[]; contextUri?: string; positionMs?: number; offset?: number }): Promise<void> {
  const body: Record<string, unknown> = {};
  if (opts?.uris) body.uris = opts.uris;
  if (opts?.contextUri) body.context_uri = opts.contextUri;
  if (opts?.offset !== undefined) body.offset = { position: opts.offset };
  if (opts?.positionMs !== undefined) body.position_ms = opts.positionMs;
  return call<void>(`/me/player/play${dq(opts?.deviceId)}`, {
    method: "PUT",
    body: Object.keys(body).length ? JSON.stringify(body) : undefined,
  }, false);
}

export function pause(deviceId?: string): Promise<void> {
  return call<void>(`/me/player/pause${dq(deviceId)}`, { method: "PUT" }, false);
}
export function next(deviceId?: string): Promise<void> {
  return call<void>(`/me/player/next${dq(deviceId)}`, { method: "POST" }, false);
}
export function previous(deviceId?: string): Promise<void> {
  return call<void>(`/me/player/previous${dq(deviceId)}`, { method: "POST" }, false);
}
export function seek(positionMs: number, deviceId?: string): Promise<void> {
  return call<void>(`/me/player/seek?position_ms=${Math.round(positionMs)}${deviceId ? `&device_id=${deviceId}` : ""}`, { method: "PUT" }, false);
}
// volumePercent 0..100
export function setVolume(volumePercent: number, deviceId?: string): Promise<void> {
  const v = Math.max(0, Math.min(100, Math.round(volumePercent)));
  return call<void>(`/me/player/volume?volume_percent=${v}${deviceId ? `&device_id=${deviceId}` : ""}`, { method: "PUT" }, false);
}
export function setShuffle(state: boolean, deviceId?: string): Promise<void> {
  return call<void>(`/me/player/shuffle?state=${state}${deviceId ? `&device_id=${deviceId}` : ""}`, { method: "PUT" }, false);
}
export function setRepeat(state: "off" | "track" | "context", deviceId?: string): Promise<void> {
  return call<void>(`/me/player/repeat?state=${state}${deviceId ? `&device_id=${deviceId}` : ""}`, { method: "PUT" }, false);
}

// Move playback onto a device (our in-page SDK device). play=true to start there.
export function transferPlayback(deviceId: string, play: boolean): Promise<void> {
  return call<void>("/me/player", {
    method: "PUT",
    body: JSON.stringify({ device_ids: [deviceId], play }),
  }, false);
}
