<div align="center">

![skeuo.fm — a gallery of skeuomorphic music players generated from one-sentence prompts](docs/cover.png)

# 🎛️ skeuo.fm

### Turn one sentence into a real, *working* skeuomorphic music player.

Say **"a fanged anglerfish jaw"** and get back a finished player — a body shaped like
that jaw, with **genuinely working hardware**: switches that flip, knobs that turn,
faders that slide — driving your real music. 🎶

[![live demo](https://img.shields.io/badge/▶_live_demo-skeuo.fm-9dff4d?style=flat-square&labelColor=08080a)](https://skeuo.fm)
[![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react&logoColor=white&labelColor=08080a)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178c6?style=flat-square&logo=typescript&logoColor=white&labelColor=08080a)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-646cff?style=flat-square&logo=vite&logoColor=white&labelColor=08080a)](https://vitejs.dev)
[![Tauri](https://img.shields.io/badge/Tauri-desktop-ffc131?style=flat-square&logo=tauri&logoColor=black&labelColor=08080a)](https://tauri.app)
[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare-Pages-f38020?style=flat-square&logo=cloudflare&logoColor=white&labelColor=08080a)](https://pages.cloudflare.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-e8ece2?style=flat-square&labelColor=08080a)](LICENSE)

</div>

---

## ✨ What it is

skeuo.fm is an AI image model that designs the *shape* of a music player, and a real
front-end that makes the controls **actually work**. You type a prompt, the model
sculpts a wild device body around it, and you get switches, knobs, faders, a live
spectrum, a marquee, and a playlist — all functional, all driving real audio (or your
real Spotify). 🔊

The trick isn't the picture — it's that the **controls never drift out of the painted
device**. Alignment isn't detected and repaired; it's true *by construction* (we draw
the controls inside the painted mask and emit the layout from those exact coordinates).
→ [How it works](docs/architecture.md)

![Four skins playing — Pebble (minimal), Media Capsule (WMP9), Angler Maw (radial), Bone Totem (tall)](docs/skins.gif)

## 🚀 Try it

**[skeuo.fm](https://skeuo.fm)** — no install.

- 📱 **Mobile** — swipe left/right to switch skins.
- 🖥️ **Desktop** — a sidebar of skins, plus:
  - ➕ **Create skin** — generate a new body from a prompt
  - ✎ **Edit template** — drag / resize the control layout
  - 🎧 **Connect Spotify** — drive real playback through any skin
  - 🪟 **Open in desktop player** — launch it as a floating desktop toy (see below)

## 🧑‍💻 Run it locally

```bash
npm install
npm run dev
```

The dev server binds all interfaces, so it's reachable from your phone on the same
wifi (mDNS) or over a tailnet. That's it for the website.

## 🪟 Desktop widget

The **same React bundle** is also a transparent, non-rectangular **desktop music
widget** — a floating "desktop toy" whose shape is the skin's own silhouette, driving
your real Spotify. Pick a skin on the site → **Open in desktop player** → it launches
already wearing that skin.

```bash
npm run tauri:dev      # run the widget locally
npm run tauri:build    # local .app + .dmg
```

→ [Desktop widget docs](docs/desktop.md) (transparency, tray, deep-link handoff, OAuth)

## 📱 iOS app

The **same React bundle** is also a **full-screen iOS app** (Tauri) — the skin
fills the screen, you swipe between skins, and a one-tap **Connect Spotify** pill
drives real playback through your active Spotify device. It's the full site
running natively, *not* the transparent widget.

```bash
npm run tauri:ios:dev                                    # run on a booted Simulator
npm run tauri:ios:build -- --debug --target aarch64-sim  # build a Simulator .app
```

→ [iOS app docs](docs/ios.md) (mode split, loopback OAuth + `skeuo://` bounce, build/sign)

## 🛠️ How it's built

Three layers, composited live by React:

| Layer | What | Built by |
|---|---|---|
| 🫥 **Body** | the wild AI-generated device shape + its painted cavities | `generation/wild_sculpt.py` |
| 🎚️ **Sprites** | switches / knobs / faders / molded buttons, *with states* | `generation/gen_sprites.py`, `gen_buttons.py` |
| ⚡ **Live UI** | spectrum, marquee, clock, playlist, seek ring, WebAudio engine | `src/player/*` |

The whole design exists to make one guarantee: **the live controls and the painted
device can never disagree.** The deep-dives:

- 📐 **[Architecture](docs/architecture.md)** — alignment by construction, the three
  layers, layout grammars, full source map
- 🧪 **[Generation](docs/generation.md)** — regenerating bodies / sprites / templates,
  the CLI, model notes (which model for what, and why)
- 🪟 **[Desktop](docs/desktop.md)** — the Tauri transparent-widget + handoff internals

## 📦 Also available as

- 🔌 **A Claude Code plugin + MCP server** — generate a skin from a sentence inside
  Claude, with an inline Create/preview app. Part of the
  [ckw-skills](https://github.com/connerkward/ckw-skills) marketplace.

---

<div align="center">

MIT © [Conner K. Ward](https://github.com/connerkward) · built with AI image models,
WebAudio, React, and Tauri

</div>
