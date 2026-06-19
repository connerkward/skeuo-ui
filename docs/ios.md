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

## Spotify — easy connect (iOS: HTTPS bounce → deep link)

Audio plays through the user's **active Spotify device** (their phone's Spotify
app or any Connect target) via the Web API — the in-page Web Playback SDK ("play
here") is hidden on iOS because the WKWebView has no EME/Widevine.

Connecting is a single tap. The top bar carries a green **Connect Spotify** pill
(`src/mobile/MobileSpotify.tsx`):

- not linked → tap calls `login()` directly (no menu in the way);
- linked → tap opens a bottom sheet (mode · playlist · disconnect), reusing the
  same `<SpotifyConnect/>` body the desktop sidebar uses.

The OAuth return path **differs per shell** (`src/platform.ts` `redirectUri()`):

- **iOS** redirects to an **HTTPS bounce page** (`https://skeuo.fm/callback`,
  served from `public/callback.html`):
  1. `login()` opens Safari at Spotify `/authorize` (PKCE), `redirect_uri =
     https://skeuo.fm/callback`.
  2. Spotify redirects Safari to that page; it immediately forwards the whole
     query to **`skeuo://callback?code=…`** (the app's own scheme).
  3. iOS routes the deep link to the app, re-foregrounding it; the deep-link
     effect in `useSpotify` runs the PKCE exchange and the pill flips to linked.
- **macOS widget** keeps the **loopback** path (`oauth_loopback` in `lib.rs`,
  `http://127.0.0.1:14565/callback`) — see below.

### Why iOS can't use the loopback (the bug this fixed)

The desktop loopback works because the system browser and the app **coexist** —
the app stays alive to answer the `127.0.0.1` listener. On **iOS this is broken**:
opening Safari backgrounds the app and iOS **suspends** it, freezing the listener,
so after the user taps *Agree* the redirect hits a dead socket and **Safari hangs
forever** (confirmed on a real device, 2026-06-18). The Simulator masks it — it
doesn't suspend aggressively, so the loopback "worked" there.

The bounce avoids any backgrounded socket: Spotify only ever talks to an HTTPS URL
(which its rules require — custom schemes like `skeuo://` are rejected by the
authorize endpoint), and the app is **re-launched/foregrounded** by the deep link
with the code in hand.

**Dashboard:** register **all three** redirect URIs and set
`VITE_SPOTIFY_CLIENT_ID`:
- `https://skeuo.fm/callback` — iOS (HTTPS bounce)
- `http://127.0.0.1:14565/callback` — macOS widget (loopback)
- `https://skeuo.fm/` — web

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
- **Loopback + app suspension (RESOLVED).** The loopback OAuth return hung on a
  real device (app suspended behind Safari → dead listener). Fixed by the HTTPS
  bounce above; iOS no longer uses the loopback. Desktop still does.

## Rebuilding for TestFlight

`tauri ios build` derives the bundle version from **`tauri.conf.json` `version`**
(it overwrites the iOS Info.plist at build) — so bump the version *there*, not in
`gen/apple`, for a new TestFlight build number (App Store Connect rejects a
duplicate). `gen/apple/` is **gitignored** (regenerated by `tauri ios init`), so
two local fixes there must be **reapplied after any re-init** (then
`xcodegen generate --spec project.yml`):

1. **`project.yml` → `sources: - path: Externals` gets `buildPhase: none`.**
   Otherwise xcodegen sweeps the Rust static lib `libapp.a` into a `CpResource`
   phase — it's already *linked* via the `framework: libapp.a` dependency, so the
   copy is a duplicate that **fails the archive** and gets **rejected on upload
   (90171: static lib not permitted in bundle)**. `buildPhase: none` = linked,
   never copied. (No more manual `rm libapp.a` after archiving.)
2. **`project.yml` → `info.properties: ITSAppUsesNonExemptEncryption: false`** —
   skips the manual export-compliance prompt in App Store Connect each build.

Pipeline: `tauri ios build --export-method app-store-connect --archive-only` →
`xcodebuild -exportArchive … -exportOptionsPlist /tmp/skeuo-export-options.plist`
→ `xcrun altool --upload-app -f Skeuo.ipa -t ios -u "$APPLE_ID" -p @env:APPLE_PASSWORD`
(creds in gitignored `.env`). Internal testers with auto-distribution get it once
processing finishes.
