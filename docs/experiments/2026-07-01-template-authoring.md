# Template authoring — DATA-authored vs RENDERED-template — 2026-07-01

**Question:** Should the layout template be authored as **DATA** (an LLM emits the
control coordinates directly) or as a **RENDERED template image** (a model paints a
template, then segmentation recovers the hotspots)?

**Method:**

- **Branch A — DATA path:** the existing `deriveLayout` data path; reused **3 repo
  paints** (WMP-9 chrome pill, Mandalay gunmetal square, Y2K aqua bubble). Hotspots
  are the authored coords — no detection.
- **Branch B — RENDERED path:** **nano-banana-2** (`fal-ai/gemini-3.1-flash-image-preview/edit`)
  renders a **template image** from a coord-seeded wireframe (**3 concepts**), then a
  **segmentation bake-off** recovers the 16 control hotspots.

Scratch: `/tmp/tplexp` (`gen_templates.py`, `gen_paints.py`, `build_seeds.py`,
`branchB_gt.json` = ground-truth boxes).

**Candidates / conditions — hotspot recovery (16 controls):**

| Method | Recall | False positives | Pos err | Cost / speed |
|--------|:------:|:---------------:|:-------:|--------------|
| **Classical CV** on the **clean template** | **16/16** | **0** | **0.2%** | free, fast |
| **SAM (ViT-B)** on the clean template | 15/16 | 0 | 0.2% | free, **~100× slower** |
| **Classical CV** on the **PAINT** (not the template) | 15/16 | 2 | 0.4% | free, fast |
| **VLM — gpt-4o** boxes | 7/16 | 10 | 4.3% | **unusable** |

**Verdict (human-reviewed — Conner, 2026-07-01):**

- **DATA-authored wins the hotspot axis outright** — **100% exact** recovery, **free**,
  **zero false positives**. There is nothing to recover because the coords *are* the
  authored data.
- **Rendered-template + segmentation is ruled out** as the hotspot source: even the
  best segmentation (classical CV on a clean template) only *matches* free/exact data
  at real cost, and degrades on the paint; the **VLM is unusable** (7/16, 10 FP).
- **Synthesis adopted — HYBRID:** **enrich `deriveLayout` to author ORGANIC
  (bezel-hugging, non-rectangular) layouts as DATA.** This keeps the **free + exact +
  zero-FP** hotspots of Branch A *and* buys the **organic WMP/Winamp look** that made
  Branch B's rendered templates attractive — without inheriting segmentation.

**Caveat recorded:** the segmentation numbers were measured on **EASY synthetic
templates** (round / square shapes on a clean field). A follow-up must **stress-test
hard / wild shapes** (organic bezels, overlapping, low-contrast) before treating
"classical CV = 16/16" as general — it is a best-case number here.

**Candidate model:** templates + paints rendered with **nano-banana-2**
(`fal-ai/gemini-3.1-flash-image-preview/edit`). Segmentation methods: OpenCV classical,
SAM ViT-B, gpt-4o VLM boxes.

## Artifacts

- **A-vs-B integration** (Branch A data-authored vs Branch B rendered-authored, 3
  concepts — which reads more like a cohesive early-2000s device) —
  [`assets/2026-07-01-template-integration-a-vs-b.png`](./assets/2026-07-01-template-integration-a-vs-b.png)
- **Segmentation overlay — Classical CV, WMP-pill** (the winner: recall 16/16, FP 0,
  posErr 0.2%; yellow cross = intended button, overlay = recovered match) —
  [`assets/2026-07-01-template-seg-classical-wmp.png`](./assets/2026-07-01-template-seg-classical-wmp.png)
- **Segmentation overlay — VLM gpt-4o, WMP-pill** (why it's ruled out: sparse recall +
  many false positives) —
  [`assets/2026-07-01-template-seg-vlm-wmp.png`](./assets/2026-07-01-template-seg-vlm-wmp.png)
