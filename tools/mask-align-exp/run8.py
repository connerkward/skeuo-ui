#!/usr/bin/env python3
"""JOINT-ONLY, 4K. Fixes from user feedback:
 - NO text labels in the blueprint sent to the model (labels confuse it — it rendered them).
 - FLAT DARK contrasting backdrop + a BRIGHT SILVER device, so the device + parts can actually
   be keyed out (silver-on-charcoal, not silver-on-grey).
 - Toggle has BOTH states (off + on) on the sprite sheet + an empty toggle socket on the device.
 - PAINT stays monochrome; guide colours only in the mask."""
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
OUT = os.path.join(os.path.dirname(__file__), "assets8"); os.makedirs(OUT, exist_ok=True)

HB = {"prev":(255,90,60),"play":(0,120,255),"next":(240,180,0),"stop":(170,80,255)}
SP = {"vol":(0,190,90),"bal":(0,200,220),"seek":(255,140,30),"tog":(255,90,160)}
BG = (22,22,26)                 # flat dark charcoal backdrop (contrasts the bright silver device)
BODY = (140,140,144)            # device footprint guide
COL_W,H = 1200,1920; DEV_H = 1440

SHAPES={"wedge":[(-1,-.5),(.5,-1),(1,0),(.5,1),(-1,.5),(-.4,0)],
    "kidney":[(-1,-.2),(-.4,-.9),(.5,-.8),(1,-.1),(.7,.4),(1,.8),(.2,1),(-.7,.7),(-1,.3)],
    "trapezoid":[(-1,-.7),(.9,-.5),(.7,.8),(-.8,.6)],"teardrop":[(0,-1),(.8,-.3),(.7,.7),(0,1),(-.7,.7),(-.8,-.3)]}

def poly_at(cx,cy,pts,scale,rot=0):
    c,s=math.cos(rot),math.sin(rot)
    return [(cx+(x*c-y*s)*scale, cy+(x*s+y*c)*scale) for (x,y) in pts]
def rrect(d,cx,cy,w,h,col,r=24):
    d.rounded_rectangle([cx-w/2,cy-h/2,cx+w/2,cy+h/2],radius=r,outline=col,width=13)

def make_blueprint():
    W=COL_W*2; img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    d.rectangle([COL_W,0,W,H],fill=(0,0,0)); d.line([COL_W,0,COL_W,H],fill=(70,70,74),width=3)
    body=poly_at(COL_W*0.5,DEV_H*0.52,[(-.72,-.9),(-.1,-.98),(.55,-.82),(.86,-.35),(.72,.05),
        (.95,.45),(.6,.82),(.05,.96),(-.55,.86),(-.9,.45),(-.78,-.05),(-.92,-.5)],scale=min(COL_W,DEV_H)*0.47)
    d.polygon(body,fill=BODY)
    d.polygon(poly_at(COL_W*0.46,DEV_H*0.20,[(-1,-.7),(.9,-.8),(1,.6),(-.9,.75)],scale=250),fill=(18,19,22))
    rrect(d,COL_W*0.50,DEV_H*0.40,620,90,SP["seek"],r=44)                 # seek track
    rrect(d,COL_W*0.17,DEV_H*0.62,120,200,SP["tog"],r=40)                 # toggle socket
    for b,shp,fx,fy,sc,rot in [("prev","wedge",0.36,0.60,100,-0.4),("play","kidney",0.55,0.63,112,0.1),
                                ("next","trapezoid",0.76,0.57,102,0.3),("stop","teardrop",0.44,0.84,92,0.8)]:
        pts=poly_at(COL_W*fx,DEV_H*fy,SHAPES[shp],scale=sc,rot=rot)
        d.line(pts+[pts[0]],fill=HB[b],width=12,joint="curve")
    for k,(fx,fy) in {"vol":(0.70,0.83),"bal":(0.88,0.68)}.items():
        x,y=COL_W*fx,DEV_H*fy; r=86; d.ellipse([x-r,y-r,x+r,y+r],outline=SP[k],width=12)
    d.line([0,DEV_H,COL_W,DEV_H],fill=(70,70,74),width=3)
    sy=DEV_H+(H-DEV_H)//2
    # 5 strip cells: vol, bal, seek thumb, toggle-OFF, toggle-ON  (both toggle cells pink)
    cells=[("vol","circle"),("bal","circle"),("seek","pill"),("tog","rect"),("tog","rect")]
    for i,(k,shp) in enumerate(cells):
        x=COL_W*(0.11+0.195*i)
        if shp=="circle": r=88; d.ellipse([x-r,sy-r,x+r,sy+r],outline=SP[k],width=12)
        elif shp=="pill": rrect(d,x,sy,66,150,SP[k],r=32)
        else: rrect(d,x,sy,120,150,SP[k],r=28)
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

PROMPT=("Two side-by-side columns of identical size. LEFT column: a BLUEPRINT of a wild ORGANIC Y2K "
  "media-player (there is NO text anywhere — the coloured shapes ARE the guides). Coloured guides mark "
  "controls: RED=PREV, BLUE=PLAY, AMBER=NEXT, VIOLET=STOP buttons (non-circular, molded into the body); "
  "GREEN circle=VOLUME knob socket, CYAN circle=BALANCE knob socket; an ORANGE rounded bar=the SEEK slider "
  "track; a PINK slot=the TOGGLE switch socket; dark shape=screen. The BOTTOM BAND of the left column is a "
  "SPRITE STRIP with the loose PARTS to manufacture, left to right: GREEN circle (volume knob cap), CYAN "
  "circle (balance knob cap), ORANGE pill (seek slider thumb), and TWO PINK rounded rects — the LEFT pink "
  "is the toggle switch in its OFF position, the RIGHT pink is the SAME toggle switch in its ON position "
  "(lever flipped). RIGHT column: pure black.\n"
  "Fill everything, keeping the LEFT column's device+strip layout IDENTICAL in the RIGHT column so the two "
  "overlay pixel-for-pixel:\n"
  "LEFT column — paint the FINISHED device and parts in BRIGHT POLISHED SILVER CHROME. CRITICAL for cutout: "
  "the BACKDROP around the device and BEHIND every strip part is a FLAT, PERFECTLY UNIFORM NEAR-BLACK "
  "CHARCOAL — a separate backdrop that gets KEYED OUT to cut the device and parts free. It MUST strongly "
  "CONTRAST the bright silver metal (NEVER a grey or silver tone near the device's own colour), be one solid "
  "uniform dark tone with NO gradient/texture/vignette, and must not tint or bleed onto anything.\n"
  "  • The device and every control/part must contain NONE of the guide colours — everything is the SAME "
  "bright silver chrome, distinguished only by shape, embossed icon and raised relief.\n"
  "  • The 4 buttons are MOLDED into the body (icon + relief, remove the coloured outlines).\n"
  "  • The 2 knob sockets and the toggle socket are EMPTY NEUTRAL recessed DARK wells cut into the silver — "
  "do NOT colour them.\n"
  "  • The SEEK slider TRACK on the device is a COMPLETELY EMPTY recessed groove — a plain dark horizontal "
  "slot with ABSOLUTELY NOTHING inside it: NO thumb, NO handle, NO slider knob, NO nub, NO bead, NO bar, NO "
  "fill, NO marker. It is JUST an empty channel. The slider THUMB is a SEPARATE loose part that appears ONLY "
  "in the sprite strip below — NEVER paint a thumb or any object inside the track on the device.\n"
  "  • SPRITE STRIP — paint EXACTLY FIVE parts in ONE SINGLE horizontal row (do NOT add a second row, do NOT "
  "duplicate the parts, do NOT repeat), left to right: volume knob cap, balance knob cap, slider thumb, toggle "
  "switch OFF, toggle switch ON — finished glossy SILVER CHROME parts on the flat charcoal backdrop, outlines "
  "removed, uncoloured.\n"
  "  • CRITICAL — CAMERA/VIEW: render EVERY strip part from the EXACT SAME straight-down, FLAT, TOP-DOWN "
  "ORTHOGRAPHIC view as the device above (you are looking directly DOWN from straight overhead at 90°). A knob "
  "cap is a FLAT CIRCLE seen from directly above — show ONLY its round top face with a knurled rim and a small "
  "raised pointer notch; you must NOT see the cylindrical SIDE of the knob at all. The slider thumb and the "
  "toggle switch are likewise seen from straight overhead, flat. ABSOLUTELY NO 3/4 perspective, NO product-shot "
  "angle, NO tilt, NO isometric view, NO visible sides or depth — each part must look EXACTLY as it appears "
  "when seated flat in its socket on the top-down device, so it drops in and lines up perfectly.\n"
  "  • The screen is blank dark glass.\n"
  "RIGHT column — a REGION MASK on pure BLACK. Fill each target with a FLAT solid colour aligned to the "
  "left: each BUTTON facet (prev=red 255,90,60; play=blue 0,120,255; next=amber 240,180,0; stop=violet "
  "170,80,255); each on-device SOCKET (volume=green 0,190,90; balance=cyan 0,200,220; seek track=orange "
  "255,140,30; toggle=pink 255,90,160); and each STRIP CELL in its part's colour (volume cap=green, balance "
  "cap=cyan, seek thumb=orange, BOTH toggle states=pink). Everything else pure black.")

def run():
    bp=make_blueprint(); url=upload(bp); print(f"[blueprint] {bp}",flush=True)
    t=time.time(); out=edit(url,PROMPT)
    open(os.path.join(OUT,"joint-4k.png"),"wb").write(out); print(f"[joint 4K] {time.time()-t:.0f}s",flush=True)
    im=Image.open(io.BytesIO(out)).convert("RGB"); w,h=im.size; half=w//2
    im.crop((0,0,half,h)).save(os.path.join(OUT,"paint.png"))
    im.crop((half,0,w,h)).save(os.path.join(OUT,"mask.png"))
    json.dump({"dims":[w,h]},open(os.path.join(OUT,"results.json"),"w"))
    print(f"DONE dims={w}x{h}",flush=True)

if __name__=="__main__":
    run()
