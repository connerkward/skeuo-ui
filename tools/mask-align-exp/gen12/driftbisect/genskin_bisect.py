#!/usr/bin/env python3
"""genskin_bisect — drift-clause bisect generator (2026-07-11, docs/design/2026-07-11-
think-about-notes.md §3). Isolates whether the "BOLD, DISTINCTIVE... ONLY the control
positions stay fixed" freedom clause in genskin.py's templated prompt is a driver of the
measured template-drift regression (roster audit: 4/6 templated skins regressed,
fallout-pipboy 143->950px).

Does NOT edit ../genskin.py — imports its shared constants/build_canvas/pick_keys/
edit_vertex from the module directly (read-only import, per project rule), then builds its
OWN prompt text for three arms so genskin.py's mainline prompt is never touched:

  A  current production wording verbatim (the templated, non-twoimg, `conditioning="solid"`
     branch of genskin.py's main()) — this run's control.
  B  A minus the bold-silhouette-freedom sentence, replaced with a neutral instruction to
     keep the housing close to the guide's rough placeholder shape.
  C  A, bold-silhouette clause KEPT verbatim, plus an appended explicit numeric position-lock
     addendum (every control's centre must land within 2% of its guide centre).

conditioning is FORCED to 'solid' for every arm (genskin.py's BLUEPRINT_TRIAL arm-draw and
BLUEPRINT_TWOIMG mode are both bypassed) so the trial/twoimg confound never enters this
bisect — only the housing-freedom wording varies between A/B/C.

Usage: python3 genskin_bisect.py <spec.json> --arm A|B|C --seed N [--blueprint-only]
  -> writes driftbisect/assets-bisect-<sid>-<arm>-<seed>/
"""
import os, sys, io, json, time, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

# ---- read-only import of ../genskin.py (never edited) for shared constants/helpers ----
_spec = importlib.util.spec_from_file_location("genskin", os.path.join(GEN12, "genskin.py"))
genskin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(genskin)

from PIL import Image

COL_W, H, DEV_H, DEVF = genskin.COL_W, genskin.H, genskin.DEV_H, genskin.DEVF
BUTTONS, KNOB, SLIDER, TOGGLE = genskin.BUTTONS, genskin.KNOB, genskin.SLIDER, genskin.TOGGLE
REGIONS, CONTROLS, ROLES, ICON = genskin.REGIONS, genskin.CONTROLS, genskin.ROLES, genskin.ICON
BTN_R, PLAY_R, KNOB_R = genskin.BTN_R, genskin.PLAY_R, genskin.KNOB_R
GROOVE_H, TOG_W = genskin.GROOVE_H, genskin.TOG_W
LAYOUTS = genskin.LAYOUTS
cname, pick_keys, build_canvas = genskin.cname, genskin.pick_keys, genskin.build_canvas
edit_vertex = genskin.edit_vertex

# ---- the exact sentence under test, copied verbatim from genskin.py's templated/non-twoimg
# left_layout (search anchor; if this ever drifts from mainline the KeyError below will fire
# loudly instead of silently testing stale wording) ----
BOLD_CLAUSE = (
    "BUT the grey body is ONLY a rough placeholder showing WHERE the controls sit — you "
    "are FREE and STRONGLY ENCOURAGED to sculpt a BOLD, DISTINCTIVE, ASYMMETRIC, theme-appropriate outer "
    "HOUSING around them: an ornate, characterful, sculpted form with a memorable silhouette (organic curves, "
    "wings, pods, fins, greebles, ornament, asymmetry) — NOT a plain rounded rectangle, NOT a generic slab or "
    "pod. Reshape the outer silhouette DRAMATICALLY to suit the theme; ONLY the control positions stay fixed."
)
# B — neutral, conservative, locked-layout replacement (same length register, opposite instruction)
LOCKED_CLAUSE = (
    "The grey body is a rough placeholder for the device's outer housing shape — keep the finished "
    "housing's outer silhouette CLOSE to this placeholder: a smoothly rounded, conservative body at "
    "the SAME overall size and position, not dramatically reshaped or expanded. Style the surface "
    "materials, finish, ornament and colour fully in the theme below; the outer silhouette itself "
    "should closely follow the placeholder's proportions."
)
# C — bold clause kept, position-lock addendum appended
POSITION_LOCK_ADDENDUM = (
    " REGARDLESS of how bold or dramatic the outer housing becomes, this is a HARD numeric constraint: "
    "every control's CENTRE must land within 2% of the device's width/height of its own guide shape's "
    "centre. Reshape and ornament the housing AROUND the guides, never THROUGH them or shifting them — "
    "the guide positions are immovable anchors, not suggestions, no matter how the silhouette is sculpted."
)

ARM_CLAUSE = {"A": BOLD_CLAUSE, "B": LOCKED_CLAUSE, "C": BOLD_CLAUSE + POSITION_LOCK_ADDENDUM}


def build_prompt(spec, KEYS, arm):
    """Reproduces genskin.py main()'s templated, non-twoimg, conditioning='solid' prompt
    branch verbatim, with ONLY the housing-freedom sentence swapped per ARM_CLAUSE. Every
    other clause (residue, empty-cavity, camera, mask-column, etc.) is copied unchanged so
    the bisect isolates exactly one variable."""
    def kn(c): return cname(KEYS[c])
    def rgb(c): return ",".join(str(v) for v in KEYS[c])
    NO_LIST = ", ".join(f"NO {kn(c).lower()}" for c in CONTROLS)
    roster_desc = "; ".join(f"{kn(c)} = {ICON[c]}" for c in CONTROLS)
    STRUCT = spec["theme_prompt"].strip()
    mask_lines = "; ".join(f"{kn(c)} region filled {rgb(c)}" for c in CONTROLS)
    dark = spec.get("material_is_dark", False)
    BG = (235, 235, 238) if dark else (18, 18, 24)

    preamble = "Two side-by-side columns of identical size, output at 5:4."
    # conditioning forced 'solid' for every bisect arm
    guide_word, marking_word, residue_word = "SOLID FILLED patches", "filled patches", "patch"

    left_layout = (
        "The LEFT column is a BLUEPRINT: a neutral grey placeholder body with COLOURED "
        f"{guide_word} marking each control's EXACT position, size and shape, plus a bottom SPRITE-STRIP "
        "band with 4 loose parts (volume knob cap, seek slider thumb, shuffle switch first state, shuffle switch second state). "
        "Each guide's colour maps to a control: " + roster_desc + ". KEEP EVERY CONTROL AT THE EXACT POSITION, "
        "SIZE AND SHAPE OF ITS GUIDE — do NOT move, resize, swap, rearrange, add or drop any control (their "
        "layout is locked). " + ARM_CLAUSE[arm] + " "
        f"The coloured {marking_word} are ALIGNMENT MARKINGS (like masking tape) and MUST be completely removed."
    )
    residue_bullet = (
        f"  • ZERO RESIDUE (CRITICAL) — the coloured guide {residue_word} around EVERY control is a temporary "
        "alignment marking, NOT part of the design. It must VANISH completely. Each finished BUTTON is ONE solid "
        "piece of the device's own material with absolutely NO coloured ring, rim, bezel, halo, outline or "
        "edge-tint around it — if a button has a coloured ring, it is WRONG. Likewise the album-art and "
        "visualizer windows have NO coloured frame (just a dark recessed glass panel flush in the body), and no "
        f"socket/groove/slot has any coloured rim. Paint the body/button material seamlessly OVER where each "
        f"guide {residue_word} was.\n")

    ticks_spec = spec.get("ticks", {})
    tick_skin_bullet = (
        "  • The panel immediately surrounding the volume knob's socket carries a swept ring of "
        "tick or index marks framing the opening, cut/engraved/cast into the device's own housing "
        "material and finish — subtle, part of the panel, not a separate applied sticker. This is "
        "on the surrounding panel only; the socket cavity itself stays the bare empty hole described "
        "above.\n"
    ) if ticks_spec.get("skin") == "baked" else ""
    tick_sprite_bullet = (
        "  • The volume knob cap (the loose strip part) carries one small pointer or index mark at "
        "its rim, in the device's own material and finish, clearly distinguishable from the rest of "
        "the cap's surface so its rotation reads at a glance.\n"
    ) if ticks_spec.get("sprite") == "baked" else ""

    prompt = (
        preamble + " ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO "
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
        + residue_bullet
        + "  • The 5 transport/function BUTTONS (play/pause, previous, next, repeat, queue) are raised, glossy, "
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
        + tick_skin_bullet
        + "  • SEEK IS JUST AN EMPTY SLOT — treat the seek as a plain EMPTY recessed horizontal SLOT/CHANNEL only, "
        "NOT a functioning slider. Absolutely do NOT bake a slider thumb, grip, knob, handle, bar, fill, track-fill "
        "or progress indicator into it — it is a bare dark empty channel; the thumb is a SEPARATE loose part in the "
        "strip. A seek slot with anything riding in it is WRONG.\n"
        "  • The ALBUM-ART window and the VISUALIZER window are BLANK, DARK, EMPTY recessed glass SCREENS — flat "
        "unlit dark glass panels only, with NOTHING inside them: NO baked spectrum/equalizer bars, NO album cover "
        "or artwork, NO waveform, NO icons, NO text, NO content whatsoever. They are powered-down screens; the app draws "
        "their live content later. If either window contains any baked graphics, it is WRONG.\n"
        "  • SPRITE STRIP — EXACTLY FOUR finished parts in ONE horizontal row, left→right: volume knob cap, seek "
        "slider thumb, shuffle switch in its first state, shuffle switch in its second state — in the device's own materials, outlines removed, on "
        f"the flat {'pale' if dark else 'charcoal'} backdrop.\n"
        + tick_sprite_bullet
        + "  • THE SEEK STRIP PART IS THE LOOSE THUMB/GRIP **ONLY** — the small handle piece a finger slides, shown "
        "by itself on the backdrop, like a spare part in a parts tray. It is ABSOLUTELY NOT a slot, groove, "
        "channel, track, rail or recess, and must NOT be drawn sitting in/on any slot or dark channel — no groove "
        "under it, no track through it, no recessed surround. If the strip's seek cell shows any slot/track "
        "instead of a lone thumb piece, the output is WRONG.\n"
        "  • EXACT FIT — each strip part is the EXACT size & shape of its slot (knob cap = socket diameter; thumb "
        "fits the groove; each shuffle state exactly fills the switch slot). Do NOT resize/re-proportion a part.\n"
        "  • SHUFFLE STATES — design a CHARACTERFUL switch that fits the theme: it does NOT have to be a plain "
        "pill/rocker — a lever, flip-toggle, sliding bolt, rotating latch, gem that shifts, valve, eye that opens — "
        "any physical two-state mechanism, as long as BOTH states share the SAME OUTER HOUSING SILHOUETTE at the "
        "same size and are CLEARLY MIRROR-OPPOSITE: the moving element sits at ONE end/side in the first state and "
        "at the OPPOSITE end/side in the second state (never the same position in both). Put ABSOLUTELY NO text, "
        "letters, numerals, glyphs, words or labels of ANY kind on either switch part or on ANY strip part — the "
        "state must read from the mechanism's position alone, with zero markings.\n"
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
    return prompt


def main():
    spec = json.load(open(sys.argv[1]))
    arm = sys.argv[sys.argv.index("--arm") + 1].upper()
    seed = int(sys.argv[sys.argv.index("--seed") + 1])
    assert arm in ARM_CLAUSE, f"arm must be A/B/C, got {arm}"
    sid = spec["id"]; mode = spec["mode"]
    assert mode == "templated", "drift-clause bisect only applies to templated mode"
    palette = {k: tuple(v) for k, v in spec["palette"].items()}
    dark = spec.get("material_is_dark", False)
    BG = (235, 235, 238) if dark else (18, 18, 24)
    tag = f"{sid}-{arm.lower()}-{seed}"
    OUT = os.path.join(HERE, f"assets-bisect-{tag}"); os.makedirs(OUT, exist_ok=True)
    keys = pick_keys(palette)
    KEYS = dict(zip(CONTROLS, keys))
    layout = LAYOUTS[spec.get("layout", "vpod")]()

    # -------- blueprint: FORCED solid guides (no trial draw, no twoimg) --------
    edit_img, template = build_canvas(BG, layout, KEYS, "solid")
    bp = os.path.join(OUT, "blueprint.png"); edit_img.save(bp)

    defsz = {KNOB: 2 * KNOB_R / COL_W, SLIDER: GROOVE_H / COL_W, TOGGLE: TOG_W / COL_W,
             **{b: (2 * PLAY_R if b == "playpause" else 2 * BTN_R) / COL_W for b in BUTTONS}}
    res = {"id": sid, "arm": arm, "mode": mode, "seed": seed, "model": genskin.VERTEX_MODEL,
           "backdrop": list(BG), "palette": {k: list(v) for k, v in palette.items()},
           "keys": {k: list(v) for k, v in KEYS.items()}, "keyNames": {k: cname(v) for k, v in KEYS.items()},
           "buttons": BUTTONS, "sprites": [KNOB, SLIDER, TOGGLE], "extras": REGIONS,
           "roles": ROLES, "defsz": defsz, "devFrac": DEVF,
           "lighting": spec.get("lighting", {}), "ticks": spec.get("ticks", {}),
           "template": template, "blueprint_conditioning": "solid (forced, bisect)"}
    aa = layout["album_art"]; res["album_art_rect"] = [aa[0] - aa[3] / COL_W / 2, (aa[1] - aa[4] / DEV_H / 2) * DEVF, aa[3] / COL_W, aa[4] / DEV_H * DEVF]
    vz = layout["visualizer"]; res["visualizer_rect"] = [vz[0] - vz[3] / COL_W / 2, (vz[1] - vz[4] / DEV_H / 2) * DEVF, vz[3] / COL_W, vz[4] / DEV_H * DEVF]
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)

    prompt = build_prompt(spec, KEYS, arm)
    res["prompt"] = prompt; res["prompt_len"] = len(prompt)
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)

    if "--blueprint-only" in sys.argv:
        print(f"[blueprint-only] {sid} arm={arm} seed={seed} prompt {len(prompt)} chars -> {bp}")
        return

    t = time.time(); out = edit_vertex(bp, prompt, seed)
    open(os.path.join(OUT, "joint-4k.png"), "wb").write(out)
    im = Image.open(io.BytesIO(out)).convert("RGB"); w, h = im.size; half = w // 2
    im.crop((0, 0, half, h)).save(os.path.join(OUT, "paint.png"))
    im.crop((half, 0, w, h)).save(os.path.join(OUT, "mask.png"))
    res["dims"] = [w, h]; json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print(f"[gen] {sid} arm={arm} seed={seed} joint {time.time()-t:.0f}s dims={w}x{h}", flush=True)

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
