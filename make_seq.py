#!/usr/bin/env python3
"""Assemble a 'skins reel': concatenate the per-favorite hero clips, each shown
for D seconds, in a given color-ordered sequence. Hard cuts. Outputs mp4 + gif.
  make_seq.py <outdir> <name> <dur> <skin1,skin2,...>
The order is chosen by the caller so similar colors never sit adjacent in time."""
import os, sys, subprocess

OUT, NAME, DUR, ORDER = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4].split(",")
SRC = os.path.expanduser(OUT)
START = 0.4                     # skip into each clip so it opens mid-animation
clips = [os.path.join(SRC, f"hero-{s}-1080x1920.mp4") for s in ORDER]
for c in clips:
    if not os.path.exists(c): sys.exit(f"missing source: {c}")

# build a trim+concat filtergraph
parts, labels = [], []
for i, _ in enumerate(clips):
    parts.append(f"[{i}:v]trim={START}:{START+DUR},setpts=PTS-STARTPTS,scale=1080:1920:flags=lanczos[v{i}]")
    labels.append(f"[v{i}]")
fg = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(clips)}:v=1:a=0[out]"

mp4 = os.path.join(SRC, f"{NAME}.mp4")
ins = []
for c in clips: ins += ["-i", c]
subprocess.run(["ffmpeg", "-y", *ins, "-filter_complex", fg, "-map", "[out]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow",
    "-movflags", "+faststart", mp4], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("mp4 ✓", mp4)

# gif from the assembled mp4 (own palette)
pal = os.path.join(SRC, f"_{NAME}-pal.png")
subprocess.run(["ffmpeg", "-y", "-i", mp4, "-vf",
    "fps=12,scale=900:1600:flags=lanczos,palettegen=stats_mode=diff", pal],
    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
gif = os.path.join(SRC, f"{NAME}.gif")
subprocess.run(["ffmpeg", "-y", "-i", mp4, "-i", pal, "-lavfi",
    "fps=12,scale=900:1600:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3", gif],
    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.remove(pal)
print("gif ✓", gif)
