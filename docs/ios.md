# iOS app (Tauri)

> Deep-dive companion to the [README](../README.md). The same React bundle that
> is the website and the macOS widget is also a **full-screen iOS app** — the
> skin fills the screen, you swipe between skins, and one tap connects Spotify
> for real playback. It is NOT the transparent desktop widget; on iOS the app
> renders the full site, mobile-shell layout.

## Build & run

```bash
npm run tauri:ios:dev                       # run on a booted Simulator with HMR
npm run tauri:ios:build -- --debug --target aarch64-sim   # build a Simulator .app
npm run tauri:ios:build                     # device build (.ipa, needs signing)
```

First-time setup (regenerates the gitignored Xcode project under
`src-tauri/gen/apple/`):

```bash
rustup target add aarch64-apple-ios aarch64-apple-ios-sim x86_64-apple-ios
npm run tauri -- ios init
```

Install/launch a Simulator build by hand (what CI / verification does):

```bash
xcrun simctl boot "iPhone 16 Pro"
xcrun simctl install booted "$(find ~/Library/Developer/Xcode/DerivedData/skeuo-* \
  -name Skeuo.app -path '*iphonesimulator*' | head -1)"
xcrun simctl launch booted run.ward.skeuo
```

> Dev-mode note: `tauri ios dev` drives the build through Xcode, whose "Build
> Rust Code" phase connects back to the CLI over a localhost WebSocket. If that
> connection is refused (`mobile/mod.rs:403 … Connection refused`), use
> `tauri ios build --debug --target aarch64-sim` instead — it builds against the
> static `dist/` and skips the dev-server socket entirely.

## One bundle, the right mode

`src/platform.ts` decides what to render. The iOS WKWebView UA still carries
`iPhone`/`iPad` (the macOS shell reports `Macintosh`), so:

- `isMobileApp()` → true only under Tauri **on iOS**.
- `isWidget()` → `isTauri() && !isMobileApp()` — i.e. **desktop Tauri only**. So
  `main.tsx` mounts the full `<App/>` on iOS (not the transparent `WidgetApp`),
  and `App.tsx` forces the mobile swipe shell regardless of viewport.

The result is the website's mobile experience, running natively full-screen: the
swipeable skin carriage, the live player (spectrum / marquee / clock), the
create-a-skin flow — all shared code, zero fork.

## Spotify — easy connect, loopback OAuth

Audio plays through the user's **active Spotify device** (their phone's Spotify
app or any Connect target) via the Web API — the in-page Web Playback SDK ("play
here") is hidden on iOS because the WKWebView has no EME/Widevine.

Connecting is a single tap. The top bar carries a green **Connect Spotify** pill
(`src/mobile/MobileSpotify.tsx`):

- not linked → tap calls `login()` directly (no menu in the way);
- linked → tap opens a bottom sheet (mode · playlist · disconnect), reusing the
  same `<SpotifyConnect/>` body the desktop sidebar uses.

The OAuth flow is the **loopback** path shared with the desktop widget
(`useSpotify.login()` → `oauth_loopback` in `src-tauri/src/lib.rs`):

1. App binds a one-shot `http://127.0.0.1:14565/callback` listener (Rust).
2. `openUrl` opens the **system browser** (Safari) at Spotify `/authorize` (PKCE,
   no secret).
3. Spotify redirects Safari to the loopback URL; the listener captures `?code=…`.
4. The reply page **bounces to `skeuo://connected`** — the app's own scheme (which
   Spotify never sees) — so iOS pulls focus back to Skeuo. The PKCE exchange runs
   in the app and the pill flips to linked.

### Why loopback, not a custom scheme

Spotify's redirect rules permit only **HTTPS** and **loopback**
(`http://127.0.0.1:PORT`); custom schemes like `skeuo://callback` are not in the
sanctioned list and have hit `INVALID_CLIENT: Insecure redirect URI` regressions
for PKCE apps since 2025. Loopback is the one type the docs guarantee for native
apps, so both shells use it. `skeuo://` is still registered on iOS (deep-link
`mobile` config → `CFBundleURLTypes`) — but only as the return-to-app bounce,
never as the redirect Spotify validates.

**Dashboard:** register `http://127.0.0.1:14565/callback` as a redirect URI
alongside the web origins, and set `VITE_SPOTIFY_CLIENT_ID`.

## Desktop vs iOS — what's gated

`src-tauri/src/lib.rs` and `Cargo.toml` keep the desktop-only pieces behind
`#[cfg(desktop)]` / a `cfg(not(ios/android))` dependency target: the menu-bar
**tray** (the `tray-icon` crate doesn't build for iOS), **window-state**
persistence, **single-instance** forwarding, and hide-to-tray. The
`window-state` *permission* likewise lives in a desktop-scoped capability
(`capabilities/desktop.json`, `"platforms": ["macOS","windows","linux"]`) so the
iOS build doesn't require a permission whose plugin isn't compiled in. Shared on
both: the deep-link + opener plugins and the `oauth_loopback` command.

## Known caveats (real device)

- **Signing/provisioning.** Simulator builds need no team. A device `.ipa` needs
  the App ID `run.ward.skeuo` registered and a provisioning profile under the
  Apple Developer account (team `N4YGB5B92K`). Not yet wired — Simulator is the
  verified target so far.
- **Loopback + app suspension.** When the app opens Safari for OAuth it gets
  backgrounded; iOS suspends it after ~30 s, which would freeze the loopback
  listener. The redirect normally lands within that window (Spotify redirects
  immediately once authorized), but a slow first-time consent could miss it. If
  it proves flaky on device, the fix is a native `ASWebAuthenticationSession`
  plugin (keeps auth in-process, no suspension) — a follow-up.
