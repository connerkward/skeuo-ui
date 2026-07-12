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
import os, re, io, sys, json, time, math, random, base64, subprocess
import requests
from PIL import Image, ImageDraw
# ⟦cite:...⟧ provenance markers ride inside the prompt string literals below (why each clause
# exists — experiment/review/commit refs, rendered in PROMPT-PROVENANCE.md). strip_cites()
# removes them before the prompt reaches any model API or results.json — see prompt_provenance.py.
from prompt_provenance import strip_cites

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

# BLUEPRINT_TRIAL: randomized longitudinal trial wired into mainline templated-mode generation —
# every gen draws ONE of two blueprint guide-style arms (deterministically, seeded off the gen
# seed) so solid-vs-outline evidence accumulates for free across inevitable future rolls, instead
# of needing a dedicated A/B batch. False => always 'solid' (the abshape A/B winner, see
# abshape/verdict.json: solid wins emptiness 3:1 pooled and never produces the outline arm's
# tell-tale coloured-ring-around-a-button residue — becomes the fixed default when the trial is
# off). ON since 2026-07-10 (this change).
BLUEPRINT_TRIAL_ENABLED = True
# Weighted arm draw — favor the incumbent 'solid' per generation-spend-rule (don't burn rolls on
# the arm the A/B already showed weaker); 'outline' stays in rotation because the user isn't yet
# convinced it's categorically worse, just that it lost the small abshape sample.
BLUEPRINT_ARM_WEIGHTS = [("solid", 0.75), ("outline", 0.25)]

# BLUEPRINT_TWOIMG: two-image conditioning (clean guide-pixel-free edit canvas + the colour-keyed
# layout drawn as a SEPARATE reference image) — the twoimg/ experiment FALSIFIED this as a bleed
# fix (bleed still transfers semantically in 3/4 treat gens, AND layout adherence collapsed 4/4 vs
# 0/4 control; see twoimg/results.html + docs/experiments/2026-07-10-twoimg-conditioning.md). Kept
# here as a working, flag-gated MODE (not a trial arm — the user wants it accumulating longitudinal
# data separately, pending a decision between this raw variant and a neutral-reference variant) so
# it can be flipped on generally, OR forced per-skin via spec["conditioning"] = "twoimg", without
# reintroducing the construction code from scratch. Default OFF: falsified, not proven better.
BLUEPRINT_TWOIMG = False

# PROMPT_JSON_SPEC: encode the per-control specification (roster, guide-colour map,
# positions/sizes as fractions, strip cell order, congruence rule) as ONE fenced ```json```
# block instead of inline prose; the narrative clauses (theme, camera, no-text, empty-cavity,
# zero-residue, exact-fit, shuffle-states, mask column) stay prose either way. The jsonspec/
# experiment (2026-07-11, n=4 paired gens, ~$2.2 spend) found this NEUTRAL-TO-MILDLY-HELPFUL,
# not a fix: guide-hue bleed lower in the treatment in 4/4 paired gens (mean 5.04% -> 1.56%),
# extract12 gate PASS 3/4 treat vs 2/4 control (both control fails were emptiness) — but layout
# drift was unaffected (690px control vs 641px treat on a ~2300px canvas, both arms treat the
# locked template as a suggestion) and guide-hue button echo still occurred in one treatment gen.
# See jsonspec/verdict.json, docs/experiments/2026-07-11-jsonspec-paint.md, commit 8abf3e8a.
# Only swaps the ENCODING of the templated 'solid'-conditioning control spec (the only arm the
# experiment actually tested — see the `conditioning == "solid"` guard below); the 'outline' and
# 'twoimg' conditioning arms and templateless mode are untouched by this flag regardless of its
# value, so BLUEPRINT_TRIAL_ENABLED's outline draws keep using the prose encoding either way.
# FLIPPED ON 2026-07-12 (user call): the 4/4 paired guide-hue-bleed reduction (5.04% -> 1.56%)
# and the 3/4-vs-2/4 gate-PASS lift are enough signal to promote the treatment to mainline
# production, even though layout drift was unaffected. Flip only BETWEEN batches, never
# mid-batch (see generation-spend-rule) — a re-roll batch may be running against genskin.py
# right now.
PROMPT_JSON_SPEC = True

# KNOB_POINTER_UP: paint the volume-cap's pointer notch AT the zero-degree convention instead of
# painting it at whatever angle the model feels like and counter-rotating post-hoc (the whole
# knob_angle.py detect+correct machinery). User insight, 2026-07-11 (verbatim): "maybe instead of
# all this bullshit [detect-and-counter-rotate] you can just specify in prompt that the tick on
# knob face should point upwards 0 degrees?" — invert the architecture, paint AT the convention
# instead of detecting and correcting after. See knobup/ (compliance experiment against the
# pre-fix random-angle distribution) + docs/experiments/2026-07-11-knob-pointer-up.md for the
# verdict. Deliberately no position-label word or angle number in the clause below (bproof
# lesson, see the tick-provisioning comment further down: named positions/numbers bake in as
# literal engraved TEXT) — "straight up" is a direction, not a label. Default OFF pending verdict.
KNOB_POINTER_UP = False
_POINTER_UP_CLAUSE = (", its pointer notch aiming straight up"
                      "⟦cite:docs/experiments/2026-07-11-knob-pointer-up.md;sha:11b34684⟧"
                      if KNOB_POINTER_UP else "")

# SEEK_SLOT_BULLET / SEEK_STRIP_BULLET: the LITE "seek is an empty slot" wording, PROMOTED TO
# MAINLINE 2026-07-12 (user directive, verbatim: "why even make it a flag. just roll into
# mainline") — the flag (SEEK_CLAUSE_LITE) and its HEAVY two-paragraph alternative are DELETED.
# History: the heavy bullets were hardened across many rounds, yet review-2026-07-11-round1.json
# still showed BAKED SLIDER THUMBS on 6+ skins (diablo-gothic, fallout-pipboy, fallout-vault,
# n64-cutscene, wc-goldshield confirmed by direct paint.png crop inspection; claymation's review
# note turned out to be a false read — its groove is genuinely empty, see TODO.md). Per the
# bproof lesson (constraint BULK costs quality, not just precision — more words compete for the
# model's finite per-call attention budget and don't reliably win the fight), stop trying to
# out-word the model: erase12.py is the proven safety net (a deterministic groove-anomaly
# detector + $0 classical inpaint, falling back to a ~$0.05-0.1 targeted model edit, that
# caught 4/6 review-flagged baked thumbs live — commit 5c378e5b) that catches a baked thumb
# post-hoc regardless of what the prompt said. That net is what makes the LITE wording safe as
# the ONLY path: PROMPT BUDGET stays freed for clauses erase12.py canNOT backstop (icon
# identity, silhouette, no-text, camera angle).
# ⟦cite:sha:5c378e5b;tools/mask-align-exp/gen12/erase12.py;tools/mask-align-exp/gen12/review-2026-07-11-round1.json;tools/mask-align-exp/gen12/TODO.md⟧
SEEK_SLOT_BULLET = (
    "  • The seek slot is an empty recessed channel — no thumb, grip or fill baked into it."
    "⟦cite:sha:5c378e5b;tools/mask-align-exp/gen12/erase12.py;docs/experiments/2026-07-10-bproof-constraint-load.md⟧\n"
)
SEEK_STRIP_BULLET = (
    "  • The seek strip cell shows the loose thumb/grip alone, not sitting in a slot or groove."
    "⟦cite:sha:5c378e5b;tools/mask-align-exp/gen12/erase12.py⟧\n"
)

# TOGGLE_TRACK_ENABLED: replace the shuffle TWO-STATE SPRITE-SWAP switch with a TWO-DETENT
# SLIDER, architecturally identical to the seek groove — a painted EMPTY TRACK/HOUSING on the
# device (recessed channel with two end positions, NO lever baked in) whose moving part is ONE
# loose lever sprite in the strip (was two: shuffle_off + shuffle_on). Kills all mirror/
# same-silhouette-two-states language: there is exactly one lever part now, not a pair to keep
# in sync — and that pair was exactly the failure mode: review-2026-07-11-round1.json's #1
# spread complaint was switch/slot mismatch (fa-pod "switch isnt scaled to slot, too small",
# steam-porthole "slot and switch dont match", n64-cutscene "siwtch doesnt match slot",
# wc-goldshield "fun switch but doesnt match slot", wmp-vario "siwtch doesnt match slot",
# claymation "switch doesnt fit slot" — 8+/14 skins named it). User-approved architecture
# change, 2026-07-12 (his hypothesis, refined). Validated in
# docs/experiments/2026-07-12-toggle-track.md. Default ON (the new architecture); flip False
# only to roll back to the old two-state path, which stays fully intact below so already-
# generated regions.json / assets keep rendering unchanged.
TOGGLE_TRACK_ENABLED = True

# ---- shuffle device-cavity clause (spliced into "EVERY MOVING-PART CAVITY IS EMPTY") ----
_SHUFFLE_CAVITY_TWOSTATE = ("The shuffle switch slot is an EMPTY DARK rounded well (NO switch, "
                             "NO lever, NO toggle installed). ")
_SHUFFLE_CAVITY_TRACK = (
    "The shuffle track is an EMPTY DARK recessed CHANNEL/HOUSING cut into the body, physically "
    "like a shorter version of the seek groove, with two end positions (NO lever, NO slider, NO "
    "switch, NO bolt installed — nothing riding in it). "
)
SHUFFLE_CAVITY_CLAUSE = _SHUFFLE_CAVITY_TRACK if TOGGLE_TRACK_ENABLED else _SHUFFLE_CAVITY_TWOSTATE

# ---- strip part count/list (varies: 3 parts in track mode, 4 in the legacy two-state mode) ----
SHUFFLE_STRIP_N = 3 if TOGGLE_TRACK_ENABLED else 4
SHUFFLE_STRIP_N_WORD = "THREE" if TOGGLE_TRACK_ENABLED else "FOUR"
SHUFFLE_STRIP_PARTS_COMMA = ("volume knob cap, seek slider thumb, shuffle lever" if TOGGLE_TRACK_ENABLED
    else "volume knob cap, seek slider thumb, shuffle switch first state, shuffle switch second state")
SHUFFLE_STRIP_PARTS_ARROW = ("volume knob cap, seek slider thumb, shuffle lever" if TOGGLE_TRACK_ENABLED
    else "volume knob cap, seek slider thumb, shuffle switch in its first state, shuffle switch in "
         "its second state")

# ---- SHUFFLE MECHANISM bullet — replaces SHUFFLE STATES, drops all mirror/state-pair language ----
_SHUFFLE_MECHANISM_TRACK = (
    "  • SHUFFLE MECHANISM — design a CHARACTERFUL two-position TRACK that fits the theme: any "
    "physical mechanism whose moving part travels a SHORT TRACK between two end positions — a "
    "lever slot, a sliding bolt channel, a valve track, a rotating latch groove, a bead that "
    "rides a rail — as long as it has ONE moving part riding a track (NOT a rocker/pill switch "
    "with two interchangeable faces, and NOT a mirror-pair of states). The track itself is "
    "painted EMPTY on the device (per the cavity rule above); its moving part — the lever — "
    "appears ONLY as the single loose strip part, shown by itself, NOT sitting in/on any track, "
    "groove, channel or recess in the strip (same isolation as the seek thumb). Put ABSOLUTELY "
    "NO text, letters, numerals, glyphs, words or labels of ANY kind on the lever or on ANY "
    "strip part.⟦cite:docs/experiments/2026-07-12-toggle-track.md⟧\n"
)
_SHUFFLE_MECHANISM_TWOSTATE = (
    "  • SHUFFLE STATES — design a CHARACTERFUL switch that fits the theme: it does NOT have to "
    "be a plain pill/rocker — a lever, flip-toggle, sliding bolt, rotating latch, gem that "
    "shifts, valve, eye that opens — any physical two-state mechanism, as long as BOTH states "
    "share the SAME OUTER HOUSING SILHOUETTE at the same size and are CLEARLY MIRROR-OPPOSITE: "
    "the moving element sits at ONE end/side in the first state and at the OPPOSITE end/side in "
    "the second state (never the same position in both). Put ABSOLUTELY NO text, letters, "
    "numerals, glyphs, words or labels of ANY kind on either switch part or on ANY strip part — "
    "the state must read from the mechanism's position alone, with zero markings."
    "⟦cite:sha:e8546e22;sha:ac28cd74;sha:3eeccc55⟧\n"
)
SHUFFLE_MECHANISM_BULLET = _SHUFFLE_MECHANISM_TRACK if TOGGLE_TRACK_ENABLED else _SHUFFLE_MECHANISM_TWOSTATE

# ---- EXACT FIT tail — the shuffle clause differs (a lever SLIDES within its track, it does not
# fill it, unlike the legacy state-swap sprite which filled the whole slot) ----
_SHUFFLE_EXACTFIT_TRACK = ("the shuffle lever is sized to SLIDE WITHIN the track — narrower than "
    "the track's long axis, matching its short axis, like the seek thumb inside the seek groove")
_SHUFFLE_EXACTFIT_TWOSTATE = "each shuffle state exactly fills the switch slot"
SHUFFLE_EXACTFIT_TAIL = _SHUFFLE_EXACTFIT_TRACK if TOGGLE_TRACK_ENABLED else _SHUFFLE_EXACTFIT_TWOSTATE

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
    "shuffle": ("an empty two-position TRACK/HOUSING for a sliding lever (no lever installed — "
                "the lever is a separate loose part)" if TOGGLE_TRACK_ENABLED
                else "a SHUFFLE icon (two crossing arrows)"),
    "visualizer": "a VISUALIZER / spectrum-analyzer display window",
    "album_art": "an ALBUM ART / cover display window",
}
# congruence contract — sizes shared between device slot and strip anchor (px on COL_W x DEV_H)
BTN_R, PLAY_R, KNOB_R = 74, 104, 84
GROOVE_W, GROOVE_H, THUMB_W, THUMB_H, THUMB_R = 640, 76, 150, 96, 44
TOG_W, TOG_H, TOG_R = 120, 178, 40
# TOGGLE_TRACK_ENABLED lever size — the loose MOVING PART that travels within the (unchanged)
# TOG_W x TOG_H track footprint above; smaller than the full track so it visibly slides WITHIN
# it rather than filling it (that "exact fit to slot" congruence was the OLD state-swap
# contract — see SHUFFLE_EXACTFIT_TAIL above). ~half the track's long axis, most of its short
# axis minus a margin so it visibly seats inside the track wall.
LEVER_W, LEVER_H, LEVER_R = TOG_W - 24, int(TOG_H * 0.42), 32
ART_W, ART_H, VIZ_W, VIZ_H = 560, 300, 640, 156

# ---------------------------------------------------------------- layout archetypes (templated)
# each entry: name -> {control: (fx, fy, kind, *size)}   fx,fy = fraction of (COL_W, DEV_H)
def _vpod():
    # album_art/visualizer gap widened 0.15/0.335 -> 0.13/0.36 (2026-07-11, artdrift fix):
    # the old pair sat ~2.7% of DEV_H apart (near-touching, two near-identical dark-glass
    # rects) -- the model had no visual cue to keep them stacked and 14/32 gens in the
    # artdrift analysis reinterpreted them as side-by-side or vertically swapped. New gap
    # ~7.2% of DEV_H, still leaves >2.5% margin above album_art and >2.9% before the seek
    # groove -- verified with --blueprint-only, no overlap. See artdrift_data.json + TODO.md.
    return {
        "album_art": (0.50, 0.13, "rect", ART_W, ART_H),
        "visualizer": (0.50, 0.36, "rect", VIZ_W, VIZ_H),
        "seek": (0.50, 0.47, "groove"),
        "prev": (0.28, 0.60, "btn", BTN_R), "playpause": (0.50, 0.60, "btn", PLAY_R),
        "next": (0.72, 0.60, "btn", BTN_R),
        "repeat": (0.24, 0.75, "btn", BTN_R), "vol": (0.42, 0.76, "knob"),
        "shuffle": (0.60, 0.76, "tog"), "queue": (0.78, 0.75, "btn", BTN_R),
    }
def _hcapsule():
    # checked against the same artdrift fix (2026-07-11): this pairing already sits ~12.6% of
    # DEV_H apart (0.30 vs 0.60, minus their half-heights) -- well clear of the vpod near-touch
    # bug above -- so no geometry change needed here; kept as-is.
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


def pick_blueprint_arm(gen_seed):
    """Deterministic weighted draw of the blueprint guide-STYLE arm ('solid'/'outline') for the
    longitudinal trial. Seeded from the GENERATION seed itself (no separately-stored draw seed) —
    re-running the same seed reproduces the same arm, no Math.random-style nondeterminism in the
    record. See BLUEPRINT_ARM_WEIGHTS for the favor-the-incumbent weighting."""
    rng = random.Random(gen_seed)
    x = rng.random(); acc = 0.0
    for name, w in BLUEPRINT_ARM_WEIGHTS:
        acc += w
        if x < acc:
            return name
    return BLUEPRINT_ARM_WEIGHTS[-1][0]


def draw_control_shape(d, kind, sz, x, y, col, style):
    """Draw one guide shape. style='solid' fills it with the guide colour (abshape-verdict
    winner); style='outline' strokes an outline only (the old/losing arm, kept for the trial).
    Shared by the single-canvas solid/outline arms AND the twoimg guided reference image (which
    always uses style='solid' — that experiment only ever varied single- vs two-image
    conditioning, not guide style)."""
    if kind == "btn":
        r = sz[0]
        if style == "solid": d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        else: d.line(poly_circle(x, y, r) + [poly_circle(x, y, r)[0]], fill=col, width=12)
    elif kind == "knob":
        if style == "solid": d.ellipse([x - KNOB_R, y - KNOB_R, x + KNOB_R, y + KNOB_R], fill=col)
        else: d.ellipse([x - KNOB_R, y - KNOB_R, x + KNOB_R, y + KNOB_R], outline=col, width=12)
    elif kind == "groove":
        box = [x - GROOVE_W / 2, y - GROOVE_H / 2, x + GROOVE_W / 2, y + GROOVE_H / 2]
        if style == "solid": d.rounded_rectangle(box, radius=35, fill=col)
        else: d.rounded_rectangle(box, radius=35, outline=col, width=13)
    elif kind == "tog":
        box = [x - TOG_W / 2, y - TOG_H / 2, x + TOG_W / 2, y + TOG_H / 2]
        if style == "solid": d.rounded_rectangle(box, radius=TOG_R, fill=col)
        else: d.rounded_rectangle(box, radius=TOG_R, outline=col, width=13)
    elif kind == "rect":
        w, hh = sz; box = [x - w / 2, y - hh / 2, x + w / 2, y + hh / 2]
        if style == "solid": d.rounded_rectangle(box, radius=28, fill=col)
        else: d.rounded_rectangle(box, radius=28, outline=col, width=13)


def build_canvas(BG, layout, KEYS, guide_style):
    """Build one templated-mode two-column joint canvas (device placeholder + strip band).
    guide_style='solid'|'outline' paints colour-key guide shapes with draw_control_shape;
    guide_style=None paints the SAME placeholder body + strip band with ZERO guide-coloured
    pixels — the clean edit-target canvas used by BLUEPRINT_TWOIMG. Ported from
    twoimg/genskin_twoimg.py:build_canvas (proven code, not reinvented)."""
    W = COL_W * 2
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    d.rectangle([COL_W, 0, W, H], fill=(0, 0, 0))
    d.line([COL_W, 0, COL_W, H], fill=(70, 70, 74), width=3)
    d.line([0, DEV_H, COL_W, DEV_H], fill=(70, 70, 74), width=3)
    d.rounded_rectangle([70, 60, COL_W - 70, DEV_H - 40], radius=140, fill=(140, 140, 146))
    template = {}
    for name, spec_l in layout.items():
        fx, fy, kind, *sz = spec_l
        x, y = COL_W * fx, DEV_H * fy
        if guide_style:
            draw_control_shape(d, kind, sz, x, y, KEYS[name], guide_style)
        template[name] = [fx, fy * DEVF]
    sy = DEV_H + (H - DEV_H) // 2
    # TOGGLE_TRACK_ENABLED: ONE lever cell (was two: OFF/ON state pair) — 3-cell strip instead
    # of 4. Own spacing formula (evenly spread 3 cells); the legacy 4-cell spacing is untouched
    # so a flag=False regen keeps producing byte-identical geometry (rollback safety).
    if TOGGLE_TRACK_ENABLED:
        cells = [(KNOB, "circle"), (SLIDER, "thumb"), (TOGGLE, "lever")]
        cx_of = lambda i: COL_W * (0.18 + 0.32 * i)   # 3 cells: .18, .50, .82
    else:
        cells = [(KNOB, "circle"), (SLIDER, "thumb"), (TOGGLE, "tog"), (TOGGLE, "tog")]
        cx_of = lambda i: COL_W * (0.13 + 0.20 * i)   # unchanged 4-cell spacing
    for i, (k, shp) in enumerate(cells):
        cx = cx_of(i)
        if not guide_style: continue
        col = KEYS[k]
        if shp == "circle":
            if guide_style == "solid": d.ellipse([cx - KNOB_R, sy - KNOB_R, cx + KNOB_R, sy + KNOB_R], fill=col)
            else: d.ellipse([cx - KNOB_R, sy - KNOB_R, cx + KNOB_R, sy + KNOB_R], outline=col, width=12)
        elif shp == "thumb":
            box = [cx - THUMB_W / 2, sy - THUMB_H / 2, cx + THUMB_W / 2, sy + THUMB_H / 2]
            if guide_style == "solid": d.rounded_rectangle(box, radius=THUMB_R, fill=col)
            else: d.rounded_rectangle(box, radius=THUMB_R, outline=col, width=12)
        elif shp == "lever":
            box = [cx - LEVER_W / 2, sy - LEVER_H / 2, cx + LEVER_W / 2, sy + LEVER_H / 2]
            if guide_style == "solid": d.rounded_rectangle(box, radius=LEVER_R, fill=col)
            else: d.rounded_rectangle(box, radius=LEVER_R, outline=col, width=12)
        else:   # "tog" — legacy two-state cell (drawn twice, once per state)
            box = [cx - TOG_W / 2, sy - TOG_H / 2, cx + TOG_W / 2, sy + TOG_H / 2]
            if guide_style == "solid": d.rounded_rectangle(box, radius=TOG_R, fill=col)
            else: d.rounded_rectangle(box, radius=TOG_R, outline=col, width=12)
    return img, template


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


def edit(FAL, urls, prompt, seed):
    """urls: list of one or more uploaded image URLs (fal's image_urls is already array-typed —
    N>1 is used by BLUEPRINT_TWOIMG's two-reference-image conditioning)."""
    job = requests.post(f"https://queue.fal.run/{MODEL}",
        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
        json={"prompt": prompt, "image_urls": urls, "resolution": "4K", "aspect_ratio": "5:4",
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
    # 429 retry — same backoff edit_vertex_multi() carries (proven there); without it a
    # quota blip burns a whole orchestrate12 roll per 429 (4 skins x 3 rolls burned to
    # RESOURCE_EXHAUSTED with zero real generations, 2026-07-11 re-roll batch).
    for attempt in range(5):
        r = requests.post(VERTEX_URL, headers={"Authorization": f"Bearer {tok}",
                                                "Content-Type": "application/json"},
                           json=body, timeout=420)
        if r.status_code == 429 and attempt < 4:
            wait = 15 * (attempt + 1)
            print(f"[vertex] 429 rate-limited, retry {attempt+1}/5 in {wait}s", flush=True)
            time.sleep(wait)
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:500]}")
    for part in r.json()["candidates"][0]["content"]["parts"]:
        d = part.get("inlineData") or part.get("inline_data") or {}
        if d.get("data"):
            return base64.b64decode(d["data"])
    raise RuntimeError("vertex: no image part in response")


def edit_vertex_multi(image_paths, prompt, seed, aspect="5:4"):
    """Vertex generateContent with N inline_data image parts + one text part. Extends
    edit_vertex() to multiple reference images for BLUEPRINT_TWOIMG. Ported line-for-line from
    twoimg/genskin_twoimg.py:edit_vertex_multi() (proven code, already ran real generations
    there) — same request shape, `parts` is just a list; adds the 429 retry twoimg found useful."""
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    parts = []
    for p in image_paths:
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        parts.append({"inline_data": {"mime_type": "image/png", "data": b64}})
    parts.append({"text": prompt})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "seed": seed,
            "candidateCount": 1,
            "imageConfig": {"aspectRatio": aspect, "imageSize": "4K"},
        },
    }
    for attempt in range(5):
        r = requests.post(VERTEX_URL, headers={"Authorization": f"Bearer {tok}",
                                                "Content-Type": "application/json"},
                           json=body, timeout=420)
        if r.status_code == 429 and attempt < 4:
            wait = 15 * (attempt + 1)
            print(f"[vertex] 429 rate-limited, retry {attempt+1}/5 in {wait}s", flush=True)
            time.sleep(wait)
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:500]}")
    for part in r.json()["candidates"][0]["content"]["parts"]:
        d = part.get("inlineData") or part.get("inline_data") or {}
        if d.get("data"):
            return base64.b64decode(d["data"])
    raise RuntimeError("vertex: no image part in response")


# ------------------------------------------------------------------------------------- PROMPT_JSON_SPEC
# Ported (structure + wording) from jsonspec/genskin_jsonspec.py's build_spec_json() /
# build_treatment_prompt() — the harness actually scored by the 2026-07-11 experiment (see the
# flag's why-comment above). Only the module-level names differ (no `G.` prefix; we ARE genskin.py).
# Tick bullets (tick_skin_bullet/tick_sprite_bullet — a feature that shipped before jsonspec/ ran
# and that harness never referenced) are spliced in at the SAME textual position as the production
# prose prompt below, so PROMPT_JSON_SPEC=True doesn't silently drop the tick-provisioning feature.
def _json_spec_control_size_frac(kind, sz):
    if kind in ("btn", "knob"):
        r = sz[0] if kind == "btn" else KNOB_R
        return {"shape": "circle", "radius_frac_of_col_w": round(r / COL_W, 4)}
    if kind == "groove":
        return {"shape": "rounded_rect", "w_frac_of_col_w": round(GROOVE_W / COL_W, 4),
                 "h_frac_of_dev_h": round(GROOVE_H / DEV_H, 4)}
    if kind == "tog":
        return {"shape": "rounded_rect", "w_frac_of_col_w": round(TOG_W / COL_W, 4),
                 "h_frac_of_dev_h": round(TOG_H / DEV_H, 4)}
    if kind == "rect":
        w, h = sz
        return {"shape": "rounded_rect", "w_frac_of_col_w": round(w / COL_W, 4),
                 "h_frac_of_dev_h": round(h / DEV_H, 4)}
    return {}


def _build_json_spec_obj(KEYS, layout):
    controls = []
    for name in CONTROLS:
        fx, fy, kind, *sz = layout[name]
        controls.append({
            "id": name,
            "role": ROLES[name],
            "guide_color_name": cname(KEYS[name]),
            "guide_color_rgb": list(KEYS[name]),
            "final_icon_or_content": ICON[name],
            "position_frac": {"fx": round(fx, 4), "fy_of_device_area": round(fy, 4)},
            **_json_spec_control_size_frac(kind, sz),
        })
    strip_sizes = {
        "vol_cap": {"shape": "circle", "radius_frac_of_col_w": round(KNOB_R / COL_W, 4)},
        "seek_thumb": {"shape": "rounded_rect", "w_frac_of_col_w": round(THUMB_W / COL_W, 4),
                       "h_frac_of_dev_h": round(THUMB_H / DEV_H, 4)},
    }
    if TOGGLE_TRACK_ENABLED:
        strip_sizes["shuffle_lever"] = {"shape": "rounded_rect", "w_frac_of_col_w": round(LEVER_W / COL_W, 4),
                                         "h_frac_of_dev_h": round(LEVER_H / DEV_H, 4)}
        strip_order = ["vol_cap", "seek_thumb", "shuffle_lever"]
        congruence_rule = ("each strip part's size EXACTLY equals its matching device slot's size "
                            "above (vol_cap radius == vol's radius_frac_of_col_w; seek_thumb fits "
                            "the seek groove; the shuffle_lever SLIDES WITHIN the shuffle track, "
                            "narrower than its long axis, matching its short axis)")
    else:
        strip_sizes["shuffle_state"] = {"shape": "rounded_rect", "w_frac_of_col_w": round(TOG_W / COL_W, 4),
                                         "h_frac_of_dev_h": round(TOG_H / DEV_H, 4)}
        strip_order = ["vol_cap", "seek_thumb", "shuffle_state_1", "shuffle_state_2"]
        congruence_rule = ("each strip part's size EXACTLY equals its matching device slot's size "
                            "above (vol_cap radius == vol's radius_frac_of_col_w; seek_thumb fits "
                            "the seek groove; each shuffle_state exactly fills the shuffle slot)")
    return {
        "_note": ("machine-readable control spec. position_frac is a fraction of the device "
                  "column's own width (fx) and the device area's own height (fy), guide_color_rgb "
                  "marks this control's blueprint position ONLY and must never be painted into the "
                  "finished device, sizes are congruence-locked between the device slot and its "
                  "matching loose strip part."),
        "controls": controls,
        "strip_order_left_to_right": strip_order,
        "strip_part_sizes": strip_sizes,
        "congruence_rule": congruence_rule,
    }


def _build_json_spec_prompt(KEYS, layout, dark, BG, STRUCT, tick_skin_bullet, tick_sprite_bullet):
    spec_obj = _build_json_spec_obj(KEYS, layout)
    json_block = "```json\n" + json.dumps(spec_obj, indent=1) + "\n```"
    NO_LIST = ", ".join(f"NO {cname(KEYS[c]).lower()}" for c in CONTROLS)

    preamble = ("Two side-by-side columns of identical size, output at 5:4. Below is THE "
                "MACHINE-READABLE SPEC for this generation — follow it exactly for every "
                "control's identity, guide-colour, position and size:"
                "⟦cite:docs/experiments/2026-07-11-jsonspec-paint.md;sha:7445fb15;sha:8abf3e8a⟧"
                "\n\n" + json_block + "\n")
    left_layout = (
        "The LEFT column is a BLUEPRINT: a neutral grey placeholder body with COLOURED SOLID "
        "FILLED patches marking each control's exact position/size/shape PER THE SPEC ABOVE, "
        f"plus a bottom SPRITE-STRIP band with {len(spec_obj['strip_order_left_to_right'])} loose "
        "parts in the order given by the spec's "
        "strip_order_left_to_right. KEEP EVERY CONTROL AT THE EXACT POSITION, SIZE AND SHAPE "
        "given by the spec — do NOT move, resize, swap, rearrange, add or drop any control "
        "(their layout, as specified, is locked). BUT the grey body is ONLY a rough placeholder "
        "showing WHERE the controls sit — you are FREE and STRONGLY ENCOURAGED to sculpt a BOLD, "
        "DISTINCTIVE, ASYMMETRIC, theme-appropriate outer HOUSING around them: an ornate, "
        "characterful, sculpted form with a memorable silhouette (organic curves, wings, pods, "
        "fins, greebles, ornament, asymmetry) — NOT a plain rounded rectangle, NOT a generic "
        "slab or pod. Reshape the outer silhouette DRAMATICALLY to suit the theme; ONLY the "
        "control positions given by the spec stay fixed. The coloured filled patches described "
        "in the spec are ALIGNMENT MARKINGS (like masking tape) and MUST be completely removed."
        "⟦cite:sha:794da20e;docs/experiments/2026-07-11-drift-clause-bisect.md;tools/mask-align-exp/gen12/abshape/verdict.json⟧")
    residue_bullet = (
        "  • ZERO RESIDUE (CRITICAL) — the coloured guide patch around EVERY control is a "
        "temporary alignment marking, NOT part of the design. It must VANISH completely. Each "
        "finished BUTTON is ONE solid piece of the device's own material with absolutely NO "
        "coloured ring, rim, bezel, halo, outline or edge-tint around it — if a button has a "
        "coloured ring, it is WRONG. Likewise the album-art and visualizer windows have NO "
        "coloured frame (just a dark recessed glass panel flush in the body), and no "
        "socket/groove/slot has any coloured rim. Paint the body/button material seamlessly "
        "OVER where each guide patch was.⟦cite:tools/mask-align-exp/gen12/abshape/verdict.json;sha:8c97ef9a⟧\n")

    prompt = (
        preamble + " ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO CAPTIONS and NO "
        "LABELS anywhere in EITHER column — not under controls, not on the strip, not a title, "
        "nothing; the device is wordless, identified by icons and shapes only.⟦cite:sha:794da20e;sha:3eeccc55⟧ "
        + left_layout + "\n"
        "THEME (design the finished device in THIS style — you own all materials, colours, "
        "form, lighting):⟦cite:sha:794da20e⟧ " + STRUCT + "\n"
        "Fill BOTH columns keeping the device+strip layout IDENTICAL so they overlay "
        "pixel-for-pixel.⟦cite:sha:794da20e⟧\n"
        "LEFT column — the FINISHED, richly 3D, tactile, skeuomorphic media player and its "
        "loose parts, in the theme above.⟦cite:sha:794da20e⟧ CRITICAL for cutout: the BACKDROP around the device "
        f"and BEHIND every strip part is a FLAT, PERFECTLY UNIFORM "
        f"{'pale grey-white' if dark else 'near-black charcoal'} tone (RGB ~{BG[0]},{BG[1]},{BG[2]}) "
        "— a separate keyed-out backdrop with NO gradient/texture/vignette that strongly "
        "contrasts the body; the device must never approach the backdrop tone."
        "⟦cite:sha:794da20e;docs/DECISIONS.md⟧\n"
        "  • The finished device uses ONLY its own theme materials/colours — NONE of the guide "
        f"colours from the spec. ABSOLUTELY {NO_LIST} anywhere in the LEFT column; the guide "
        "colours from the spec exist ONLY in the RIGHT mask.⟦cite:sha:794da20e⟧\n"
        + residue_bullet
        + "  • The 5 transport/function BUTTONS (playpause, prev, next, repeat, queue) are "
        "raised, glossy, tactile control facets set into the body, EACH clearly bearing its "
        "icon EMBOSSED/engraved in relief per the spec's final_icon_or_content field for that "
        "control. Shape + icon + relief only; no text labels; no coloured rim.⟦cite:sha:794da20e⟧\n"
        "  • BUTTON COLOURS COME FROM THE THEME, NEVER FROM THE GUIDES: a button's guide_color "
        "in the spec marks its POSITION ONLY — the finished button's material/fill must NOT "
        "inherit, echo or be tinted toward its guide colour in ANY way (no red play because its "
        "guide was red, no magenta next, etc). ALL five buttons are made of the device's OWN "
        "theme materials/palette, coloured consistently with each other and the body. If any "
        "button's colour visibly matches its spec guide_color, the output is WRONG.⟦cite:sha:a8bbaad0⟧\n"
        "  • THE SINGLE MOST IMPORTANT RULE — EVERY MOVING-PART CAVITY IS EMPTY. The volume "
        "knob socket is a bare round HOLE showing only its dark recessed floor (NO knob, NO "
        "cap, NO dome, NO dial, NO pointer — nothing installed). The seek slider groove is an "
        "EMPTY DARK RECESSED CHANNEL cut into the body (NO thumb, NO grip, NO handle, NO fill "
        "— it is NOT a coloured or filled bar, it is a hollow dark slot). "
        + SHUFFLE_CAVITY_CLAUSE +
        "The device is photographed BEFORE ASSEMBLY: those parts exist ONLY in the bottom sprite "
        "strip and have NOT been installed yet. Do NOT colour the empty wells — neutral DARK "
        "recesses only. If ANY of the three cavities (knob socket, seek slot, shuffle slot) "
        "contains ANY part or any fill colour, the output is WRONG and must be redone."
        "⟦cite:sha:794da20e;docs/experiments/2026-07-10-bproof-constraint-load.md;docs/DECISIONS.md⟧\n"
        + tick_skin_bullet
        + SEEK_SLOT_BULLET
        + "  • The ALBUM-ART window and the VISUALIZER window are BLANK, DARK, EMPTY recessed "
        "glass SCREENS — flat unlit dark glass panels only, with NOTHING inside them: NO baked "
        "spectrum/equalizer bars, NO album cover or artwork, NO waveform, NO icons, NO text, NO "
        "content whatsoever. They are powered-down screens; the app draws their live content "
        "later. If either window contains any baked graphics, it is WRONG.⟦cite:sha:794da20e;sha:3eeccc55⟧ "
        "The album-art window "
        "sits ABOVE the visualizer window, clearly separated — never side-by-side, never swapped."
        "⟦cite:sha:e8f249db;tools/mask-align-exp/gen12/artdrift_data.json⟧\n"
        f"  • SPRITE STRIP — EXACTLY {SHUFFLE_STRIP_N_WORD} finished parts in ONE horizontal row, in the order "
        f"given by the spec's strip_order_left_to_right ({SHUFFLE_STRIP_PARTS_COMMA}) — in the device's own "
        f"materials, patches removed, on the flat {'pale' if dark else 'charcoal'} backdrop."
        "⟦cite:docs/experiments/2026-07-12-toggle-track.md⟧\n"
        + tick_sprite_bullet
        + SEEK_STRIP_BULLET
        + "  • EXACT FIT — per the spec's congruence_rule: each strip part is the EXACT size & "
        f"shape of its slot (vol_cap radius = vol's socket radius; seek_thumb fits the groove; "
        f"{SHUFFLE_EXACTFIT_TAIL}). Do NOT resize/re-proportion a part."
        "⟦cite:sha:794da20e;tools/mask-align-exp/gen12/review-2026-07-11-round1.json;docs/experiments/2026-07-12-toggle-track.md⟧\n"
        + SHUFFLE_MECHANISM_BULLET
        + "  • CAMERA — this is THE MOST COMMON MISTAKE, get it right: render EVERY strip part in "
        "a PERFECTLY FLAT, STRAIGHT-DOWN, TOP-DOWN ORTHOGRAPHIC view — the camera is directly "
        "overhead at exactly 90°, the same view as the device. Each part is drawn as if lying "
        "FLAT on a table seen from straight above, with ZERO thickness, height or depth "
        "visible. The volume knob cap is a FLAT ROUND DISC / COIN — you see ONLY its circular "
        "TOP FACE (a knurled outer rim and a small pointer notch" + _POINTER_UP_CLAUSE + "); you must NOT see any "
        "cylindrical SIDE WALL, edge, height or 3D body of the knob. The seek thumb and the "
        f"shuffle {'lever' if TOGGLE_TRACK_ENABLED else 'switch'} are likewise flat shapes seen from directly overhead. ABSOLUTELY NO "
        "product-shot angle, NO 3/4 view, NO tilt, NO isometric, NO perspective, NO visible "
        "sides — a part showing its side wall or any thickness is WRONG. Each part must look "
        "EXACTLY as it appears seated flat in its socket on the top-down device, so it drops "
        "straight in.⟦cite:sha:794da20e⟧\n"
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
        "is WRONG⟦cite:sha:86f69c75⟧; and each STRIP PART as a solid COMPACT blob of its matching control's "
        "guide_color_rgb (vol_cap uses vol's colour, seek_thumb uses seek's colour, "
        f"{'the shuffle_lever uses' if TOGGLE_TRACK_ENABLED else 'BOTH shuffle states use'} shuffle's colour)"
        "⟦cite:docs/experiments/2026-07-12-toggle-track.md⟧ exactly matching its part's silhouette & position "
        "in the strip, in the spec's strip_order_left_to_right. CRITICAL: each blob is TIGHT to "
        "its shape — NEVER let a colour bleed or stretch across the strip band or flood a "
        f"rectangle; the {SHUFFLE_STRIP_N_WORD.lower()} strip blobs are {len(spec_obj['strip_order_left_to_right'])} separate compact shapes with black gaps between "
        "them. Every blob is ONE solid filled silhouette, no outlines, no holes. Everything "
        "else is pure black.⟦cite:sha:794da20e;sha:ac28cd74⟧")
    return prompt


def main():
    spec = json.load(open(sys.argv[1]))
    sid = spec["id"]; mode = spec["mode"]; seed = spec.get("seed", 71)
    palette = {k: tuple(v) for k, v in spec["palette"].items()}
    dark = spec.get("material_is_dark", False)
    # director-decided knob tick-mark provisioning (WIRE-pbr.md "ticks" schema, sibling of
    # css/lighting): {"skin":"baked"|"css"|"none","sprite":"baked"|"css"|"none"}. A spec
    # without this block behaves as {"skin":"css","sprite":"css"} (build_player.py's default).
    ticks_spec = spec.get("ticks", {})
    BG = (235, 235, 238) if dark else (18, 18, 24)
    OUT = os.path.join(HERE, f"assets-{sid}"); os.makedirs(OUT, exist_ok=True)
    keys = pick_keys(palette)
    KEYS = dict(zip(CONTROLS, keys))
    layout = LAYOUTS[spec.get("layout", "vpod")]() if mode == "templated" else None

    # -------- blueprint conditioning: trial arm draw (solid/outline) + twoimg mode --------
    # arm draw only applies to templated mode (templateless has no guide pixels to vary — untouched).
    trial_arm = pick_blueprint_arm(seed) if (mode == "templated" and BLUEPRINT_TRIAL_ENABLED) else "solid"
    use_twoimg = mode == "templated" and (BLUEPRINT_TWOIMG or spec.get("conditioning") == "twoimg")
    conditioning = "twoimg" if use_twoimg else trial_arm

    # -------- blueprint --------
    W = COL_W * 2
    guided_path = None
    if mode == "templated":
        if use_twoimg:
            guided_img, template = build_canvas(BG, layout, KEYS, "solid")
            edit_img, _ = build_canvas(BG, layout, KEYS, None)
            guided_path = os.path.join(OUT, "blueprint-guided.png"); guided_img.save(guided_path)
        else:
            edit_img, template = build_canvas(BG, layout, KEYS, conditioning)  # 'solid' or 'outline'
    else:
        # templateless: scaffold only — a faint 'device area' hint box + strip band, NO controls
        edit_img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(edit_img)
        d.rectangle([COL_W, 0, W, H], fill=(0, 0, 0)); d.line([COL_W, 0, COL_W, H], fill=(70, 70, 74), width=3)
        d.line([0, DEV_H, COL_W, DEV_H], fill=(70, 70, 74), width=3)
        d.text((90, 40), "", fill=(0, 0, 0))
        template = {}
    bp = os.path.join(OUT, "blueprint.png"); edit_img.save(bp)
    image_paths = [bp] + ([guided_path] if guided_path else [])

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
           "ticks": ticks_spec,  # director-authored knob tick provisioning (build_player.py)
           # director CSS chrome colors (WIRE-pbr.md "css") — passthrough so build_player.py's
           # RES.get("css") resolves even when the assets dir's SID has no theme_specs/<SID>.json
           # (suffixed experiment/re-roll ids); the spec-file fallback there still covers
           # pre-existing assets generated before this passthrough existed.
           "css": spec.get("css", {}),
           "template": template if mode == "templated" else {},
           # -------- blueprint-conditioning trial record (additive; see TODO.md) --------
           "blueprint_trial_enabled": BLUEPRINT_TRIAL_ENABLED,
           "blueprint_arm": trial_arm,               # what the weighted draw picked: solid|outline
           "blueprint_arm_draw_seed": seed,          # == the generation seed; re-running it reproduces trial_arm
           "blueprint_twoimg": use_twoimg,           # whether twoimg mode overrode the trial arm this gen
           "blueprint_conditioning": conditioning,   # the arm ACTUALLY used to build the blueprint: solid|outline|twoimg
           # shuffle architecture (2026-07-12): True = two-detent TRACK slider (1 strip cell,
           # regions[toggle] gets track/detents/vertical from extract12); False = legacy
           # two-state sprite-swap (2 strip cells, off/on). Downstream (extract12/biref12/
           # build_player) reads this instead of re-deriving mode from cell count.
           "toggle_track_enabled": TOGGLE_TRACK_ENABLED}
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
    # defaults (templateless, and the single-canvas solid/outline arms use these column refs)
    fill_line = ("Fill BOTH columns keeping the device+strip layout IDENTICAL so they overlay pixel-for-pixel."
                 "⟦cite:sha:794da20e⟧\n")
    left_col_hdr = ("LEFT column — the FINISHED, richly 3D, tactile, skeuomorphic media player and its loose "
                     "parts, in the theme above.⟦cite:sha:794da20e⟧")
    right_col_hdr = ("RIGHT column — a precise REGION MASK on pure BLACK, pixel-aligned to the LEFT."
                     "⟦cite:sha:794da20e;docs/DECISIONS.md⟧")
    left_ref = "the left"
    strip_side = "the left"
    mask_guide_ref = ""
    residue_bullet = (
        "  • ZERO RESIDUE (CRITICAL) — the coloured guide outline around EVERY control is a temporary alignment "
        "marking, NOT part of the design. It must VANISH completely. Each finished BUTTON is ONE solid piece of the "
        "device's own material with absolutely NO coloured ring, rim, bezel, halo, outline or edge-tint around it — "
        "if a button has a coloured ring, it is WRONG. Likewise the album-art and visualizer windows have NO "
        "coloured frame (just a dark recessed glass panel flush in the body), and no socket/groove/slot has any "
        "coloured rim. Paint the body/button material seamlessly OVER where each guide outline was."
        "⟦cite:tools/mask-align-exp/gen12/abshape/verdict.json;sha:8c97ef9a⟧\n")
    if mode == "templated":
        if conditioning == "twoimg":
            # ported from twoimg/genskin_twoimg.py:build_prompt('treat', ...) — proven wording,
            # adapted only for the mainline variable names (arm/conditioning instead of arm='treat').
            preamble = ("TWO images are provided. IMAGE 1 is the EDIT TARGET / CANVAS — two side-by-side "
                "columns of identical size, output at 5:4, matching IMAGE 1's layout exactly. IMAGE 2 is a "
                "LAYOUT REFERENCE ONLY, shown purely to tell you WHERE each control goes — it is NOT part of "
                "the canvas you edit and NONE of its colours may ever appear in your output."
                "⟦cite:docs/experiments/2026-07-10-twoimg-conditioning.md⟧")
            left_layout = (
                "IMAGE 1's LEFT column is a neutral grey placeholder body (a rough blob, no colour markings "
                "at all) plus a bottom SPRITE-STRIP band that is currently EMPTY/blank. IMAGE 2 shows the SAME "
                "placeholder body and the SAME strip band, but with COLOURED SOLID FILLED patches marking each "
                "control's EXACT position, size and shape — READ IMAGE 2 to know where each control belongs, "
                "then PAINT that control at that exact position/size/shape into IMAGE 1's left column. Each "
                "guide colour in IMAGE 2 maps to a control: " + roster_desc + ". COPY THE POSITION, SIZE AND "
                "SHAPE of every guide shape from IMAGE 2 exactly (their layout is locked) — but IMAGE 2's "
                "COLOURS ARE NEVER PAINTED anywhere in your output; they exist ONLY in IMAGE 2, purely as "
                "position markers for you to read, and must not leak, echo, tint or appear in ANY form in "
                "IMAGE 1's edited output. The grey body in IMAGE 1 is ONLY a rough placeholder showing roughly "
                "where the controls sit — you are FREE and STRONGLY ENCOURAGED to sculpt a BOLD, DISTINCTIVE, "
                "ASYMMETRIC, theme-appropriate outer HOUSING around them: an ornate, characterful, sculpted "
                "form with a memorable silhouette (organic curves, wings, pods, fins, greebles, ornament, "
                "asymmetry) — NOT a plain rounded rectangle, NOT a generic slab or pod. Reshape the outer "
                "silhouette DRAMATICALLY to suit the theme; ONLY the control positions (as shown by IMAGE 2) "
                "stay fixed.⟦cite:docs/experiments/2026-07-10-twoimg-conditioning.md;sha:794da20e⟧")
            fill_line = ("Fill BOTH columns of your OUTPUT (matching IMAGE 1's device+strip layout) keeping "
                          "them pixel-aligned.\n")
            left_col_hdr = ("LEFT column of your output — the FINISHED, richly 3D, tactile, skeuomorphic "
                             "media player and its loose parts, in the theme above.")
            right_col_hdr = "RIGHT column of your output — a precise REGION MASK on pure BLACK, pixel-aligned to your LEFT column."
            left_ref = "your LEFT column"
            strip_side = "your LEFT"
            mask_guide_ref = " (as shown in IMAGE 2)"
            residue_bullet = (
                "  • ZERO RESIDUE (CRITICAL) — no coloured ring, rim, bezel, halo, outline or edge-tint of ANY "
                "guide colour may appear around any button, socket, groove or slot. Each finished BUTTON is ONE "
                "solid piece of the device's own material with NO coloured ring around it — if a button has a "
                "coloured ring, it is WRONG. Likewise the album-art and visualizer windows have NO coloured "
                "frame (just a dark recessed glass panel flush in the body), and no socket/groove/slot has any "
                "coloured rim.⟦cite:tools/mask-align-exp/gen12/abshape/verdict.json;sha:8c97ef9a⟧\n")
        else:
            preamble = ("Two side-by-side columns of identical size, output at 5:4."
                        "⟦cite:sha:794da20e;docs/DECISIONS.md⟧")
            guide_word = "SOLID FILLED patches" if conditioning == "solid" else "OUTLINE guides"
            marking_word = "filled patches" if conditioning == "solid" else "outlines"
            residue_word = "patch" if conditioning == "solid" else "outline"
            left_layout = ("The LEFT column is a BLUEPRINT: a neutral grey placeholder body with COLOURED "
                f"{guide_word} marking each control's EXACT position, size and shape, plus a bottom SPRITE-STRIP "
                f"band with {SHUFFLE_STRIP_N} loose parts ({SHUFFLE_STRIP_PARTS_COMMA}). "
                "Each guide's colour maps to a control: " + roster_desc + ". KEEP EVERY CONTROL AT THE EXACT POSITION, "
                "SIZE AND SHAPE OF ITS GUIDE — do NOT move, resize, swap, rearrange, add or drop any control (their "
                "layout is locked). BUT the grey body is ONLY a rough placeholder showing WHERE the controls sit — you "
                "are FREE and STRONGLY ENCOURAGED to sculpt a BOLD, DISTINCTIVE, ASYMMETRIC, theme-appropriate outer "
                "HOUSING around them: an ornate, characterful, sculpted form with a memorable silhouette (organic curves, "
                "wings, pods, fins, greebles, ornament, asymmetry) — NOT a plain rounded rectangle, NOT a generic slab or "
                "pod. Reshape the outer silhouette DRAMATICALLY to suit the theme; ONLY the control positions stay fixed. "
                f"The coloured {marking_word} are ALIGNMENT MARKINGS (like masking tape) and MUST be completely removed."
                "⟦cite:sha:794da20e;docs/experiments/2026-07-11-drift-clause-bisect.md;tools/mask-align-exp/gen12/abshape/verdict.json⟧")
            residue_bullet = (
                f"  • ZERO RESIDUE (CRITICAL) — the coloured guide {residue_word} around EVERY control is a temporary "
                "alignment marking, NOT part of the design. It must VANISH completely. Each finished BUTTON is ONE solid "
                "piece of the device's own material with absolutely NO coloured ring, rim, bezel, halo, outline or "
                "edge-tint around it — if a button has a coloured ring, it is WRONG. Likewise the album-art and "
                "visualizer windows have NO coloured frame (just a dark recessed glass panel flush in the body), and no "
                f"socket/groove/slot has any coloured rim. Paint the body/button material seamlessly OVER where each "
                f"guide {residue_word} was.⟦cite:tools/mask-align-exp/gen12/abshape/verdict.json;sha:8c97ef9a⟧\n")
    else:
        preamble = ("Two side-by-side columns of identical size, output at 5:4."
                    "⟦cite:sha:794da20e;docs/DECISIONS.md⟧")
        left_layout = ("The LEFT column has a thin horizontal DIVIDER LINE near the bottom: everything ABOVE it is "
            "the DEVICE AREA, the thin band BELOW it is the SPRITE STRIP. YOU design the device from scratch. Paint "
            "EXACTLY ONE single media player filling the device area (do NOT draw two devices, variants, copies, "
            "alternates, or a size range — ONE player only), containing EXACTLY these controls, each a distinct "
            "recognizable element, each appearing EXACTLY ONCE: " + roster_desc + ". Give the housing a BOLD, "
            "DISTINCTIVE, ASYMMETRIC silhouette with real character — an ornate, sculpted, memorable form (curves, "
            "wings, pods, fins, greebles, ornament) that suits the theme, NOT a plain pod, slab or rectangle. "
            "Arrange the controls in one attractive layout of your choosing. In the bottom strip band below the divider, paint "
            f"EXACTLY {SHUFFLE_STRIP_N_WORD} loose parts in ONE row left-to-right: {SHUFFLE_STRIP_PARTS_ARROW} "
            "— and NOTHING else in the strip."
            "⟦cite:sha:794da20e;sha:3eeccc55;docs/experiments/2026-07-12-toggle-track.md⟧")

    # -------- knob tick-mark provisioning (director-decided, per-spec) --------
    # docs/experiments/2026-07-11-knob-tick-provisioning.md found baked ticks UNRELIABLE
    # (0/8 adjudicated PASS) specifically because the clause NAMED positions (MIN/MAX/CENTER) —
    # that vocabulary baked in as literal engraved TEXT. These clauses stay deliberately LIGHT:
    # describe the physical mark only, never a position-label word, never an angle number.
    tick_skin_bullet = (
        "  • The panel immediately surrounding the volume knob's socket carries a swept ring of "
        "tick or index marks framing the opening, cut/engraved/cast into the device's own housing "
        "material and finish — subtle, part of the panel, not a separate applied sticker. This is "
        "on the surrounding panel only; the socket cavity itself stays the bare empty hole described "
        "above.⟦cite:docs/experiments/2026-07-11-knob-tick-provisioning.md;sha:8679c132⟧\n"
    ) if ticks_spec.get("skin") == "baked" else ""
    tick_sprite_bullet = (
        "  • The volume knob cap (the loose strip part) carries one small pointer or index mark at "
        "its rim, in the device's own material and finish, clearly distinguishable from the rest of "
        "the cap's surface so its rotation reads at a glance."
        "⟦cite:docs/experiments/2026-07-11-knob-tick-provisioning.md;sha:8679c132⟧\n"
    ) if ticks_spec.get("sprite") == "baked" else ""

    # PROMPT_JSON_SPEC only covers what jsonspec/ tested: templated mode, 'solid' conditioning
    # (see the flag's why-comment at the top of the file). Every other path (outline/twoimg
    # conditioning, templateless mode) keeps the prose prompt below byte-for-byte.
    use_json_spec = PROMPT_JSON_SPEC and mode == "templated" and conditioning == "solid"
    res["prompt_json_spec"] = use_json_spec
    if use_json_spec:
        prompt = _build_json_spec_prompt(KEYS, layout, dark, BG, STRUCT, tick_skin_bullet, tick_sprite_bullet)
    else:
        prompt = (
        preamble + " ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO "
        "NUMBERS, NO CAPTIONS and NO LABELS anywhere in EITHER column — not under controls, not on the strip, not "
        "a title, nothing; the device is wordless, identified by icons and shapes only."
        "⟦cite:sha:794da20e;sha:3eeccc55⟧ " + left_layout + "\n"
        "THEME (design the finished device in THIS style — you own all materials, colours, form, lighting):"
        "⟦cite:sha:794da20e⟧ "
        + STRUCT + "\n"
        + fill_line
        + left_col_hdr + " CRITICAL for cutout: the BACKDROP around the device and BEHIND every strip part is a FLAT, "
        f"PERFECTLY UNIFORM {'pale grey-white' if dark else 'near-black charcoal'} tone (RGB ~{BG[0]},{BG[1]},{BG[2]}) "
        "— a separate keyed-out backdrop with NO gradient/texture/vignette that strongly contrasts the body; the "
        "device must never approach the backdrop tone.⟦cite:sha:794da20e;docs/DECISIONS.md⟧\n"
        "  • The finished device uses ONLY its own theme materials/colours — NONE of the guide colours. ABSOLUTELY "
        f"{NO_LIST} anywhere in the LEFT column; the guide colours exist ONLY in the RIGHT mask."
        "⟦cite:sha:794da20e⟧\n"
        + residue_bullet
        + "  • The 5 transport/function BUTTONS (play/pause, previous, next, repeat, queue) are raised, glossy, "
        "tactile control facets set into the body, EACH clearly bearing its icon EMBOSSED/engraved in relief: "
        + "; ".join(f"{ICON[c]}" for c in BUTTONS) + ". Shape + icon + relief only; no text labels; no coloured rim."
        "⟦cite:sha:794da20e⟧\n"
        "  • BUTTON COLOURS COME FROM THE THEME, NEVER FROM THE GUIDES: the guide colour of a button marks its "
        "POSITION ONLY — the finished button's material/fill must NOT inherit, echo or be tinted toward its guide "
        "colour in ANY way (no red play because its guide was red, no magenta next, etc). ALL five buttons are made "
        "of the device's OWN theme materials/palette, coloured consistently with each other and the body. If any "
        "button's colour visibly matches its guide colour, the output is WRONG.⟦cite:sha:a8bbaad0⟧\n"
        "  • THE SINGLE MOST IMPORTANT RULE — EVERY MOVING-PART CAVITY IS EMPTY. The volume knob socket is a bare "
        "round HOLE showing only its dark recessed floor (NO knob, NO cap, NO dome, NO dial, NO pointer — nothing "
        "installed). The seek slider groove is an EMPTY DARK RECESSED CHANNEL cut into the body (NO thumb, NO grip, "
        "NO handle, NO fill — it is NOT a coloured or filled bar, it is a hollow dark slot). "
        + SHUFFLE_CAVITY_CLAUSE +
        "The device is photographed BEFORE "
        "ASSEMBLY: those parts exist ONLY in the bottom sprite strip and have NOT been installed yet. Do NOT colour "
        "the empty wells — neutral DARK recesses only. If ANY of the three cavities (knob socket, seek slot, "
        "shuffle slot) contains ANY part or any fill colour, the output is WRONG and must be redone."
        "⟦cite:sha:794da20e;docs/experiments/2026-07-10-bproof-constraint-load.md;docs/DECISIONS.md⟧\n"
        + tick_skin_bullet
        + SEEK_SLOT_BULLET
        + "  • The ALBUM-ART window and the VISUALIZER window are BLANK, DARK, EMPTY recessed glass SCREENS — flat "
        "unlit dark glass panels only, with NOTHING inside them: NO baked spectrum/equalizer bars, NO album cover "
        "or artwork, NO waveform, NO icons, NO text, NO content whatsoever. They are powered-down screens; the app draws "
        "their live content later. If either window contains any baked graphics, it is WRONG.⟦cite:sha:794da20e;sha:3eeccc55⟧ "
        "The album-art window "
        "sits ABOVE the visualizer window, clearly separated — never side-by-side, never swapped."
        "⟦cite:sha:e8f249db;tools/mask-align-exp/gen12/artdrift_data.json⟧\n"
        f"  • SPRITE STRIP — EXACTLY {SHUFFLE_STRIP_N_WORD} finished parts in ONE horizontal row, left→right: {SHUFFLE_STRIP_PARTS_ARROW} "
        "— in the device's own materials, outlines removed, on "
        f"the flat {'pale' if dark else 'charcoal'} backdrop.⟦cite:docs/experiments/2026-07-12-toggle-track.md⟧\n"
        + tick_sprite_bullet
        + SEEK_STRIP_BULLET
        + "  • EXACT FIT — each strip part is the EXACT size & shape of its slot (knob cap = socket diameter; thumb "
        f"fits the groove; {SHUFFLE_EXACTFIT_TAIL}). Do NOT resize/re-proportion a part."
        "⟦cite:sha:794da20e;tools/mask-align-exp/gen12/review-2026-07-11-round1.json;docs/experiments/2026-07-12-toggle-track.md⟧\n"
        + SHUFFLE_MECHANISM_BULLET
        + "  • CAMERA — this is THE MOST COMMON MISTAKE, get it right: render EVERY strip part in a PERFECTLY FLAT, "
        "STRAIGHT-DOWN, TOP-DOWN ORTHOGRAPHIC view — the camera is directly overhead at exactly 90°, the same view "
        "as the device. Each part is drawn as if lying FLAT on a table seen from straight above, with ZERO "
        "thickness, height or depth visible. The volume knob cap is a FLAT ROUND DISC / COIN — you see ONLY its "
        "circular TOP FACE (a knurled outer rim and a small pointer notch" + _POINTER_UP_CLAUSE + "); you must NOT see any cylindrical SIDE "
        f"WALL, edge, height or 3D body of the knob. The seek thumb and the shuffle {'lever' if TOGGLE_TRACK_ENABLED else 'switch'} are likewise flat shapes "
        "seen from directly overhead. ABSOLUTELY NO product-shot angle, NO 3/4 view, NO tilt, NO isometric, NO "
        "perspective, NO visible sides — a part showing its side wall or any thickness is WRONG. Each part must "
        "look EXACTLY as it appears seated flat in its socket on the top-down device, so it drops straight in."
        "⟦cite:sha:794da20e⟧\n"
        + right_col_hdr + " For EACH control paint ONE "
        "SOLID FILLED blob in ITS OWN guide colour" + mask_guide_ref + ", at the EXACT same position, size and silhouette as that control "
        "on " + left_ref + " (the seek-slider blob is a FULL-HEIGHT horizontal bar matching the groove, NOT a thin line; "
        "the shuffle blob is a tall portrait rounded-rectangle; each knob/button blob a solid disc): " + mask_lines
        + ". DISPLAY-WINDOW BLOBS — the visualizer and album-art blobs must EXACTLY cover their painted "
        "window's GLASS area on " + left_ref + ": the SAME rectangle at the SAME position with the SAME rounded "
        "corners, edge-to-edge with the glass — never larger than the bezel opening, never smaller, never "
        "shifted or offset onto the surrounding body. Trace each window's glass outline precisely; a display "
        "blob that extends past its painted window, covers body/bezel around it, or sits off the window is WRONG"
        "⟦cite:sha:86f69c75⟧"
        + "; and each STRIP PART as a solid COMPACT blob of its colour (volume cap=" + kn(KNOB).lower()
        + ", seek thumb=" + kn(SLIDER).lower()
        + (", shuffle lever=" if TOGGLE_TRACK_ENABLED else ", BOTH shuffle states=") + kn(TOGGLE).lower() + ") exactly matching "
        f"its part's silhouette & position in {strip_side} strip. CRITICAL: each blob is TIGHT to its shape — NEVER let a "
        f"colour bleed or stretch across the strip band or flood a rectangle; the {SHUFFLE_STRIP_N_WORD.lower()} strip blobs are {SHUFFLE_STRIP_N} separate "
        "compact shapes with black gaps between them. Every blob is ONE solid filled silhouette, no outlines, no "
        "holes. Everything else is pure black.⟦cite:sha:794da20e;sha:ac28cd74⟧")

    # ---- provenance strip (prompt_provenance.py) ----
    # The assembled text above carries ⟦cite:...⟧ markers (why each clause exists). NOTHING
    # cited ever reaches the model or the persisted results.json "prompt" field: strip here,
    # byte-identical to the pre-annotation prompt (verified across all flag states — see
    # prompt_provenance.py's docstring + PROMPT-PROVENANCE.md, which renders prompt_annotated).
    prompt_annotated = prompt
    prompt = strip_cites(prompt)

    if "--blueprint-only" in sys.argv:
        json.dump({**res, "prompt_len": len(prompt), "prompt": prompt,
                   "prompt_annotated": prompt_annotated, "image_paths": image_paths},
                   open(os.path.join(OUT, "results.json"), "w"), indent=1)
        print(f"[blueprint-only] {sid} mode={mode} conditioning={conditioning} keys ok, "
              f"prompt {len(prompt)} chars, {len(image_paths)} image(s) → {image_paths}")
        return

    if PAINT_VERTEX:
        if len(image_paths) > 1:
            t = time.time(); out = edit_vertex_multi(image_paths, prompt, seed)
        else:
            t = time.time(); out = edit_vertex(bp, prompt, seed)
    else:
        FAL = load_fal()
        urls = [upload(FAL, p) for p in image_paths]
        t = time.time(); out = edit(FAL, urls, prompt, seed)
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
