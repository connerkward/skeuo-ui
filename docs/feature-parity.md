# Feature parity across platforms

A maintainer's reference: every feature and design decision in skeuo-ui, where it
lives, which platform it runs on, and where the parity gaps are.

- **Repo:** `/Users/conner/dev/skeuo-ui` · branch `main` · app version `0.1.6`
  (`src-tauri/tauri.conf.json`)
- **Generated:** 2026-06-25. This doc reflects the **code on `main`**, which can
  diverge from the prose docs in `docs/*.md` — see [Doc drift](#doc-drift) for the
  specific places the older docs describe a superseded design.

---

## 0. The platforms

One React bundle (`src/main.tsx`) renders as four shells. Everything that branches
on platform funnels through **`src/platform.ts`** — that file is the single gating
point for the whole app.

| Shell | What it is | Detection | Entry mount |
|---|---|---|---|
| **Web** (skeuo.fm) | Full site: desktop left-rail gallery + stage, OR responsive mobile swipe shell ≤820px | `!isTauri()` | `App` (`src/main.tsx:37`) |
| **iOS app** | Tauri WKWebView, full-screen native player + swipe carriage (NOT a widget) | `isMobileApp()` = `isTauri() && /iPhone\|iPad\|iPod/.test(UA)` | `App` → forced mobile shell (`App.tsx:161-169`) |
| **macOS desktop widget** | Tauri transparent floating single-skin player | `isWidget()` = `isTauri() && !isMobileApp()` | `WidgetApp` (`src/main.tsx:32-35`) |
| **Share page** | Server-hydrated single skin at `/share?id=<id>` | separate Vite entry | `ShareApp` (`src/share/main.tsx`) |

Notes:
- **`?widget=1`** on the web also triggers `isWidget()` (browser preview of widget
  chrome) — `platform.ts:26-30`.
- **Responsive web mobile shell (≤820px)** is the *same* `MobileChrome` carriage the
  native iOS shell uses — but in a browser, not the native app. `isMobileApp()` stays
  `false` in mobile Safari (`platform.ts:14-20`), so the web mobile shell never claims
  to be the native app (e.g. it keeps web OAuth redirect, no deep links).
- **Android:** the Tauri deep-link config has a `mobile` entry and `lib.rs` uses
  `#[cfg_attr(mobile, …)]`, but there is **no Android build wired** (no
  `gen/android`, no scripts, no docs). iOS is the only mobile target shipped.

### The three `platform.ts` switches everything keys on

| Function | Web | iOS | macOS widget |
|---|---|---|---|
| `apiUrl(path)` (`platform.ts:46`) | relative (same-origin) | absolute `https://skeuo.fm` | absolute `https://skeuo.fm` |
| `redirectUri()` (`platform.ts:73`) | `origin + "/"` | `https://skeuo.fm/callback` (HTTPS bounce → `skeuo://`) | `http://127.0.0.1:14565/callback` (loopback) |
| `openAuthorizeUrl(url)` (`platform.ts:91`) | `location.assign` | system browser (opener plugin) | system browser (opener plugin) |

Tauri shells serve the bundle from `tauri://localhost`, so a relative `/api/…` never
reaches the backend — hence `apiUrl()` rewrites to the absolute origin under Tauri.

---

## 1. FEATURE × PLATFORM PARITY MATRIX

Legend: ✅ full · 🟡 partial / constrained · ❌ gap (not present) · — n/a (doesn't apply)

| Feature | Web | iOS | macOS widget | Share |
|---|:--:|:--:|:--:|:--:|
| **Player / Composite** (all control kinds) | ✅ | ✅ | ✅ | ✅ |
| Visualizer (linear/radial/teeth/ribbon) | ✅ | ✅ | ✅ | ✅ |
| CD / albumart visualizer | ✅ | ✅ | ✅ | ✅ |
| Marquee · time/clock · seek · EQ · playlist | ✅ | ✅ | ✅ | ✅ |
| Wireframe ("Template view") overlay | ✅ | ❌ | ❌ | ❌ |
| **Skin gallery** | ✅ desktop rail | ✅ swipe carriage | ❌ single skin | — |
| Built-in skins | ✅ | ✅ | ✅ | ✅ |
| Runtime (localStorage) skins | ✅ | ✅ | ❌ | via `?id=` |
| Cloud skins (`/api/skins`) | ✅ | ✅ | ❌ | via `?id=` |
| **Create skin** (CreateWizard) | ✅ | ✅ | ❌ | ❌ |
| Live generation preview | 🟡 flag off | 🟡 flag off | — | — |
| **Generation pipeline** (server) | ✅ shared backend | ✅ shared backend | ✅ shared backend | — |
| Client-side cutout | ✅ | ✅ (WKWebView) | ✅ | — |
| **Spotify connect** (OAuth) | ✅ | ✅ HTTPS bounce | ✅ loopback | ✅ |
| Spotify drive (real playback) | 🟡 `CONNECT_ENABLED=false` | 🟡 off | 🟡 off | 🟡 off |
| Web Playback SDK ("Play here") | 🟡 removed (hook intact) | ❌ no EME | 🟡 removed | ❌ |
| **Export PNG** | ✅ | ✅ | ✅ | ✅ |
| Export GIF / Video | ✅ (≥700px) | ❌ (<700px gate) | ✅ | ❌ |
| Native share (`navigator.share`) | 🟡 if supported | ✅ | ❌ | ✅ |
| Copy share link | ✅ | ✅ | ✅ | ✅ |
| **Desktop handoff** (`skeuo://skin/<id>`) | ✅ launches app | — | — (already running) | ✅ |
| Document-PiP "Float player" | 🟡 `FLOAT_ENABLED=false` (Chrome/Edge 111+) | ❌ | — | ❌ |
| **Transparent float window** | — | ❌ | ✅ | — |
| Always-on-top toggle | — | ❌ | ✅ | — |
| Menu-bar tray / hide-to-tray | — | ❌ | ✅ | — |
| Window-state persistence | — | ❌ | ✅ | — |
| Single-instance forwarding | — | ❌ | ✅ | — |
| Drag-to-move | — | ❌ | ✅ | — |
| Per-pixel click-through | — | ❌ | ✅ | — |
| Deep-link scheme `skeuo://` registered | — | ✅ | ✅ | — |
| OAuth loopback command | — | ✅ (w/ bounce reply) | ✅ | — |

The desktop-widget rows (transparent window … click-through) are **intentional**
macOS-only — all `#[cfg(desktop)]`-gated in Rust; iOS is full-screen by design.
See [§6](#6-desktop-widget-macos-only) and [Parity gaps](#9-parity-gaps--risks).

---

## 2. Generation pipeline

The shipping pipeline on `main` is **single-pass, layout-first, combined-blueprint**.
Server-side draws a blueprint and runs **one** fal paint pass; the browser does the
cutout. Runtime-agnostic core (`src/generate/*`) runs identically under the CF Pages
Function and the Node dev server. There is no per-platform branch in generation —
all four shells (sans widget, which has no Create UI) hit the same backend.

> **Important — single pass.** The envelope pass was removed. `costPerSkin` in
> `MODELS` is now an upper-bound for the one paint call; `timingMs.envelope` is
> always `0` (`pipeline.ts:519-520`). Legacy "envelope → paint two-pass" wording
> survives in `functions/api/generate.ts` comments and in `docs/architecture.md` /
> `docs/generation.md` — that prose is **stale**; see [Doc drift](#doc-drift).

### 2.1 Stages

| # | Stage | One-line | File(s) · symbol | Platform | Gating |
|---|---|---|---|---|---|
| 1 | **Director — material** | prompt → `{style, materialPrompt, font, name, blurb}` via gpt-4o (heuristic fallback w/o key) | `director.ts` `deriveMaterial()` (heuristic `heuristic()`) | server | `OPENAI_API_KEY` present? |
| 2 | **Director — layout** | prompt → custom `Region[]` (temp 0.9), caps ≤9 interactables / ≤5 EQ | `director.ts` `deriveLayout()` | server | OpenAI key; else preset variant |
| 3 | **Layout source** | explicit wizard regions → Director layout → preset variant | `handler.ts` `handleGenerate()`; `pipeline.ts:383-407` | server | request `regions?` |
| 4 | **Repack (custom only)** | de-overlap + CANON-size **only** Director/custom rects; presets kept as-is | `pipeline.ts:383-407`; `layouts.ts` `repackTemplate()`, `resolveOverlaps()` | server | `input.regions?.length` ⇒ repack, else preset verbatim |
| 5 | **Bank transport** | snap prev/play/next/stop into one baked cluster | `layouts.ts` `bankTransport()` | server | always |
| 6 | **CD screen inject** | swap a screen for a spinning-CD display for music/disc prompts | `pipeline.ts` `maybeCdScreen()` | server | prompt regex |
| 7 | **Combined blueprint** | one 9:16 SVG: device body (magenta/cyan rings) on a colour-key backdrop + white sprite strip | `blueprint.ts` `combinedBlueprint()`, `pickKeyColor()` | server | always |
| 8 | **Paint (single fal pass)** | restyle the whole blueprint at once into the material | `pipeline.ts` `generateSkin()`, `falSubmit()` | server | model choice |
| 9 | **Cutout (device)** | colour-key hybrid OR BiRefNet, connected-component fill, despill | `cutoutClient.ts`; `blueprint.ts` `cutoutColorAware()` / `cutoutAlpha()` | **browser** | `key == white` ⇒ legacy white path |
| 10 | **Cutout (sprites)** | BiRefNet strip once → connected-component segmentation → per-control sprites | `cutoutClient.ts` `segmentStripByComponents()`, `cutSprite()` | **browser** | count-match vs greedy; grid/geometric fallbacks |
| 11 | **Upload / finalize** | frame + sprites + template + publish marker → R2 | `cutoutClient.ts` `uploadFrame/uploadSprite`; `finalize/[[path]].ts` | browser → server | template must exist |

### 2.2 The two load-bearing decisions

**A. ~~Color-key device hybrid vs BiRefNet~~ — SUPERSEDED 2026-07-01.**
This section described the 2026-06-24 decision (color-key beat BiRefNet on the
device). `cutoutClient.ts` has since switched the DEVICE cutout to BiRefNet too
(comment: "DEVICE cutout = BiRefNet (object-based), same as the strip
(2026-07-01)"), painted on a neutral grey/white/black backdrop chosen to CONTRAST
the material (`pipeline.pickKeyColor`) rather than a saturated color-key — a
saturated key was found to eat grey/chrome device parts and bleed a pink frame
into translucent bodies. Verified live against skeuo.fm 2026-07-11 (production
hardening pass, see TODO.md): the returned device alpha traces the real painted
silhouette (gear teeth, notches, cut-through holes — 84% fill inside its bbox, not
a rectangle). The color-key-only fallback (`cutoutColorAware`/`cutoutAlpha`, row 9
above) is now LEGACY/DEMO-only — it fires when there's no `layout` or the paint is
a `data:` URL, neither of which happens in a real deployed generation (see
`functions/api/generate.ts` header comment for the current audited state of all
four generation-pipeline production-hardening items).
- **Sprite strip still uses BiRefNet + connected-components** — loose parts on a
  clean white sweep is the case BiRefNet handles well, unchanged.
- *(This doc (2.1-2.3) otherwise wasn't re-audited in this pass — row 1's "gpt-4o"
  Director is also stale, replaced by Vertex/Gemini per `wrangler.toml`'s header
  comment. Treat the rest of §2 as a snapshot, not current truth, until re-checked.)*

**B. The alignment fix — repack only custom/Director rects (`pipeline.ts:383-407`).**
Preset variants (simple/radial/capsule/minimal) are hand-authored with intentional
sizes/overlaps (tight EQ rows, paired knobs). Running `repackTemplate` on them
applied CANON sizes (e.g. EQ slider-v h 0.085 → 0.24) which tripped `resolveOverlaps`
into scattering the band — the root cause of "buttons way off". Fix:
```ts
const baseRegs = input.regions?.length
  ? repackTemplate(input.regions)        // messy Director/custom input → de-overlap
  : regionsForVariant(input.variant);    // clean authored preset → keep geometry
```
(Commits `c1f580f`, `62152eb`.)

### 2.3 Paint models & aspect

`MODELS` (`pipeline.ts:156-162`):

| id | label | $/skin | notes |
|---|---|---|---|
| `fal-ai/gemini-3-pro-image-preview/edit` | nano-banana-pro | 0.30 | |
| `fal-ai/gemini-3.1-flash-image-preview/edit` | nano-banana-2 | 0.16 | **DEFAULT_MODEL** |
| `openai/gpt-image-2/edit` | gpt-image-2 | 0.34 | approx |

Aspect is load-bearing (`ai-image-coords-rule`): the blueprint is built to **9:16**
exactly; Gemini endpoints request `aspect_ratio:"9:16"` + `resolution:"2K"`,
gpt-image-2 requests explicit `image_size 1024×1820`. Output dims are checked after
paint and a >3% drift warns (`pipeline.ts:469-472`) — a mismatch would mis-place the
normalized sprite-strip cells.

### 2.4 Rate limit / spend cap

ONE mechanism now (2026-07-11: the old in-memory duplicate was deleted — see below):

- **`src/generate/meter.ts`, KV-backed, edge-shared.** Lifetime **spend cap** in cents
  (`RATELIMIT` key `spend:cents`, default **1000 = $10**, override `SPEND_CAP_CENTS`)
  PLUS a **per-IP/day bucket** (`GEN_BUCKET`, 5/day for `/api/generate`; `CUT_BUCKET`,
  40/day for `/api/cutout`). Both are RESERVED before the paid fal call and refunded
  on failure. Cost estimated *before* the fal call (`estCostCents`, `generate.ts`);
  refuse 429 if `spent + est > cap` or the IP is over its daily bucket. Spend has
  **no TTL — never auto-resets** (manual reset via `wrangler kv key put … spend:cents
  0`); the IP bucket TTLs at ~25h. `GET /api/budget` reads the spend total.
- **Known limitation, documented not hidden:** KV is eventually consistent, so a
  concurrent burst can overshoot the cap slightly. A Durable Object would remove that
  race; not worth it at this traffic level (hobby endpoint, single-digit-dollar cap).
- **Deleted:** `src/generate/ratelimit.ts`, an in-memory per-isolate duplicate
  (`MAX_PER_IP_PER_DAY=5`) that was still wired into `handler.ts` alongside the KV
  meter above — redundant and non-durable (real ceiling ≈ `isolates × cap`). Removed
  once confirmed the KV meter already covered the same ground correctly.

### 2.5 Create UI — CreatePanel vs CreateWizard

- **`CreateWizard.tsx`** is the one App.tsx uses (`App.tsx:264, 418`). 4 steps:
  Idea (prompt + ref + 🎲) → Layout (variant + drag-edit via `LayoutStage`, palette
  add/remove) → Body (auto-grow / ✦ sculpt 2× / upload) → Generate (model checklist +
  cost). **`LIVE_PREVIEW_ENABLED=false`** (`CreateWizard.tsx:459`) hides the in-loader
  live preview card; server still streams stages.
- **`CreatePanel.tsx`** is a simpler flat form (prompt + ref + multi-model compare,
  no layout editing, fixed `radial` variant). **Not mounted by App.tsx** — present in
  the tree but not referenced as the active create surface on `main` (App imports the
  `RuntimeSkin` *type* from it, `App.tsx:11`, but renders `CreateWizard`). Treat as
  legacy / comparison harness unless re-wired.

---

## 3. Player / Composite (shared by all shells)

`src/player/Composite.tsx` renders a `Template` (control regions). The **same
component** drives web stage, mobile carriage page, widget, and share page — there is
no per-platform control fork. Controls render as **baked clusters** (painted into the
body; React overlays a transparent hit-region) or **cut sprites** (per-control PNGs).

### 3.1 Control kinds (`template/schema.ts`)

| kind | render | file · component | notes |
|---|---|---|---|
| `button` | baked hit-region, molded transport face, generic 9-slice, or per-skin sprite | `Composite.tsx:248-303` | two-state play/pause (`/(^\|_)play(_\|$)/`); `shape:"ellipse"` for round |
| `toggle` | stacked `switch-off/on` sprites or CSS bat | `Composite.tsx` `FlipSwitch`, `toggleBinding` | shuffle/eqOn/eqAuto/mute |
| `slider-h` | rail+fill (+ optional sprite thumb) | `Composite.tsx` `SliderH` | volume/balance/seek |
| `slider-v` | vertical fader | `Composite.tsx` `SliderV` | EQ bands (`index`), disabled when `!eqOn` |
| `slider-arc` | SVG arc, thumb on `arc.start/end` | `Composite.tsx` `SliderArc` | angle-unwrap so seek is monotonic past 50% |
| `slider-path` | thumb on Catmull-Rom spline, arc-length projected | `Composite.tsx` `SliderPath`; `spline.ts` | freeform seek |
| `knob` | static sprite cap + orbiting pointer, or CSS rotator | `Composite.tsx` `Knob` | −135..+135° (270° sweep) |
| `segmented` | N buttons | `Composite.tsx` `Segmented` | repeatMode / eqPreset |
| `xy` | grid + puck | `Composite.tsx` `XYPad` | tone {x,y}; cosmetic under Spotify |
| `display` | sprite screen or live React content | `Composite.tsx:146-240` | see dynamic content |
| `flourish` | baked decoration | schema | no runtime element |

**Shape freedom** = `shape:"ellipse"` + `baked` + freeform `path`/`arc` let a control
be any silhouette; round controls are kept pixel-square through repack/overlap so they
never become ovals (`layouts.ts`).

### 3.2 Dynamic display content (`content:"dynamic"`)

`time`, `marquee`, `meta` (bitrate/khz/stereo), `title`, `eq-curve`, `playlist`,
`visualizer`, `cd`, `albumart` (`schema.ts:41-47`).

- **Visualizer** (`Visualizer.tsx`): modes `linear` (19 bars), `radial` (5 dial
  sub-styles: bars/rings/radar/bloom/wave), `teeth` (red grin), `ribbon` (bars along a
  spline). **`blob` is declared in the schema/type but not rendered** — future.
- **CD** (`Composite.tsx` `CdDisc`): spinning mock disc — torque-limited spin-up,
  ~1000°/s cruise, friction spin-down, 5-layer rotational motion blur, album-art tint
  via `mix-blend-mode:color`, fixed specular gloss. **albumart** = bare cover image w/
  text fallback. (Merged + baked + deployed per `TODO.md`.)
- A skin selects a mode via region fields `vis` / `dialStyle` (`schema.ts:80-81`).

### 3.3 Player state & audio

- `usePlayer.ts` holds transport/EQ/tone/playlist; `useAudio.ts` is the
  **generative WebAudio synth — currently disabled** (returns a null `AnalyserNode`);
  the visualizer falls back to a deterministic mock animation. Synth is restorable
  from git history (per file comment).
- **`spotifyDrive`** (when present) overrides playback; EQ/tone stay local cosmetic
  state (Spotify has no per-stream EQ). Playlist mutation is a no-op in Spotify mode.

### 3.4 Default template

`template/winamp-layout.ts` `playerTemplate` — a 480×700 full Winamp-style layout
(~51 regions: flourishes, dual LCD, visualizer, marquee, meta, volume/balance knobs,
XY, seek, full transport, EQ head + 11 faders, playlist + its own transport). **Every
shell renders `playerTemplate`** (web stage, mobile page, widget, share) except for
generated/cloud skins which carry their own template.

### 3.5 Thumbnails & fonts

- `SkinThumb.tsx` renders the static frame + an optional live visualizer overlay at
  real rects (fetches the skin template). Built-ins use baked 256px `thumb.webp`
  (`scripts/bake-thumbs.mjs`); runtime/cloud use the served frame.
- `skinFonts.ts` loads per-skin Google logomark fonts on demand (`ensureGoogleFont`,
  `isFontReady`, `preloadSkinFonts`), held hidden until ready to avoid FOUT. Generated
  skins use the Director's `font` pick.

---

## 4. Skins & gallery

### 4.1 Three skin sources

| Source | Where stored | In desktop rail | In mobile carriage | Notes |
|---|---|---|---|---|
| **Built-in** | `public/skins/<id>/` + `skins.ts` `skinList` | ✅ | ✅ | ~30 skins (28 visible + winamp/toilet donor styles `hidden`); `hidden` filters gallery, `?all` reveals |
| **Runtime (generated)** | `localStorage["skeuo:skins"]` (small URLs; frames on R2) | ✅ (`App.tsx:316`) | ✅ (`runtimeAsAssets`, `App.tsx:206`) | "×" = **hide, not delete** (`hidden:true`, raw kept). Carriage parity was just fixed (`e4fd2cd`). |
| **Cloud (published)** | R2 `published/<id>` marker + `skins/<id>/*`; merged via `GET /api/skins` | ✅ (`App.tsx:347`) | ✅ (`cloudAsAssets`) | template fetched lazily on activate (`/api/skin/<id>`); built-in ids win on collision; appended after built-ins; reaches the app **without a rebuild** |

The widget shows **one** skin (no gallery). Share shows one skin (no gallery).

### 4.2 Backend endpoints (CF Pages Functions, `functions/api/`)

| Route | Method | Purpose | Storage |
|---|---|---|---|
| `/api/generate` | POST | single-pass generate, NDJSON stream of stages | KV `spend:cents`; R2 `skins/<id>/{paint,template,meta}` |
| `/api/cutout` | POST | BiRefNet (`fal-ai/birefnet/v2`) bg-removal | — (stateless) |
| `/api/extract` | POST | gpt-4o VLM control bbox localization | — (present; **not** used by shipping cutout) |
| `/api/skins` | GET | cloud gallery index (scan `published/`) | R2 read |
| `/api/skin/<id>` | GET | reconstruct one skin (template+frame+sprites flag) — drives share + cloud activate | R2 read |
| `/api/finalize/<id>[/sprites/<bind>][/publish]` | POST | upload cut frame/sprites; write publish marker | R2 write (gated on `template.json` exists) |
| `/api/asset/<key…>` | GET | stream any R2 object, immutable cache, CORS `*` | R2 read |
| `/api/budget` | GET | `{capCents, spentCents, remainingCents}` | KV read |

**R2 layout** (`skeuo-skins`, binding `SKINS`): `skins/<id>/` holds `paint.png` (raw,
**reprocessable** — re-run cutout without re-paying fal), `template.json`
(authoritative), `meta.json`, `frame.png` (browser-cut), `sprites/<bind>.png`;
`published/<id>` is the JSON publish marker (display overrides; deleting it
unpublishes). All endpoints CORS `*` so the Tauri `tauri://` origins can reach them.
Local dev mirrors this via `server/devApiPlugin.ts` into `public/generated/`.

---

## 5. Spotify, share & export

### 5.1 Spotify OAuth — three redirect paths

PKCE (no secret in bundle), gated on `VITE_SPOTIFY_CLIENT_ID`. `src/spotify/*`,
redirect chosen in `platform.ts:73`.

| Platform | redirect_uri | Return mechanism |
|---|---|---|
| Web / Share | `origin + "/"` | SPA reads `?code`, exchanges in page |
| macOS widget | `http://127.0.0.1:14565/callback` | Rust `oauth_loopback` one-shot listener (`lib.rs:50-98`) |
| iOS | `https://skeuo.fm/callback` | HTTPS page forwards code to `skeuo://callback` → app re-foregrounds |

**Why iOS differs:** a loopback is unreachable on iOS — opening Safari backgrounds
the app, iOS suspends it, the listener dies, Safari hangs forever (confirmed on device
2026-06-18, `docs/ios.md`). The HTTPS→deep-link bounce avoids a backgrounded socket.

**Web Playback SDK** (`sdk.ts`, in-page "Play here") needs EME/Widevine — **absent in
iOS WKWebView**, so it's unavailable there by platform constraint. The UI toggle was
removed everywhere for now (hook plumbing intact); TODO is to re-add it gated
`!isMobileApp()`. Either way `CONNECT_ENABLED=false` (`App.tsx:54`) currently hides
all Spotify connect UI and the player drives only the **local demo**; `useSpotify()`
still runs.

### 5.2 Share page (`/share?id=<id>`)

`ShareApp.tsx`: fetches `/api/skin/<id>`, renders a **single** `Composite` + metadata +
Spotify connect + copy-link + native share + Desktop-handoff button. **Omits** the
gallery, swipe carriage, create wizard, and mobile/desktop branching. Separate Vite
entry (`share/main.tsx`) for a light shared-link bundle. Canonical link form:
generated → `/share?id=`; built-in → `/?skin=` (`ShareModal.tsx:41`).

### 5.3 Export (`src/export/`)

- **ExportGifButton** opens **ShareModal**, which mounts its own live `Composite` and
  captures from it. Outputs render to 1080×1920 (IG story) with margins/branding.
- **PNG** snapshot — all platforms. **GIF + Video** (`recordPlayerGif`,
  `recordPlayerVideo`) are **gated to ≥700px width**, so hidden on mobile web and the
  iOS app; available on desktop web and the widget. Pre-generated + cached on modal
  open so re-downloads don't re-encode.
- **Native share** via `navigator.share` (iOS/Android; web if supported; absent on
  macOS browser). **Copy link** everywhere.

---

## 6. Desktop widget (macOS-only)

All of the following are **`#[cfg(desktop)]`** in `src-tauri/src/lib.rs` (or
`cfg(not(any(ios, android)))` deps in `Cargo.toml`) — **iOS never compiles or runs
them**. The iOS app is a full-screen player by design, not a floating overlay.

| Feature | File · symbol | Gate |
|---|---|---|
| Transparent / decorationless / skipTaskbar window | `tauri.conf.json` window block; `macOSPrivateApi:true` | macOS |
| Always-on-top toggle | `lib.rs` `AlwaysOnTop`, tray "toggle-aot" | `#[cfg(desktop)]` |
| Menu-bar tray + hide-to-tray (close = hide) | `lib.rs` `build_tray()`, `on_window_event` | `#[cfg(desktop)]` |
| Window-state persistence | `tauri-plugin-window-state`; `restore_state`/`save_window_state`; `capabilities/desktop.json` | `cfg(not(ios/android))` |
| Single-instance forwarding (focus existing) | `tauri-plugin-single-instance` | `cfg(not(ios/android))` |
| Drag-to-move (DPI-aware `setPosition`) | `src/widget/drag.ts` `startWidgetDrag` | `isTauri()` runtime check |
| Per-pixel click-through (alpha hit-map + cursor poll) | `src/widget/clickthrough.ts` `initClickThrough` | `isTauri()` runtime check |
| Deep-link `skeuo://` (register) | `lib.rs` `register_all()` | `#[cfg(desktop)]` (iOS gets it via Info.plist) |
| `oauth_loopback` command | `lib.rs:50-98` | **shared** (not cfg-gated); UA sniff switches the reply (desktop plain HTML vs iOS `skeuo://connected` bounce) |

`WidgetApp.tsx` renders a single `Composite` (default/`?skin=`/deep-link skin) + an
auto-hiding bar; wires `initClickThrough` + `updateClickThroughSkin` on skin change +
`initDeepLinks`. **Web → desktop handoff** (`DesktopHandoff.tsx`, `deeplink.ts`):
the site's "Open in desktop player" navigates a hidden iframe to `skeuo://skin/<id>`;
the installed `.app` (deep links only work from the **built** app, not `tauri dev`)
switches skin live; single-instance forwards to a running widget.

---

## 7. Tooling / QA

- **Alignment grader** (`tools/align-grader/`, `det.py` + `vlm.py` + `grade.py` +
  `overlay.py`): per-control alignment check combining a deterministic saliency
  signal (gradient over opaque body pixels; presence + offset thresholds) with a
  gpt-4o VLM bbox read; `aligned = det.aligned AND vlm.aligned` (conservative veto).
  Calibrated on 38 real + synthetically-shifted skins: 92.1% accuracy, 100%
  precision, 84.2% recall; per-skin tinted overlays in `grader-report.html`. The
  per-skin `tools/align-grader/last-*.json` files are saved grades.
- **Tailnet proof viewer** (`.proof/index.html`, served on tailnet via a `.serve-url`
  file): static HTML + JPEG overlays showing the radial alignment fix, walkman
  before/after, color-key cutout quality, body-retention old vs new, and grader
  calibration. Review artifact, not a runtime dependency.
- **Render/export pipeline** (`docs/render-pipeline.md`, `scripts/render-pass.sh`,
  `capture.mjs` on hardcoded port **5210**) — Playwright captures of IG-story
  clips/stills for marketing, handed to a beat-cut editor. Not part of the shipped app.

---

## 8. How parity is enforced

- **Single bundle, zero fork.** One React build is the website, the iOS app, and the
  macOS widget (`src/main.tsx` picks the mount). No platform-specific branch of the
  player, the template, or the generation client exists — `Composite` and
  `playerTemplate` are shared verbatim.
- **One gating point.** Every web-vs-Tauri / mobile-vs-desktop decision routes
  through **`src/platform.ts`** (`isTauri`/`isMobileApp`/`isWidget`/`apiUrl`/
  `redirectUri`/`openAuthorizeUrl`). New platform behavior belongs there, not
  scattered.
- **Native divergence is `#[cfg]`-fenced.** Desktop-only OS integration is
  `#[cfg(desktop)]` in `lib.rs` / `cfg(not(ios/android))` deps; iOS simply never
  builds it, and `capabilities/desktop.json` scopes the permissions to macOS.
- **Shared backend.** All clients hit the same `functions/api/*` (CORS `*`); the
  generation core (`src/generate/*`) is DOM-free and runs identically under CF and
  the Node dev server.

**Build / deploy flow (the parity caveat):**

| Target | Command | Lag |
|---|---|---|
| Web | `npm run deploy` → `wrangler pages deploy dist --project-name skeuo-ui` (no CI) | instant on deploy |
| Cloud skins | published to R2; merged via `/api/skins` | **no rebuild** needed |
| macOS widget | `npm run tauri:build` (ad-hoc signed; notarized via `scripts/build-desktop.sh`, blocked on certs) | needs a Tauri build to ship client changes |
| iOS | `tauri ios build … --archive-only` → `xcodebuild -exportArchive` → `altool upload` → TestFlight | **client changes need a TestFlight build** — the iOS client lags web deploys until rebuilt |

Because the iOS client is a bundled webview build, **a web deploy does not update the
iOS app's client code** — only its backend calls (which hit live `skeuo.fm`) follow
along. Same for the widget. This is the structural reason TestFlight/widget builds lag.

---

## 9. Parity gaps & risks

### Intentional (platform constraint — not a bug)
- **iOS lacks tray / window-state / single-instance / always-on-top / drag /
  click-through / transparent window.** All `#[cfg(desktop)]`; iOS is full-screen by
  design. (`docs/ios.md`, `lib.rs`.)
- **iOS lacks the in-page Web Playback SDK** — no EME/Widevine in WKWebView; can only
  drive an active Spotify Connect device. (`docs/ios.md`.)
- **iOS uses an HTTPS→`skeuo://` OAuth bounce** instead of the desktop loopback — the
  loopback is unreachable once iOS suspends the backgrounded app.
- **Widget shows a single skin, no gallery/create/export-grid** — it's a floating toy,
  not the full studio.
- **GIF/Video export hidden < 700px** — mobile web + iOS get PNG + native share only.
- **Desktop handoff `skeuo://` only works from the built `.app`**, not `tauri dev`.

### TODO / unresolved divergences
- **`CONNECT_ENABLED=false`** (`App.tsx:54`) — Spotify connect UI hidden on **all**
  platforms; player drives only the local demo. Needs the BYO-Client-ID wizard
  (prototype exists, pending Spotify cooldown). Spotify dev-mode quota (5 users,
  Premium owner) blocks public multi-user Spotify regardless.
- **`?skin=<cloud-id>` deep link not honored at first mount.** `App.tsx:64-70` resolves
  `?skin=` only against `visible` (built-ins) + `localStorage` runtime skins;
  `cloudSkins` are fetched in a *later* effect, so a shared link to a **cloud** skin
  falls back to `visible[0]` on first paint and never re-selects. Built-in and runtime
  `?skin=` links work; cloud ones silently don't. (Real bug; share links for cloud
  skins should use `/share?id=` which *does* hydrate — but the in-app `/?skin=` path
  doesn't.)
- **`FLOAT_ENABLED=false`** (`App.tsx:52`) — Document-PiP "Float player" is wired
  (Chrome/Edge 111+) but hidden because the PiP window's browser chrome can't match the
  transparent widget.
- **`LIVE_PREVIEW_ENABLED=false`** (`CreateWizard.tsx:459`) — in-loader live preview
  card hidden; server still streams stages.
- **TestFlight/widget clients lag web deploys** — client changes require a native
  rebuild; the iOS device `.ipa` signing/provisioning is **not yet wired** (Simulator
  is the verified target; team `N4YGB5B92K`).
- **`xcodegen` regeneration strips `CFBundleURLTypes` / static-lib `buildPhase`** —
  three `project.yml` fixes must be re-applied after `tauri ios init` or OAuth bounce
  and the archive break (`docs/ios.md`).
- **CreatePanel not wired** — `CreateWizard` is the active create UI; `CreatePanel` is
  an unmounted legacy/compare surface.
- **`blob` visualizer + XY-pad-under-Spotify are stubs** — `blob` is typed but not
  rendered; XY tone is cosmetic when Spotify drives.
- **No un-hide UI** — hidden runtime skins persist in storage and `?all` reveals the
  built-in catalog, but there's no restore affordance.
- **Per-IP rate limiter is in-memory** — not edge-shared/persistent; only the KV spend
  cap is authoritative. (No daily reset on the spend cap either — manual.)

---

## Doc drift

The narrative docs predate the current `main` pipeline in places. Trust the code:
- **`docs/architecture.md`, `docs/generation.md`** describe a **two-pass
  (envelope → paint)** Python `wild_sculpt.py` / `gen_sprites.py` pipeline and a
  three-layer "drawn-into-mask" design. `main` ships a **single fal paint pass** on a
  combined blueprint with browser-side cutout (`pipeline.ts`, `cutoutClient.ts`).
- **`functions/api/generate.ts`** header comments still say "two fal passes
  (envelope → paint)"; the code imports `MODELS`/`combinedBlueprint` and runs one pass
  (`estCostCents` applies a 0.55 factor only as a legacy ceiling knob).
- `docs/desktop.md`, `docs/ios.md` are accurate for the native shells and the OAuth
  divergence.

---

*File: `docs/feature-parity.md` — regenerate when `platform.ts`, the generation
pipeline, the control schema, or the Tauri `cfg` boundaries change.*
