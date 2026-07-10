#!/usr/bin/env python3
"""
Ambient-video modified-area masking prototype (2026-07-10).

Question: can we reliably detect which pixels an i2v ambient-loop model actually
changed vs the source frame, and hard-composite the source back in wherever it
shouldn't have touched (the interactive control regions)?

Method:
  1. Extract every frame of a round-2 winner clip (Seedance 1.0 pro fast).
  2. touched_mask = per-frame absdiff(frame_i, true_source_frame) -> threshold ->
     morphological open (kills 1-2px compression/noise specks) -> union (OR) across
     all frames. This is "everywhere the model moved a pixel, at any point in the loop."
  3. protected_mask = union of the skin's *control* boxes (playpause, prev, next,
     repeat, queue, vol, seek, shuffle), mapped from `protected_regions.json` (hand-read
     off the actual frozen subject-<skin>-34.png -- see that file's `_note`: the live
     assets-<skin>/regions.json could NOT be used here because paint.png is gitignored
     and gets overwritten on every pipeline regen; the version live on disk when this
     ran had already been replaced by a different device design, confirmed by rendering
     its own boxes on its own paint.png crop and seeing they land on nothing this
     experiment's frames contain) into the video frame's pixel space (one measured
     anisotropic scale factor, see NOTE below).
  4. leak = touched_mask & protected_mask -- pixels inside a "must stay frozen" control
     that the model touched anyway.
  5. hard_composite: for every frame, force protected_mask pixels back to the true
     source frame (feathered blend at the mask edge to avoid a hard seam), keep the
     model's frame everywhere else. Re-loop with the existing xfade helper.

NOTE on the video's pixel space: the model resizes its 1152x1536 (3:4) input to its own
supported output grid -- here 832x1120 -- with a very slightly different scale on each
axis (0.7222 vs 0.7292, ~1% aspect drift). This is the known "i2v model reshapes to its
own grid" gotcha (ai-image-coords-rule); it's applied as a measured anisotropic scale,
not assumed uniform.
"""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
SCRATCH = Path(
    "/private/tmp/claude-501/-Users-conner-dev-skeuo-ui/611b9abe-9cc9-406e-b2cf-e61f122b3eae/scratchpad/maskexp"
)
SCRATCH.mkdir(parents=True, exist_ok=True)

CONTROL_KEYS = ["playpause", "prev", "next", "repeat", "queue", "vol", "seek", "shuffle"]

DIFF_THRESH = 22          # per-channel abs-diff threshold -> "touched"
MORPH_KERNEL = 3          # open kernel size (px) to kill compression-noise specks
FEATHER_PX = 6            # gaussian feather radius on the composite seam


def ffprobe_dims(path: Path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()[0]
    w, h = out.split("x")
    return int(w), int(h)


def extract_frames(video: Path, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    existing = sorted(outdir.glob("f*.png"))
    if existing:
        return existing
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vsync", "0",
         str(outdir / "f%04d.png")],
        check=True,
    )
    return sorted(outdir.glob("f*.png"))


def build_protected_mask(boxes: dict, subj34_w: int, subj34_h: int,
                          video_w: int, video_h: int) -> tuple[np.ndarray, dict]:
    """Union of hand-annotated control boxes, mapped subject34-normalized -> video px."""
    sx = video_w / subj34_w
    sy = video_h / subj34_h
    mask = np.zeros((video_h, video_w), dtype=np.uint8)
    boxes_video = {}
    for key in CONTROL_KEYS:
        rect = boxes.get(key)
        if not rect:
            continue
        nx1, ny1, nx2, ny2 = rect
        x1, y1 = int(round(nx1 * subj34_w * sx)), int(round(ny1 * subj34_h * sy))
        x2, y2 = int(round(nx2 * subj34_w * sx)), int(round(ny2 * subj34_h * sy))
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(video_w, x2), min(video_h, y2)
        mask[y1:y2, x1:x2] = 255
        boxes_video[key] = (x1, y1, x2, y2)
    return mask, boxes_video


def compute_touched_mask(frame_paths, source_ref: np.ndarray, dc_correct: bool = False) -> np.ndarray:
    """Naive method: per-frame absdiff vs the TRUE source frame, union across time.
    dc_correct subtracts each frame's global mean-shift vs the reference first, to strip
    a spatially-uniform relight/grade/compression-noise pulse before thresholding."""
    h, w = source_ref.shape[:2]
    kernel = np.ones((MORPH_KERNEL, MORPH_KERNEL), np.uint8)
    union = np.zeros((h, w), dtype=np.uint8)
    ref = source_ref.astype(np.float32)
    for fp in frame_paths:
        frame = cv2.imread(str(fp))
        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        if dc_correct:
            frame = frame - (frame.mean(axis=(0, 1)) - ref.mean(axis=(0, 1)))
        diff = np.abs(frame - ref).max(axis=2)  # per-pixel max over channels
        touched = (diff > DIFF_THRESH).astype(np.uint8) * 255
        touched = cv2.morphologyEx(touched, cv2.MORPH_OPEN, kernel)
        union = cv2.bitwise_or(union, touched)
    return union


def compute_touched_mask_stdev(frame_paths, w: int, h: int, std_thresh: float = 6.0) -> np.ndarray:
    """Alternative method (round-2's own judge): per-pixel TEMPORAL std-dev across all frames,
    grayscale, thresholded. Localizes genuine motion instead of a one-frame-vs-reference diff,
    so it isn't thrown by a single frame's compression noise -- only by *sustained* variance."""
    kernel = np.ones((MORPH_KERNEL, MORPH_KERNEL), np.uint8)
    stack = []
    for fp in frame_paths:
        frame = cv2.imread(str(fp))
        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
        stack.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32))
    stack = np.stack(stack, axis=0)
    std = stack.std(axis=0)
    touched = (std > std_thresh).astype(np.uint8) * 255
    touched = cv2.morphologyEx(touched, cv2.MORPH_OPEN, kernel)
    return touched, std


def hard_composite(frame_paths, source_ref: np.ndarray, protected_mask: np.ndarray, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    h, w = source_ref.shape[:2]
    # feathered alpha: 1.0 inside protected (force source), 0.0 outside (keep model frame)
    alpha = cv2.GaussianBlur(protected_mask.astype(np.float32) / 255.0, (0, 0), FEATHER_PX)
    alpha = alpha[..., None]
    for fp in frame_paths:
        frame = cv2.imread(str(fp))
        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        comp = frame * (1 - alpha) + source_ref.astype(np.float32) * alpha
        cv2.imwrite(str(outdir / fp.name), comp.astype(np.uint8))


def encode(frames_dir: Path, out_mp4: Path, fps: int):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i",
         str(frames_dir / "f%04d.png"), "-an", "-c:v", "libx264", "-crf", "16",
         "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)],
        check=True,
    )


def run_skin(skin: str, model_tag: str, all_boxes: dict):
    print(f"\n=== {skin} ({model_tag}) ===")
    boxes = all_boxes[skin]

    subj34 = cv2.imread(str(HERE / f"subject-{skin}-34.png"))
    subj34_h, subj34_w = subj34.shape[:2]

    # Prefer -v2 when it exists: for diablo-gothic that's round 2's PASS (glow-only 2nd
    # prompt); the bare filename is the 1st-prompt FAIL (whole tablet ignites) that's kept
    # only as a failure exhibit -- do not silently grade the FAIL clip as the skin's result.
    video = HERE / f"loop2-{model_tag}-{skin}-v2.mp4"
    if not video.exists():
        video = HERE / f"loop2-{model_tag}-{skin}.mp4"
    video_w, video_h = ffprobe_dims(video)
    print(f"video dims {video_w}x{video_h}  subject34 dims {subj34_w}x{subj34_h}  "
          f"scale=({video_w/subj34_w:.4f}, {video_h/subj34_h:.4f})  (anisotropic, confirms ai-image-coords-rule)")

    frames_dir = SCRATCH / f"frames-{skin}"
    frame_paths = extract_frames(video, frames_dir)
    fps_out = 24

    source_ref = cv2.resize(subj34, (video_w, video_h), interpolation=cv2.INTER_AREA)

    protected_mask, boxes_video = build_protected_mask(boxes, subj34_w, subj34_h, video_w, video_h)

    # Method A: naive absdiff(frame_i, true_source) union across time.
    touched_naive = compute_touched_mask(frame_paths, source_ref, dc_correct=False)
    # Method B: same but with per-frame global-mean (DC) correction first.
    touched_dc = compute_touched_mask(frame_paths, source_ref, dc_correct=True)
    # Method C: round-2's own judge -- per-pixel temporal std-dev across the clip.
    touched_std, std_map = compute_touched_mask_stdev(frame_paths, video_w, video_h)

    def stats(mask, label):
        leak = cv2.bitwise_and(mask, protected_mask)
        protected_px = int((protected_mask > 0).sum())
        touched_px = int((mask > 0).sum())
        leak_px = int((leak > 0).sum())
        leak_frac = leak_px / protected_px if protected_px else 0.0
        touched_frac = touched_px / (video_w * video_h)
        print(f"  [{label}] touched={touched_frac*100:.1f}% of frame  leak_into_controls={leak_frac*100:.2f}%")
        return leak, touched_frac, leak_frac

    print("comparing 3 detection methods (per verify-outputs-rule -- look before trusting):")
    leak_naive, tf_naive, lf_naive = stats(touched_naive, "A naive absdiff")
    leak_dc, tf_dc, lf_dc = stats(touched_dc, "B DC-corrected absdiff")
    leak_std, tf_std, lf_std = stats(touched_std, "C temporal-std")

    def save_overlay(mask, leak, tag):
        overlay = source_ref.copy()
        overlay[mask > 0] = (overlay[mask > 0] * 0.4 + np.array([0, 0, 255]) * 0.6).astype(np.uint8)
        contours, _ = cv2.findContours(protected_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (255, 200, 0), 2)
        overlay[leak > 0] = (0, 255, 255)
        # label legend + per-box control identity (label-overlays-rule)
        cv2.rectangle(overlay, (4, 4), (300, 74), (0, 0, 0), -1)
        cv2.putText(overlay, "red=touched  cyan=protected ctrl", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
        cv2.putText(overlay, "yellow=leak (touched AND ctrl)", (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
        cv2.putText(overlay, f"method={tag}", (10, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
        for key, (x1, y1, x2, y2) in boxes_video.items():
            cv2.putText(overlay, key, (x1 + 2, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 200, 0), 1)
        cv2.imwrite(str(HERE / f"mask-overlay-{skin}-{tag}.png"), overlay)

    save_overlay(touched_naive, leak_naive, "A-naive")
    save_overlay(touched_dc, leak_dc, "B-dc")
    save_overlay(touched_std, leak_std, "C-std")

    # Use method C (temporal std) for the hard composite -- it's the one that visually
    # localizes to real motion rather than flooding the whole frame (see write-up).
    per_control = {}
    for key, (x1, y1, x2, y2) in boxes_video.items():
        box_area = max(1, (x2 - x1) * (y2 - y1))
        box_leak = int((leak_std[y1:y2, x1:x2] > 0).sum())
        per_control[key] = round(box_leak / box_area, 4)
        print(f"    {key:10s} leak_frac(std)={per_control[key]:.3f}  box=({x1},{y1},{x2},{y2})")

    comp_dir = SCRATCH / f"comp-{skin}"
    raw_comp_mp4 = SCRATCH / f"rawcomp-{skin}.mp4"
    hard_composite(frame_paths, source_ref, protected_mask, comp_dir)
    encode(comp_dir, raw_comp_mp4, fps_out)
    subprocess.run(
        ["bash", str(HERE / "postloop.sh"), str(raw_comp_mp4),
         str(HERE / f"loop2-{model_tag}-{skin}-composited"), "xfade"],
        check=True,
    )

    return {
        "skin": skin,
        "model": model_tag,
        "video_dims": [video_w, video_h],
        "anisotropic_scale": [round(video_w / subj34_w, 4), round(video_h / subj34_h, 4)],
        "diff_thresh": DIFF_THRESH,
        "methods": {
            "A_naive_absdiff": {"touched_frac": round(tf_naive, 4), "leak_frac": round(lf_naive, 4)},
            "B_dc_corrected_absdiff": {"touched_frac": round(tf_dc, 4), "leak_frac": round(lf_dc, 4)},
            "C_temporal_std": {"touched_frac": round(tf_std, 4), "leak_frac": round(lf_std, 4)},
        },
        "protected_px": int((protected_mask > 0).sum()),
        "per_control_leak_frac_stdmethod": per_control,
    }


if __name__ == "__main__":
    import shutil
    # force a clean re-extract since we're correcting which diablo-gothic clip is used
    shutil.rmtree(SCRATCH / "frames-diablo-gothic", ignore_errors=True)
    all_boxes = json.loads((HERE / "protected_regions.json").read_text())
    results = []
    results.append(run_skin("steam-porthole", "seedancefast", all_boxes))
    results.append(run_skin("diablo-gothic", "seedancefast", all_boxes))
    out = HERE / "mask_experiment_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out}")
