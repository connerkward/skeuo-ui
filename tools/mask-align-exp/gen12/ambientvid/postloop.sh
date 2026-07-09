#!/bin/bash
# postloop.sh <in.mp4> <outbase> <mode>
# mode=native : already a seamless loop -> just re-encode to spec mp4 + webm
# mode=xfade  : crossfade loop: blend last XF seconds over first XF seconds
set -e
IN="$1"; OUT="$2"; MODE="$3"; XF=1.0
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
if [ "$MODE" = "xfade" ]; then
  # main part: 0 .. DUR-XF ; tail: last XF sec fades over head
  MAIN=$(python3 -c "print(f'{$DUR-$XF:.3f}')")
  ffmpeg -y -v error -i "$IN" -filter_complex "
    [0:v]trim=start=$XF:end=$MAIN,setpts=PTS-STARTPTS[body];
    [0:v]trim=start=$MAIN,setpts=PTS-STARTPTS[tail];
    [0:v]trim=end=$XF,setpts=PTS-STARTPTS[head];
    [tail][head]xfade=transition=fade:duration=$XF:offset=0[loopseg];
    [body][loopseg]concat=n=2:v=1[out]" \
    -map "[out]" -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -movflags +faststart "${OUT}.mp4"
else
  ffmpeg -y -v error -i "$IN" -an -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -movflags +faststart "${OUT}.mp4"
fi
ffmpeg -y -v error -i "${OUT}.mp4" -c:v libvpx-vp9 -crf 32 -b:v 0 -an "${OUT}.webm"
