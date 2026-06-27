---
name: clip-finder
description: Find and extract a single relevant SHOT/CLIP from inside a longer video. Three locators — visual (PySceneDetect+CLIP, free/local), semantic (Twelve Labs), and dialogue (subtitle file or OpenSubtitles). Use for the "documentary → one clip" problem: you have a film/long video and need just the robot-welding shot, or the line "I'll be back", not the whole thing. Pairs with web-media (which finds the film).
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# clip-finder

`web-media` finds whole videos; **clip-finder finds the *shot inside* one.**
Archival/long videos are documentaries, not clips — this cuts the relevant moment out.

## Prerequisites (local locators)

`clipfind.py` and `clip_subtitle.py` are **not standalone** — they borrow muser's Python env for CLIP / PySceneDetect. On a fresh machine: `~/dev/Muser` must exist (the `muser` skill clones it), then run them as `cd ~/dev/Muser && uv run python ~/dev/central/skills/clip-finder/<script>` (see Usage). `clip_twelvelabs.py` is independent — only needs `TWELVELABS_API_KEY` in `central/.env` + `pip install twelvelabs`. `ffmpeg` required for all three.

## Locators (same job — find a moment — different tradeoffs)

| | `clipfind.py` — PySceneDetect + CLIP (local) | `clip_twelvelabs.py` — Twelve Labs marengo3.0 (cloud) |
|---|---|---|
| Cost | free, local, offline | API key, ~indexing-minute/min of video (600 free) |
| How | cut shots → CLIP-rank keyframes → ffmpeg clip | index video → semantic moment search → ffmpeg clip |
| Signal | **similarity score** (confidence gate) | rank order (no score) |
| Modality | pure visual (single keyframe/shot) | visual **+ audio + on-screen text (OCR)** |
| Best when | visual shots, you want a confidence threshold, free | semantic/audio/text recall, ready-made moments |

### Third locator — subtitle / dialogue (`clip_subtitle.py`)

Locate a moment by **dialogue**: match a line in the film's subtitles → timestamp →
frame + clip. Subtitles from a local file (`--subs`) or **OpenSubtitles** (`--fetch`).

```bash
# local subtitle file
python clip_subtitle.py VIDEO.mp4 "I'll be back" --subs SUBS.srt -k 5
# fetch subs by movie title from OpenSubtitles
python clip_subtitle.py VIDEO.mp4 "I'll be back" --fetch "Terminator 2" --lang en
```
- OpenSubtitles creds in `central/.env`: `OPENSUBTITLES_API_KEY`, `OPENSUBTITLES_USERNAME`,
  `OPENSUBTITLES_PASSWORD` (the script logs in programmatically; free tier ≈ 5–20 dl/day).
- You always supply the **video** — point it at a film you hold (e.g. the Emby library
  from `media-download`). No API serves frames of commercial films you don't own.
- Sub-sync caveat: a fetched `.srt` is timed to *some* release; if it drifts from your
  copy, pick another result or apply an offset.

## Usage

```bash
# local (run from the muser repo so CLIP + scenedetect are importable)
cd ~/dev/Muser && uv pip install "scenedetect[opencv]"   # one-time
uv run python ~/dev/central/skills/clip-finder/clipfind.py VIDEO.mp4 \
    "a robot arm welding a car body with sparks" -k 5 --out /tmp/clip --min-sim 0.12

# cloud (needs TWELVELABS_API_KEY in central/.env, pip install twelvelabs)
python ~/dev/central/skills/clip-finder/clip_twelvelabs.py VIDEO.mp4 \
    "robot welding sparks" -k 5 --out /tmp/clip-tl
```
Both write cut `.mp4` clips + `results.json` (rank, start, end, sim/clip). ffmpeg required.
Twelve Labs requires video ≥480×360 — upscale first if smaller (`ffmpeg -vf scale=640:480`).

## What the benchmark showed (Master Hands 1936 vs a modern robot-welding line)

- **When the target shot is present** (modern robot welding), both backends independently
  picked the **same #1 shot** (the sparks @ 1:30) — strong cross-method agreement.
- **When it's absent** (Master Hands is parts-manufacturing, no final line), both return
  nearest-industrial shots and CLIP's top similarity stays low (~0.11 vs ~0.16 when present).
  **So the CLIP score is a real "match present?" gate** — threshold with `--min-sim` (~0.12)
  for agent auto-pick; below it, treat as "no confident clip found."
- **Twelve Labs reads on-screen text** — for a text-heavy film it surfaced intertitle cards
  ("…assembly plants…cars are made") as matches. Great for "where is X discussed," but a
  false positive for a purely *visual* shot. Filter/penalize text-card hits in agent mode.

## Recommendation

- **Agent auto-pick:** `clipfind.py` (local) with `--min-sim` gating — free, precise, and
  the score lets you refuse when there's no real match (the precision the agent needs).
- **Semantic / "find where they talk about X" / audio:** Twelve Labs.
- They're complementary: run local first (free + thresholded); escalate to TL when the
  local score is borderline or you need audio/text understanding.
