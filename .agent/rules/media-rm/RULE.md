---
name: "media-rm-rule"
id: "media-rm-01"
description: "Media files route through the system Trash (/usr/bin/trash), never rm — rm is unrecoverable. Recovery and edge cases in the media-rm skill."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Media files — trash, never rm

When deleting media files (images, videos, audio, fonts, 3D models), **route through the
system Trash, not `rm`** — `rm` is unrecoverable and media is the most expensive thing on
disk to recreate (captures, renders, exports, RAWs). Use the native tool:

```bash
trash <file1> [<file2> …]    # ✓ recoverable (macOS /usr/bin/trash, Sequoia 15.0+)
rm -f *.png                  # ✗ unrecoverable — never on media
```

**Media** = images (jpg png webp avif gif tiff heic raw dng cr2/3 arw nef psd svg…),
video (mp4 mov webm mkv prores…), audio (mp3 wav flac aac m4a…), fonts (ttf otf woff…),
3D (glb gltf usd fbx obj blend stl…), and their thumb/preview sidecars.

**`rm` IS fine** for: `/tmp/*`, `<repo>/.scratch/*`, a file the user explicitly named to
delete, or a file you wrote this same turn. "Clean up the folder" is a category, not an
explicit instruction — the category default is trash.

Recovery, the brew-tool comparison, and full carve-outs: load the **`media-rm`** skill.
Related: `human-labeled-data-rule` (same reversible-paths philosophy for human judgments).
