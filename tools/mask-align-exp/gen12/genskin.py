#!/usr/bin/env python3
"""genskin — parameterized skin generator for the gen12 batch.

Reads a THEME SPEC json and produces a joint paint+mask via one nano-banana-pro edit, then
splits it. All the *structural* prompt machinery is fixed (backdrop keying, ZERO RESIDUE,
empty-before-assembly, EXACT FIT, top-down orthographic, no-guide-colours, single-row strip);
only the THEME (materials/colours/form) and per-skin palette vary. Two modes:

  * templated   — a clean LAYOUT-ONLY blueprint (role-scaled circle buttons + knob + seek groove
                  + shuffle slot + album-art & visualizer rects), icons named in the prompt (NOT
                  drawn). One of two archetypes: 'vpod' (vertical) or 'hcapsule' (horizontal).
  * templateless — scaffold canvas only (flat backdrop + strip divider + black right column, ZERO
                  control geometry). Roster + colour map + congruence stated textually; extract12
                  recovers everything post-hoc from the returned mask.

Roster (10, all Spotify-Web-API capable): playpause, prev, next, repeat, queue (baked icon
buttons); vol (knob); seek (slider); shuffle (2-state toggle); visualizer, album_art (regions).

Spec json fields: {id, title, mode: templated|templateless, layout: vpod|hcapsule,
  palette:{name:[r,g,b],...}, material_is_dark: bool, theme_prompt: "...", seed}.
Usage: python3 genskin.py <spec.json> [--blueprint-only]   → writes gen12/assets-<id>/
"""
import os, re, io, sys, json, time, math, base64, subprocess
import requests
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "fal-ai/gemini-3-pro-image-preview/edit"

# PAINT_VERTEX: call the SAME Gemini image model direct via Vertex AI instead of fal's wrapper —
# fal charges $0.30/img at 4K (verified live on fal.ai, 2x its $0.15 1K/2K rate) vs Vertex's
# $0.24/img at 4K (2000 output tokens x $120/1M, verified on the Vertex AI pricing page) — Vertex
# is ~20% cheaper AND removes the dependency on fal's billing state (see generation-spend-rule).
# Flip only BETWEEN batches. ON since 2026-07-10 (user call; verified live gen, ~20% cheaper).
PAINT_VERTEX = True
VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")  # same project proven working by bproof/run_bproof_vertex.py
VERTEX_MODEL = "gemini-3-pro-image-preview"  # same underlying model fal proxies at MODEL above
VERTEX_URL = (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/global/"
              f"publishers/google/models/{VERTEX_MODEL}:generateContent")
COL_W, H, DEV_H = 1200, 1920, 1440
DEVF = DEV_H / H

BUTTONS = ["playpause", "prev", "next", "repeat", "queue"]
KNOB, SLIDER, TOGGLE = "vol", "seek", "shuffle"
REGIONS = ["visualizer", "album_art"]
CONTROLS = BUTTONS + [KNOB, SLIDER, TOGGLE] + REGIONS
ROLES = {**{b: "button" for b in BUTTONS}, KNOB: "knob", SLIDER: "slider",
         TOGGLE: "toggle", **{r: "region" for r in REGIONS}}
ICON = {  # named in the prompt so the model embosses the right glyph — never drawn in the template
    "playpause": "a PLAY triangle (right-pointing) merged with pause bars",
    "prev": "a SKIP-BACK double-triangle / rewind chevrons",
    "next": "a SKIP-FORWARD double-triangle / fast-forward chevrons",
    "repeat": "a REPEAT loop (two arrows chasing in a circle)",
    "queue": "a QUEUE / playlist icon (stacked horizontal lines)",
    "vol": "a VOLUME knob (top face, knurled rim, pointer notch)",
    "seek": "the SEEK progress slider thumb (wide low grip)",
    "shuffle": "a SHUFFLE icon (two crossing arrows)",
    "visualizer": "a VISUALIZER / spectrum-analyzer display window",
    "album_art": "an ALBUM ART / cover display window",
}
# congruence contract — sizes shared between device slot and strip anchor (px on COL_W x DEV_H)
BTN_R, PLAY_R, KNOB_R = 74, 104, 84
GROOVE_W, GROOVE_H, THUMB_W, THUMB_H, THUMB_R = 640, 76, 150, 96, 44
TOG_W, TOG_H, TOG_R = 120, 178, 40
ART_W, ART_H, VIZ_W, VIZ_H = 560, 300, 640, 156

# ---------------------------------------------------------------- layout archetypes (templated)
# each entry: name -> {control: (fx, fy, kind, *size)}   fx,fy = fraction of (COL_W, DEV_H)
def _vpod():
    return {
        "album_art": (0.50, 0.15, "rect", ART_W, ART_H),
        "visualizer": (0.50, 0.335, "rect", VIZ_W, VIZ_H),
        "seek": (0.50, 0.47, "groove"),
        "prev": (0.28, 0.60, "btn", BTN_R), "playpause": (0.50, 0.60, "btn", PLAY_R),
        "next": (0.72, 0.60, "btn", BTN_R),
        "repeat": (0.24, 0.75, "btn", BTN_R), "vol": (0.42, 0.76, "knob"),
        "shuffle": (0.60, 0.76, "tog"), "queue": (0.78, 0.75, "btn", BTN_R),
    }
def _hcapsule():
    return {
        "album_art": (0.28, 0.30, "rect", ART_W, int(ART_H * 1.15)),
        "visualizer": (0.28, 0.60, "rect", VIZ_W, VIZ_H),
        "seek": (0.30, 0.82, "groove"),
        "prev": (0.66, 0.28, "btn", BTN_R), "playpause": (0.78, 0.40, "btn", PLAY_R),
        "next": (0.90, 0.28, "btn", BTN_R),
        "repeat": (0.66, 0.55, "btn", BTN_R), "vol": (0.90, 0.58, "knob"),
        "shuffle": (0.78, 0.68, "tog"), "queue": (0.66, 0.78, "btn", BTN_R),
    }
LAYOUTS = {"vpod": _vpod, "hcapsule": _hcapsule}

NAMEMAP = {(0, 0, 255): "PURE BLUE", (0, 128, 255): "AZURE BLUE", (0, 255, 255): "CYAN",
           (0, 128, 128): "DARK TEAL", (0, 255, 128): "SPRING GREEN", (0, 255, 0): "PURE GREEN",
           (128, 255, 0): "CHARTREUSE", (128, 0, 255): "VIOLET-PURPLE", (255, 0, 255): "MAGENTA",
           (128, 128, 255): "PERIWINKLE", (128, 255, 128): "PALE MINT", (128, 0, 128): "DEEP PURPLE",
           (0, 0, 128): "NAVY", (255, 0, 128): "ROSE PINK", (128, 255, 255): "PALE AQUA",
           (255, 128, 255): "ORCHID", (0, 128, 0): "FOREST GREEN", (255, 0, 0): "PURE RED",
           (255, 128, 0): "ORANGE", (128, 128, 0): "OLIVE", (255, 255, 0): "YELLOW"}
def cname(c): return NAMEMAP.get(tuple(c), f"RGB{tuple(c)}")


def pick_keys(palette, n=10):
    cands = [(r, g, b) for r in (0, 128, 255) for g in (0, 128, 255) for b in (0, 128, 255)
             if (max((r, g, b)) - min((r, g, b))) > 55 and max((r, g, b)) > 90]
    scored = []
    for c in cands:
        dm = min(math.dist(c, p) for p in palette.values())
        if dm >= 120: scored.append((round(dm, 1), c))
    scored.sort(key=lambda t: (-t[0], t[1]))
    keys = [c for _, c in scored[:n]]
    if len(keys) < n:
        sys.exit(f"PALETTE TOO GREEDY: only {len(keys)}/{n} guide keys survive >=120 from all majors. "
                 f"Declare fewer/darker palette majors.")
    print(f"[keys] {len(keys)} guide keys, min-vs-palette {scored[n-1][0]:.0f} (>=120 ok)")
    return keys


def poly_circle(cx, cy, r, k=32):
    return [(cx + r * math.cos(2 * math.pi * i / k), cy + r * math.sin(2 * math.pi * i / k)) for i in range(k)]


def load_fal():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")


def upload(FAL, p):
    init = requests.post("https://rest.alpha.fal.ai/storage/upload/initiate",
        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
        json={"file_name": os.path.basename(p), "content_type": "image/png"}).json()
    requests.put(init["upload_url"], headers={"Content-Type": "image/png"}, data=open(p, "rb").read())
    return init["file_url"]


def edit(FAL, url, prompt, seed):
    job = requests.post(f"https://queue.fal.run/{MODEL}",
        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
        json={"prompt": prompt, "image_urls": [url], "resolution": "4K", "aspect_ratio": "5:4",
              "output_format": "png", "num_images": 1, "seed": seed}).json()
    t0 = time.time()
    while True:
        s = requests.get(job["status_url"], headers={"Authorization": f"Key {FAL}"}).json().get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR") or time.time() - t0 > 420: raise RuntimeError(f"fal {s}")
        time.sleep(4)
    r = requests.get(job["response_url"], headers={"Authorization": f"Key {FAL}"}).json()
    return requests.get(r["images"][0]["url"]).content


def edit_vertex(bp_path, prompt, seed, aspect="5:4"):
    """Same nano-banana-pro edit as edit(), direct via Vertex AI (no fal). Same proven pattern
    as abshape/genskin_ab.py:edit_vertex() — that copy already ran 4 real generations today on
    this project/auth; this is the mainline-genskin port of it (gcloud user-auth access token,
    no ADC file needed). Returns raw output PNG bytes, same contract as edit()."""
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    b64 = base64.b64encode(open(bp_path, "rb").read()).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "seed": seed,
            "candidateCount": 1,
            "imageConfig": {"aspectRatio": aspect, "imageSize": "4K"},
        },
    }
    r = requests.post(VERTEX_URL, headers={"Authorization": f"Bearer {tok}",
                                            "Content-Type": "application/json"},
                       json=body, timeout=420)
    if r.status_code != 200:
        raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:500]}")
    for part in r.json()["candidates"][0]["content"]["parts"]:
        d = part.get("inlineData") or part.get("inline_data") or {}
        if d.get("data"):
            return base64.b64decode(d["data"])
    raise RuntimeError("vertex: no image part in response")


def main():
    spec = json.load(open(sys.argv[1]))
    sid = spec["id"]; mode = spec["mode"]; seed = spec.get("seed", 71)
    palette = {k: tuple(v) for k, v in spec["palette"].items()}
    dark = spec.get("material_is_dark", False)
    BG = (235, 235, 238) if dark else (18, 18, 24)
    OUT = os.path.join(HERE, f"assets-{sid}"); os.makedirs(OUT, exist_ok=True)
    keys = pick_keys(palette)
    KEYS = dict(zip(CONTROLS, keys))
    layout = LAYOUTS[spec.get("layout", "vpod")]() if mode == "templated" else None

    # -------- blueprint --------
    W = COL_W * 2
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    d.rectangle([COL_W, 0, W, H], fill=(0, 0, 0)); d.line([COL_W, 0, COL_W, H], fill=(70, 70, 74), width=3)
    d.line([0, DEV_H, COL_W, DEV_H], fill=(70, 70, 74), width=3)
    template = {}
    if mode == "templated":
        # neutral placeholder body: generous rounded blob covering all control positions
        d.rounded_rectangle([70, 60, COL_W - 70, DEV_H - 40], radius=140, fill=(140, 140, 146))
        for name, spec_l in layout.items():
            fx, fy, kind, *sz = spec_l
            x, y = COL_W * fx, DEV_H * fy
            col = KEYS[name]
            if kind == "btn":
                r = sz[0]; d.line(poly_circle(x, y, r) + [poly_circle(x, y, r)[0]], fill=col, width=12)
            elif kind == "knob":
                d.ellipse([x - KNOB_R, y - KNOB_R, x + KNOB_R, y + KNOB_R], outline=col, width=12)
            elif kind == "groove":
                d.rounded_rectangle([x - GROOVE_W / 2, y - GROOVE_H / 2, x + GROOVE_W / 2, y + GROOVE_H / 2], radius=35, outline=col, width=13)
            elif kind == "tog":
                d.rounded_rectangle([x - TOG_W / 2, y - TOG_H / 2, x + TOG_W / 2, y + TOG_H / 2], radius=TOG_R, outline=col, width=13)
            elif kind == "rect":
                w, hh = sz; d.rounded_rectangle([x - w / 2, y - hh / 2, x + w / 2, y + hh / 2], radius=28, outline=col, width=13)
            template[name] = [fx, fy * DEVF]
        # strip cells clone device geometry (vol cap, seek thumb, shuffle OFF, shuffle ON)
        sy = DEV_H + (H - DEV_H) // 2
        cells = [(KNOB, "circle"), (SLIDER, "thumb"), (TOGGLE, "tog"), (TOGGLE, "tog")]
        for i, (k, shp) in enumerate(cells):
            cx = COL_W * (0.13 + 0.20 * i); col = KEYS[k]
            if shp == "circle": d.ellipse([cx - KNOB_R, sy - KNOB_R, cx + KNOB_R, sy + KNOB_R], outline=col, width=12)
            elif shp == "thumb": d.rounded_rectangle([cx - THUMB_W / 2, sy - THUMB_H / 2, cx + THUMB_W / 2, sy + THUMB_H / 2], radius=THUMB_R, outline=col, width=12)
            else: d.rounded_rectangle([cx - TOG_W / 2, sy - TOG_H / 2, cx + TOG_W / 2, sy + TOG_H / 2], radius=TOG_R, outline=col, width=12)
    else:
        # templateless: scaffold only — a faint 'device area' hint box + strip band, NO controls
        d.text((90, 40), "", fill=(0, 0, 0))
    bp = os.path.join(OUT, "blueprint.png"); img.save(bp)

    # -------- results.json (colours + roles + optional template) --------
    defsz = {KNOB: 2 * KNOB_R / COL_W, SLIDER: GROOVE_H / COL_W, TOGGLE: TOG_W / COL_W,
             **{b: (2 * PLAY_R if b == "playpause" else 2 * BTN_R) / COL_W for b in BUTTONS}}
    res = {"id": sid, "mode": mode, "seed": seed, "model": MODEL, "backdrop": list(BG),
           "palette": {k: list(v) for k, v in palette.items()},
           "keys": {k: list(v) for k, v in KEYS.items()},
           "keyNames": {k: cname(v) for k, v in KEYS.items()},
           "buttons": BUTTONS, "sprites": [KNOB, SLIDER, TOGGLE], "extras": REGIONS,
           "roles": ROLES, "defsz": defsz, "devFrac": DEVF,
           "lighting": spec.get("lighting", {}),  # director-authored emissive/lighting (pbr_pass)
           "template": template if mode == "templated" else {}}
    if mode == "templated":
        aa = layout["album_art"]; res["album_art_rect"] = [aa[0] - aa[3] / COL_W / 2, (aa[1] - aa[4] / DEV_H / 2) * DEVF, aa[3] / COL_W, aa[4] / DEV_H * DEVF]
        vz = layout["visualizer"]; res["visualizer_rect"] = [vz[0] - vz[3] / COL_W / 2, (vz[1] - vz[4] / DEV_H / 2) * DEVF, vz[3] / COL_W, vz[4] / DEV_H * DEVF]
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)

    # -------- prompt --------
    def kn(c): return cname(KEYS[c])
    def rgb(c): return ",".join(str(v) for v in KEYS[c])
    NO_LIST = ", ".join(f"NO {kn(c).lower()}" for c in CONTROLS)
    roster_desc = "; ".join(f"{kn(c)} = {ICON[c]}" for c in CONTROLS)
    STRUCT = spec["theme_prompt"].strip()
    mask_lines = "; ".join(
        f"{kn(c)} region filled {rgb(c)}" for c in CONTROLS)
    if mode == "templated":
        left_layout = ("The LEFT column is a BLUEPRINT: a neutral grey placeholder body with COLOURED "
            "OUTLINE guides marking each control's EXACT position, size and shape, plus a bottom SPRITE-STRIP "
            "band with 4 loose parts (volume knob cap, seek slider thumb, shuffle switch OFF, shuffle switch ON). "
            "Each guide's colour maps to a control: " + roster_desc + ". KEEP EVERY CONTROL AT THE EXACT POSITION, "
            "SIZE AND SHAPE OF ITS GUIDE — do NOT move, resize, swap, rearrange, add or drop any control (their "
            "layout is locked). BUT the grey body is ONLY a rough placeholder showing WHERE the controls sit — you "
            "are FREE and STRONGLY ENCOURAGED to sculpt a BOLD, DISTINCTIVE, ASYMMETRIC, theme-appropriate outer "
            "HOUSING around them: an ornate, characterful, sculpted form with a memorable silhouette (organic curves, "
            "wings, pods, fins, greebles, ornament, asymmetry) — NOT a plain rounded rectangle, NOT a generic slab or "
            "pod. Reshape the outer silhouette DRAMATICALLY to suit the theme; ONLY the control positions stay fixed. "
            "The coloured outlines are ALIGNMENT MARKINGS (like masking tape) and MUST be completely removed.")
    else:
        left_layout = ("The LEFT column has a thin horizontal DIVIDER LINE near the bottom: everything ABOVE it is "
            "the DEVICE AREA, the thin band BELOW it is the SPRITE STRIP. YOU design the device from scratch. Paint "
            "EXACTLY ONE single media player filling the device area (do NOT draw two devices, variants, copies, "
            "alternates, or a size range — ONE player only), containing EXACTLY these controls, each a distinct "
            "recognizable element, each appearing EXACTLY ONCE: " + roster_desc + ". Give the housing a BOLD, "
            "DISTINCTIVE, ASYMMETRIC silhouette with real character — an ornate, sculpted, memorable form (curves, "
            "wings, pods, fins, greebles, ornament) that suits the theme, NOT a plain pod, slab or rectangle. "
            "Arrange the controls in one attractive layout of your choosing. In the bottom strip band below the divider, paint "
            "EXACTLY FOUR loose parts in ONE row left-to-right: volume knob cap, seek slider thumb, shuffle switch "
            "OFF, shuffle switch ON — and NOTHING else in the strip.")

    prompt = (
        "Two side-by-side columns of identical size, output at 5:4. ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO "
        "NUMBERS, NO CAPTIONS and NO LABELS anywhere in EITHER column — not under controls, not on the strip, not "
        "a title, nothing; the device is wordless, identified by icons and shapes only. " + left_layout + "\n"
        "THEME (design the finished device in THIS style — you own all materials, colours, form, lighting): "
        + STRUCT + "\n"
        "Fill BOTH columns keeping the device+strip layout IDENTICAL so they overlay pixel-for-pixel.\n"
        "LEFT column — the FINISHED, richly 3D, tactile, skeuomorphic media player and its loose parts, in the "
        "theme above. CRITICAL for cutout: the BACKDROP around the device and BEHIND every strip part is a FLAT, "
        f"PERFECTLY UNIFORM {'pale grey-white' if dark else 'near-black charcoal'} tone (RGB ~{BG[0]},{BG[1]},{BG[2]}) "
        "— a separate keyed-out backdrop with NO gradient/texture/vignette that strongly contrasts the body; the "
        "device must never approach the backdrop tone.\n"
        "  • The finished device uses ONLY its own theme materials/colours — NONE of the guide colours. ABSOLUTELY "
        f"{NO_LIST} anywhere in the LEFT column; the guide colours exist ONLY in the RIGHT mask.\n"
        "  • ZERO RESIDUE (CRITICAL) — the coloured guide outline around EVERY control is a temporary alignment "
        "marking, NOT part of the design. It must VANISH completely. Each finished BUTTON is ONE solid piece of the "
        "device's own material with absolutely NO coloured ring, rim, bezel, halo, outline or edge-tint around it — "
        "if a button has a coloured ring, it is WRONG. Likewise the album-art and visualizer windows have NO "
        "coloured frame (just a dark recessed glass panel flush in the body), and no socket/groove/slot has any "
        "coloured rim. Paint the body/button material seamlessly OVER where each guide outline was.\n"
        "  • The 5 transport/function BUTTONS (play/pause, previous, next, repeat, queue) are raised, glossy, "
        "tactile control facets set into the body, EACH clearly bearing its icon EMBOSSED/engraved in relief: "
        + "; ".join(f"{ICON[c]}" for c in BUTTONS) + ". Shape + icon + relief only; no text labels; no coloured rim.\n"
        "  • BUTTON COLOURS COME FROM THE THEME, NEVER FROM THE GUIDES: the guide colour of a button marks its "
        "POSITION ONLY — the finished button's material/fill must NOT inherit, echo or be tinted toward its guide "
        "colour in ANY way (no red play because its guide was red, no magenta next, etc). ALL five buttons are made "
        "of the device's OWN theme materials/palette, coloured consistently with each other and the body. If any "
        "button's colour visibly matches its guide colour, the output is WRONG.\n"
        "  • THE SINGLE MOST IMPORTANT RULE — EVERY MOVING-PART CAVITY IS EMPTY. The volume knob socket is a bare "
        "round HOLE showing only its dark recessed floor (NO knob, NO cap, NO dome, NO dial, NO pointer — nothing "
        "installed). The seek slider groove is an EMPTY DARK RECESSED CHANNEL cut into the body (NO thumb, NO grip, "
        "NO handle, NO fill — it is NOT a coloured or filled bar, it is a hollow dark slot). The shuffle switch slot "
        "is an EMPTY DARK rounded well (NO switch, NO lever, NO toggle installed). The device is photographed BEFORE "
        "ASSEMBLY: those parts exist ONLY in the bottom sprite strip and have NOT been installed yet. Do NOT colour "
        "the empty wells — neutral DARK recesses only. If ANY of the three cavities (knob socket, seek slot, "
        "shuffle slot) contains ANY part or any fill colour, the output is WRONG and must be redone.\n"
        "  • SEEK IS JUST AN EMPTY SLOT — treat the seek as a plain EMPTY recessed horizontal SLOT/CHANNEL only, "
        "NOT a functioning slider. Absolutely do NOT bake a slider thumb, grip, knob, handle, bar, fill, track-fill "
        "or progress indicator into it — it is a bare dark empty channel; the thumb is a SEPARATE loose part in the "
        "strip. A seek slot with anything riding in it is WRONG.\n"
        "  • The ALBUM-ART window and the VISUALIZER window are BLANK, DARK, EMPTY recessed glass SCREENS — flat "
        "unlit dark glass panels only, with NOTHING inside them: NO baked spectrum/equalizer bars, NO album cover "
        "or artwork, NO waveform, NO icons, NO text, NO content whatsoever. They are OFF screens; the app draws "
        "their live content later. If either window contains any baked graphics, it is WRONG.\n"
        "  • SPRITE STRIP — EXACTLY FOUR finished parts in ONE horizontal row, left→right: volume knob cap, seek "
        "slider thumb, shuffle switch OFF, shuffle switch ON — in the device's own materials, outlines removed, on "
        f"the flat {'pale' if dark else 'charcoal'} backdrop.\n"
        "  • THE SEEK STRIP PART IS THE LOOSE THUMB/GRIP **ONLY** — the small handle piece a finger slides, shown "
        "by itself on the backdrop, like a spare part in a parts tray. It is ABSOLUTELY NOT a slot, groove, "
        "channel, track, rail or recess, and must NOT be drawn sitting in/on any slot or dark channel — no groove "
        "under it, no track through it, no recessed surround. If the strip's seek cell shows any slot/track "
        "instead of a lone thumb piece, the output is WRONG.\n"
        "  • EXACT FIT — each strip part is the EXACT size & shape of its slot (knob cap = socket diameter; thumb "
        "fits the groove; each shuffle state exactly fills the switch slot). Do NOT resize/re-proportion a part.\n"
        "  • SHUFFLE STATES — design a CHARACTERFUL switch that fits the theme: it does NOT have to be a plain "
        "pill/rocker — a lever, flip-toggle, sliding bolt, rotating latch, gem that shifts, valve, eye that opens — "
        "any physical two-state mechanism, as long as BOTH states share the SAME OUTER HOUSING SILHOUETTE at the "
        "same size and are CLEARLY MIRROR-OPPOSITE: the moving element sits at ONE end/side in OFF and at the "
        "OPPOSITE end/side in ON (never the same position in both). Put ABSOLUTELY NO 'ON', 'OFF', 'I', 'O' or any "
        "text/letters/words/labels on either switch part or on ANY strip part — the state reads from the mechanism's "
        "position alone.\n"
        "  • CAMERA — this is THE MOST COMMON MISTAKE, get it right: render EVERY strip part in a PERFECTLY FLAT, "
        "STRAIGHT-DOWN, TOP-DOWN ORTHOGRAPHIC view — the camera is directly overhead at exactly 90°, the same view "
        "as the device. Each part is drawn as if lying FLAT on a table seen from straight above, with ZERO "
        "thickness, height or depth visible. The volume knob cap is a FLAT ROUND DISC / COIN — you see ONLY its "
        "circular TOP FACE (a knurled outer rim and a small pointer notch); you must NOT see any cylindrical SIDE "
        "WALL, edge, height or 3D body of the knob. The seek thumb and the shuffle switch are likewise flat shapes "
        "seen from directly overhead. ABSOLUTELY NO product-shot angle, NO 3/4 view, NO tilt, NO isometric, NO "
        "perspective, NO visible sides — a part showing its side wall or any thickness is WRONG. Each part must "
        "look EXACTLY as it appears seated flat in its socket on the top-down device, so it drops straight in.\n"
        "RIGHT column — a precise REGION MASK on pure BLACK, pixel-aligned to the LEFT. For EACH control paint ONE "
        "SOLID FILLED blob in ITS OWN guide colour, at the EXACT same position, size and silhouette as that control "
        "on the left (the seek-slider blob is a FULL-HEIGHT horizontal bar matching the groove, NOT a thin line; "
        "the shuffle blob is a tall portrait rounded-rectangle; each knob/button blob a solid disc): " + mask_lines
        + ". DISPLAY-WINDOW BLOBS — the visualizer and album-art blobs must EXACTLY cover their painted "
        "window's GLASS area on the left: the SAME rectangle at the SAME position with the SAME rounded "
        "corners, edge-to-edge with the glass — never larger than the bezel opening, never smaller, never "
        "shifted or offset onto the surrounding body. Trace each window's glass outline precisely; a display "
        "blob that extends past its painted window, covers body/bezel around it, or sits off the window is WRONG"
        + "; and each STRIP PART as a solid COMPACT blob of its colour (volume cap=" + kn(KNOB).lower()
        + ", seek thumb=" + kn(SLIDER).lower() + ", BOTH shuffle states=" + kn(TOGGLE).lower() + ") exactly matching "
        "its part's silhouette & position in the left strip. CRITICAL: each blob is TIGHT to its shape — NEVER let a "
        "colour bleed or stretch across the strip band or flood a rectangle; the 4 strip blobs are 4 separate "
        "compact shapes with black gaps between them. Every blob is ONE solid filled silhouette, no outlines, no "
        "holes. Everything else is pure black.")

    if "--blueprint-only" in sys.argv:
        json.dump({**res, "prompt_len": len(prompt)}, open(os.path.join(OUT, "results.json"), "w"), indent=1)
        print(f"[blueprint-only] {sid} mode={mode} keys ok, prompt {len(prompt)} chars → {bp}")
        return

    if PAINT_VERTEX:
        t = time.time(); out = edit_vertex(bp, prompt, seed)
    else:
        FAL = load_fal()
        t = time.time(); out = edit(FAL, upload(FAL, bp), prompt, seed)
    open(os.path.join(OUT, "joint-4k.png"), "wb").write(out)
    im = Image.open(io.BytesIO(out)).convert("RGB"); w, h = im.size; half = w // 2
    im.crop((0, 0, half, h)).save(os.path.join(OUT, "paint.png"))
    im.crop((half, 0, w, h)).save(os.path.join(OUT, "mask.png"))
    res["dims"] = [w, h]; json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print(f"[gen] {sid} joint {time.time()-t:.0f}s dims={w}x{h}", flush=True)
    # leak gate — checks CONTROL keys only (buttons+sprites). Region keys (album_art, visualizer) are
    # excluded: those are large display panels meant to carry content, and a colourful design legitimately
    # uses saturated button fills that can coincide with a warm guide key. A thin residue RING around a
    # socket is small; a FLOODED region is large — so only a gross leak (>0.30%) is a hard fail here, and the
    # authoritative empty-socket check is extract12's emptiness gate. Everything is printed for the log.
    import numpy as np
    a = np.asarray(Image.open(os.path.join(OUT, "paint.png")).convert("RGB")).astype(int)
    tot = a.shape[0] * a.shape[1]; sat = (a.max(2) - a.min(2)) > 55; worst = ("none", 0.0)
    for name in BUTTONS + [KNOB, SLIDER, TOGGLE]:
        c = KEYS[name]; d2 = ((a - np.array(c)) ** 2).sum(2); frac = int((sat & (d2 < 60 ** 2)).sum()) / tot
        if frac > 0.0003: print(f"  [leak] {name:9} {frac*100:.4f}%")
        if frac > worst[1]: worst = (name, frac)
    print(f"[leak gate] worst-control={worst[0]} {worst[1]*100:.4f}% -> {'FAIL (gross)' if worst[1]>0.0030 else 'ok'}", flush=True)
    res["leak"] = round(worst[1], 6); json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
