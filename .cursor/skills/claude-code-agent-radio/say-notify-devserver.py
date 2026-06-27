#!/usr/bin/env python3
"""Lookdev studio for the say-notify RTS "incoming transmission" overlay (macOS).

A single-page web tool with live controls for tuning the native Swift floating
card's look — width, portrait size, border, radius, teal/amber/bg colors,
scanline + static opacity, CRT power on/off durations, lead/linger timing,
speech rate/voice/portrait, sample text, and corner position.

LEFT: sticky control sidebar (every numeric control is a range slider PAIRED
with an editable number input, two-way synced). RIGHT: a live WYSIWYG HTML/CSS
mock of the card that re-renders on every change, a JSON readout of all values,
and trigger buttons that hit the server to fire the REAL native overlay (so you
SEE/HEAR it) via the existing detached-Popen + env-override approach.

Run:  python3 say-notify-devserver.py     (binds a free port, prints the URL)
"""
import base64, json, os, subprocess, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK = SCRIPTS_DIR + "/say-notify.sh"
PORTRAITS_DIR = SCRIPTS_DIR + "/portraits"
PERMISSION_MSG = "Claude needs your permission to use Bash"
VOICES_RETRO = ["Grandpa", "Grandma", "Ralph", "Fred", "Junior", "Albert",
                "Zarvox", "Kathy", "Trinoids", "Cellos", "Bells", "Whisper",
                "Reed", "Rocko", "Sandy", "Shelley", "Eddy", "Flo"]
VOICES_CLEARER = ["Samantha", "Alex", "Daniel", "Karen", "Moira", "Tom", "Fiona"]


def portrait_options():
    """Basenames (no ext) of gifs in PORTRAITS_DIR, sorted."""
    try:
        return sorted(os.path.splitext(f)[0] for f in os.listdir(PORTRAITS_DIR)
                      if f.lower().endswith(".gif"))
    except OSError:
        return []


PROJECTS = [os.path.expanduser("~/dev/" + p) for p in (
    # demo callsign sources (placeholder names — the studio only uses the basename)
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
)]
_counter = 0


# settings-key -> overlay env-var name. Colors pass through as the 6-digit
# hex string the color inputs provide (e.g. "#5fe0d6").
LOOK_ENV = {
    "cardWidth": "SN_W", "portraitSize": "SN_IMG", "borderWidth": "SN_BORDER",
    "cornerRadius": "SN_RADIUS", "tealColor": "SN_TEAL", "amberColor": "SN_AMBER",
    "cardBg": "SN_BG", "staticOpacity": "SN_STATIC",
    "crtOnMs": "SN_CRTON", "crtOffMs": "SN_CRTOFF", "corner": "SN_CORNER",
    # audio timing — valid at 0 and negative; always passed through (never auto/blank)
    "beepGap": "SAY_BEEPGAP", "msgGap": "SAY_MSGGAP",
    # speech mode: radio chatter (default) vs themed movie quotes; never "auto"
    "mode": "SAY_MODE",
}


def fire(cwd, msg, voice="", portrait="", rate="", look=None):
    """Spawn the hook fully detached, feeding it JSON on stdin.

    voice/portrait/rate are optional overrides passed as env vars; each is
    omitted when blank/auto so the hook's auto-mapping applies. `look` is the
    decoded studio settings dict — its visual keys are mapped to SN_* env vars
    that the native overlay (a grandchild of this Popen) inherits.
    """
    global _counter
    _counter += 1
    sid = f"{os.path.basename(cwd)}-{int(time.time())}-{_counter}"
    payload = json.dumps({"message": msg, "session_id": sid,
                          "cwd": cwd, "transcript_path": "/tmp/none"})
    env = dict(os.environ)
    if voice and voice != "auto":
        env["SAY_VOICE"] = voice
    if portrait and portrait != "auto":
        env["SAY_PORTRAIT"] = portrait
    if rate:
        env["SAY_RATE"] = rate
    for key, var in LOOK_ENV.items():
        v = (look or {}).get(key)
        if v is None or v == "" or v == "auto":
            continue
        env[var] = str(v)
    p = subprocess.Popen(["bash", HOOK], stdin=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, env=env)
    p.stdin.write(payload.encode()); p.stdin.close()


PAGE = r"""<!doctype html><html><head><meta charset=utf-8>
<title>say-notify lookdev studio</title><style>
:root{--teal:#5fe0d6;--amber:#ffce6b;--bg0:#070a0d;--bg1:#0a0e12;--bg2:#0f1620;
  --line:#1d2a33;--edge:#29404d;--dim:#6f8a99;--fg:#9fe6c0;}
*{box-sizing:border-box}
body{background:var(--bg0);color:var(--fg);font:13px/1.5 ui-monospace,Menlo,monospace;margin:0}
.app{display:grid;grid-template-columns:340px 1fr;min-height:100vh}
aside{position:sticky;top:0;align-self:start;height:100vh;overflow-y:auto;
  background:var(--bg1);border-right:1px solid var(--line);padding:16px 14px}
main{padding:24px 28px}
h1{color:var(--teal);font-size:14px;letter-spacing:2px;text-transform:uppercase;margin:0 0 4px}
h2{color:var(--dim);font-size:11px;letter-spacing:2px;text-transform:uppercase;
  margin:18px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.sub{color:var(--dim);font-size:11px;margin:0 0 12px}
.ctl{margin:9px 0}
.ctl>label{display:block;color:var(--dim);font-size:11px;letter-spacing:.5px;
  text-transform:uppercase;margin-bottom:3px}
.pair{display:flex;gap:8px;align-items:center}
.pair input[type=range]{flex:1;accent-color:var(--teal);min-width:0}
.pair input[type=number]{width:64px;background:var(--bg2);color:var(--fg);
  border:1px solid var(--edge);padding:4px 6px;font:inherit}
input[type=color]{width:46px;height:28px;background:var(--bg2);border:1px solid var(--edge);
  padding:1px;cursor:pointer;vertical-align:middle}
.colrow{display:flex;gap:14px;flex-wrap:wrap}
.colrow .c{display:flex;flex-direction:column;align-items:center;gap:4px}
.colrow .c span{color:var(--dim);font-size:10px}
select,input[type=text]{width:100%;background:var(--bg2);color:var(--fg);
  border:1px solid var(--edge);padding:5px 7px;font:inherit}
.btnrow{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
button{background:var(--bg2);color:var(--fg);border:1px solid var(--edge);
  padding:7px 11px;font:inherit;cursor:pointer;text-transform:uppercase;
  letter-spacing:1px;transition:background .15s,transform .08s}
button:hover{background:#1b3340;border-color:#4f8aa6}
button:active{transform:scale(.95)}
button.teal{border-color:#2f5468;color:var(--teal)}
button.amber{border-color:#a6612f;color:var(--amber)}button.amber:hover{background:#2b1c10}
button.sm{padding:5px 9px;font-size:11px}
/* ---- preview stage ---- */
.stage{position:relative;min-height:420px;background:
  radial-gradient(120% 90% at 80% 10%,#10171d 0,#05070a 70%);
  border:1px solid var(--line);border-radius:6px;overflow:hidden;
  display:flex;padding:24px}
.stage.tr{justify-content:flex-end;align-items:flex-start}
.stage.tl{justify-content:flex-start;align-items:flex-start}
.stage.br{justify-content:flex-end;align-items:flex-end}
.stage.bl{justify-content:flex-start;align-items:flex-end}
/* the card mock — mirrors the Swift layout: header / portrait+overlays / amber msg */
.card{position:relative;background:#060c0c;overflow:hidden;
  box-shadow:0 6px 26px rgba(0,0,0,.7);transform-origin:center}
.card.powering{animation:crton var(--ponMs,220ms) ease-out}
@keyframes crton{0%{transform:scaleY(.015);filter:brightness(2.4)}
  55%{transform:scaleY(1);filter:brightness(1.6)}100%{transform:scaleY(1);filter:none}}
.hdr{display:flex;align-items:center;gap:6px;padding:4px 7px 2px}
.dot{width:7px;height:7px;border-radius:50%;background:#ff5c4d;
  box-shadow:0 0 6px #ff5c4d;animation:blink 1.4s steps(2) infinite}
@keyframes blink{50%{opacity:.35}}
.hdr .lbl{font:bold 9px/1 "Courier New",monospace;letter-spacing:1.5px}
.port{position:relative;margin:0 2px}
.port img{display:block;width:100%;height:100%;object-fit:cover;image-rendering:auto}
.scan{position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(
  to bottom,rgba(0,0,0,.55) 0,rgba(0,0,0,.55) 1px,transparent 1px,transparent 3px)}
.static{position:absolute;inset:0;pointer-events:none;mix-blend-mode:screen;
  background-image:var(--staticUrl);background-size:cover}
.msg{font:11px/1.25 "Courier New",monospace;padding:5px 8px 6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.note{color:var(--dim);font-size:11px;margin:14px 0 6px}
pre#json{background:var(--bg1);border:1px solid var(--line);border-radius:5px;
  padding:12px;color:#bfe9d4;font-size:11px;overflow-x:auto;max-height:300px}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.histbtns{display:flex;gap:6px}
#log{margin-top:10px;color:#5f7886;white-space:pre-wrap;font-size:11px;max-height:120px;overflow-y:auto}
.fieldgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
</style></head><body>
<div class=app>
<aside>
  <h1>// say-notify</h1>
  <p class=sub>lookdev studio</p>
  <div class=histbtns>
    <button class="sm teal" onclick=undo() title="undo (Cmd/Ctrl-Z)">&#8630;</button>
    <button class="sm teal" onclick=redo() title="redo (Cmd/Ctrl-Shift-Z)">&#8631;</button>
    <button class="sm amber" onclick=resetAll() title="reset to defaults">reset</button>
  </div>

  <h2>geometry</h2>
  <div id=geomCtls></div>

  <h2>colors</h2>
  <div class=colrow id=colorCtls></div>

  <h2>crt &amp; overlays</h2>
  <div id=crtCtls></div>

  <h2>timing</h2>
  <div id=timeCtls></div>

  <h2>voice &amp; portrait</h2>
  <div class=ctl><label>speech rate</label>
    <div class=pair><input type=range id=rate_r min=120 max=320 step=5>
      <input type=number id=rate_n></div></div>
  <div class=ctl><label>voice</label>
    <select id=voice><option value=auto>auto (match portrait)</option>
    <optgroup label=retro>__VOICES_RETRO__</optgroup>
    <optgroup label=clearer>__VOICES_CLEARER__</optgroup></select></div>
  <div class=ctl><label>portrait</label>
    <select id=portrait><option value=auto>auto (by callsign)</option>__PORTRAITS__</select></div>

  <h2>sample text</h2>
  <div class=ctl><label>callsign</label><input type=text id=callsign></div>
  <div class=ctl><label>two-word desc</label><input type=text id=desc></div>

  <h2>position</h2>
  <div class=ctl><label>corner</label>
    <select id=corner>
      <option value=tr>top-right (default)</option>
      <option value=tl>top-left</option>
      <option value=br>bottom-right</option>
      <option value=bl>bottom-left</option>
    </select></div>

  <h2>speech mode</h2>
  <div class=ctl><label>speech mode</label>
    <select id=mode>
      <option value=radio>radio chatter (default)</option>
      <option value=quotes>movie quotes</option>
    </select></div>
</aside>

<main>
  <div class=topbar>
    <h1 style="margin:0">transmission card preview</h1>
    <div class=histbtns>
      <button class="sm teal" onclick=copyJSON()>copy settings json</button>
    </div>
  </div>

  <div class="stage tr" id=stage>
    <div class=card id=card>
      <div class=hdr><span class=dot></span><span class=lbl id=cardLbl>TRANSMISSION</span></div>
      <div class=port id=port>
        <img id=portImg src="" alt="">
        <div class=scan id=scan></div>
        <div class=static id=staticEl></div>
      </div>
      <div class=msg id=cardMsg></div>
    </div>
  </div>

  <p class=note>live preview re-renders on every control change. the <b>static</b> layer reuses the
  real <code>say-notify-static.gif</code>; the portrait is a real cast gif.</p>

  <h2>fire the real native overlay</h2>
  <p class=sub>these hit the server &rarr; run the real hook (beep + say + Swift card). voice / portrait / rate are passed as env overrides.</p>
  <div class=btnrow>
    <button class=amber onclick=fireOne()>fire 1</button>
    <button class=amber onclick=fireAll()>fire all 8</button>
    <label style="color:var(--dim);align-self:center">concurrent</label>
    <input type=number id=nConc value=3 min=1 max=8 style="width:60px;background:var(--bg2);color:var(--fg);border:1px solid var(--edge);padding:5px">
    <button class=amber onclick=fireN()>fire n concurrent</button>
  </div>
  <div id=log></div>

  <h2>settings json</h2>
  <pre id=json></pre>
</main>
</div>

<script>
const STATIC_URL = "/static.gif";
const PORTRAITS = __PORTRAITS_JSON__;
const PROJECTS  = __PROJECTS__;
const PERM      = "__PERM__";

// ---- DEFAULTS: every control value lives here (single source of truth) ----
const DEFAULTS = {
  cardWidth:158, portraitSize:138, borderWidth:1.5, cornerRadius:4,
  tealColor:"#5fe0d6", amberColor:"#ffce6b", cardBg:"#0a1010",
  scanlineOpacity:0.35, staticOpacity:0.10,
  crtOnMs:220, crtOffMs:240, fade:1.0,
  lead:0.10, linger:0.0,
  beepGap:0, msgGap:0,
  rate:230, voice:"auto", portrait:"auto",
  callsign:"CENTRAL 1", desc:"your input",
  corner:"tr", mode:"radio"
};

// numeric control specs: [key,label,min,max,step] grouped by section
const GEOM = [
  ["cardWidth","card width (px)",110,320,1],
  ["portraitSize","portrait size (px)",80,300,1],
  ["borderWidth","border width",0,6,0.5],
  ["cornerRadius","corner radius",0,20,0.5],
];
const CRT = [
  ["scanlineOpacity","scanline opacity",0,1,0.01],
  ["staticOpacity","static opacity",0,1,0.01],
  ["crtOnMs","power-on duration (ms)",40,800,10],
  ["crtOffMs","power-off duration (ms)",40,800,10],
  ["fade","fade",0,1,0.05],
];
const TIME = [
  ["lead","lead (s before voice)",0,2,0.05],
  ["linger","linger (s after voice)",0,5,0.1],
  ["beepGap","SFX → voice gap (s)",-0.5,1.0,0.05],
  ["msgGap","between-messages gap (s)",-0.3,2.0,0.05],
];
const COLORS = [["tealColor","teal"],["amberColor","amber"],["cardBg","card bg"]];

let state = structuredClone(DEFAULTS);

// ---- build the paired slider+number controls ----
function pairCtl(host,[key,label,min,max,step]){
  const w=document.createElement('div'); w.className='ctl';
  w.innerHTML=`<label>${label}</label><div class=pair>
    <input type=range id="${key}_r" min=${min} max=${max} step=${step}>
    <input type=number id="${key}_n" min=${min} max=${max} step=${step}></div>`;
  host.appendChild(w);
}
GEOM.forEach(s=>pairCtl(document.getElementById('geomCtls'),s));
CRT.forEach(s=>pairCtl(document.getElementById('crtCtls'),s));
TIME.forEach(s=>pairCtl(document.getElementById('timeCtls'),s));
COLORS.forEach(([key,label])=>{
  const c=document.createElement('div'); c.className='c';
  c.innerHTML=`<input type=color id="${key}_c"><span>${label}</span>`;
  document.getElementById('colorCtls').appendChild(c);
});

// numeric keys (those with slider+number pairs)
const NUMKEYS=[...GEOM,...CRT,...TIME].map(s=>s[0]);

// ---- two-way sync: don't clobber a focused field ----
function pushToUI(){
  NUMKEYS.forEach(k=>{
    const r=document.getElementById(k+'_r'), n=document.getElementById(k+'_n');
    if(document.activeElement!==r) r.value=state[k];
    if(document.activeElement!==n) n.value=state[k];
  });
  COLORS.forEach(([k])=>{const c=document.getElementById(k+'_c');
    if(document.activeElement!==c) c.value=state[k];});
  ['voice','portrait','corner','mode','callsign','desc'].forEach(k=>{
    const e=document.getElementById(k); if(document.activeElement!==e) e.value=state[k];});
  document.getElementById('rate_r').value=state.rate;
  if(document.activeElement!==document.getElementById('rate_n'))
    document.getElementById('rate_n').value=state.rate;
}

// ---- render the live preview from state ----
function autoPortrait(){return PORTRAITS.length?PORTRAITS[0]:"";}
function render(){
  const s=state;
  const stage=document.getElementById('stage');
  stage.className='stage '+s.corner;
  const card=document.getElementById('card');
  card.style.width=s.cardWidth+'px';
  card.style.border=s.borderWidth+'px solid '+s.tealColor;
  card.style.borderRadius=s.cornerRadius+'px';
  card.style.background=s.cardBg;
  card.style.opacity=s.fade;
  card.style.setProperty('--ponMs',s.crtOnMs+'ms');
  document.getElementById('cardLbl').style.color=s.tealColor;
  document.getElementById('dot');
  const port=document.getElementById('port');
  port.style.height=s.portraitSize+'px';
  const pname = s.portrait==='auto'?autoPortrait():s.portrait;
  const img=document.getElementById('portImg');
  const wantSrc='/portraits/'+pname+'.gif';
  if(img.getAttribute('src')!==wantSrc) img.src=wantSrc;
  document.getElementById('scan').style.opacity=s.scanlineOpacity;
  const st=document.getElementById('staticEl');
  st.style.opacity=s.staticOpacity; st.style.setProperty('--staticUrl',`url(${STATIC_URL})`);
  const msg=document.getElementById('cardMsg');
  msg.style.color=s.amberColor;
  msg.textContent=s.callsign+': '+s.desc;
}

function applyState(){ pushToUI(); render(); writeJSON(); syncURL(); }

// ---- JSON readout ----
function writeJSON(){document.getElementById('json').textContent=JSON.stringify(state,null,2);}
function copyJSON(){navigator.clipboard.writeText(JSON.stringify(state,null,2))
  .then(()=>log('settings JSON copied to clipboard'));}

// ---- URL round-trip (shareable look) ----
function syncURL(){
  const q=new URLSearchParams(); q.set('s',btoa(JSON.stringify(state)));
  history.replaceState(null,'',location.pathname+'?'+q.toString());
}
function loadURL(){
  const p=new URLSearchParams(location.search).get('s');
  if(!p) return false;
  try{const o=JSON.parse(atob(p));state={...DEFAULTS,...o};return true;}catch(e){return false;}
}

// ---- history (undo/redo), debounced so a drag = one step ----
let hist=[], redoStack=[], histTimer=null;
function snapshot(){
  clearTimeout(histTimer);
  histTimer=setTimeout(()=>{
    hist.push(JSON.stringify(state)); if(hist.length>100) hist.shift();
    redoStack.length=0;
  },220);
}
function undo(){
  clearTimeout(histTimer);
  if(hist.length<1) return;
  redoStack.push(JSON.stringify(state));
  state=JSON.parse(hist.pop()); applyState();
}
function redo(){
  if(!redoStack.length) return;
  hist.push(JSON.stringify(state));
  state=JSON.parse(redoStack.pop()); applyState();
}
function commit(){snapshot();applyState();}

// ---- wire inputs ----
function num(v){const n=parseFloat(v);return isNaN(n)?0:n;}
NUMKEYS.forEach(k=>{
  ['input','change'].forEach(ev=>{
    document.getElementById(k+'_r').addEventListener(ev,e=>{state[k]=num(e.target.value);commit();});
    document.getElementById(k+'_n').addEventListener(ev,e=>{state[k]=num(e.target.value);commit();});
  });
});
COLORS.forEach(([k])=>document.getElementById(k+'_c')
  .addEventListener('input',e=>{state[k]=e.target.value;commit();}));
document.getElementById('rate_r').addEventListener('input',e=>{state.rate=num(e.target.value);commit();});
document.getElementById('rate_n').addEventListener('input',e=>{state.rate=num(e.target.value);commit();});
['voice','portrait','corner','mode','callsign','desc'].forEach(k=>{
  ['input','change'].forEach(ev=>document.getElementById(k)
    .addEventListener(ev,e=>{state[k]=e.target.value;commit();}));
});

function resetAll(){state=structuredClone(DEFAULTS);snapshot();applyState();log('reset to defaults');}

// ---- keyboard undo/redo (guarded when focus is in a field) ----
document.addEventListener('keydown',e=>{
  const t=e.target.tagName;
  const inField=(t==='INPUT'&&e.target.type==='text')||t==='TEXTAREA'||t==='SELECT';
  if(inField) return;
  const mod=e.metaKey||e.ctrlKey;
  if(mod&&e.key.toLowerCase()==='z'){e.preventDefault(); e.shiftKey?redo():undo();}
});

// ---- triggers (fire the real native overlay) ----
function log(s){const l=document.getElementById('log');l.textContent=s+"\n"+l.textContent;}
function ov(){return '&voice='+encodeURIComponent(state.voice)
  +'&portrait='+encodeURIComponent(state.portrait)
  +'&rate='+encodeURIComponent(state.rate)
  +'&s='+encodeURIComponent(btoa(JSON.stringify(state)));}
function msgVal(){return encodeURIComponent('Claude is waiting for your input');}
function fireOne(){const cwd=PROJECTS[0];
  fetch('/fire?cwd='+encodeURIComponent(cwd)+'&msg='+msgVal()+ov())
    .then(r=>r.text()).then(t=>log('fired 1 ('+cwd.split('/').pop()+') -> '+t));}
function fireAll(){fetch('/fireall?msg='+msgVal()+ov())
  .then(r=>r.text()).then(t=>log('FIRE ALL -> '+t));}
function fireN(){const n=Math.max(1,Math.min(8,+document.getElementById('nConc').value));
  PROJECTS.slice(0,n).forEach(cwd=>fetch('/fire?cwd='+encodeURIComponent(cwd)+'&msg='+msgVal()+ov()));
  log('fired '+n+' concurrent');}

// ---- init ----
loadURL();
applyState();
hist.push(JSON.stringify(state));
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="text/plain"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)
        except OSError:
            self._send(404, "not found")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        msg = q.get("msg", ["Claude is waiting for your input"])[0]
        voice = q.get("voice", [""])[0]
        portrait = q.get("portrait", [""])[0]
        rate = q.get("rate", [""])[0]
        look = {}
        s = q.get("s", [""])[0]
        if s:
            try:
                look = json.loads(base64.b64decode(s).decode())
            except Exception:
                look = {}

        if u.path in ("/", "/index.html"):
            opts = lambda xs: "".join(f"<option value={v}>{v}</option>" for v in xs)
            ports = portrait_options()
            page = (PAGE.replace("__VOICES_RETRO__", opts(VOICES_RETRO))
                        .replace("__VOICES_CLEARER__", opts(VOICES_CLEARER))
                        .replace("__PORTRAITS__", opts(ports))
                        .replace("__PORTRAITS_JSON__", json.dumps(ports))
                        .replace("__PROJECTS__", json.dumps(PROJECTS))
                        .replace("__PERM__", PERMISSION_MSG))
            return self._send(200, page, "text/html; charset=utf-8")

        if u.path == "/static.gif":
            return self._send_file(SCRIPTS_DIR + "/say-notify-static.gif", "image/gif")

        if u.path.startswith("/portraits/"):
            name = os.path.basename(u.path)  # strips dirs, blocks traversal
            if name.lower().endswith(".gif"):
                return self._send_file(os.path.join(PORTRAITS_DIR, name), "image/gif")
            return self._send(404, "not found")

        if u.path == "/fire":
            cwd = q.get("cwd", [""])[0]
            if not cwd:
                return self._send(400, "missing cwd")
            fire(cwd, msg, voice, portrait, rate, look)
            return self._send(200, "ok")

        if u.path == "/fireall":
            for p in PROJECTS:
                fire(p, msg, voice, portrait, rate, look)
            return self._send(200, f"ok ({len(PROJECTS)})")

        self._send(404, "not found")

    do_POST = do_GET


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    print(f"http://127.0.0.1:{srv.server_address[1]}/", flush=True)
    srv.serve_forever()
