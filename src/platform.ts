// Platform abstraction — the SAME React bundle runs as the website and inside
// the Tauri desktop widget. A handful of behaviors differ between the two
// (where OAuth redirects to, how an external URL is opened, whether we're a
// floating widget or the full site). Everything that branches on web-vs-Tauri
// lives here so the rest of the app stays platform-agnostic.

// Tauri v2 injects this global into the webview before any app code runs.
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

// iOS app = running under Tauri on an iOS device. The WKWebView UA still carries
// "iPhone"/"iPad"/"iPod" (the macOS shell reports "Macintosh"), so a UA split
// distinguishes the mobile shell from the desktop one with no extra plugin.
// Outside Tauri this is always false — the website in mobile Safari stays the
// plain responsive site, never claiming to be the native app.
export function isMobileApp(): boolean {
  if (!isTauri() || typeof navigator === "undefined") return false;
  return /iPhone|iPad|iPod/i.test(navigator.userAgent);
}

// Widget mode = the transparent floating DESKTOP toy: Tauri on macOS, OR the
// website opened with ?widget=1 (to preview the widget chrome in a browser).
// The iOS app is NOT a widget — it renders the full site full-screen — so the
// mobile shell is explicitly excluded here.
export function isWidget(): boolean {
  if (isTauri()) return !isMobileApp();
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("widget") === "1";
}

// Skin requested at launch: Tauri passes it via the deep link (handled in
// desktop/deeplink.ts), but a ?skin=<id> query also works for browser preview.
export function initialSkinParam(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("skin");
}

// API origin for the backend (Cloudflare Pages Functions). The native shells
// (macOS widget + iOS app) bundle the frontend and serve it from a non-HTTP
// origin (tauri://localhost), so a RELATIVE "/api/…" never reaches the backend —
// the same reason redirectUri() uses an absolute OAuth URL on native. So under
// Tauri we point API calls at the deployed origin; on the web they stay relative
// (same-origin). Pass through anything already absolute (http(s)/data/blob).
export const API_ORIGIN = "https://skeuo.fm";
export function apiUrl(path: string): string {
  if (/^(https?:|data:|blob:)/.test(path)) return path;
  return isTauri() ? API_ORIGIN + path : path;
}

// OAuth redirect target — three cases, because the return path differs per shell:
//
// • Web → the site's own origin. Spotify reloads it with ?code and the SPA
//   exchanges it.
// • macOS widget → a LOOPBACK (http://127.0.0.1:14565) caught by a one-shot
//   listener in Rust. Works on desktop because the system browser and the app
//   coexist — the app stays alive to answer the loopback.
// • iOS → an HTTPS bounce page (skeuo.fm/callback.html) that forwards the code to
//   the app's skeuo:// scheme. A loopback is UNREACHABLE on iOS: opening Safari
//   backgrounds the app and iOS suspends it, killing the listener — so the
//   127.0.0.1 redirect hangs forever. The HTTPS→deep-link bounce re-foregrounds
//   the app with the code instead. Custom schemes can't be sent to Spotify
//   directly (its authorize endpoint only accepts https/loopback redirect URIs),
//   hence the HTTPS hop first.
//
// Spotify requires an EXACT match between the authorize and token-exchange
// redirect_uri AND the dashboard entry, so each constant must be registered there
// verbatim. Keep NATIVE_REDIRECT's port in sync with oauth_loopback() in lib.rs.
export const NATIVE_REDIRECT = "http://127.0.0.1:14565/callback";
// Clean URL (Cloudflare Pages serves public/callback.html here; the .html form
// just 308s to this). Register this EXACT string in the Spotify dashboard.
export const MOBILE_REDIRECT = "https://skeuo.fm/callback";
export function redirectUri(): string {
  if (isMobileApp()) return MOBILE_REDIRECT;
  if (isTauri()) return NATIVE_REDIRECT;
  return window.location.origin + "/";
}

// Native (desktop + iOS): start the loopback listener and resolve with the full
// callback URL (http://127.0.0.1:14565/callback?code=...) once the system browser
// redirects to it. Bind BEFORE opening the browser so the redirect isn't missed.
export async function awaitDesktopCallback(): Promise<string> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<string>("oauth_loopback");
}

// Open an external URL. On the web we just navigate the page to Spotify's
// /authorize. Inside Tauri the webview is embedded and Spotify won't authorize
// there, so we hand the URL to the system default browser; Spotify then
// redirects back to skeuo://callback which the OS routes to the app.
export async function openAuthorizeUrl(url: string): Promise<void> {
  if (isTauri()) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
    return;
  }
  window.location.assign(url);
}
