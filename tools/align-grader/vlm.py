#!/usr/bin/env python3
"""
LLM-VISION half of the button-alignment grader for skeuo-ui.

grade_vlm(overlay_path, controls) -> {bind: {aligned, votes, confidence, note}}

SHARED SEAM CONTRACT
- Interactive controls = template regions with kind in
    {button,knob,toggle,slider-h,slider-v,slider-arc,slider-path,segmented,xy}.
    (Display/flourish regions are SKIPPED by the caller; this grader only sees
     the controls list it's handed.)
- A control's rect (normalized) is region.rect = {x,y,w,h};
    in frame pixels: [x*W, y*H, w*W, h*H].
- vlm record fields produced per control:
    { bind, aligned: bool, votes: [bool,...], confidence: 0..1, note: string }

The overlay image (a JPEG produced by overlay.py) shows the device with LABELED
colored boxes drawn over each control's rect. We ask gpt-4o, per control, whether
that labeled box sits correctly ON the matching painted control/well, or is
misaligned. Called 3x; majority vote per control.

OPENAI_API_KEY is read from /Users/conner/dev/central/.env (never printed).
"""

import base64
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o"
ENV_PATH = "/Users/conner/dev/central/.env"
N_VOTES = 3


def _load_api_key():
    """Read OPENAI_API_KEY. Prefer central .env over a non-OpenAI shell shim.

    The shell here often exports OPENAI_API_KEY=lm-studio (a local LM Studio
    proxy). A real OpenAI key starts with 'sk-'; if the env var isn't one, fall
    through to the real key in central .env. Never print the value.
    """
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key.startswith("sk-"):
        return key
    if not os.path.exists(ENV_PATH):
        if key:
            return key  # not 'sk-' but it's all we have
        raise RuntimeError(f"OPENAI_API_KEY not set and {ENV_PATH} not found")
    with open(ENV_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if line.startswith("OPENAI_API_KEY="):
                val = line.split("=", 1)[1].strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                return val.strip()
    raise RuntimeError(f"OPENAI_API_KEY not found in {ENV_PATH}")


def _b64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _build_prompt(controls):
    lines = [
        "This image shows a music-player device. Each LABELED colored box marks",
        "where the app will OVERLAY an interactive control (button/knob/slider/etc).",
        "For EACH control listed below, decide whether its labeled box sits CORRECTLY",
        "ON the matching painted control/well in the device art (aligned: true), OR is",
        "MISALIGNED (aligned: false) — i.e. floating on blank body, badly off-center,",
        "covering the wrong painted element, or no painted control under it.",
        "",
        "Controls (label = bind, with its kind):",
    ]
    for c in controls:
        lines.append(f"  - {c['bind']}  ({c.get('kind', '?')})")
    lines += [
        "",
        "Return STRICT JSON ONLY (no markdown, no prose), an object keyed by each",
        'control bind, each value: {"aligned": true|false, "confidence": 0..1, "note": "<short>"}.',
        "Example:",
        '{"play": {"aligned": true, "confidence": 0.9, "note": "box on round play well"},',
        ' "seek": {"aligned": false, "confidence": 0.7, "note": "box floats on blank body"}}',
    ]
    return "\n".join(lines)


def _extract_json(text):
    """Robustly pull a JSON object out of a model reply."""
    if not text:
        return None
    text = text.strip()
    # strip ```json ... ``` fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # grab the outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def _one_call(api_key, b64, prompt, retries=2):
    """One vision call -> parsed dict {bind: {...}}, or {} on failure."""
    payload = {
        "model": MODEL,
        "temperature": 0.2,
        "max_tokens": 1200,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                OPENAI_URL,
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            if isinstance(parsed, dict):
                return parsed
            last_err = "unparseable JSON"
        except urllib.error.HTTPError as e:
            try:
                last_err = f"HTTP {e.code}: {e.read().decode('utf-8')[:200]}"
            except Exception:
                last_err = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    sys.stderr.write(f"[vlm] call failed: {last_err}\n")
    return {}


def grade_vlm(overlay_path, controls):
    """
    overlay_path : path to the JPEG overlay (labeled boxes over each control).
    controls     : list of {bind, kind}.
    returns      : {bind: {aligned, votes, confidence, note}}
    """
    api_key = _load_api_key()
    b64 = _b64_image(overlay_path)
    prompt = _build_prompt(controls)

    # N independent calls (votes).
    rounds = []
    for _ in range(N_VOTES):
        rounds.append(_one_call(api_key, b64, prompt))

    out = {}
    for c in controls:
        bind = c["bind"]
        votes = []
        confs = []
        notes = []
        for r in rounds:
            rec = r.get(bind)
            if isinstance(rec, dict) and "aligned" in rec:
                votes.append(bool(rec["aligned"]))
                try:
                    cf = float(rec.get("confidence", 0.5))
                except (TypeError, ValueError):
                    cf = 0.5
                confs.append(max(0.0, min(1.0, cf)))
                n = rec.get("note")
                if isinstance(n, str) and n.strip():
                    notes.append(n.strip())
        if votes:
            n_true = sum(1 for v in votes if v)
            aligned = n_true > (len(votes) / 2.0)
            confidence = round(sum(confs) / len(confs), 3) if confs else 0.5
            # prefer a note from a vote that matches the majority decision
            note = ""
            for r in rounds:
                rec = r.get(bind)
                if (
                    isinstance(rec, dict)
                    and bool(rec.get("aligned")) == aligned
                    and isinstance(rec.get("note"), str)
                    and rec["note"].strip()
                ):
                    note = rec["note"].strip()
                    break
            if not note and notes:
                note = notes[0]
        else:
            # all calls failed to report this control
            aligned = False
            confidence = 0.0
            note = "no vlm response"
        out[bind] = {
            "bind": bind,
            "aligned": aligned,
            "votes": votes,
            "confidence": confidence,
            "note": note,
        }
    return out


def _parse_controls_args(args):
    controls = []
    for a in args:
        if ":" in a:
            bind, kind = a.split(":", 1)
        else:
            bind, kind = a, "?"
        controls.append({"bind": bind.strip(), "kind": kind.strip()})
    return controls


def main():
    if len(sys.argv) < 3:
        sys.stderr.write(
            "usage: python vlm.py <overlay.jpg> <bind1:kind1> <bind2:kind2> ...\n"
        )
        sys.exit(2)
    overlay = sys.argv[1]
    controls = _parse_controls_args(sys.argv[2:])
    if not os.path.exists(overlay):
        sys.stderr.write(f"overlay not found: {overlay}\n")
        sys.exit(1)
    result = grade_vlm(overlay, controls)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
