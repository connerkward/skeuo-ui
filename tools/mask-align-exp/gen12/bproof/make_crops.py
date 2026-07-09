#!/usr/bin/env python3
"""Cut matched close-up crop pairs (gen12 device vs froggo render) for the page."""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

# boxes in FULL-RES pixel coords of each source image
CROPS = {
    "steam-porthole": {
        "gen12": "gen12-steam-porthole-device.png",   # 2304x2784
        "froggo": "froggo-steam-porthole.png",        # 3712x4608
        "pairs": [
            ("buttons",  "transport button cluster", (500, 1750, 1850, 2150), (1150, 2800, 2550, 3250)),
            ("knob",     "volume knob area",         (600, 2050, 1100, 2550), (500, 2450, 1100, 3250)),
            ("screen",   "porthole / display",       (690, 510, 1710, 1500),  (1400, 1500, 2300, 2350)),
        ],
    },
    "diablo-gothic": {
        "gen12": "gen12-diablo-gothic-device.png",
        "froggo": "froggo-diablo-gothic.png",
        "pairs": [
            ("buttons", "transport button cluster", (600, 390, 1680, 1290),  (750, 1500, 1950, 2700)),
            ("knob",    "volume knob area",         (450, 1200, 900, 1650),  (2250, 2275, 3000, 3100)),
            ("slider",  "seek slider",              (495, 1600, 1800, 1980), (750, 2750, 2100, 3150)),
        ],
    },
}

for sid, cfg in CROPS.items():
    g = Image.open(os.path.join(HERE, cfg["gen12"]))
    f = Image.open(os.path.join(HERE, cfg["froggo"]))
    for key, label, gbox, fbox in cfg["pairs"]:
        g.crop(gbox).save(os.path.join(HERE, f"crop-{sid}-{key}-gen12.png"))
        f.crop(fbox).save(os.path.join(HERE, f"crop-{sid}-{key}-froggo.png"))
        print(sid, key, "gen12", gbox, "froggo", fbox)
