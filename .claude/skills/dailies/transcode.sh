#!/usr/bin/env bash
# transcode — wrap ffmpeg (HEVC via VideoToolbox) + AVIF for dailies.
# Sub-commands:
#   still  <in.png>  <out.avif>
#   video  <in.mov>  <out.mp4>  <out.thumb.avif>  [seconds]
# Emits a sibling .gif if the source is ≤4 seconds (shareable on image-only platforms).
#
# Requires: ffmpeg, avifenc (from libavif). Falls back to ImageMagick avif if avifenc missing.

set -euo pipefail

die() { echo "transcode: $*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

have ffmpeg || die "ffmpeg not installed (brew install ffmpeg)"

mode="${1:-}"
case "$mode" in

  still)
    in="${2:?in path}"
    out="${3:?out path}"
    [[ -f "$in" ]] || die "no such input: $in"
    mkdir -p "$(dirname "$out")"
    # AVIF via avifenc (best quality/byte), fallback to ffmpeg libaom-av1.
    # Stills are the high-quality side of the archive — text-heavy UI shots
    # need sharper edges than motion clips, so push avif quality higher.
    if have avifenc; then
      avifenc --speed 6 -q 65 "$in" "$out" >/dev/null
    else
      ffmpeg -y -loglevel error -i "$in" -c:v libaom-av1 -still-picture 1 -crf 26 "$out"
    fi
    bytes=$(stat -f %z "$out" 2>/dev/null || stat -c %s "$out")
    echo "transcode: still → $out ($bytes bytes)"
    ;;

  video)
    in="${2:?in path}"
    out_mp4="${3:?out mp4}"
    out_thumb="${4:?out thumb}"
    seconds="${5:-}"
    [[ -f "$in" ]] || die "no such input: $in"
    mkdir -p "$(dirname "$out_mp4")"

    # Optional split-from-master via env vars: TRANSCODE_SS = start seconds,
    # TRANSCODE_T = duration seconds. When set, we feed the master input
    # directly through libx265 and skip the intermediate webm→webm re-encode
    # the import script used to do — one lossy pass instead of three. Place
    # -ss BEFORE -i for fast input seek, then -t AFTER for accurate trim.
    ss_args=()
    t_args=()
    if [[ -n "${TRANSCODE_SS:-}" ]]; then ss_args=(-ss "$TRANSCODE_SS"); fi
    if [[ -n "${TRANSCODE_T:-}"  ]]; then t_args=(-t "$TRANSCODE_T");   fi

    # 1. Transcode to HEVC mp4 via libx265 (software). VideoToolbox's hardware
    #    HEVC ('hevc_videotoolbox') exposes only a coarse -q:v knob, no
    #    psycho-visual controls, and 8-bit Main only — fine for grading but
    #    visibly soft on text-in-motion (parallax scrolls, UI lookdev sliders).
    #
    #    libx265 CRF 18 preset slow, 10-bit (yuv420p10le), with text-tuned
    #    psy-rd=2.0 / psy-rdoq=1.0 and tuned rectangular partitions. CRF 18 is
    #    visually transparent for screen content; slow gives the encoder
    #    enough budget per macroblock to keep small antialiased text edges
    #    intact through motion (the smearing that dropped from CRF 22 + slow).
    #    -tag:v hvc1 = QuickTime / Safari compatible. -movflags +faststart =
    #    mp4 streaming-friendly. Keep source resolution (no clamp); round even
    #    because yuv420p requires it.
    # Optional downscale: TRANSCODE_W = target width (height auto via -2).
    # This is the lever for Playwright-source clips — its built-in VP8 encoder
    # ships ~2.6 Mbps at 1920×1080, which is below VP8's text-clean threshold.
    # Downscaling with Lanczos averages out VP8's edge artifacts AND gives
    # libx265 more bits per pixel at the same CRF — text comes out sharper.
    # Common choices: 1280, 1440.
    if [[ -n "${TRANSCODE_W:-}" ]]; then
      vf="scale=${TRANSCODE_W}:-2:flags=lanczos+accurate_rnd+full_chroma_int,format=yuv420p10le"
    else
      vf="scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p10le"
    fi

    ffmpeg -y -loglevel error "${ss_args[@]}" -i "$in" "${t_args[@]}" \
      -an \
      -c:v libx265 -preset slow -crf 18 -pix_fmt yuv420p10le \
      -tune animation \
      -x265-params "psy-rd=2.5:psy-rdoq=2.0:rect=1:aq-mode=3:aq-strength=0.9:strong-intra-smoothing=0:rd=5" \
      -tag:v hvc1 \
      -vf "$vf" \
      -movflags +faststart \
      "$out_mp4"
    mp4_bytes=$(stat -f %z "$out_mp4" 2>/dev/null || stat -c %s "$out_mp4")

    # 2. (Removed.) We used to generate a small thumb.avif sidecar here for
    #    Finder preview, but macOS QuickLook previews HEVC mp4 natively — the
    #    separate thumb was just clutter that confused "thumb (640×360)" with
    #    "actual screenshot (3840×2160)" in the same folder. If you actually
    #    need a still from a clip, take it explicitly with `transcode.sh still`
    #    or `ffmpeg -ss <t> -i <mp4> -frames:v 1 still.png`.

    # 3. Sibling GIF for short clips (≤4s) — palette-optimised, shareable.
    if [[ -n "$seconds" && "$seconds" -le 4 ]]; then
      out_gif="${out_mp4%.mp4}.gif"
      # mktemp's -t template appends random chars after the LAST char of the
      # template — so a ".png" suffix has to be added manually after the fact,
      # not put inside the template (otherwise ffmpeg can't infer format).
      pal="/tmp/dailies-pal-$$-${RANDOM}.png"
      ffmpeg -y -loglevel error -i "$in" \
        -vf "fps=15,scale=720:-1:flags=lanczos,palettegen=max_colors=128" "$pal"
      ffmpeg -y -loglevel error -i "$in" -i "$pal" \
        -lavfi "fps=15,scale=720:-1:flags=lanczos,paletteuse=dither=bayer:bayer_scale=3" \
        "$out_gif"
      rm -f "$pal"
      gif_bytes=$(stat -f %z "$out_gif" 2>/dev/null || stat -c %s "$out_gif")
      echo "transcode: gif → $out_gif ($gif_bytes bytes)"
    fi

    echo "transcode: video → $out_mp4 ($mp4_bytes bytes) + thumb"
    ;;

  ""|-h|--help)
    sed -n '2,9p' "$0"
    ;;

  *) die "unknown mode: $mode" ;;
esac
