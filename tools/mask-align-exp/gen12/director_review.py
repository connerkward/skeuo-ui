#!/usr/bin/env python3
"""director_review.py — DIRECTOR FINAL REVIEW stage (DISABLED BY DEFAULT; see
DIRECTOR_REVIEW_ENABLED in orchestrate12.py).

For one FINISHED skin (post build_player.py), renders the REAL served player.html via a
throwaway, isolated Node/Playwright script — its own fresh chromium.launch(), never the
shared claude-in-chrome MCP browser — capturing a full stage screenshot plus the standard
per-control crops (knob, seek at mid, switch, buttons, screens). Sends those images to the
DIRECTOR model — gemini-3.1-pro-preview via Vertex AI, same gcloud-token auth pattern as
genskin.py's edit_vertex()/edit_vertex_multi(), thinkingConfig thinkingLevel "low" (see
src/generate/director.ts's directorChat() — gemini-3.1-pro-preview defaults to "high" and
will burn the whole token budget on internal thought tokens before emitting any JSON) —
with a director-persona prompt: judge the FINISHED render against its OWN theme brief
(theme_specs/<id>.json: theme_prompt, palette, lighting, css) for cohesion, material
fidelity, control legibility, seating, and what to improve. Output is enforced via
generationConfig.responseMimeType=application/json + responseSchema (see RESPONSE_SCHEMA
below; verdict per docs/experiments/2026-07-11-image-model-json-output.md — "director YES"),
not rhetorical "STRICT JSON" prompting — see semissive/judge.py for the same pattern.
Writes to <assets-dir>/director-review.json, with the model id + a cost estimate recorded
in the output (media-attribution / dev-facing-model-cost-annotation). ~$0.02-0.05/skin (one
gemini-3.1-pro-preview vision call, full frame + after frame + ~6-10 control crops).

NOT observe12.py. observe12.py is the [[skin-observation-rule]] SOTA-eye pass: GEOMETRY /
DEFECT verification — is control X seated within +/-px of its socket, is a sprite
missing/misplaced/exposed, is there a stray guide ring. director_review.py is a different
axis entirely: AESTHETIC / THEMATIC judgment against the theme brief — does the material
read as the theme, is the palette cohesive, does the composition feel directed. Keep the
two passes and their output files separate; never merge them into one script or one JSON.

Usage: python3 director_review.py <assets-dir> [--url=http://host:port/assets-x/player.html]
"""
import os, re, sys, json, time, base64, tempfile, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # repo root, for node_modules/playwright

OUT = os.path.abspath(sys.argv[1])
SID = re.sub(r"^assets-", "", os.path.basename(OUT))
SID = re.sub(r"_(biref|pbr)$", "", SID)  # defensive: director review runs on the base assets-<id> dir
URL = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--url=")), None)
if not URL:
    su = open(os.path.join(HERE, ".serve-url")).read().strip().rstrip("/")
    URL = f"{su}/assets-{SID}/player.html"

DIR_OUT = os.path.join(OUT, "director")
os.makedirs(DIR_OUT, exist_ok=True)

regs = json.load(open(os.path.join(OUT, "regions.json")))
ROLES = regs.get("roles", {})
DEVF = regs.get("devFrac", 1.0)

spec_path = os.path.join(HERE, "theme_specs", f"{SID}.json")
spec = json.load(open(spec_path)) if os.path.exists(spec_path) else {}

# --- 1. render the REAL player via a throwaway, isolated Node/Playwright driver -----------
# Written to a tempfile per run (never checked in) — its own chromium.launch(), no shared
# browser/profile, so it can't collide with (or leak into) claude-in-chrome or any other
# session's Playwright instance. Node, not Python: python playwright isn't installed here;
# the repo's node playwright dep already exists (same reason observe12.py shells to node).
DRIVER = """
import { chromium } from 'playwright';
import path from 'node:path';
const [url, out] = process.argv.slice(2);
const b = await chromium.launch();
const pg = await b.newPage({ viewport: { width: 900, height: 1100 } });
await pg.goto(url);
await pg.waitForFunction("document.querySelectorAll('#phone .pbtn').length > 0", { timeout: 20000 });
await pg.waitForTimeout(2500); // sprite decode + seat
const phone = pg.locator('#phone');
await phone.screenshot({ path: path.join(out, 'full.png') });

// standard interaction pass so the director sees seek-at-mid + a toggled switch + a
// dragged knob, not just the untouched idle frame — same handlers the real UI uses.
await pg.evaluate('window.__seek && window.__seek(0.5)');
const tog = pg.locator('#phone .ptog');
if (await tog.count()) await tog.first().evaluate(e => e.click());
const knob = pg.locator('#phone .pknob');
if (await knob.count()) {
  const bb = await knob.first().boundingBox();
  const cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;
  await pg.mouse.move(cx, cy); await pg.mouse.down();
  await pg.mouse.move(cx, cy - 30, { steps: 8 }); await pg.mouse.up();
}
await pg.waitForTimeout(400);
await phone.screenshot({ path: path.join(out, 'after.png') });
await b.close();
console.log('[director_review] wrote full.png + after.png');
"""
# Node ESM resolves node_modules by walking up from the SCRIPT FILE's own path, not cwd —
# so the driver must live inside the repo tree (to see node_modules/playwright), not /tmp.
# Written with a dotfile-style throwaway name and always deleted after the run.
fd, driver_path = tempfile.mkstemp(dir=HERE, prefix=".director-drive-", suffix=".mjs")
with os.fdopen(fd, "w") as f:
    f.write(DRIVER)
try:
    subprocess.run(["node", driver_path, URL, DIR_OUT], cwd=REPO, check=True, timeout=120)
finally:
    os.unlink(driver_path)

# --- 2. per-control close-up crops (device-frac -> phone-frac, 3x upscale) ----------------
# Same math as observe12.py's crop() (independently re-derived here on purpose — this
# script owns its own render pass and must not import observe12.py, which is a top-level
# script, not a module).
from PIL import Image

full = Image.open(os.path.join(DIR_OUT, "full.png"))
after = Image.open(os.path.join(DIR_OUT, "after.png"))


def crop(img, dev, pad=0.35):
    x, y, w, h = dev
    y, h = y / DEVF, h / DEVF
    px, py = w * pad, h * pad
    W, H = img.size
    box = (max(0, (x - px)) * W, max(0, (y - py)) * H,
           min(1, (x + w + px)) * W, min(1, (y + h + py)) * H)
    c = img.crop(tuple(int(v) for v in box))
    return c.resize((c.width * 3, c.height * 3), Image.LANCZOS)


# after-frame for controls whose interacted state is the informative one; full-frame for
# static ones (buttons at rest, screens/visualizer/album art).
AFTER_ROLES = {"slider", "toggle", "knob"}
crop_files = []
for key, r in regs.get("regions", {}).items():
    if not r.get("device"):
        continue
    src = after if ROLES.get(key) in AFTER_ROLES else full
    name = f"crop-{key}.png"
    crop(src, r["device"]).save(os.path.join(DIR_OUT, name))
    crop_files.append((key, ROLES.get(key, "?"), name))

# --- 3. build the DIRECTOR persona prompt --------------------------------------------------
palette_txt = ", ".join(f"{k}=rgb{tuple(v)}" for k, v in spec.get("palette", {}).items())
css_txt = ", ".join(f"{k}={v}" for k, v in spec.get("css", {}).items())
lighting = spec.get("lighting", {})
controls_txt = ", ".join(f"{k} ({role})" for k, role, _ in crop_files)

SYSTEM_PROMPT = (
    "You are the DIRECTOR — the creative lead giving final sign-off on a finished "
    "skeuomorphic music-player skin render. You are judging AESTHETIC and THEMATIC "
    "fidelity against the skin's own brief, NOT geometric alignment (a separate pass "
    "already checks pixel seating). Judge: (1) cohesion — do the parts read as one "
    "designed object in one material world, not a collage; (2) material fidelity — does "
    "the surface actually read as the requested theme/material, not a generic plastic "
    "skin with a tinted texture; (3) control legibility — can a user tell what each "
    "control does and its current state at a glance; (4) seating — do sprites look "
    "physically mounted in their sockets (shadow, occlusion, scale) rather than pasted "
    "on top; (5) what would most improve the shot if regenerated. Designed asymmetry is "
    "fine (toggle OFF/ON states may legitimately differ; theme-styled controls may be "
    "unconventional shapes) — only flag it if it reads as broken, not merely unusual. "
    "Flag any visible baked-in text/words (the device must be wordless)."
)
USER_PROMPT = (
    f"Skin id: {SID}\n"
    f"Theme brief (theme_prompt): {spec.get('theme_prompt', '(none)')}\n"
    f"Palette: {palette_txt or '(none)'}\n"
    f"CSS accent colors: {css_txt or '(none)'}\n"
    f"Lighting/emissive hint: {lighting.get('emissive_hint', '(none)')}, "
    f"pulse={lighting.get('pulse', '(none)')}\n"
    f"Controls in this render: {controls_txt}\n\n"
    "Images attached, in order: [0] full idle-state screenshot of the whole player, "
    "[1] after-interaction screenshot (seek dragged to mid, switch toggled, knob "
    f"dragged), then {len(crop_files)} per-control 3x close-up crops in this order: "
    + ", ".join(f"[{i+2}] {k}" for i, (k, _, _) in enumerate(crop_files)) + ".\n\n"
    "Judge the render against ITS OWN brief above. Include ONE per_control entry for "
    "EVERY control listed above, using its exact key as the 'control' field."
)

# OpenAPI-3.0 subset, uppercase Type enum — same pattern verified live against Vertex/Gemini
# docs 2026-07-11 in semissive/judge.py. per_control is an ARRAY of {control,status,note}
# rather than a keyed object because Gemini's schema subset has no free-form-object-key
# support; director_chat() below folds it back into the {control_key: {...}} dict shape the
# rest of the pipeline (build_dashboard.py) already expects — the on-disk contract is
# unchanged, only the wire shape the model returns.
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "verdict": {"type": "STRING", "enum": ["PASS", "FAIL"]},
        "score_0_10": {"type": "NUMBER", "description": "overall directorial score, 0-10"},
        "per_control": {
            "type": "ARRAY",
            "description": "one entry per control listed in the prompt",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "control": {"type": "STRING", "description": "the control's exact key from the prompt"},
                    "status": {"type": "STRING", "enum": ["good", "needs_work"]},
                    "note": {"type": "STRING", "description": "short note"},
                },
                "required": ["control", "status", "note"],
            },
        },
        "notes": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "short observations"},
        "improve": {"type": "ARRAY", "items": {"type": "STRING"},
                    "description": "concrete, actionable regeneration notes"},
    },
    "required": ["verdict", "score_0_10", "per_control", "notes", "improve"],
}


# --- 4. Vertex AI call — gemini-3.1-pro-preview, gcloud-token auth (same pattern as ------
# genskin.py's edit_vertex()/edit_vertex_multi()) --------------------------------------
VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
VERTEX_LOCATION = "global"
VERTEX_MODEL = "gemini-3.1-pro-preview"
VERTEX_URL = (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/"
              f"{VERTEX_LOCATION}/publishers/google/models/{VERTEX_MODEL}:generateContent")


def image_part(path):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return {"inline_data": {"mime_type": "image/png", "data": b64}}


def director_chat():
    import requests
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    parts = [image_part(os.path.join(DIR_OUT, "full.png")), image_part(os.path.join(DIR_OUT, "after.png"))]
    parts += [image_part(os.path.join(DIR_OUT, name)) for _, _, name in crop_files]
    parts.append({"text": USER_PROMPT})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "systemInstruction": {"role": "system", "parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            # gemini-3.1-pro-preview defaults to thinkingLevel "high", which burns the
            # whole maxOutputTokens budget on internal thought tokens before emitting any
            # JSON (finishReason MAX_TOKENS, zero content) — see director.ts. This is a
            # short structured-review call, not open reasoning; force "low".
            "thinkingConfig": {"thinkingLevel": "low"},
            "maxOutputTokens": 3000,
        },
    }
    r = requests.post(VERTEX_URL, headers={"Authorization": f"Bearer {tok}",
                                            "Content-Type": "application/json"},
                       json=body, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    return text or "{}", cand.get("finishReason")


t0 = time.time()
raw_text, finish_reason = director_chat()
elapsed = round(time.time() - t0, 1)

# responseSchema guarantees the shape on a 200 response, but stay defensive: a schema
# mismatch, an empty/truncated response (e.g. finishReason MAX_TOKENS), or any other
# surprise must log the raw text and fall through with an empty verdict — never crash
# the run (per verify-outputs-rule / human-labeled-data-rule: a downstream reader that
# gets {} instead of a traceback is fine; a stack trace mid-batch is not).
try:
    parsed = json.loads(raw_text) if raw_text else {}
    per_control_list = parsed.get("per_control", [])
    if not isinstance(per_control_list, list):
        raise ValueError(f"per_control not a list: {type(per_control_list)}")
    verdict = {
        "verdict": parsed["verdict"],
        "score_0_10": parsed["score_0_10"],
        "per_control": {item["control"]: {"status": item["status"], "note": item["note"]}
                         for item in per_control_list},
        "notes": parsed.get("notes", []),
        "improve": parsed.get("improve", []),
    }
    parse_error = None
except Exception as e:
    verdict = {}
    parse_error = f"{e}"

record = {
    "skin": SID,
    "model": f"vertex:{VERTEX_MODEL}",
    "vertex_project": VERTEX_PROJECT,
    "structured_io": {"responseMimeType": "application/json", "responseSchema_used": True,
                       "finish_reason": finish_reason},
    "cost_estimate_usd": "0.02-0.05",
    "frames": ["full.png", "after.png"] + [name for _, _, name in crop_files],
    "elapsed_s": elapsed,
    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    **verdict,
}
if parse_error:
    record["parse_error"] = parse_error
    record["raw"] = raw_text[:4000]

json.dump(record, open(os.path.join(OUT, "director-review.json"), "w"), indent=2)
v = record.get("verdict", "UNPARSED" if parse_error else "?")
s = record.get("score_0_10", "?")
print(f"[director_review] {SID}: verdict={v} score={s} ({VERTEX_MODEL}, {elapsed}s) "
      f"-> {os.path.join(OUT, 'director-review.json')}")
