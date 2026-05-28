#!/usr/bin/env python3
"""
Extract per-style assets from styled idle images:
  - Panel 9-slice atlases (4 corners + 4 edges composed; center transparent)
  - Per-button sprites at known hotspot coords
  - A clean chrome tile for tileable background
"""
from PIL import Image, ImageChops
from pathlib import Path
import json
import sys

REPO = Path(__file__).resolve().parents[1]
REFS = REPO / "assets" / "refs"
OUT  = REPO / "public" / "sprites"

# Per-style refs (idle = unpressed / clean)
STYLES = ["pipboy", "winamp", "ipod", "nautical", "cyberpunk"]

# Panel y-ranges relative to image height (all images share the canonical layout)
PANEL_RANGES = {
    "main":     (0.000, 0.380),
    "eq":       (0.385, 0.665),
    "playlist": (0.670, 1.000),
}

# Hotspot map (normalized coords) — same component coords for all styles
# (idle images preserve the canonical layout exactly)
HOTSPOTS = [
    # main panel - transport
    {"id": "prev",     "x": 0.073, "y": 0.290, "w": 0.075, "h": 0.075},
    {"id": "play",     "x": 0.155, "y": 0.286, "w": 0.080, "h": 0.082},
    {"id": "pause",    "x": 0.245, "y": 0.290, "w": 0.065, "h": 0.075},
    {"id": "stop",     "x": 0.318, "y": 0.290, "w": 0.065, "h": 0.075},
    {"id": "next",     "x": 0.389, "y": 0.290, "w": 0.075, "h": 0.075},
    {"id": "eject",    "x": 0.476, "y": 0.290, "w": 0.050, "h": 0.070},
    {"id": "shuffle",  "x": 0.555, "y": 0.290, "w": 0.140, "h": 0.072},
    {"id": "repeat",   "x": 0.705, "y": 0.290, "w": 0.060, "h": 0.072},
    {"id": "eq-on",    "x": 0.087, "y": 0.432, "w": 0.045, "h": 0.045},
    {"id": "eq-auto",  "x": 0.137, "y": 0.432, "w": 0.060, "h": 0.045},
    {"id": "presets",  "x": 0.857, "y": 0.432, "w": 0.070, "h": 0.045},
    # playlist panel
    {"id": "pl-add",   "x": 0.083, "y": 0.913, "w": 0.045, "h": 0.050},
    {"id": "pl-rem",   "x": 0.135, "y": 0.913, "w": 0.045, "h": 0.050},
    {"id": "pl-sel",   "x": 0.188, "y": 0.913, "w": 0.045, "h": 0.050},
    {"id": "pl-misc",  "x": 0.240, "y": 0.913, "w": 0.055, "h": 0.050},
    {"id": "pl-play",  "x": 0.555, "y": 0.913, "w": 0.050, "h": 0.052},
    {"id": "pl-pause", "x": 0.610, "y": 0.913, "w": 0.045, "h": 0.052},
    {"id": "pl-stop",  "x": 0.660, "y": 0.913, "w": 0.045, "h": 0.052},
    {"id": "pl-next",  "x": 0.710, "y": 0.913, "w": 0.050, "h": 0.052},
    {"id": "pl-list",  "x": 0.905, "y": 0.910, "w": 0.070, "h": 0.060},
]

# Chrome tile sample regions: clean chrome patches inside each panel
# (frame-only image has clean material inside the panels, so we can sample the center)
CHROME_TILE_SAMPLES = {
    "main":     (0.55, 0.16, 0.10, 0.10),   # center of main panel
    "eq":       (0.55, 0.52, 0.10, 0.08),   # center of eq panel
    "playlist": (0.55, 0.80, 0.10, 0.08),   # center of playlist panel
}


def crop_norm(img: Image.Image, x: float, y: float, w: float, h: float) -> Image.Image:
    W, H = img.size
    return img.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))


def extract_panel(img: Image.Image, name: str) -> Image.Image:
    y0, y1 = PANEL_RANGES[name]
    H = img.size[1]
    return img.crop((0, int(y0 * H), img.size[0], int(y1 * H)))


def build_nine_slice_atlas(panel_img: Image.Image, slice_px: int = 60) -> Image.Image:
    """Build a 9-slice atlas: keep the outer `slice_px` ring, blank the center transparently.
    Result is the same dimensions as the panel image, but the center is transparent.
    Used as border-image-source with `border-image-slice: slice_px` (no fill).
    """
    W, H = panel_img.size
    out = panel_img.convert("RGBA").copy()
    # Make center transparent
    from PIL import ImageDraw
    draw = ImageDraw.Draw(out)
    # rectangle (inside) bbox: (slice_px, slice_px, W - slice_px, H - slice_px)
    draw.rectangle((slice_px, slice_px, W - slice_px, H - slice_px), fill=(0, 0, 0, 0))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}

    for style in STYLES:
        idle_path = REFS / f"{style}-idle.png"
        frame_path = REFS / f"{style}-frame.png"
        if not idle_path.exists():
            print(f"!! missing {idle_path}", file=sys.stderr)
            continue
        idle = Image.open(idle_path).convert("RGBA")
        # If we have a frame-only asset, use it for chrome borders/tiles; else fall back to idle.
        frame = Image.open(frame_path).convert("RGBA") if frame_path.exists() else idle
        W, H = idle.size
        print(f"[{style}] idle={W}x{H} frame={'ok' if frame_path.exists() else 'fallback to idle'}")

        style_out = OUT / style
        style_out.mkdir(exist_ok=True)
        manifest[style] = {"buttons": {}, "panels": {}}

        # --- Panels: save full panel chrome (no atlas — used as background-size:100% 100%) ---
        for pname in PANEL_RANGES:
            panel = extract_panel(frame, pname)
            panel.save(style_out / f"panel-{pname}.png")
            manifest[style]["panels"][pname] = {
                "src": f"/sprites/{style}/panel-{pname}.png",
                "w": panel.size[0],
                "h": panel.size[1],
            }

        # --- Chrome tile per panel (sampled from frame-only chrome interior) ---
        for pname, (tx, ty, tw, th) in CHROME_TILE_SAMPLES.items():
            tile = crop_norm(frame, tx, ty, tw, th)
            tile.save(style_out / f"tile-{pname}.png")
            manifest[style]["panels"][pname]["tile"] = f"/sprites/{style}/tile-{pname}.png"

        # --- Button sprites (from idle image, where the components are visible) ---
        for h in HOTSPOTS:
            spr = crop_norm(idle, h["x"], h["y"], h["w"], h["h"])
            spr.save(style_out / f"{h['id']}.png")
            manifest[style]["buttons"][h["id"]] = {
                "src": f"/sprites/{style}/{h['id']}.png",
                "w": spr.size[0],
                "h": spr.size[1],
            }

    # Emit manifest
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest -> {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
