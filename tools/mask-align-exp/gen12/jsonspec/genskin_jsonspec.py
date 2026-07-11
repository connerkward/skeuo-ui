#!/usr/bin/env python3
"""genskin_jsonspec — "does a fenced-JSON blueprint spec help PAINT generation itself?"
experiment (2026-07-11). The prior structured-I/O experiment (imgjson/) tested fenced-JSON
prompts only for EXTRACTION (asking a TEXT model to read boxes back out of an already-painted
image) and found it neutral there; the paint/generation side was explicitly flagged untested
(imgjson doc verdict: "paint-side untested" — needs image gens, was out of that experiment's
budget). This is that test.

Self-contained copy pattern (like twoimg/genskin_ab.py, abshape/genskin_ab.py) EXCEPT the
CONTROL arm's prompt is not hand-retyped — retyping ~150 lines of production prompt text by
hand risks silent transcription drift, which would make "verbatim" a lie. Instead this script
IMPORTS genskin.py as a module and calls its OWN main() (via --blueprint-only, then via a real
run) with two module-level attributes monkeypatched IN MEMORY for the duration of the call
(G.HERE -> this experiment's own output dir, G.BLUEPRINT_ARM_WEIGHTS -> force 'solid' arm) —
genskin.py the FILE is never edited; only the imported module OBJECT's attributes are swapped
back and forth. This produces byte-identical CONTROL prompts to what a real production run
would send, and writes into jsonspec/assets-jsonspec-*/ instead of gen12/assets-<id>/ so it
never collides with the live production roster.

Both arms share ONE blueprint image (production solid-guide canvas, copied byte-for-byte from
the CONTROL run into the TREATMENT dir) — the manipulation is prompt ENCODING only:
  CONTROL   — the verbatim production prose prompt (captured from genskin.py's own main()).
  TREATMENT — identical semantic content, but the per-control spec (roster, guide-colour
              mapping, positions/sizes as fractions, strip cell order, congruence
              constraints) is delivered as ONE fenced ```json``` block with a one-line
              preamble ("the machine-readable spec; follow it exactly"); the surrounding
              narrative clauses (theme, camera, no-text, empty-cavity, zero-residue,
              exact-fit, shuffle-states, mask-painting) stay prose, generically referencing
              "the JSON spec above" instead of re-stating the specific numbers/colours/icons.

Usage: python3 genskin_jsonspec.py <theme> <seed>   (writes both arms for that theme+seed)
  e.g. python3 genskin_jsonspec.py wc-goldshield 121
Writes jsonspec/assets-jsonspec-<theme>-control-<seed>/ and -treat-<seed>/.
"""
import os, sys, io, json, shutil, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
import genskin as G  # noqa: E402  (proven builder — imported, never edited)

THEME_SPECS = os.path.join(GEN12, "theme_specs")


def load_spec(theme):
    return json.load(open(os.path.join(THEME_SPECS, f"{theme}.json")))


def run_control(theme, seed, blueprint_only=False):
    """Runs genskin.py's OWN main() end-to-end for the CONTROL arm — the verbatim production
    templated/'solid' prompt path — monkeypatching only in-memory module attributes so the
    file on disk is never touched and output lands under jsonspec/, not gen12/assets-<id>/."""
    spec = dict(load_spec(theme))
    sid = f"jsonspec-{theme}-control-{seed}"
    spec["id"] = sid
    spec["seed"] = seed
    tmp_spec = os.path.join(HERE, f".tmp-spec-{sid}.json")
    json.dump(spec, open(tmp_spec, "w"))

    orig_here, orig_weights = G.HERE, G.BLUEPRINT_ARM_WEIGHTS
    orig_argv = sys.argv
    G.HERE = HERE                                   # -> writes to jsonspec/assets-<sid>/
    G.BLUEPRINT_ARM_WEIGHTS = [("solid", 1.0)]       # force the abshape-verdict winner arm
    try:
        sys.argv = ["genskin.py", tmp_spec] + (["--blueprint-only"] if blueprint_only else [])
        G.main()
    finally:
        G.HERE, G.BLUEPRINT_ARM_WEIGHTS, sys.argv = orig_here, orig_weights, orig_argv
        os.remove(tmp_spec)

    out_dir = os.path.join(HERE, f"assets-{sid}")
    res = json.load(open(os.path.join(out_dir, "results.json")))
    return out_dir, res


# ---------------------------------------------------------------- treatment (fenced-JSON) arm
def control_size_frac(kind, sz):
    if kind in ("btn", "knob"):
        r = sz[0] if kind == "btn" else G.KNOB_R
        return {"shape": "circle", "radius_frac_of_col_w": round(r / G.COL_W, 4)}
    if kind == "groove":
        return {"shape": "rounded_rect", "w_frac_of_col_w": round(G.GROOVE_W / G.COL_W, 4),
                 "h_frac_of_dev_h": round(G.GROOVE_H / G.DEV_H, 4)}
    if kind == "tog":
        return {"shape": "rounded_rect", "w_frac_of_col_w": round(G.TOG_W / G.COL_W, 4),
                 "h_frac_of_dev_h": round(G.TOG_H / G.DEV_H, 4)}
    if kind == "rect":
        w, h = sz
        return {"shape": "rounded_rect", "w_frac_of_col_w": round(w / G.COL_W, 4),
                 "h_frac_of_dev_h": round(h / G.DEV_H, 4)}
    return {}


def build_spec_json(spec, KEYS, layout):
    controls = []
    for name in G.CONTROLS:
        fx, fy, kind, *sz = layout[name]
        controls.append({
            "id": name,
            "role": G.ROLES[name],
            "guide_color_name": G.cname(KEYS[name]),
            "guide_color_rgb": list(KEYS[name]),
            "final_icon_or_content": G.ICON[name],
            "position_frac": {"fx": round(fx, 4), "fy_of_device_area": round(fy, 4)},
            **control_size_frac(kind, sz),
        })
    strip_sizes = {
        "vol_cap": {"shape": "circle", "radius_frac_of_col_w": round(G.KNOB_R / G.COL_W, 4)},
        "seek_thumb": {"shape": "rounded_rect", "w_frac_of_col_w": round(G.THUMB_W / G.COL_W, 4),
                       "h_frac_of_dev_h": round(G.THUMB_H / G.DEV_H, 4)},
        "shuffle_state": {"shape": "rounded_rect", "w_frac_of_col_w": round(G.TOG_W / G.COL_W, 4),
                           "h_frac_of_dev_h": round(G.TOG_H / G.DEV_H, 4)},
    }
    return {
        "_note": ("machine-readable control spec. position_frac is a fraction of the device "
                  "column's own width (fx) and the device area's own height (fy), guide_color_rgb "
                  "marks this control's blueprint position ONLY and must never be painted into the "
                  "finished device, sizes are congruence-locked between the device slot and its "
                  "matching loose strip part."),
        "controls": controls,
        "strip_order_left_to_right": ["vol_cap", "seek_thumb", "shuffle_state_1", "shuffle_state_2"],
        "strip_part_sizes": strip_sizes,
        "congruence_rule": ("each strip part's size EXACTLY equals its matching device slot's size "
                             "above (vol_cap radius == vol's radius_frac_of_col_w; seek_thumb fits "
                             "the seek groove; each shuffle_state exactly fills the shuffle slot)"),
    }


def build_treatment_prompt(spec, KEYS, layout, dark, BG):
    STRUCT = spec["theme_prompt"].strip()
    spec_obj = build_spec_json(spec, KEYS, layout)
    json_block = "```json\n" + json.dumps(spec_obj, indent=1) + "\n```"

    preamble = ("Two side-by-side columns of identical size, output at 5:4. Below is THE "
                "MACHINE-READABLE SPEC for this generation — follow it exactly for every "
                "control's identity, guide-colour, position and size:\n\n" + json_block + "\n")
    left_layout = (
        "The LEFT column is a BLUEPRINT: a neutral grey placeholder body with COLOURED SOLID "
        "FILLED patches marking each control's exact position/size/shape PER THE SPEC ABOVE, "
        "plus a bottom SPRITE-STRIP band with 4 loose parts in the order given by the spec's "
        "strip_order_left_to_right. KEEP EVERY CONTROL AT THE EXACT POSITION, SIZE AND SHAPE "
        "given by the spec — do NOT move, resize, swap, rearrange, add or drop any control "
        "(their layout, as specified, is locked). BUT the grey body is ONLY a rough placeholder "
        "showing WHERE the controls sit — you are FREE and STRONGLY ENCOURAGED to sculpt a BOLD, "
        "DISTINCTIVE, ASYMMETRIC, theme-appropriate outer HOUSING around them: an ornate, "
        "characterful, sculpted form with a memorable silhouette (organic curves, wings, pods, "
        "fins, greebles, ornament, asymmetry) — NOT a plain rounded rectangle, NOT a generic "
        "slab or pod. Reshape the outer silhouette DRAMATICALLY to suit the theme; ONLY the "
        "control positions given by the spec stay fixed. The coloured filled patches described "
        "in the spec are ALIGNMENT MARKINGS (like masking tape) and MUST be completely removed.")
    NO_LIST = ", ".join(f"NO {G.cname(KEYS[c]).lower()}" for c in G.CONTROLS)
    residue_bullet = (
        "  • ZERO RESIDUE (CRITICAL) — the coloured guide patch around EVERY control is a "
        "temporary alignment marking, NOT part of the design. It must VANISH completely. Each "
        "finished BUTTON is ONE solid piece of the device's own material with absolutely NO "
        "coloured ring, rim, bezel, halo, outline or edge-tint around it — if a button has a "
        "coloured ring, it is WRONG. Likewise the album-art and visualizer windows have NO "
        "coloured frame (just a dark recessed glass panel flush in the body), and no "
        "socket/groove/slot has any coloured rim. Paint the body/button material seamlessly "
        "OVER where each guide patch was.\n")

    prompt = (
        preamble + " ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO CAPTIONS and NO "
        "LABELS anywhere in EITHER column — not under controls, not on the strip, not a title, "
        "nothing; the device is wordless, identified by icons and shapes only. " + left_layout + "\n"
        "THEME (design the finished device in THIS style — you own all materials, colours, "
        "form, lighting): " + STRUCT + "\n"
        "Fill BOTH columns keeping the device+strip layout IDENTICAL so they overlay "
        "pixel-for-pixel.\n"
        "LEFT column — the FINISHED, richly 3D, tactile, skeuomorphic media player and its "
        "loose parts, in the theme above. CRITICAL for cutout: the BACKDROP around the device "
        f"and BEHIND every strip part is a FLAT, PERFECTLY UNIFORM "
        f"{'pale grey-white' if dark else 'near-black charcoal'} tone (RGB ~{BG[0]},{BG[1]},{BG[2]}) "
        "— a separate keyed-out backdrop with NO gradient/texture/vignette that strongly "
        "contrasts the body; the device must never approach the backdrop tone.\n"
        "  • The finished device uses ONLY its own theme materials/colours — NONE of the guide "
        f"colours from the spec. ABSOLUTELY {NO_LIST} anywhere in the LEFT column; the guide "
        "colours from the spec exist ONLY in the RIGHT mask.\n"
        + residue_bullet
        + "  • The 5 transport/function BUTTONS (playpause, prev, next, repeat, queue) are "
        "raised, glossy, tactile control facets set into the body, EACH clearly bearing its "
        "icon EMBOSSED/engraved in relief per the spec's final_icon_or_content field for that "
        "control. Shape + icon + relief only; no text labels; no coloured rim.\n"
        "  • BUTTON COLOURS COME FROM THE THEME, NEVER FROM THE GUIDES: a button's guide_color "
        "in the spec marks its POSITION ONLY — the finished button's material/fill must NOT "
        "inherit, echo or be tinted toward its guide colour in ANY way (no red play because its "
        "guide was red, no magenta next, etc). ALL five buttons are made of the device's OWN "
        "theme materials/palette, coloured consistently with each other and the body. If any "
        "button's colour visibly matches its spec guide_color, the output is WRONG.\n"
        "  • THE SINGLE MOST IMPORTANT RULE — EVERY MOVING-PART CAVITY IS EMPTY. The volume "
        "knob socket is a bare round HOLE showing only its dark recessed floor (NO knob, NO "
        "cap, NO dome, NO dial, NO pointer — nothing installed). The seek slider groove is an "
        "EMPTY DARK RECESSED CHANNEL cut into the body (NO thumb, NO grip, NO handle, NO fill "
        "— it is NOT a coloured or filled bar, it is a hollow dark slot). The shuffle switch "
        "slot is an EMPTY DARK rounded well (NO switch, NO lever, NO toggle installed). The "
        "device is photographed BEFORE ASSEMBLY: those parts exist ONLY in the bottom sprite "
        "strip and have NOT been installed yet. Do NOT colour the empty wells — neutral DARK "
        "recesses only. If ANY of the three cavities (knob socket, seek slot, shuffle slot) "
        "contains ANY part or any fill colour, the output is WRONG and must be redone.\n"
        "  • SEEK IS JUST AN EMPTY SLOT — treat the seek as a plain EMPTY recessed horizontal "
        "SLOT/CHANNEL only, NOT a functioning slider. Absolutely do NOT bake a slider thumb, "
        "grip, knob, handle, bar, fill, track-fill or progress indicator into it — it is a bare "
        "dark empty channel; the thumb is a SEPARATE loose part in the strip (see spec's "
        "strip_order_left_to_right). A seek slot with anything riding in it is WRONG.\n"
        "  • The ALBUM-ART window and the VISUALIZER window are BLANK, DARK, EMPTY recessed "
        "glass SCREENS — flat unlit dark glass panels only, with NOTHING inside them: NO baked "
        "spectrum/equalizer bars, NO album cover or artwork, NO waveform, NO icons, NO text, NO "
        "content whatsoever. They are powered-down screens; the app draws their live content "
        "later. If either window contains any baked graphics, it is WRONG.\n"
        "  • SPRITE STRIP — EXACTLY FOUR finished parts in ONE horizontal row, in the order "
        "given by the spec's strip_order_left_to_right (volume knob cap, seek slider thumb, "
        "shuffle switch first state, shuffle switch second state) — in the device's own "
        f"materials, patches removed, on the flat {'pale' if dark else 'charcoal'} backdrop.\n"
        "  • THE SEEK STRIP PART IS THE LOOSE THUMB/GRIP **ONLY** — the small handle piece a "
        "finger slides, shown by itself on the backdrop, like a spare part in a parts tray. It "
        "is ABSOLUTELY NOT a slot, groove, channel, track, rail or recess, and must NOT be "
        "drawn sitting in/on any slot or dark channel — no groove under it, no track through "
        "it, no recessed surround. If the strip's seek cell shows any slot/track instead of a "
        "lone thumb piece, the output is WRONG.\n"
        "  • EXACT FIT — per the spec's congruence_rule: each strip part is the EXACT size & "
        "shape of its slot (vol_cap radius = vol's socket radius; seek_thumb fits the groove; "
        "each shuffle_state exactly fills the switch slot). Do NOT resize/re-proportion a part.\n"
        "  • SHUFFLE STATES — design a CHARACTERFUL switch that fits the theme: it does NOT "
        "have to be a plain pill/rocker — a lever, flip-toggle, sliding bolt, rotating latch, "
        "gem that shifts, valve, eye that opens — any physical two-state mechanism, as long as "
        "BOTH states share the SAME OUTER HOUSING SILHOUETTE at the same size (per the spec's "
        "shuffle_state size) and are CLEARLY MIRROR-OPPOSITE: the moving element sits at ONE "
        "end/side in the first state and at the OPPOSITE end/side in the second state (never "
        "the same position in both). Put ABSOLUTELY NO text, letters, numerals, glyphs, words "
        "or labels of ANY kind on either switch part or on ANY strip part — the state must read "
        "from the mechanism's position alone, with zero markings.\n"
        "  • CAMERA — this is THE MOST COMMON MISTAKE, get it right: render EVERY strip part in "
        "a PERFECTLY FLAT, STRAIGHT-DOWN, TOP-DOWN ORTHOGRAPHIC view — the camera is directly "
        "overhead at exactly 90°, the same view as the device. Each part is drawn as if lying "
        "FLAT on a table seen from straight above, with ZERO thickness, height or depth "
        "visible. The volume knob cap is a FLAT ROUND DISC / COIN — you see ONLY its circular "
        "TOP FACE (a knurled outer rim and a small pointer notch); you must NOT see any "
        "cylindrical SIDE WALL, edge, height or 3D body of the knob. The seek thumb and the "
        "shuffle switch are likewise flat shapes seen from directly overhead. ABSOLUTELY NO "
        "product-shot angle, NO 3/4 view, NO tilt, NO isometric, NO perspective, NO visible "
        "sides — a part showing its side wall or any thickness is WRONG. Each part must look "
        "EXACTLY as it appears seated flat in its socket on the top-down device, so it drops "
        "straight in.\n"
        "RIGHT column — a precise REGION MASK on pure BLACK, pixel-aligned to the LEFT. For "
        "EACH control paint ONE SOLID FILLED blob in its own guide_color_rgb (from the spec), "
        "at the EXACT same position, size and silhouette as that control on the left (the "
        "seek-slider blob is a FULL-HEIGHT horizontal bar matching the groove, NOT a thin line; "
        "the shuffle blob is a tall portrait rounded-rectangle; each knob/button blob a solid "
        "disc) — one blob per control id in the spec's controls array, coloured by that "
        "control's guide_color_rgb. DISPLAY-WINDOW BLOBS — the visualizer and album_art blobs "
        "must EXACTLY cover their painted window's GLASS area on the left: the SAME rectangle "
        "at the SAME position with the SAME rounded corners, edge-to-edge with the glass — "
        "never larger than the bezel opening, never smaller, never shifted or offset onto the "
        "surrounding body. Trace each window's glass outline precisely; a display blob that "
        "extends past its painted window, covers body/bezel around it, or sits off the window "
        "is WRONG; and each STRIP PART as a solid COMPACT blob of its matching control's "
        "guide_color_rgb (vol_cap uses vol's colour, seek_thumb uses seek's colour, BOTH "
        "shuffle states use shuffle's colour) exactly matching its part's silhouette & position "
        "in the strip, in the spec's strip_order_left_to_right. CRITICAL: each blob is TIGHT to "
        "its shape — NEVER let a colour bleed or stretch across the strip band or flood a "
        "rectangle; the 4 strip blobs are 4 separate compact shapes with black gaps between "
        "them. Every blob is ONE solid filled silhouette, no outlines, no holes. Everything "
        "else is pure black.")
    return prompt


def leak_gate(paint_path, KEYS):
    a = np.asarray(Image.open(paint_path).convert("RGB")).astype(int)
    tot = a.shape[0] * a.shape[1]; sat = (a.max(2) - a.min(2)) > 55; worst = ("none", 0.0)
    for name in G.BUTTONS + [G.KNOB, G.SLIDER, G.TOGGLE]:
        c = KEYS[name]; d2 = ((a - np.array(c)) ** 2).sum(2); frac = int((sat & (d2 < 60 ** 2)).sum()) / tot
        if frac > worst[1]: worst = (name, frac)
    return worst


def run_treatment(theme, seed, control_dir, control_res):
    sid = f"jsonspec-{theme}-treat-{seed}"
    out_dir = os.path.join(HERE, f"assets-{sid}")
    os.makedirs(out_dir, exist_ok=True)

    bp_src = os.path.join(control_dir, "blueprint.png")
    bp_dst = os.path.join(out_dir, "blueprint.png")
    shutil.copyfile(bp_src, bp_dst)  # bit-identical shared blueprint, per experiment design

    spec = load_spec(theme)
    dark = spec.get("material_is_dark", False)
    BG = (235, 235, 238) if dark else (18, 18, 24)
    KEYS = {k: tuple(v) for k, v in control_res["keys"].items()}
    layout = G.LAYOUTS[spec.get("layout", "vpod")]()

    prompt = build_treatment_prompt(spec, KEYS, layout, dark, BG)
    res = {"id": sid, "theme": theme, "arm": "treat", "seed": seed, "model": G.MODEL,
           "backdrop": list(BG), "keys": control_res["keys"], "keyNames": control_res["keyNames"],
           "buttons": G.BUTTONS, "sprites": [G.KNOB, G.SLIDER, G.TOGGLE], "extras": G.REGIONS,
           "roles": G.ROLES, "devFrac": G.DEVF, "template": control_res["template"],
           "album_art_rect": control_res.get("album_art_rect"),
           "visualizer_rect": control_res.get("visualizer_rect"),
           "blueprint": "blueprint.png (byte-identical copy of control arm's)",
           "prompt": prompt, "prompt_len": len(prompt)}
    json.dump(res, open(os.path.join(out_dir, "results.json"), "w"), indent=1)

    if "--blueprint-only" in sys.argv:
        print(f"[blueprint-only] {sid} prompt {len(prompt)} chars -> {out_dir}")
        return out_dir, res

    t = time.time()
    out = G.edit_vertex(bp_dst, prompt, seed)
    open(os.path.join(out_dir, "joint-4k.png"), "wb").write(out)
    im = Image.open(io.BytesIO(out)).convert("RGB"); w, h = im.size; half = w // 2
    im.crop((0, 0, half, h)).save(os.path.join(out_dir, "paint.png"))
    im.crop((half, 0, w, h)).save(os.path.join(out_dir, "mask.png"))
    res["dims"] = [w, h]
    worst = leak_gate(os.path.join(out_dir, "paint.png"), KEYS)
    res["leak"] = round(worst[1], 6)
    json.dump(res, open(os.path.join(out_dir, "results.json"), "w"), indent=1)
    print(f"[gen] {sid} joint {time.time()-t:.0f}s dims={w}x{h} leak worst={worst[0]}={worst[1]*100:.4f}%")
    return out_dir, res


def main():
    theme, seed = sys.argv[1], int(sys.argv[2])
    bp_only = "--blueprint-only" in sys.argv
    print(f"=== {theme} seed={seed} CONTROL (verbatim production prompt, imported genskin.main) ===")
    control_dir, control_res = run_control(theme, seed, blueprint_only=bp_only)
    print(f"[control] -> {control_dir}  prompt {len(control_res.get('prompt') or '')} chars"
          if bp_only else f"[control] -> {control_dir}")
    print(f"=== {theme} seed={seed} TREATMENT (fenced-JSON spec) ===")
    treat_dir, treat_res = run_treatment(theme, seed, control_dir, control_res)
    print(f"[treat]   -> {treat_dir}")


if __name__ == "__main__":
    main()
