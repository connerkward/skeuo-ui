// Spotify OAuth — Authorization Code with PKCE (SPA-safe, NO client secret).
//
// Why PKCE: a single-page app cannot keep a client secret, so the classic
// Authorization Code flow is unsafe here. PKCE replaces the secret with a
// per-login random `code_verifier`: we send only its SHA-256 hash (the
// `code_challenge`) to the /authorize endpoint, then prove possession of the
// verifier at the /api/token exchange. Nothing secret is ever shipped in the
// bundle. This is Spotify's recommended browser flow.
//
// Tokens live in localStorage with a stored expiry; `getAccessToken()` refreshes
// silently (using the refresh_token, also via the token endpoint with PKCE — no
// secret) when it's within a minute of expiring.

import { redirectUri as platformRedirectUri, openAuthorizeUrl, isTauri } from "../platform";

const AUTHORIZE = "https://accounts.spotify.com/authorize";
const TOKEN = "https://accounts.spotify.com/api/token";

// Scopes: playback read+modify, currently-playing, the Web Playback SDK
// ("streaming"), and reading the user's private playlists for the playlist screen.
export const SCOPES = [
  "user-read-playback-state",
  "user-modify-playback-state",
  "user-read-currently-playing",
  "streaming",
  "playlist-read-private",
].join(" ");

const LS = {
  access: "sp_access_token",
  refresh: "sp_refresh_token",
  expires: "sp_expires_at", // epoch ms
  verifier: "sp_pkce_verifier",
};

export const CLIENT_ID: string = import.meta.env.VITE_SPOTIFY_CLIENT_ID ?? "";

// Spotify requires an EXACT redirect-URI match and (since 2024) rejects
// `localhost` — it wants `127.0.0.1` in dev. Web uses the current origin + "/";
// the desktop widget uses the custom scheme `skeuo://callback`. Both must be
// registered in the dashboard. See src/platform.ts.
export function redirectUri(): string {
  return platformRedirectUri();
}

// ---- PKCE helpers ---------------------------------------------------------
function randomString(len: number): string {
  const bytes = new Uint8Array(len);
  crypto.getRandomValues(bytes);
  // base64url alphabet, no padding
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

async function sha256(input: string): Promise<ArrayBuffer> {
  return crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
}

function base64url(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// ---- public state ---------------------------------------------------------
export function isConfigured(): boolean {
  return CLIENT_ID.length > 0;
}

export function hasTokens(): boolean {
  return !!localStorage.getItem(LS.refresh) || !!localStorage.getItem(LS.access);
}

export function clearTokens(): void {
  Object.values(LS).forEach((k) => localStorage.removeItem(k));
}

// ---- step 1: kick off login (redirects the page away) ---------------------
export async function beginLogin(): Promise<void> {
  if (!isConfigured()) throw new Error("VITE_SPOTIFY_CLIENT_ID is not set");
  const verifier = randomString(64);
  localStorage.setItem(LS.verifier, verifier);
  const challenge = base64url(await sha256(verifier));
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: "code",
    redirect_uri: redirectUri(),
    code_challenge_method: "S256",
    code_challenge: challenge,
    scope: SCOPES,
  });
  // NATIVE (iOS/desktop) opens the SYSTEM browser, which may already hold a
  // Spotify session for a DIFFERENT account than the one the user expects — and
  // Spotify silently consents as that session, so the app gets a token for the
  // wrong account (→ Web API 403 "User not registered" in dev mode even though
  // the *intended* account is allowlisted). `show_dialog=true` forces the account
  // / consent chooser so the user sees and picks the right account. The website
  // works without it (its browser session IS the user's), so web stays untouched.
  if (isTauri()) params.set("show_dialog", "true");
  // Web: navigate the page to /authorize. Tauri: open the system browser, since
  // Spotify won't authorize inside an embedded webview (the callback returns via
  // the skeuo:// deep link). openAuthorizeUrl branches on platform.
  await openAuthorizeUrl(`${AUTHORIZE}?${params.toString()}`);
}

// ---- step 2: handle the redirect back (?code=...) -------------------------
// Returns true if a code was present and exchanged. `href` lets the desktop
// deep-link handler pass the skeuo://callback?code=... URL explicitly; on the
// web it defaults to the address bar (and we strip the query after exchange).
export async function handleRedirectCallback(href?: string): Promise<boolean> {
  const url = new URL(href ?? window.location.href);
  const code = url.searchParams.get("code");
  const err = url.searchParams.get("error");
  if (err) {
    // user denied or config error — clean the URL (web only) and surface it
    if (!isTauri()) window.history.replaceState({}, "", redirectUri());
    throw new Error(`Spotify auth error: ${err}`);
  }
  if (!code) return false;
  const verifier = localStorage.getItem(LS.verifier);
  if (!verifier) throw new Error("Missing PKCE verifier (login was not started here)");

  const body = new URLSearchParams({
    client_id: CLIENT_ID,
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri(),
    code_verifier: verifier,
  });
  const res = await fetch(TOKEN, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error(`Token exchange failed: ${res.status} ${await res.text()}`);
  const data = (await res.json()) as TokenResponse;
  storeTokens(data);
  localStorage.removeItem(LS.verifier);
  // remove ?code=... from the address bar so a refresh doesn't re-exchange
  // (web only — in Tauri the code arrived via the deep link, not the URL bar,
  // and redirectUri() is the skeuo:// scheme which can't be a history entry)
  if (!isTauri()) window.history.replaceState({}, "", redirectUri());
  return true;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number; // seconds
  refresh_token?: string; // present on initial exchange; may be omitted on refresh
  scope?: string;
}

function storeTokens(t: TokenResponse): void {
  localStorage.setItem(LS.access, t.access_token);
  localStorage.setItem(LS.expires, String(Date.now() + t.expires_in * 1000));
  if (t.refresh_token) localStorage.setItem(LS.refresh, t.refresh_token);
}

// ---- step 3: get a fresh access token (silent refresh) --------------------
let refreshing: Promise<string | null> | null = null;

export async function getAccessToken(): Promise<string | null> {
  const access = localStorage.getItem(LS.access);
  const expires = Number(localStorage.getItem(LS.expires) ?? 0);
  // valid with >60s of headroom
  if (access && Date.now() < expires - 60_000) return access;

  const refresh = localStorage.getItem(LS.refresh);
  if (!refresh) return access && Date.now() < expires ? access : null;

  // de-dupe concurrent refreshes (poller + SDK both ask at once)
  if (refreshing) return refreshing;
  refreshing = (async () => {
    try {
      const body = new URLSearchParams({
        client_id: CLIENT_ID,
        grant_type: "refresh_token",
        refresh_token: refresh,
      });
      const res = await fetch(TOKEN, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!res.ok) {
        // refresh token revoked/expired — force re-login
        clearTokens();
        return null;
      }
      const data = (await res.json()) as TokenResponse;
      storeTokens(data);
      return data.access_token;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}
