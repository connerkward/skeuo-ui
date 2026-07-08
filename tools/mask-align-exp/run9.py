#!/usr/bin/env python3
"""run9 — NEW design: early-2000s candybar CELL-PHONE / WALKMAN hybrid with ORGANIC
non-circular, non-rectangular transport buttons (pebble / teardrop / kidney / crescent).
Same joint-image contract as run8: LEFT = painted device + sprite strip on a flat uniform
backdrop CHOSEN FOR CONTRAST against the material brief (dark graphite body → LIGHT pale
grey-white backdrop; a light silver body would get the dark charcoal), RIGHT = colour-keyed
region mask on pure black. Paint is MONOCHROME (Y2K gunmetal graphite + chrome) — guide
colours appear ONLY in the mask. The chosen backdrop is written to results.json so the
extractor keys parts by distance-from-backdrop instead of an absolute dark/bright rule."""
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
OUT = os.path.join(os.path.dirname(__file__), "assets9"); os.makedirs(OUT, exist_ok=True)

HB = {"prev":(255,90,60),"play":(0,120,255),"next":(240,180,0),"stop":(170,80,255)}
SP = {"vol":(0,190,90),"bal":(0,200,220),"seek":(255,140,30),"tog":(255,90,160)}
SC = {"screen":(100,255,0)}   # lime — SCREEN/LCD region (device-only; no sprite-strip cell)
# Backdrop is picked OPPOSITE the material brief's lightness so the body can actually be keyed out:
# run9's brief is DARK (gunmetal graphite) → LIGHT backdrop. A light brief (silver/chrome) → charcoal.
MATERIAL_IS_DARK = True         # run9 brief: rubberized gunmetal graphite body
BG = (235,235,238) if MATERIAL_IS_DARK else (22,22,26)
if MATERIAL_IS_DARK:
    BD_CAP,BD_LOW,BD_TONE = "PALE GREY-WHITE","pale grey-white","pale"
    BODY_VS,BD_APPROACH = "DARKER","lightness"
else:
    BD_CAP,BD_LOW,BD_TONE = "NEAR-BLACK CHARCOAL","charcoal","dark"
    BODY_VS,BD_APPROACH = "BRIGHTER","darkness"
BODY = (140,140,144)            # device footprint guide (mid-grey — reads on either backdrop)
COL_W,H = 1200,1920; DEV_H = 1440

def crescent_pts():
    pts=[]
    for a in range(60,301,20):                       # outer arc — the left bow
        r=math.radians(a); pts.append((math.cos(r),math.sin(r)))
    for a in range(285,74,-20):                      # inner arc — the bite from the right
        r=math.radians(a); pts.append((0.35+0.62*math.cos(r),0.62*math.sin(r)))
    return pts

SHAPES={
 "pebble":  [(-1.15,-.2),(-.6,-.62),(.1,-.72),(.72,-.55),(1.1,-.05),(.85,.42),(.25,.66),(-.4,.6),(-.9,.32)],
 "teardrop":[(0,-1.3),(.3,-.6),(.68,.05),(.62,.6),(.12,.92),(-.45,.8),(-.72,.25),(-.3,-.65)],
 "kidney":  [(-1,-.2),(-.4,-.9),(.5,-.8),(1,-.1),(.7,.4),(1,.8),(.2,1),(-.7,.7),(-1,.3)],
 "crescent":crescent_pts()}

# button placements (fx of COL_W, fy of DEV_H) — these ARE the authored template centres
BTN=[("prev","pebble",  0.35,0.335, 88,-0.3),
     ("play","teardrop",0.63,0.360, 92, 0.5),
     ("next","kidney",  0.37,0.505, 86, 0.25),
     ("stop","crescent",0.645,0.525,90,-0.55)]
KNOB={"vol":(0.36,0.765),"bal":(0.64,0.765)}
SEEK=(0.50,0.645); TOG=(0.50,0.895)

def poly_at(cx,cy,pts,scale,rot=0):
    c,s=math.cos(rot),math.sin(rot)
    return [(cx+(x*c-y*s)*scale, cy+(x*s+y*c)*scale) for (x,y) in pts]
def rrect(d,cx,cy,w,h,col,r=24):
    d.rounded_rectangle([cx-w/2,cy-h/2,cx+w/2,cy+h/2],radius=r,outline=col,width=13)

def make_blueprint():
    W=COL_W*2; img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    d.rectangle([COL_W,0,W,H],fill=(0,0,0)); d.line([COL_W,0,COL_W,H],fill=(70,70,74),width=3)
    # tall candybar body — rounded rect
    d.rounded_rectangle([COL_W*0.19,DEV_H*0.03,COL_W*0.81,DEV_H*0.97],radius=150,fill=BODY)
    # small screen up top (dark glass) — LIME outline marks it as a mask region like every control
    d.rounded_rectangle([COL_W*0.26,DEV_H*0.075,COL_W*0.74,DEV_H*0.225],radius=26,fill=(18,19,22),
                        outline=SC["screen"],width=12)
    # speaker grille dots (two rows)
    for row,fy in enumerate((0.255,0.276)):
        for i in range(8):
            x=COL_W*(0.38+0.034*i)+(9 if row else 0); y=DEV_H*fy
            d.ellipse([x-7,y-7,x+7,y+7],fill=(60,60,64))
    # 4 ORGANIC transport buttons (outline only, guide colour)
    for b,shp,fx,fy,sc,rot in BTN:
        pts=poly_at(COL_W*fx,DEV_H*fy,SHAPES[shp],scale=sc,rot=rot)
        d.line(pts+[pts[0]],fill=HB[b],width=12,joint="curve")
    # CONGRUENCE CONTRACT: each part's strip anchor is the EXACT SAME geometry as its device
    # slot — one definition, drawn twice. (The old blueprint authored a 110×170 socket with a
    # 120×150 strip anchor and a portrait thumb for a landscape groove; the model faithfully
    # painted the mismatch, so slot and part could never fit.)
    KNOB_R=76                      # socket circle == cap circle
    TOG_W,TOG_H,TOG_R=110,170,38   # toggle socket == toggle part (both states)
    GROOVE_W,GROOVE_H=520,70
    THUMB_W,THUMB_H,THUMB_R=150,92,44   # landscape grip, height ~1.3× groove height
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

PROMPT=("Two side-by-side columns of identical size. LEFT column: a BLUEPRINT of an early-2000s candybar "
  "CELL-PHONE / WALKMAN hybrid (there is NO text anywhere — the coloured outlines ARE the guides). Every "
  "control is identified by BOTH its guide colour AND its shape+position: RED top-left PEBBLE=PREV, BLUE "
  "top-right TEARDROP=PLAY, AMBER lower-left KIDNEY-BEAN=NEXT, VIOLET lower-right CRESCENT-MOON=STOP — each "
  "button an ORGANIC IRREGULAR shape, deliberately NOT a circle and NOT a rectangle; GREEN left circle="
  "VOLUME knob socket, CYAN right circle=BALANCE knob socket; the ORANGE rounded horizontal bar=the SEEK "
  "slider track; the PINK rounded slot near the bottom=the TOGGLE switch socket; the LIME-outlined dark "
  "rounded rectangle near the top=the SCREEN (blank LCD window); the small dots=speaker grille. "
  "IMPORTANT: these coloured outlines are ALIGNMENT MARKINGS on a technical drawing — like masking tape on a "
  "workpiece — they are NOT part of the product's design and must be COMPLETELY removed in the finished paint. "
  "The BOTTOM BAND of the left column is a SPRITE STRIP with the loose PARTS to manufacture, left to right: "
  "(1) GREEN circle=volume knob cap, (2) CYAN circle=balance knob cap, (3) ORANGE outline=seek slider thumb "
  "(a wide low grip), (4) PINK=the toggle switch in its OFF position, (5) PINK=the SAME toggle switch in its "
  "ON position (lever flipped). RIGHT column: pure black.\n"
  "Fill everything, keeping the LEFT column's device+strip layout IDENTICAL in the RIGHT column so the two "
  "overlay pixel-for-pixel:\n"
  "LEFT column — paint the FINISHED phone and parts in Y2K GUNMETAL GRAPHITE: a rubberized soft-touch "
  "graphite body with POLISHED CHROME accent bezels and raised chrome button facets. Every surface of the "
  f"device and every loose part must stay clearly {BODY_VS} than the backdrop. CRITICAL for cutout: the "
  f"BACKDROP around the device and BEHIND every strip part is a FLAT, PERFECTLY UNIFORM {BD_CAP} — "
  "a separate backdrop that gets KEYED OUT to cut the device and parts free. It MUST strongly CONTRAST the "
  f"graphite body (the body must never approach the backdrop's {BD_APPROACH}), be one solid uniform "
  f"{BD_TONE} tone with NO gradient/texture/vignette, and must not tint or bleed onto anything.\n"
  "  • The device and every control/part must contain NONE of the guide colours — everything is the SAME "
  "monochrome gunmetal-graphite-and-chrome palette, controls distinguished only by shape, raised relief and "
  "material contrast (rubber vs chrome). ABSOLUTELY NO red, NO blue, NO amber/yellow, NO violet, NO green, "
  "NO cyan, NO orange, NO pink, NO lime paint ANYWHERE in the left column — the painted transport buttons "
  "are BARE UNCOLOURED CHROME facets; the guide colours exist ONLY in the RIGHT mask column.\n"
  "  • ZERO RESIDUE — where a coloured guide outline was, paint the body material seamlessly over it. Do NOT "
  "leave ANY thin coloured rim, ring, halo, edge tint or glow around ANY socket, button, slot or part (e.g. "
  "no pink rim around the toggle socket, no orange edge on the seek groove, no green/cyan ring around a knob "
  "socket). Inspect every socket edge: if even a sliver of guide colour survives, the output is WRONG.\n"
  "  • The 4 transport buttons are MOLDED into the body as raised chrome facets that KEEP their EXACT "
  "irregular ORGANIC outlines from the guide — the pebble stays a pebble, the teardrop stays a teardrop, the "
  "kidney stays a kidney bean, the crescent stays a crescent moon. Do NOT round any of them into a circle, "
  "do NOT square any of them into a rectangle, do NOT add icons, symbols or text on them — shape and relief "
  "only. Remove the pale grey guide outlines.\n"
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
  "switch OFF, toggle switch ON — finished graphite-and-chrome parts on the flat "
  f"{BD_LOW} backdrop, outlines removed, uncoloured.\n"
  "  • EXACT FIT — every strip part's guide outline is drawn at the EXACT SAME SIZE AND SHAPE as its slot on "
  "the device, and the painted part MUST match its outline precisely: each knob cap is exactly the diameter of "
  "its socket circle, each toggle part exactly fills the toggle-socket outline (same rounded-rect, same "
  "proportions, in its OFF / ON state), and the slider thumb matches its outline (a wide, low grip that rides "
  "the groove). Do NOT resize, restyle, or re-proportion any part relative to its outline — a part that does "
  "not fit its slot is WRONG.\n"
  "  • CRITICAL — CAMERA/VIEW: render EVERY strip part from the EXACT SAME straight-down, FLAT, TOP-DOWN "
  "ORTHOGRAPHIC view as the device above (you are looking directly DOWN from straight overhead at 90°). A knob "
  "cap is a FLAT CIRCLE seen from directly above — show ONLY its round top face with a knurled rim and a small "
  "raised pointer notch; you must NOT see the cylindrical SIDE of the knob at all. The slider thumb and the "
  "toggle switch are likewise seen from straight overhead, flat. ABSOLUTELY NO 3/4 perspective, NO product-shot "
  "angle, NO tilt, NO isometric view, NO visible sides or depth — each part must look EXACTLY as it appears "
  "when seated flat in its socket on the top-down device, so it drops in and lines up perfectly.\n"
  "  • The screen is blank dark glass — remove its lime outline, keep it UNCOLOURED (no lime tint, no content, "
  "no icons) with a slim chrome bezel; the speaker grille is a field of tiny drilled holes.\n"
  "RIGHT column — a REGION MASK on pure BLACK. Fill each target with a FLAT solid colour aligned to the "
  "left, in ITS OWN guide colour (the same colour its outline has in the blueprint): each BUTTON facet "
  "filled in its EXACT organic outline (PEBBLE/prev=red 255,90,60; TEARDROP/play=blue 0,120,255; "
  "KIDNEY/next=amber 240,180,0; CRESCENT/stop=violet 170,80,255); each on-device SOCKET (LEFT-circle "
  "volume=green 0,190,90; RIGHT-circle balance=cyan 0,200,220; seek track bar=orange 255,140,30; toggle "
  "slot=pink 255,90,160); the SCREEN as ONE SOLID LIME-CHARTREUSE "
  "rounded rectangle (lime 100,255,0 — a yellow-green clearly distinct from the volume green) that EXACTLY "
  "covers the screen glass on the device; and each STRIP PART as a SOLID FLAT blob of its part's colour "
  "(volume cap=green, balance cap=cyan, seek thumb=orange, BOTH toggle states=pink) that EXACTLY matches that "
  "part's SILHOUETTE in the left column — same shape, same size, same position. NEVER flood a whole strip cell "
  "or any rectangle of background with colour; NEVER draw outlines or hollow shapes — every blob is ONE solid "
  "filled silhouette, no interior holes. Everything else pure black.")

def leak_check(paint_path):
    """LEAK GATE: scan the PAINT panel for surviving guide colours (prompts are persuasion,
    not law). Reports per-colour leak pixel counts; returns worst offender fraction."""
    import numpy as np
    a=np.asarray(Image.open(paint_path).convert("RGB")).astype(int)
    keys={**HB,**SP,**SC}; tot=a.shape[0]*a.shape[1]; worst=("none",0.0)
    sat=(a.max(2)-a.min(2))>55   # only saturated pixels can be guide leaks on a monochrome paint
    for name,c in keys.items():
        d2=((a-np.array(c))**2).sum(2)
        n=int((sat&(d2<60**2)).sum()); frac=n/tot
        if frac>worst[1]: worst=(name,frac)
        if n>200: print(f"  [leak] {name:6} {n:7d}px ({frac*100:.3f}%)",flush=True)
    status="FAIL" if worst[1]>0.0005 else "ok"
    print(f"[leak gate] worst={worst[0]} {worst[1]*100:.4f}% → {status}",flush=True)
    return worst[1]

def run(blueprint_only=False, seed=41):
    bp=make_blueprint(); print(f"[blueprint] {bp}",flush=True)
    if blueprint_only: return
    url=upload(bp)
    t=time.time(); out=edit(url,PROMPT,seed=seed)
    open(os.path.join(OUT,"joint-4k.png"),"wb").write(out); print(f"[joint 4K] {time.time()-t:.0f}s",flush=True)
    im=Image.open(io.BytesIO(out)).convert("RGB"); w,h=im.size; half=w//2
    im.crop((0,0,half,h)).save(os.path.join(OUT,"paint.png"))
    im.crop((half,0,w,h)).save(os.path.join(OUT,"mask.png"))
    json.dump({"dims":[w,h],"seed":seed,"model":MODEL,"backdrop":list(BG)},
              open(os.path.join(OUT,"results.json"),"w"))
    leak_check(os.path.join(OUT,"paint.png"))
    print(f"DONE dims={w}x{h}",flush=True)

if __name__=="__main__":
    run(blueprint_only=("--blueprint-only" in sys.argv),
        seed=int(sys.argv[sys.argv.index("--seed")+1]) if "--seed" in sys.argv else 41)
