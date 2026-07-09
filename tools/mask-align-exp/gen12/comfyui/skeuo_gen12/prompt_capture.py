#!/usr/bin/env python3
"""Capture the EXACT structural prompt genskin.py builds — without any fal/network call.

Imports the UNMODIFIED genskin.py, stubs its three fal helpers (load_fal / upload / edit),
and runs main(). genskin writes blueprint.png + results.json exactly as it always does; the
prompt is intercepted at the precise point genskin would have sent it to the image model.
Zero duplication of prompt logic, zero network, zero key handling.

Usage: python3 prompt_capture.py <spec.json> <gen12_dir> <prompt_out.txt>
"""
import os
import sys
import importlib.util

spec_path, gen12_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

_ml = importlib.util.spec_from_file_location("genskin", os.path.join(gen12_dir, "genskin.py"))
m = importlib.util.module_from_spec(_ml)
_ml.loader.exec_module(m)


class _Captured(Exception):
    pass


cap = {}
m.load_fal = lambda: "STUB-NO-CALL"          # never reads/needs FAL_KEY
m.upload = lambda FAL, p: "https://invalid.local/blueprint.png"


def _edit(FAL, url, prompt, seed):
    cap["prompt"] = prompt
    raise _Captured


m.edit = _edit

sys.argv = ["genskin.py", spec_path]
try:
    m.main()
except _Captured:
    pass
else:
    sys.exit("prompt was NOT captured — genskin.py flow changed; update prompt_capture.py")

with open(out_path, "w") as f:
    f.write(cap["prompt"])
print(f"[prompt-capture] {len(cap['prompt'])} chars -> {out_path}")
