// Platform abstraction — the SAME React bundle runs as the website and inside
// the Tauri desktop widget. A handful of behaviors differ between the two
// (where OAuth redirects to, how an external URL is opened, whether we're a
// floating widget or the full site). Everything that branches on web-vs-Tauri
// lives here so the rest of the app stays platform-agnostic.

// Tauri v2 injects this global into the webview before any app code runs.
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

// Widget mode = running under Tauri, OR the website opened with ?widget=1
// (handy for previewing the widget chrome in a normal browser tab).
export function isWidget(): boolean {
  if (isTauri()) return true;
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("widget") === "1";
}

// Skin requested at launch: Tauri passes it via the deep link (handled in
// desktop/deeplink.ts), but a ?skin=<id> query also works for browser preview.
export function initialSkinParam(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("skin");
}

// OAuth redirect target. The website registers its own origin with Spotify; the
// desktop app registers the custom scheme and catches the callback via the
// deep-link plugin. Spotify requires an EXACT match for whichever we send.
export function redirectUri(): string {
  if (isTauri()) return "skeuo://callback";
  return window.location.origin + "/";
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
