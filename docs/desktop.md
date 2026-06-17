# Desktop widget (macOS, Tauri)

> Deep-dive companion to the [README](../README.md). The same React bundle is also
> a transparent, non-rectangular desktop music widget — a floating "desktop toy"
> whose shape is the skin's own silhouette (the frame PNG's alpha over a transparent
> window), driving the user's real Spotify (active-device control via the Web API).
> Pick a skin on the website, hit **Open in desktop player**, and it launches already
> wearing that skin.

## Build & run

```bash
npm run tauri:dev       # run the widget locally (hot-reloads the webview)
npm run tauri:build     # unsigned/ad-hoc .app + .dmg (local use)
scripts/build-desktop.sh   # signed + notarized .dmg for distribution
```

## How it works

- **One bundle, two modes.** `src/platform.ts#isWidget()` is true under Tauri (or
  `?widget=1`); `src/main.tsx` then mounts `src/widget/WidgetApp.tsx` (a single
  `<Composite>` on a transparent background) instead of the website. The skin CSS is
  shared via `src/skins/all.ts` so the player renders identically in both.
- **Transparent shaped window.** `tauri.conf.json` sets `transparent` +
  `macOSPrivateApi`, `decorations:false`, `shadow:false`, `alwaysOnTop`; the widget
  fills it at the frame's 2:3 aspect, so only the skin paints. Grabbing a non-control
  area drags the OS window (`startDragging`, called synchronously).
- **Menu-bar tray** (`src-tauri/src/lib.rs`): switch skin, toggle always-on-top,
  show/hide, quit. Closing the window hides it to the tray.
- **web → desktop handoff.** The site navigates to `skeuo://skin/<id>`; the Tauri
  deep-link plugin (`src/desktop/deeplink.ts`) catches it and switches the skin
  (single-instance forwards it to a running widget). The macOS scheme is registered
  from the bundled app's Info.plist — deep links work from the built `.app`, not
  `tauri dev`.
- **Spotify on desktop.** Reuses `src/spotify/*` unchanged; only the OAuth edges
  differ (`src/platform.ts`): the widget opens `/authorize` in the system browser
  and catches the return on a one-shot **`127.0.0.1:14565` loopback** listener
  (`oauth_loopback` in `src-tauri/src/lib.rs`) — Spotify rejects custom-scheme
  (`skeuo://`) redirects, so loopback is the native-app path (same PKCE, no secret).
  The browser-only Web Playback SDK ("play here") is disabled — desktop controls the
  active device. Register `http://127.0.0.1:14565/callback` as a redirect URI in the
  dashboard alongside the web origins. (`skeuo://` is still used for the skin
  handoff — just not for OAuth.)
