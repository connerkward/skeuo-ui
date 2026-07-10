#!/usr/bin/env python3
"""Web-size previews for round 2's 3x3 (theme x tier) grid. Idempotent."""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES2 = ["steam-porthole", "diablo-gothic", "wmp-quicksilver"]
TIERS = ["light", "medium", "heavy"]


def disp(src_path, dst_path, width=1000, quality=90):
    if os.path.exists(dst_path) or not os.path.exists(src_path):
        return False
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    if w > width:
        im = im.resize((width, round(h * width / w)), Image.LANCZOS)
    im.save(dst_path, quality=quality)
    return True


def main():
    made = 0
    for sid in THEMES2:
        for tier in TIERS:
            src = os.path.join(HERE, f"r2-{sid}-{tier}.png")
            dst = os.path.join(HERE, f"r2-{sid}-{tier}-disp.jpg")
            if disp(src, dst):
                made += 1
                print("made", dst)
            elif not os.path.exists(src):
                print("MISSING", src)
    print(f"{made} previews built")


if __name__ == "__main__":
    main()
