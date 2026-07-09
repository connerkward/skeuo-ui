#!/usr/bin/env python3
"""run11 — WILD Y2K / FRUTIGER-AERO player, MODEL-DESIGNED. The blueprint carries ONLY the
component LAYOUT (organic placeholder silhouette + control outlines); ALL look-design — housing
form, materials, colour scheme — is handed to the image model. Explicitly NOT chrome-on-grey,
NOT lava/magma: glossy translucent glass + brushed metal + backlit accents, model's choice.

THE KEY GENERALIZATION vs run9: the guide-colour contract is DATA, not constants. The design
palette is declared first; 9 guide keys are then picked MAXIMALLY DISTANT from the palette AND
from each other (RGB distance >=120 both ways, extractor gates sat>55 max>90), verified
numerically, and the full {control: rgb} map + backdrop + template geometry are written to
assets10/results.json. extract10.py / run_biref10.py read everything from there — zero
hardcoded colours anywhere downstream.

Joint contract kept from run9: LEFT = paint+strip on a flat backdrop picked OPPOSITE the
material lightness, RIGHT = colour-keyed mask on pure black, 5:4, 4K, split w//2; strip anchor
geometry == device slot geometry (congruence, defined once); anti-leak masking-tape framing +
ZERO RESIDUE; the "photographed BEFORE ASSEMBLY" emptiness block kept VERBATIM; leak gate."""
import os, re, io, time, json, sys, math
import requests
from PIL import Image, ImageDraw

def load_fal_key():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")
FAL = load_fal_key()
MODEL = "fal-ai/gemini-3-pro-image-preview/edit"
OUT = os.path.join(os.path.dirname(__file__), "assets11"); os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- design palette (DATA, first)
MATERIAL_IS_DARK = False         # bright glossy body → dark backdrop keys out cleanly
BG = (235,235,238) if MATERIAL_IS_DARK else (18,18,24)
PALETTE = {                      # the design's LIKELY major colours (cool Y2K/frutiger-aero) —
    "aqua_blue":    (30,120,235),   # keys must stay >=120 from ALL of these, so the model can
    "cyan_glass":   (70,205,230),   # paint freely in blues/teals/silver/glass without leaking
    "deep_teal":    (20,110,120),   # into a guide colour
    "liquid_silver":(175,185,200),
    "gloss_white":  (240,244,250),
    "warm_amber":   (255,175,45),   # a warm accent glow the model may reach for
    "ink_navy":     (20,26,48),
    "backdrop":     BG,
}
CONTROLS = ["prev","play","next","stop","vol","bal","seek","tog","screen"]
NAME = {(0,0,255):"PURE BLUE",(0,128,255):"AZURE SKY-BLUE",(0,255,255):"CYAN",
        (0,128,128):"DARK TEAL",(0,255,128):"SPRING GREEN",(0,255,0):"PURE GREEN",
        (128,255,0):"CHARTREUSE",(128,0,255):"VIOLET-PURPLE",(255,0,255):"MAGENTA",
        (128,128,255):"LAVENDER-PERIWINKLE",(128,255,128):"PALE MINT-GREEN",
        (128,0,128):"DEEP PURPLE",(0,0,128):"NAVY BLUE",(255,0,128):"ROSE PINK",
        (128,255,255):"PALE AQUA",(255,128,255):"ORCHID PINK",(0,128,0):"FOREST GREEN"}
def cname(c): return NAME.get(tuple(c), f"RGB{tuple(c)}")

def pick_keys(palette, n=9):
    """Adaptive colour contract: candidates on the {0,128,255}^3 lattice (any two distinct
    lattice points are >=127 apart, so pairwise distance is guaranteed by construction),
    filtered by the extractor gates (sat>55, max>90) and by RGB distance >=120 from EVERY
    palette major; ranked by distance-from-palette, top n win."""
    cands=[(r,g,b) for r in (0,128,255) for g in (0,128,255) for b in (0,128,255)
           if (max((r,g,b))-min((r,g,b)))>55 and max((r,g,b))>90]
    scored=[]
    for c in cands:
        dm=min(math.dist(c,p) for p in palette.values())
        if dm>=120: scored.append((round(dm,1),c))
    scored.sort(key=lambda t:(-t[0],t[1]))
    keys=[c for _,c in scored[:n]]
    if len(keys)<n: sys.exit(f"palette too greedy: only {len(keys)} guide keys survive")
    # numeric verification + printed matrix
    pts={f"K:{cname(k)}":k for k in keys}; pts.update({f"P:{p}":v for p,v in palette.items()})
    names=list(pts)
    print("distance matrix (guide keys K vs keys+palette P) — contract: every K-K and K-P >=120")
    kk=[nm for nm in names if nm.startswith("K:")]
    print(" "*24+" ".join(f"{nm[2:8]:>7}" for nm in names))
    ok=True
    for a in kk:
        row=[]
        for b in names:
            d=math.dist(pts[a],pts[b])
            row.append(f"{d:7.0f}")
            if a!=b and d<120: ok=False
        print(f"{a[2:]:>24} "+" ".join(row))
    if not ok: sys.exit("KEY CONTRACT VIOLATED: a guide key is <120 from a key/palette colour")
    print(f"[keys] {len(keys)} guide keys pass (min pairwise>=127 by lattice, min vs palette>=120)")
    return keys
KEYS = dict(zip(CONTROLS, pick_keys(PALETTE)))
HB = {k:KEYS[k] for k in ["prev","play","next","stop"]}
SP = {k:KEYS[k] for k in ["vol","bal","seek","tog"]}
SC = {"screen":KEYS["screen"]}

BD_CAP,BD_LOW,BD_TONE = ("PALE GREY-WHITE","pale grey-white","pale") if MATERIAL_IS_DARK else \
                        ("NEAR-BLACK CHARCOAL","charcoal","dark")
BODY_VS,BD_APPROACH = ("DARKER","lightness") if MATERIAL_IS_DARK else ("BRIGHTER","darkness")
BODY = (140,140,144)
COL_W,H = 1200,1920; DEV_H = 1440

# ------------------------------------------------------------------- organic blob body (polar)
CX,CYC = 0.50*COL_W, 715.0
A_H, B_TOP, B_BOT = 505.0, 580.0, 680.0
BUMPS = [(-1.30,0.13,0.055),(-1.82,0.13,0.055),   # two horn nubs on top
         (-math.pi/2,0.08,0.55),                   # broad crown dome (covers the screen)
         (0.15,0.14,0.30),                         # right side pod
         (math.pi-0.35,0.12,0.28),                 # left-low pod
         (math.pi/2,0.05,0.45)]                    # chin bulge (covers the toggle)
def blob_r(th):
    b = B_TOP + (B_BOT-B_TOP)*(math.sin(th)+1)/2   # egg blend: taller reach below centre
    ct,st = math.cos(th), math.sin(th)
    re = A_H*b/math.hypot(b*ct, A_H*st)
    m = 1 + 0.03*math.sin(4*th+1.3) + 0.02*math.sin(7*th+0.5)
    for mu,amp,sig in BUMPS:
        d = math.atan2(math.sin(th-mu), math.cos(th-mu))
        m += amp*math.exp(-(d/sig)**2/2)
    return re*m
def blob_pts(n=160):
    pts=[]
    for i in range(n):
        th=-math.pi+2*math.pi*i/n; r=blob_r(th)
        x=min(max(CX+r*math.cos(th),10),COL_W-10)
        y=min(max(CYC+r*math.sin(th),8),0.973*DEV_H)
        pts.append((x,y))
    return pts

def crescent_pts():
    pts=[]
    for a in range(60,301,20):
        r=math.radians(a); pts.append((math.cos(r),math.sin(r)))
    for a in range(285,74,-20):
        r=math.radians(a); pts.append((0.35+0.62*math.cos(r),0.62*math.sin(r)))
    return pts
SHAPES={
 "pebble":  [(-1.15,-.2),(-.6,-.62),(.1,-.72),(.72,-.55),(1.1,-.05),(.85,.42),(.25,.66),(-.4,.6),(-.9,.32)],
 "teardrop":[(0,-1.3),(.3,-.6),(.68,.05),(.62,.6),(.12,.92),(-.45,.8),(-.72,.25),(-.3,-.65)],
 "kidney":  [(-1,-.2),(-.4,-.9),(.5,-.8),(1,-.1),(.7,.4),(1,.8),(.2,1),(-.7,.7),(-1,.3)],
 "crescent":crescent_pts()}
BTN=[("prev","pebble",  0.36,0.360, 88,-0.3),
     ("play","teardrop",0.635,0.385,92, 0.5),
     ("next","kidney",  0.38,0.530, 86, 0.25),
     ("stop","crescent",0.65,0.550, 90,-0.55)]
KNOB={"vol":(0.365,0.780),"bal":(0.635,0.780)}
SEEK=(0.50,0.665); TOG=(0.50,0.885)
SCREEN_RECT=(0.32,0.14,0.68,0.25)     # fx0,fy0,fx1,fy1 of (COL_W, DEV_H)
# CONGRUENCE CONTRACT — strip anchor geometry == device slot geometry, defined ONCE here:
KNOB_R=76
TOG_W,TOG_H,TOG_R=110,170,38
GROOVE_W,GROOVE_H=520,70
THUMB_W,THUMB_H,THUMB_R=150,92,44

def poly_at(cx,cy,pts,scale,rot=0):
    c,s=math.cos(rot),math.sin(rot)
    return [(cx+(x*c-y*s)*scale, cy+(x*s+y*c)*scale) for (x,y) in pts]
def rrect(d,cx,cy,w,h,col,r=24):
    d.rounded_rectangle([cx-w/2,cy-h/2,cx+w/2,cy+h/2],radius=r,outline=col,width=13)

def containment_check():
    """Every control guide must sit fully INSIDE the blob body (8px margin). Programmatic —
    the organic silhouette is tuned until this passes, not eyeballed."""
    import numpy as np
    from scipy import ndimage
    m=Image.new("L",(COL_W,DEV_H),0); ImageDraw.Draw(m).polygon(blob_pts(),fill=255)
    body=ndimage.binary_erosion(np.asarray(m)>128,iterations=8)
    def inside(px):
        return all(body[min(DEV_H-1,max(0,int(y))),min(COL_W-1,max(0,int(x)))] for x,y in px)
    checks={}
    for b,shp,fx,fy,sc,rot in BTN:
        checks[b]=poly_at(COL_W*fx,DEV_H*fy,SHAPES[shp],scale=sc*1.08,rot=rot)
    for k,(fx,fy) in KNOB.items():
        x,y=COL_W*fx,DEV_H*fy
        checks[k]=[(x+ (KNOB_R+8)*math.cos(t),y+(KNOB_R+8)*math.sin(t)) for t in
                   [i*math.pi/8 for i in range(16)]]
    for nm,(fx,fy),(w,h) in [("seek",SEEK,(GROOVE_W,GROOVE_H)),("tog",TOG,(TOG_W,TOG_H))]:
        x,y=COL_W*fx,DEV_H*fy
        checks[nm]=[(x+sx*w/2,y+sy*h/2) for sx in(-1,0,1) for sy in(-1,0,1)]
    x0,y0,x1,y1=[SCREEN_RECT[i]*(COL_W if i%2==0 else DEV_H) for i in range(4)]
    checks["screen"]=[(x,y) for x in(x0,(x0+x1)/2,x1) for y in(y0,(y0+y1)/2,y1)]
    bad=[k for k,px in checks.items() if not inside(px)]
    if bad: sys.exit(f"BLOB CONTAINMENT FAIL: {bad} poke outside the body — retune blob params")
    print("[containment] all 9 controls inside the organic body (8px erosion margin)")

def make_blueprint():
    W=COL_W*2; img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    d.rectangle([COL_W,0,W,H],fill=(0,0,0)); d.line([COL_W,0,COL_W,H],fill=(70,70,74),width=3)
    # ORGANIC BLOB body — asymmetric magma silhouette with horn nubs + pods (not a rect!)
    d.polygon(blob_pts(),fill=BODY)
    # screen (dark glass) — guide-colour outline marks it as a mask region
    x0,y0,x1,y1=[SCREEN_RECT[i]*(COL_W if i%2==0 else DEV_H) for i in range(4)]
    d.rounded_rectangle([x0,y0,x1,y1],radius=40,fill=(18,19,22),outline=SC["screen"],width=12)
    # vent pores on the right pod (uncoloured structural dots, like run9's grille)
    for i,(vx,vy) in enumerate([(0.72,0.46),(0.755,0.445),(0.79,0.455),(0.74,0.49),
                                (0.775,0.50),(0.81,0.49),(0.755,0.53),(0.79,0.545)]):
        x,y=COL_W*vx,DEV_H*vy; r=8-(i%3); d.ellipse([x-r,y-r,x+r,y+r],fill=(60,60,64))
    # 4 ORGANIC transport buttons (outline only, guide colour)
    for b,shp,fx,fy,sc,rot in BTN:
        pts=poly_at(COL_W*fx,DEV_H*fy,SHAPES[shp],scale=sc,rot=rot)
        d.line(pts+[pts[0]],fill=HB[b],width=12,joint="curve")
    # seek slider groove
    rrect(d,COL_W*SEEK[0],DEV_H*SEEK[1],GROOVE_W,GROOVE_H,SP["seek"],r=35)
    # 2 knob sockets
    for k,(fx,fy) in KNOB.items():
        x,y=COL_W*fx,DEV_H*fy; d.ellipse([x-KNOB_R,y-KNOB_R,x+KNOB_R,y+KNOB_R],outline=SP[k],width=12)
    # toggle socket
    rrect(d,COL_W*TOG[0],DEV_H*TOG[1],TOG_W,TOG_H,SP["tog"],r=TOG_R)
    d.line([0,DEV_H,COL_W,DEV_H],fill=(70,70,74),width=3)
    sy=DEV_H+(H-DEV_H)//2
    # 5 strip cells — anchors CLONE the device geometry above (same size, same shape)
    cells=[("vol","circle"),("bal","circle"),("seek","thumb"),("tog","tog"),("tog","tog")]
    for i,(k,shp) in enumerate(cells):
        x=COL_W*(0.11+0.195*i)
        if shp=="circle": d.ellipse([x-KNOB_R,sy-KNOB_R,x+KNOB_R,sy+KNOB_R],outline=SP[k],width=12)
        elif shp=="thumb": rrect(d,x,sy,THUMB_W,THUMB_H,SP[k],r=THUMB_R)
        else: rrect(d,x,sy,TOG_W,TOG_H,SP[k],r=TOG_R)
    p=os.path.join(OUT,"blueprint.png"); img.save(p); return p

def upload(p):
    init=requests.post("https://rest.alpha.fal.ai/storage/upload/initiate",
        headers={"Authorization":f"Key {FAL}","Content-Type":"application/json"},
        json={"file_name":os.path.basename(p),"content_type":"image/png"}).json()
    requests.put(init["upload_url"],headers={"Content-Type":"image/png"},data=open(p,"rb").read())
    return init["file_url"]

def edit(url,prompt,aspect="5:4",res="4K",seed=41):
    job=requests.post(f"https://queue.fal.run/{MODEL}",
        headers={"Authorization":f"Key {FAL}","Content-Type":"application/json"},
        json={"prompt":prompt,"image_urls":[url],"resolution":res,"aspect_ratio":aspect,
              "output_format":"png","num_images":1,"seed":seed}).json()
    t0=time.time()
    while True:
        s=requests.get(job["status_url"],headers={"Authorization":f"Key {FAL}"}).json().get("status")
        if s=="COMPLETED": break
        if s in ("FAILED","ERROR") or time.time()-t0>420: raise RuntimeError(f"fal {s}")
        time.sleep(4)
    r=requests.get(job["response_url"],headers={"Authorization":f"Key {FAL}"}).json()
    return requests.get(r["images"][0]["url"]).content

def n(k): return cname(KEYS[k])
def rgbs(k): return ",".join(str(v) for v in KEYS[k])
NO_LIST=", ".join(f"NO {cname(KEYS[k]).lower()}" for k in CONTROLS)

PROMPT=("Two side-by-side columns of identical size. LEFT column: a BLUEPRINT of an early-2000s Y2K ALIEN "
  "MEDIA PLAYER (there is NO text anywhere — the coloured outlines ARE the guides). The grey silhouette is an "
  "ORGANIC ASYMMETRIC placeholder body — deliberately NOT a rectangle, NOT a rounded rectangle, NOT symmetric — "
  "and YOU may resculpt its surface and outline freely into a flowing Y2K gadget form (keep the overall extent "
  "and every control POSITION). Every control is identified by BOTH its guide colour AND its shape+position: "
  f"{n('prev')} upper-left PEBBLE=PREV, {n('play')} upper-right TEARDROP=PLAY, {n('next')} lower-left "
  f"KIDNEY-BEAN=NEXT, {n('stop')} lower-right CRESCENT-MOON=STOP — each button an ORGANIC IRREGULAR shape, "
  f"deliberately NOT a circle and NOT a rectangle; {n('vol')} left circle=VOLUME knob socket, {n('bal')} "
  f"right circle=BALANCE knob socket; the {n('seek')} rounded horizontal bar=the SEEK slider track; the "
  f"{n('tog')} rounded slot near the bottom=the TOGGLE switch socket; the {n('screen')}-outlined dark "
  "rounded rectangle near the top=the SCREEN (dark glassy media-player LCD window); the small dots on the right "
  "pod=vent pores. "
  "IMPORTANT: these coloured outlines are ALIGNMENT MARKINGS on a technical drawing — like masking tape on a "
  "workpiece — they are NOT part of the product's design and must be COMPLETELY removed in the finished paint. "
  "The BOTTOM BAND of the left column is a SPRITE STRIP with the loose PARTS to manufacture, left to right: "
  f"(1) {n('vol')} circle=volume knob cap, (2) {n('bal')} circle=balance knob cap, (3) {n('seek')} outline="
  f"seek slider thumb (a wide low grip), (4) {n('tog')}=the toggle switch in its OFF position, (5) {n('tog')}"
  "=the SAME toggle switch in its ON position (lever flipped). RIGHT column: pure black.\n"
  "Fill everything, keeping the LEFT column's device+strip layout IDENTICAL in the RIGHT column so the two "
  "overlay pixel-for-pixel:\n"
  "LEFT column — paint the FINISHED player and parts as a WILD, GLOSSY, EXPENSIVE early-2000s Y2K / FRUTIGER-"
  "AERO gadget (in the spirit of a translucent Winamp / Sonique / WMP skin, or a sleek alien consumer device): "
  "a richly three-dimensional, tactile, skeuomorphic object built from LUSH materials — polished chrome and "
  "brushed aluminium, deep TRANSLUCENT TINTED GLASS, glossy candy plastic, soft rubberised trim — with crisp "
  "specular highlights, reflections, and soft ambient occlusion pooling in every crease and socket. YOU ARE THE "
  "DESIGNER: choose a vivid, cohesive, premium colour scheme — lean into deep aquatic BLUES / cyans / teals and "
  "liquid silver with luminous backlit accent glows, or surprise me — but it MUST be saturated, glossy and "
  "dimensional. Do NOT make it flat matte grey, do NOT do boring chrome-on-grey, and do NOT make it lava / "
  "magma / volcanic. Sculpt the placeholder silhouette into a cohesive organic form (bevels, panel seams, "
  f"gloss, translucency, vents, subtle greebles). Every surface of the device and every loose part must stay "
  f"clearly {BODY_VS} and more saturated than the backdrop. CRITICAL for cutout: the "
  f"BACKDROP around the device and BEHIND every strip part is a FLAT, PERFECTLY UNIFORM {BD_CAP} — "
  "a separate backdrop that gets KEYED OUT to cut the device and parts free. It MUST strongly CONTRAST the "
  f"volcanic body (the body must never approach the backdrop's {BD_APPROACH}), be one solid uniform "
  f"{BD_TONE} tone with NO gradient/texture/vignette, and must not tint or bleed onto anything.\n"
  "  • The device and every control/part must contain NONE of the guide colours — the finished device uses "
  "ONLY its own design materials (glass, metal, glossy plastic, backlit accents), never a guide hue. ABSOLUTELY "
  f"{NO_LIST} paint ANYWHERE in the left column — the painted transport buttons are glossy bare control facets; "
  "the guide colours exist ONLY in the RIGHT mask column.\n"
  "  • ZERO RESIDUE — where a coloured guide outline was, paint the body material seamlessly over it. Do NOT "
  "leave ANY thin coloured rim, ring, halo, edge tint or glow around ANY socket, button, slot or part (e.g. "
  f"no {n('tog').lower()} rim around the toggle socket, no {n('seek').lower()} edge on the seek groove, no "
  f"{n('vol').lower()}/{n('bal').lower()} ring around a knob socket). Inspect every socket edge: if even a "
  "sliver of guide colour survives, the output is WRONG.\n"
  "  • The 4 transport buttons are MOLDED into the body as raised GLOSSY control facets that KEEP their EXACT "
  "irregular ORGANIC outlines from the guide — the pebble stays a pebble, the teardrop stays a teardrop, the "
  "kidney stays a kidney bean, the crescent stays a crescent moon. Do NOT round any of them into a circle, "
  "do NOT square any of them into a rectangle, do NOT add icons, symbols or text on them — shape and relief "
  "only. Remove the guide outlines.\n"
  "  • THE SINGLE MOST IMPORTANT RULE — EVERY CAVITY ON THE DEVICE IS EMPTY. The 2 knob sockets, the seek "
  "slider track, and the toggle socket are EMPTY, HOLLOW, DARK recessed wells/grooves cut into the body with "
  "ABSOLUTELY NOTHING inside any of them: NO knob, NO dome, NO nub, NO cap, NO dial, NO thumb, NO handle, NO "
  "bead, NO lever, NO switch, NO button — nothing. Each is a bare empty hole showing only its dark recessed "
  "floor. This device is photographed BEFORE ASSEMBLY: all five loose parts (two knob caps, the slider thumb, "
  "the toggle in both states) exist ONLY in the sprite strip at the bottom and have NOT been installed yet. "
  "If ANY socket or groove on the device contains ANY part, the output is WRONG. Do not colour the empty "
  "wells either — neutral dark recesses.\n"
  "  • SPRITE STRIP — paint EXACTLY FIVE parts in ONE SINGLE horizontal row (do NOT add a second row, do NOT "
  "duplicate the parts, do NOT repeat), left to right: volume knob cap, balance knob cap, slider thumb, toggle "
  "switch OFF, toggle switch ON — finished parts in the SAME materials/colours as the device, on the flat "
  f"{BD_LOW} backdrop, outlines removed, uncoloured.\n"
  "  • EXACT FIT — every strip part's guide outline is drawn at the EXACT SAME SIZE AND SHAPE as its slot on "
  "the device, and the painted part MUST match its outline precisely: each knob cap is exactly the diameter of "
  "its socket circle, each toggle part exactly fills the toggle-socket outline (same rounded-rect, same "
  "proportions, in its OFF / ON state), and the slider thumb matches its outline (a wide, low grip that rides "
  "the groove). Do NOT resize, restyle, or re-proportion any part relative to its outline — a part that does "
  "not fit its slot is WRONG.\n"
  "  • CRITICAL — CAMERA/VIEW: render EVERY strip part from the EXACT SAME straight-down, FLAT, TOP-DOWN "
  "ORTHOGRAPHIC view as the device above (you are looking directly DOWN from straight overhead at 90°). A knob "
  "cap is a FLAT CIRCLE seen from directly above — show ONLY its round top face with a knurled metal or glass rim and a "
  "small raised pointer notch; you must NOT see the cylindrical SIDE of the knob at all. The slider thumb and "
  "the toggle switch are likewise seen from straight overhead, flat. ABSOLUTELY NO 3/4 perspective, NO "
  "product-shot angle, NO tilt, NO isometric view, NO visible sides or depth — each part must look EXACTLY as "
  "it appears when seated flat in its socket on the top-down device, so it drops in and lines up perfectly.\n"
  f"  • The screen is a dark glassy LCD — remove its {n('screen').lower()} outline, keep it essentially UNLIT and "
  "content-free (no icons, no text, no album art; a faint even backlit sheen is OK) with a slim bezel; the vent pores are tiny drilled "
  "holes.\n"
  "RIGHT column — a REGION MASK on pure BLACK. Fill each target with a FLAT solid colour aligned to the "
  "left, in ITS OWN guide colour (the same colour its outline has in the blueprint): each BUTTON facet "
  f"filled in its EXACT organic outline (PEBBLE/prev={n('prev').lower()} {rgbs('prev')}; TEARDROP/play="
  f"{n('play').lower()} {rgbs('play')}; KIDNEY/next={n('next').lower()} {rgbs('next')}; CRESCENT/stop="
  f"{n('stop').lower()} {rgbs('stop')}); each on-device SOCKET (LEFT-circle volume={n('vol').lower()} "
  f"{rgbs('vol')}; RIGHT-circle balance={n('bal').lower()} {rgbs('bal')}; seek track bar={n('seek').lower()} "
  f"{rgbs('seek')}; toggle slot={n('tog').lower()} {rgbs('tog')}); the SCREEN as ONE SOLID rounded rectangle "
  f"({n('screen').lower()} {rgbs('screen')}) that EXACTLY covers the screen glass on the device; and each "
  f"STRIP PART as a SOLID FLAT blob of its part's colour (volume cap={n('vol').lower()}, balance cap="
  f"{n('bal').lower()}, seek thumb={n('seek').lower()}, BOTH toggle states={n('tog').lower()}) that EXACTLY "
  "matches that part's SILHOUETTE in the left column — same shape, same size, same position. NEVER flood a "
  "whole strip cell or any rectangle of background with colour; NEVER draw outlines or hollow shapes — every "
  "blob is ONE solid filled silhouette, no interior holes. Everything else pure black.")

def leak_check(paint_path):
    """LEAK GATE: scan the PAINT panel for surviving guide colours. The >=120 key-vs-palette
    contract is what keeps this gate valid on a VIVID paint: no legit design colour can come
    within 60 of a key."""
    import numpy as np
    a=np.asarray(Image.open(paint_path).convert("RGB")).astype(int)
    tot=a.shape[0]*a.shape[1]; worst=("none",0.0)
    sat=(a.max(2)-a.min(2))>55
    for name,c in KEYS.items():
        d2=((a-np.array(c))**2).sum(2)
        n_=int((sat&(d2<60**2)).sum()); frac=n_/tot
        if frac>worst[1]: worst=(name,frac)
        if n_>200: print(f"  [leak] {name:6} {n_:7d}px ({frac*100:.3f}%)",flush=True)
    status="FAIL" if worst[1]>0.0005 else "ok"
    print(f"[leak gate] worst={worst[0]} {worst[1]*100:.4f}% → {status}",flush=True)
    return worst[1]

def write_results(dims=None, seed=None):
    T=DEV_H/H
    template={ b:[fx,fy*T] for b,_,fx,fy,_,_ in BTN }
    template.update({k:[fx,fy*T] for k,(fx,fy) in KNOB.items()})
    template.update({"seek":[SEEK[0],SEEK[1]*T],"tog":[TOG[0],TOG[1]*T],
                     "screen":[(SCREEN_RECT[0]+SCREEN_RECT[2])/2,(SCREEN_RECT[1]+SCREEN_RECT[3])/2*T]})
    defsz={"vol":2*KNOB_R/COL_W,"bal":2*KNOB_R/COL_W,"seek":GROOVE_H/COL_W,"tog":TOG_W/COL_W}
    json.dump({"dims":dims,"seed":seed,"model":MODEL,"backdrop":list(BG),
               "palette":{k:list(v) for k,v in PALETTE.items()},
               "keys":{k:list(v) for k,v in KEYS.items()},
               "keyNames":{k:cname(v) for k,v in KEYS.items()},
               "buttons":list(HB),"sprites":list(SP),"extras":list(SC),
               "template":template,"defsz":defsz,
               "screen_rect":[SCREEN_RECT[0],SCREEN_RECT[1]*T,
                              SCREEN_RECT[2]-SCREEN_RECT[0],(SCREEN_RECT[3]-SCREEN_RECT[1])*T],
               "devFrac":T},
              open(os.path.join(OUT,"results.json"),"w"),indent=1)

def run(blueprint_only=False, seed=41):
    containment_check()
    bp=make_blueprint(); print(f"[blueprint] {bp}",flush=True)
    write_results()
    if blueprint_only: return
    url=upload(bp)
    t=time.time(); out=edit(url,PROMPT,seed=seed)
    open(os.path.join(OUT,"joint-4k.png"),"wb").write(out); print(f"[joint 4K] {time.time()-t:.0f}s",flush=True)
    im=Image.open(io.BytesIO(out)).convert("RGB"); w,h=im.size; half=w//2
    im.crop((0,0,half,h)).save(os.path.join(OUT,"paint.png"))
    im.crop((half,0,w,h)).save(os.path.join(OUT,"mask.png"))
    write_results(dims=[w,h],seed=seed)
    leak_check(os.path.join(OUT,"paint.png"))
    print(f"DONE dims={w}x{h}",flush=True)

if __name__=="__main__":
    run(blueprint_only=("--blueprint-only" in sys.argv),
        seed=int(sys.argv[sys.argv.index("--seed")+1]) if "--seed" in sys.argv else 41)
