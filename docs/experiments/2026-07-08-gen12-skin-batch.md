# gen12 — themed media-player skin batch (2026-07-08)

## Question
Can a single parameterized pipeline generate high-quality, *themed*, interactive media-player
skins — a bold distinctive housing + a fixed Spotify-capable control roster that the runtime
seats and drives — across wildly different art directions, both from an authored template and
from no template at all (post-hoc detection)?

## Method
One nano-banana-pro (`fal-ai/gemini-3-pro-image-preview/edit`) generation per roll produces a
joint paint+mask; a fully-local pass (`extract12.py` + BiRefNet) recovers every control and
builds an interactive player. An auto-regen loop (`orchestrate12.py`) reseeds until a structured
GATE passes (empty sockets · 10/10 controls detected · seek covers groove · biref parts cut ·
leak <=0.3%) or 4 tries. Roster: play/pause, prev, next, repeat, queue (baked icon buttons),
volume (knob), seek (slider), shuffle (2-state toggle), visualizer + album-art (display regions).
Two modes: **templated** (control positions locked, model sculpts a bold themed housing) and
**templateless** (blank scaffold; model designs the whole player, extractor detects post-hoc).

7 theme pairs = 14 skins, each 1 templated + 1 templateless: Frutiger Aero, WMP, Steampunk/Myst,
Fallout, Fantasy (Warcraft/Diablo), N64, PS1. Fanned out across 6 Sonnet agents driving the shared
scripts (no per-skin pipeline edits — the seam contract is the shared code).

## Result
**13/14 gate-passed** (1–4 rolls each; median ~2). Strong, distinctive, on-theme silhouettes
across the board (brass nautilus porthole, olive Pip-Boy CRT, Warcraft gold shield, grimdark
Diablo stone, rusted PS1 mech, aqua-glass Frutiger-Aero blobs, graphite/electric-blue WMP…).
Templateless matched or beat templated on bold+clean. Showcase montage:
`~/Desktop/cc-skeuo/2026-07-08-gen12-skins.png`. Live oversight dashboard: `dashboard12.html`.

Human-in-the-loop feedback drove the shared-pipeline fixes (all generalizable, not per-skin):
empty-before-assembly + zero-residue + no-text + position-lock prompts; leak gate rescoped to
controls; **bold-silhouette** freedom (positions locked, housing free); **empty display screens**
(viz drawn live, not baked); **coverage-span seek travel** (full painted groove, not the
undershooting mask bbox); **silhouette-IoU switch state registration**; **device-only PCA slot
rotation** (fixed a bug where strip cells poisoned the angle); matte-hole-centroid knob seat;
template-fallback for an omitted control; dynamic cache-buster.

Known residual defects (per-generation variance, surfaced in the dashboard, not hidden): occasional
wrong/duplicate button icon (e.g. n64-lowpoly vol, wc-goldshield missing next), doubled OFF/ON
engraved text on some toggle strip cells, faint guide-colour rim on a couple skins. The wildcard
ps1-wild failed the emptiness gate (model kept installing parts) — a genuine hard case.

## Artifacts
- Pipeline (reproducible): `tools/mask-align-exp/gen12/*.py`, `theme_specs/*.json` (committed `794da20`).
- Per-skin data: `assets-<id>/{regions,results,orch}.json`, `player.html` (committed).
- Heavy media (paints/joints/mattes/biref) gitignored — rerun the pipeline to reproduce.
- New rule: `.claude/rules/fix-generalizable-rule.md`.
