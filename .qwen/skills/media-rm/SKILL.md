---
name: media-rm
description: Recovery detail and edge cases for deleting media files safely on macOS (Trash vs rm, what counts as media, restoring from ~/.Trash, the native /usr/bin/trash vs Homebrew rmtrash). The always-on floor ("media → trash, never rm") lives in media-rm-rule; load this skill when you need the full extension list, recovery recipe, or the when-rm-IS-fine carve-outs.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# media-rm — safe media deletion (detail)

The imperative is always-on in `central/rules/media-rm-rule.md`: **media files route
through Trash (`/usr/bin/trash`), never `rm`** — `rm` is unrecoverable and media is the
most expensive thing on disk to recreate (captures, renders, exports, RAWs). This skill
carries the depth.

## Why (the concrete burn)

2026-06-04 dailies session, round 5/6: agent `rm -f`'d the `1111` mp4 that turned out to
be the highest-quality version, then was told "I liked that one" with no way to recover.
Trash buys an undo for the entire class of "agent decided to clean up."

## The tool

macOS ships `/usr/bin/trash` natively since **Sequoia 15.0** (present on Sequoia, Tahoe,
later; zero install). Use it as the `rm` replacement:

```bash
trash <file1> [<file2> …]                  # ✓ recoverable
trash ~/ideas-syncthing/proj-dailies/*.mp4 # ✓
```

Plain file/dir list (`-v` verbose, `-s` stop-on-error) — no `rm`-style `-rf`; the shell
expands globs, whole dirs move as-is. Items land in `~/.Trash` with Finder "Put Back" info.

Never on media: `rm <video>.mov`, `rm -f *.png`, `find . -name '*.mp4' -delete`.

### Native vs Homebrew

| Tool | What | When |
|------|------|------|
| **`/usr/bin/trash`** (Apple, native) | system binary, file-list args | **Default. Always.** |
| brew **`rmtrash`** (TBXark) | `rm`-compatible wrapper (`-r -f -i -v`) | only if you want `alias rm=rmtrash` shell-wide; calling `trash` directly already covers it |
| brew **`trash`** (hasseg.org) | extra `-F`/`-e`/`-l` | **removed; don't reinstall** (keg-only, redundant) |

This machine: native `/usr/bin/trash` + brew `rmtrash` present; hasseg `trash` uninstalled.

## What counts as "media"

- **Images:** jpg jpeg png webp avif gif tiff tif heic heif raw dng cr2 cr3 arw nef raf orf psd ai svg
- **Videos:** mp4 mov webm mkv m4v avi mpg mpeg hevc h264 h265 prores
- **Audio:** mp3 wav flac aac m4a ogg opus aiff alac
- **Fonts:** ttf otf woff woff2 eot
- **3D/spatial:** glb gltf usd usdz fbx obj blend stl ply
- Their thumbnail/sidecar variants (`*.thumb.*`, `*-preview.*`, `*-cover.*`)

## When `rm` IS fine

- **`/tmp/*`** — macOS clears it; nothing durable.
- **`<repo>/.scratch/*`** — gitignored, ephemeral by definition.
- **User explicitly says "delete"/"rm" that file** — scoped instruction; still consider
  asking if expensive to recreate. "Clean up the folder" is NOT explicit.
- **Files you JUST wrote this turn** — nothing of value to lose.

## Recovering

Files in `~/.Trash/` keep their name. Restore via Finder → Trash → "Put Back", or
`mv ~/.Trash/<name> <original-path>`. macOS auto-empties after 30 days only if that
Finder setting is enabled (default off).

**Rule of thumb:** if recreating the file would take >1 min of work or wait — captured,
rendered, downloaded, exported, recorded, designed — it goes to Trash, not the void.
