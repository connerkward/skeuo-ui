---
name: video-convert
description: Convert iPhone HEVC HDR (HLG) .mov to SDR H.264 .mp4 for tools that reject HDR (ComfyUI VHS upload, Discord inline preview, etc.). Also handles downscale-for-Discord (sub-10MB).
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Video Convert

iPhone footage is HEVC 10-bit HLG with bt2020 primaries. Many tools reject this:

- **ComfyUI VHS_LoadVideo**: errors out on HDR
- **Discord inline preview**: prefers H.264 yuv420p
- **Generic players**: wrong colors when HLG metadata is preserved

The fix is real tonemapping (HLG → SDR bt709), not just metadata override.

## Critical: use a static ffmpeg, not Homebrew's

Homebrew's `ffmpeg` bottle is **built without `libzimg`**, so it has no `zscale` filter and the `colorspace` filter rejects HLG (`arib-std-b67`) input transfer. Both proper tonemap routes are blocked.

Use evermeet's static build cached at a **persistent** path — not `/tmp`, which macOS clears on reboot. One-time install (survives restarts; `/tmp` is just download staging):

```bash
mkdir -p ~/.local/bin
curl -fsSL -o /tmp/ffmpeg-evermeet.zip "https://evermeet.cx/ffmpeg/getrelease/zip" \
  && unzip -o /tmp/ffmpeg-evermeet.zip -d /tmp/ \
  && mv -f /tmp/ffmpeg ~/.local/bin/ffmpeg-static
~/.local/bin/ffmpeg-static -hide_banner -filters | grep zscale   # verify zscale present
```

Recipes below call `~/.local/bin/ffmpeg-static`.

## Recipe: HLG → SDR 720p (ComfyUI VHS, generic)

```bash
~/.local/bin/ffmpeg-static -y -i INPUT.mov \
  -vf "scale=1280:720,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p" \
  -c:v libx264 -crf 18 -preset medium \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -c:a aac -b:a 192k -movflags +faststart \
  OUTPUT-720.mp4
```

Filter chain explained:
- `scale=1280:720` — downscale (omit for native res)
- `zscale=t=linear:npl=100` — convert HLG to scene-linear at 100 nits ref
- `format=gbrpf32le` — 32-bit float for tonemap
- `zscale=p=bt709` — primaries to bt709
- `tonemap=hable:desat=0` — Hable curve, no desaturation
- `zscale=t=bt709:m=bt709:r=tv` — output transfer/matrix/range
- `format=yuv420p` — 8-bit chroma subsampled

The `-color_*` flags tag the H.264 bitstream so players don't mis-decode.

## Recipe: Discord-friendly downscale (sub-10MB)

For already-SDR ComfyUI renders or anything you just need smaller. Skip tonemap, scale to max 1280 width, CRF 23:

```bash
~/.local/bin/ffmpeg-static -y -i INPUT.mp4 \
  -vf "scale='min(1280,iw)':-2,format=yuv420p" \
  -c:v libx264 -crf 23 -preset medium -movflags +faststart \
  -c:a aac -b:a 128k \
  OUTPUT-discord.mp4
```

`-2` keeps aspect ratio with even height. CRF 23 typically yields ~1–4 MB for clips under 10s. Discord free tier is 10 MB — well under.

## Verify output is SDR

```bash
ffprobe -v error -show_entries stream=color_space,color_transfer,color_primaries \
  -of default=noprint_wrappers=1 OUTPUT.mp4
```

All three should be `bt709`. If any are `bt2020`/`arib-std-b67`/`smpte2084`, the bitstream is still tagged HDR and tools may reject it.

## Batch: parallel ffmpeg

ffmpeg is single-threaded per process for many filters; running N in parallel via `&` + `wait` is faster than serial when you have multiple CPU cores free. CRF encoding is CPU-bound — don't run more than ~CPU/2 in parallel or they'll thrash.

## Why H.264 over H.265

H.265/HEVC produces ~30% smaller files at equal quality, but Discord's mobile/web inline preview for HEVC mp4 is unreliable. H.264 yuv420p is the universal safe bet. Use H.265 only when target is known-compatible.

## Anti-patterns

- ❌ Using `colorspace` filter on HLG content — it doesn't accept `arib-std-b67` as input transfer (`Invalid argument` error).
- ❌ Just adding `-color_trc bt709` flags without filter-side conversion — tags lie, pixel data is still HLG, image looks washed-out/dark.
- ❌ Outputting `yuv420p` without explicit `format=yuv420p` in the filter chain when input is 10-bit — encoder may pick yuv420p10le and fail on H.264.
- ❌ Reaching for `brew reinstall ffmpeg --build-from-source` to get zimg — slow. Just use evermeet's static binary.
