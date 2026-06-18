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

// OAuth redirect target. The website registers its own origin with Spotify; both
// native shells (macOS widget AND iOS app) use a LOOPBACK redirect — a one-shot
// 127.0.0.1 listener in Rust captures the code. Loopback (http://127.0.0.1) is
// the one redirect type Spotify's docs guarantee for native apps (custom schemes
// like skeuo:// hit an INVALID_CLIENT "insecure redirect URI" regression for some
// PKCE apps post-2025, so we avoid them). Spotify requires an EXACT match for
// whatever we send, so this must match the dashboard exactly. Keep the port in
// sync with oauth_loopback() in lib.rs.
export const NATIVE_REDIRECT = "http://127.0.0.1:14565/callback";
export function redirectUri(): string {
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
