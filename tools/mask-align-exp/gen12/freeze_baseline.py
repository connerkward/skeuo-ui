#!/usr/bin/env python3
"""freeze_baseline.py <assets-dir> — freeze paid generation outputs the moment they FIRST
pass the gate, so a later re-roll can never make them unrecoverable.

GUARDRAIL this closes (drift bisect, commit 892bf045): every June baseline paint was
re-rolled before it was ever preserved — the bytes are gone for good, which blocked a $0
follow-up experiment and violates the spirit of generation-spend-rule (paid output is not
disposable) and empirical-testing-rule (a durable record must survive the session). Paid
generation outputs must be FROZEN the moment they first matter: the first gate PASS.

What gets frozen, and how (per current media policy, TODO.md "Media policy revisit"):
  - joint-4k.png is a paid Vertex/fal roll and is NOT git-tracked (bulk-offloaded to Drive
    2026-07-11, see .gitignore's media-offload policy). It is the one file this script
    uploads: gdrive:skeuo-ui/gen12-media/frozen/<skin>/<seed>-<date>/joint-4k.png via
    `rclone copy --checksum`.
  - paint.png and mask.png ARE git-tracked (`git ls-files assets-*/paint.png assets-*/mask.png`
    confirms this for every skin as of 2026-07-11) — git itself is their freeze mechanism:
    every commit is a permanent, content-addressed snapshot of the exact bytes. This script
    intentionally does NOT re-upload them; it would be a redundant, driftable second copy of
    something git already preserves durably. If that git-tracked policy ever changes (paint/
    mask get gitignored), this script needs a matching change to freeze them too.

Idempotent by sha256: if a row for this exact joint-4k.png sha256 already exists in
media-manifest.json, the upload is skipped (already durable) and the script exits 0.

Never blocks the pipeline: any rclone failure (offline, expired auth, network) is logged
loudly to stderr and the script exits 0 regardless — freezing is a durability nice-to-have
bolted onto the gate-PASS path, never a reason to fail a generation run.

Usage: python3 freeze_baseline.py <assets-dir>
Called automatically by orchestrate12.py after a gate PASS, behind FREEZE_ON_PASS.
"""
import os
import sys
import json
import time
import hashlib
import subprocess
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_JSON = os.path.join(HERE, "media-manifest.json")
MANIFEST_MD = os.path.join(HERE, "MEDIA-MANIFEST.md")
REMOTE = "gdrive:"
FROZEN_ROOT = "skeuo-ui/gen12-media/frozen"


def log(skin, msg, err=False):
    line = f"[freeze:{skin}] {msg}"
    print(line, file=sys.stderr if err else sys.stdout, flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_root():
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                        capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        return r.stdout.strip()
    # fallback: gen12 is tools/mask-align-exp/gen12 under repo root
    return os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load_manifest():
    if os.path.exists(MANIFEST_JSON):
        return json.load(open(MANIFEST_JSON))
    return {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "drive_remote": REMOTE,
        "drive_root": "skeuo-ui/gen12-media",
        "note": "Bulk non-runtime gen12 media offloaded from git to Google Drive.",
        "files": [],
    }


def already_frozen(manifest, sha):
    # Scoped to kind=="frozen-baseline" ONLY — deliberately does not dedup against the
    # unrelated bulk-offload rows (drive_root .../2026-07-11/) that a separate, earlier
    # media-volume-savings migration wrote for the same files. Freeze-on-pass must not
    # silently no-op just because some other job happened to grab the same bytes; the
    # frozen/<skin>/<seed>-<date>/ copy is its own dedicated, gate-PASS-triggered guarantee.
    return any(row.get("sha256") == sha and row.get("kind") == "frozen-baseline"
               for row in manifest["files"])


def append_md_row(row):
    """Idempotently append a row to MEDIA-MANIFEST.md's 'Frozen baselines' section
    (creating the section on first use). Skipped if the sha is already present in the
    file's text (belt-and-suspenders alongside the JSON-side sha dedup)."""
    text = open(MANIFEST_MD).read() if os.path.exists(MANIFEST_MD) else ""
    if row["sha256"] in text:
        return
    header = "\n## Frozen baselines (gate-PASS snapshots, never re-rolled without a preserved copy)\n\n"
    header += ("Policy: `freeze_baseline.py` runs after every gate PASS in `orchestrate12.py` "
               "(`FREEZE_ON_PASS`). Uploads `joint-4k.png` (the non-git-tracked paid roll) to "
               f"`gdrive:{FROZEN_ROOT}/<skin>/<seed>-<date>/`; `paint.png`/`mask.png` are "
               "git-tracked, so git is their freeze — no separate upload for those two.\n\n")
    header += "| skin | seed | gate-pass date | repo path | bytes | sha256 | Drive link |\n"
    header += "|---|---:|---|---|---:|---|---|\n"
    if "## Frozen baselines" not in text:
        text = text.rstrip("\n") + "\n" + header
    line = (f"| `{row['skin']}` | {row['seed']} | {row['gate_pass_date']} | "
            f"`{row['repo_path']}` | {row['bytes']:,} | `{row['sha256'][:16]}…` | "
            f"[link]({row['gdrive_link']}) |\n")
    text += line
    open(MANIFEST_MD, "w").write(text)


def main():
    if len(sys.argv) < 2:
        print("usage: freeze_baseline.py <assets-dir>", file=sys.stderr)
        sys.exit(1)

    assets_dir = os.path.abspath(sys.argv[1].rstrip("/"))
    skin = os.path.basename(assets_dir)
    if skin.startswith("assets-"):
        skin = skin[len("assets-"):]

    joint = os.path.join(assets_dir, "joint-4k.png")
    if not os.path.exists(joint):
        log(skin, f"no joint-4k.png at {joint} — nothing to freeze, exiting 0")
        sys.exit(0)

    # seed: ALWAYS from results.json, never orch.json. results.json is rewritten every roll
    # by genskin.py/extract12.py, so its "seed" always matches the joint-4k.png bytes
    # currently on disk. orch.json is only written by orchestrate12.py AFTER the whole roll
    # loop finishes (see orchestrate12.py) — reading it here, mid-loop, right after the roll
    # that just passed, would silently return a STALE seed from a prior invocation. Fall back
    # to orch.json's final_seed only when results.json has nothing (standalone/edge case).
    seed = None
    try:
        seed = json.load(open(os.path.join(assets_dir, "results.json"))).get("seed")
    except Exception:
        pass
    orch_path = os.path.join(assets_dir, "orch.json")
    if seed is None and os.path.exists(orch_path):
        try:
            seed = json.load(open(orch_path)).get("final_seed")
        except Exception:
            pass

    # gate-pass date: regions.json is the file extract12.py writes carrying the gate verdict
    # itself (regions.json["gate"]["PASS"]), rewritten every roll — its mtime is the moment
    # THIS generation's gate confirmed PASS, always fresh regardless of loop position. Falls
    # back to the joint-4k.png's own mtime, then today.
    gate_pass_date = date.today().isoformat()
    regions_path = os.path.join(assets_dir, "regions.json")
    if os.path.exists(regions_path):
        gate_pass_date = date.fromtimestamp(os.path.getmtime(regions_path)).isoformat()
    elif os.path.exists(joint):
        gate_pass_date = date.fromtimestamp(os.path.getmtime(joint)).isoformat()

    sha = sha256_of(joint)
    nbytes = os.path.getsize(joint)

    manifest = load_manifest()
    if already_frozen(manifest, sha):
        log(skin, f"sha256 {sha[:12]}… already has a manifest row — skip upload (idempotent)")
        sys.exit(0)

    root = repo_root()
    repo_path = os.path.relpath(joint, root).replace(os.sep, "/")

    drive_dir = f"{FROZEN_ROOT}/{skin}/{seed}-{gate_pass_date}"
    drive_path = f"{drive_dir}/joint-4k.png"

    log(skin, f"uploading joint-4k.png ({nbytes:,} bytes, sha256 {sha[:12]}…) -> {REMOTE}{drive_dir}/")
    try:
        r = subprocess.run(["rclone", "copy", "--checksum", joint, f"{REMOTE}{drive_dir}/"],
                            capture_output=True, text=True, timeout=300)
    except Exception as e:
        log(skin, f"rclone copy raised (offline / rclone missing?): {e} — freeze SKIPPED, pipeline continues", err=True)
        sys.exit(0)
    if r.returncode != 0:
        log(skin, f"rclone copy FAILED: {(r.stderr or r.stdout).strip()[-500:]}", err=True)
        log(skin, "freeze SKIPPED — pipeline continues (freezing must never break a run)", err=True)
        sys.exit(0)

    link = None
    try:
        lr = subprocess.run(["rclone", "link", f"{REMOTE}{drive_path}"],
                             capture_output=True, text=True, timeout=60)
        if lr.returncode == 0:
            link = lr.stdout.strip()
        else:
            log(skin, f"rclone link failed (upload still succeeded): {lr.stderr.strip()[-300:]}", err=True)
    except Exception as e:
        log(skin, f"rclone link raised (upload still succeeded): {e}", err=True)

    row = {
        "kind": "frozen-baseline",
        "skin": skin,
        "seed": seed,
        "gate_pass_date": gate_pass_date,
        "repo_path": repo_path,
        "gdrive_path": drive_path,
        "gdrive_link": link,
        "sha256": sha,
        "bytes": nbytes,
    }
    manifest["files"].append(row)
    json.dump(manifest, open(MANIFEST_JSON, "w"), indent=2)
    append_md_row(row)
    log(skin, f"frozen: {REMOTE}{drive_path}" + (f" ({link})" if link else " (no share link)"))


if __name__ == "__main__":
    main()
