# skeuo.fm mascot — 2D animation pipeline IDEATION BRIEF

*A thinking artifact for ideating WITH a human. Research + design options, not a build. No final assets generated; no fal spend. All game/tool/model facts below were web-verified (sources at bottom), not asserted from memory — fal pricing was pulled live from the catalog.*

---

## 0. The problem, stated precisely

We have **one** canonical character: a chubby glossy-3D green gremlin (red backwards cap, gray horns, big eyes, fang), AI-generated. We need it to:

1. **Cycle** between animation states — idle (breathe/sway), dance (bounce/head-bob), maybe walk/run, reactions.
2. **Blend smoothly** between states, **reactive to music energy/BPM** — idle↔dance should ramp, not hard-cut.
3. Stay **exactly on-model** — independent re-generations drift, and that has burned us repeatedly.
4. End as **real-alpha sprites/clips** on a dark UI (BiRefNet matting available).
5. **Cost little** — minimize paid generations.

The central tension is a **triangle** the whole history of 2D game animation has been negotiating:

```
        ON-MODEL CONSISTENCY
               /\
              /  \
             /    \
            /      \
   SMOOTH BLEND --- CHEAP / LOW-EFFORT
```

You almost never get all three from one technique. The hand-drawn era bought consistency + control by paying in *labor* and *giving up blending*. Skeletal/puppet 2D bought blending + cheap-per-frame by paying in *rig setup* and accepting a *cut-out look*. AI image-to-video buys cheap motion but **fails exactly on consistency** — the corner we cannot afford to lose. The recommendation at the end is essentially: *which corner do we refuse to give up, and which technique sacrifices a corner we don't care about?* For us the non-negotiable corner is **on-model**, and the cheapest, highest-control way to lock it is to **stop re-generating the character per frame at all** and instead generate it **once** and animate that one asset by transform/deform — which is exactly the insight every robust pipeline below shares.

---

## 1. How 2D games actually cycled & blended animations, by era

### 1.1 Hand-drawn sprite-sheet era — discrete states, **instant swaps, NO blending**

Street Fighter, King of Fighters (SNK), Metal Slug, Castlevania, Guilty Gear / BlazBlue (Arc System Works) all share one model: each **state** (idle, walk, jab, jump) is a **fixed set of hand-drawn frames**; a simple **animation state machine** plays the current state's loop and **swaps instantly** to the next state's first frame. There is **no interpolation between states** — and that was a *deliberate design choice, not a limitation they regretted.*

The reason is **readability**. From fighting-game animation practice (Rivals of Aether's workshop guide, the Kevuru/RetroStyle breakdowns, Tuula Rantala's HD-2D-character thesis): every action is **anticipation → action → recovery**, and *"it's more important that the character's current state is very clear … if the character smoothly moves between two poses, then during the transitioning frames it's unclear which state the character is in."* So they **avoid** in-between frames that don't clearly belong to one pose. Smoothness is sacrificed *on purpose* for instant state legibility.

How they hid the lack of blending:
- **Anticipation/transition frames** baked *into* a clip (a wind-up that reads as a bridge), not generated between clips.
- **Short clips + snappy timing** so the eye never expects a tween.
- **Pose-to-pose punch**: crisp held extremes; the "snap" is the aesthetic.

**Relevance to us:** This is the *opposite* of what we want (we explicitly want idle↔dance to ramp, not cut). BUT it's the cheapest, most on-model-robust possible approach, and it's the **fallback floor**: if blending proves too hard, a small set of hand-authored loops + a couple of bespoke *transition clips* (idle→dance "getting into it", dance→idle "settling") is the fighting-game answer and it always works. Don't dismiss it.

### 1.2 The state-machine / blend-tree concept (from 3D, borrowed by 2D)

Unity **Mecanim** and Unreal formalized two layers:
- **Animation State Machine** — a flowchart of states (idle, walk, run) with transition conditions. This is the *discrete* layer the sprite era already had.
- **Blend Tree** — *continuous* blending between similar clips driven by a **float parameter** (e.g. `speed`: walk↔run weighted-blend). 2D Blend Trees blend on two parameters (e.g. move-direction X/Y). Crucially you can also **layer** an additive animation on top (shoot *while* running).

**This is the conceptual spine of what we want.** "Reactive to music energy/BPM" = a **float parameter** (`energy` 0→1) driving a **blend tree** between an idle clip and a dance clip, with BPM driving playback rate. The open question is only *what we're blending* — because **blend trees blend poses/bone-transforms, not pixels.** Cross-fading two *drawings* ghosts (the user already flagged this). Cross-fading two *skeletal poses* doesn't. That single fact is what splits the candidate pipelines below.

### 1.3 Cut-out / skeletal 2D that **DOES** blend — Spine, DragonBones, Live2D

This is the family built specifically to solve "blend where sprites can't."

- **Esoteric Software Spine** (the industry standard; used across countless shipped 2D games). You cut the character into **images attached to bones**; animation = **interpolating bone transforms** (rotation/translation/scale) over time. Because you're interpolating a *skeleton*, the runtime gives you exactly the 3D-style tools:
  - *"Animations can even be blended, for example half walking and half running"* — continuous crossfade between two animations with **no ghosting**, because it blends bone rotations, not pixels.
  - **Layering / additive** — *"play a shooting animation while your character is running … blend walking and limping more and more as damage is taken."* This is our `energy`-driven idle↔dance ramp, natively.
  - **Mesh deformation** — *"images are no longer rigid and can bend and deform … weights bind meshes to bones, so the images deform automatically."* Gives squash/stretch and bend, not just rigid limb rotation. Plus **IK**.
- **DragonBones** — open-source equivalent (free), same bone+mesh model, exports to web runtimes.
- **Live2D Cubism** — the VTuber standard, **mesh-warp-deformer-centric** rather than bone-centric. You author **parameters** (Head X/Y, Body X/Y, Mouth Open, Blink…) as **keyforms** at parameter extremes, and the runtime **interpolates between keyforms**. Per the Live2D manual: *"use keyforms to pose at specific values, then rely on interpolation to smooth motion between them."* This is *exactly* our breathe/sway/head-bob vocabulary, and VTuber rigs are famously driven by **continuous live signals** (face-tracking) — swap the signal for **music energy/BPM** and you have the skeuo idle↔dance.

**Why this family blends where sprites don't:** they never store pixels-per-frame. They store **one set of part images + a rig**, and motion is **interpolated transform/deformation parameters**. Interpolating *parameters* is continuous and ghost-free by construction; interpolating *pixels* (optical-flow/crossfade between two different drawings) is not.

> **Caveat (Hollow Knight):** Team Cherry did **NOT** use Spine. Hollow Knight / Silksong are **frame-by-frame hand-drawn PNGs in Unity** (verified — Team Cherry's own "Inside the Mind of a Bug" blog + Made-with-Unity case study). So Hollow Knight belongs in §1.1, not here. The *Ori* games (Moon Studios) are the better "skeletal-2D blends beautifully" exemplar to cite. Don't repeat the common myth that Hollow Knight is Spine.

### 1.4 Mesh-deform / puppet 2D — UbiArt, After Effects puppet pins

- **Ubisoft UbiArt Framework** (Rayman Origins / Legends, Child of Light; Michel Ancel + Ubisoft Montpellier). Hand-drawn vector art is **rigged with bones + procedural deformation**; the **GenAnim** tool does **keyframe interpolation** so a few keyposes yield 60fps output via **real-time interpolation** — *"high-frame-rate output up to 60 FPS using minimal assets through real-time interpolation."* Same principle as Spine, art-first authoring. Proof that "few keyframes → smooth high-fps motion via interpolation of a rig" is a shipped, beautiful approach.
- **After Effects puppet pins / Duik / Rubberhose / Joysticks-n-Sliders** — the motion-graphics version: drop pins on one artwork, deform it. **Joysticks-n-Sliders** literally builds a 2D blend space (a "joystick" interpolating between extreme drawings — up/down/left/right head turns). This is the AE analog of a Live2D parameter and a great mental model for "one drawing, controller-driven blend."

### 1.5 Modern hybrid — Dead Cells (the most relevant one)

**Motion Twin's Dead Cells** is the single closest precedent to our need. They **model & rig the character in 3D (3DS Max), animate in 3D, then render each frame down to a 2D pixel sprite** with a homebrew tool. (Verified: GameDeveloper "Art Design Deep Dive", Game Anim 2018.) Why they did it, and why it maps onto us almost 1:1:

- **On-model by construction.** There is exactly **one** canonical 3D asset. Every frame, every state, every angle is a *render of the same object*, so it **cannot drift off-model** — the consistency problem is solved *upstream of the frames*. This is our #1 constraint, solved structurally.
- **Cheap to produce many animations.** *"One person can create a lot of animations very quickly"*; tweak weight/timing without redrawing.
- **You keep the 2D sprite look** on output (they even pixel-render it).
- Inspired by **King of Fighters / BlazBlue / Guilty Gear** — note Arc System Works' *Guilty Gear Xrd* is the inverse trick (real-time 3D shaded to look hand-drawn 2D); Dead Cells bakes 3D to sprite sheets offline.

**The lesson for skeuo:** *"one canonical character → render many frames"* is the on-model-consistency answer the whole industry converged on. Our gremlin is already described as "glossy-3D" — it *wants* to be a real 3D/2.5D object we pose, not a pile of independent 2D generations.

### 1.6 Inbetweening — classic pose-to-pose, and modern optical-flow / generative tweening

- **Classic (Disney, Richard Williams "The Animator's Survival Kit").** Senior animators draw **extremes** (key poses) and **breakdowns** (the passing position that defines *how* you get between keys); juniors draw **inbetweens**. **Timing** (how many frames) and **spacing** (their distribution → ease) carry the feel. The breakdown is the load-bearing idea: *the transition is authored, not averaged.* This is why a good idle→dance transition is a designed breakdown pose, not a linear lerp.
- **Modern optical-flow tweening — RIFE, Google FILM.** Neural frame interpolation. RIFE (ECCV 2022, IFNet) is the "gold standard" speed/quality tradeoff; FILM ("Frame Interpolation for Large Motion") handles bigger gaps. **But on cartoon/flat art they degrade**: verified failure modes are **blur, loss of fine detail, ghosting, tearing** on *"large non-linear motion and textureless regions of cartoons"* — exactly our glossy flat gremlin. `RIFE-anime` variants help but don't fully fix it. **Verdict: fine for ×2/×4 *within* a smooth clip (cheap fps boost); risky as the *transition* mechanic between two very different poses.**
- **Generative inbetweening — ToonCrafter (SIGGRAPH Asia 2024, Doubiiu).** Diffusion-prior cartoon interpolation: give it **two keyframes** and an optional **user sketch** for the motion path, it synthesizes inbetweens *"even with large non-linear motions and dis-occlusions"* (512×320, ≤16 frames). This is the AI tool that genuinely targets the case RIFE/FILM fail at. Caveat: it's a generative model, so the inbetweens can drift off-model on a stylized character (the same consistency risk as all gen-AI), and the resolution/length caps are real. Worth a *test*, not a blind commit.

### 1.7 AI-native — and why it's a trap for our #1 constraint

- **image-to-video** (Kling/Runway/Pika/LTX on fal): animate one still. Cheap motion, **but** small subtle motion is what these are *worst* at — they tend to invent motion, warp the face, and drift. The gremlin's identity (cap, horns, fang, eyes) will wobble.
- **Pose-controlled video — ControlNet + OpenPose + AnimateDiff.** OpenPose gives a stick-figure to follow; AnimateDiff gives temporal coherence. Verified problem: *"struggle to maintain long-term appearance consistency,"* "flickering and jumpy" textures, "domain gap." On a humanoid this can work; our gremlin has **horns + a cap + non-human proportions** that OpenPose doesn't model well.
- **Animate Anyone** (arXiv 2311.17117) — the research line explicitly built to fix character consistency in pose-driven video (a ReferenceNet preserves appearance). Better, but still a generative per-frame process = residual drift, and it's humanoid-pose-driven.
- **AnimateDiff/sprite-sheet generators** — produce a grid of frames in one shot; **consistency across the grid is the known weak point.**

**Bottom line on AI-native:** every one of these **re-generates appearance per frame**, which is precisely the mechanism that drifts off-model. They're attractive for *cost* and *zero-rig effort*, and they're the corner we should be most suspicious of. Their best honest role for us is **narrow and bounded**: generating a **single canonical turnaround/pose set once** (then never re-generated), or a **bounded one-shot transition clip** we visually accept frame-by-frame — not as the live animation engine.

---

## 2. Mapping each approach to OUR problem (ranked)

Scores 1–5 (5 = best for us). "On-model" weighted highest because it's the constraint that has repeatedly burned us.

| Approach | On-model fidelity | Blend quality | Cost (paid gen) | Control | Effort to build | Net fit |
|---|---|---|---|---|---|---|
| **Render-from-one-rig** (Dead Cells–style: 1 canonical 3D/2.5D char → pose/render frames) | **5** (one asset, can't drift) | 4 (blend the *rig*, bake frames; or blend live in 3D) | **5** (≈0 ongoing — local Three.js render) | **5** | 3 (build the rig once) | **★ Best** |
| **Skeletal/puppet cut-out** (Spine/DragonBones/Live2D/code: cut 1 generated char into parts → bone/mesh blend) | **5** (one art set) | **5** (param interpolation, ghost-free, additive) | **5** (≈0 ongoing) | **5** | 3–4 (cut + rig + weight) | **★ Best** |
| **Key-pose gen + interpolation** (gen a few on-model key poses → RIFE/FILM/ToonCrafter tween) | 3 (keys on-model; tweens may wobble) | 3 (RIFE blurs cartoons; ToonCrafter better but caps) | 3 (few gens + cheap interp) | 3 | 2 | Middle |
| **Hand-authored sprite states + bespoke transition clips** (fighting-game model) | **5** | 2 (instant swaps; transitions only where authored) | 4 | 4 | 2–3 | Fallback floor |
| **image-to-video on the still** (Kling/Runway/Pika) | 2 (drifts) | 2 | 2 (per clip) | 2 | 1 | Poor |
| **Pose-controlled gen video** (ControlNet/OpenPose/AnimateDiff/Animate-Anyone) | 2 (residual drift; non-human rig) | 3 | 2 | 3 | 2 | Poor for this char |

**The two winners both share the same move: generate the character ONCE, then animate by transform/deformation — not by re-generation.** That is the entire on-model insight, and it's what Dead Cells, Spine, Live2D, and UbiArt all independently arrived at.

---

## 3. Candidate pipelines (end-to-end, concrete)

### Pipeline A — "Cut-out rig in code" (Spine/Live2D philosophy, **no rig-tool license, runs on the dark UI natively**)

**Idea:** Treat the existing gremlin generation as the canonical art. **Cut it into parts** (head, cap, horns L/R, eyes, jaw/fang, body, arms, feet) once, build a **bone/mesh rig in code** (PixiJS + `pixi-spine`, or DragonBones runtime, or a hand-rolled SVG/Canvas/Three.js sprite-bone hierarchy), and drive it with a **blend tree** parameterized by **music energy/BPM**.

**Generated vs coded:**
- *Generated (paid, once):* the canonical gremlin still, ideally in a clean **flat/neutral pose** with limbs slightly separated so cutting is easy. Optionally a 2nd nano-banana edit to get a "limbs apart" T-pose-ish variant for clean part extraction. **~1–3 paid images total, ever.**
- *Coded (free):* part-cutting (could be one BiRefNet matte + manual/▢-box slicing, or `nano-banana edit` masked cutouts), the rig, the breathe/sway/bob keyforms, the energy→blend mapping, BPM→playback-rate, the runtime on the dark UI.

**How blending works:** Two clips authored as **keyform/bone-pose tracks** — `idle` (gentle vertical breathe + slow sway) and `dance` (bounce + head-bob + cap tilt). A float `energy∈[0,1]` does a **weighted blend of the two bone-pose sets** (Spine/Live2D-style). Because we blend **transforms, not pixels, there is zero ghosting.** BPM sets the dance clip's playback speed; energy ramps the weight. Reactions = additive overlay tracks (eye-pop, fang-grin) layered on top.

**Rough cost:** **~$0.04–$0.45 one-time** in generation (1× nano-banana ≈ $0.04, or up to a few nano-banana-pro edits ≈ $0.15 ea), then **$0 forever**. Pure code at runtime.

**Failure modes:** (1) **Cutting/rigging labor** — the glossy 3D shading has baked-in highlights/occlusion, so a rotated cap may reveal a "hole" or wrong shading; mesh-deform + small rotations mitigate but extreme poses break the illusion. (2) Gloss highlights don't move correctly under deformation (they're painted, not lit) — keep motions subtle (breathe/bob/sway), which is exactly our brief. (3) Part seams on the dark UI need clean alpha (BiRefNet handles this well).

---

### Pipeline B — "Dead Cells in the browser" (one canonical 2.5D character → render pose frames)

**Idea:** Reconstruct the gremlin as a **lightweight 2.5D/3D-ish posable object** and **render frames from it** — Motion Twin's exact trick, but with a **Three.js/WebGL** renderer (local, free) instead of 3DS Max, per the team's web-render-first preference. Two sub-variants:

- **B1 (true 3D):** build/commission a simple 3D gremlin (or image-to-3D from the canonical still as a *starting mesh*), rig it, render idle/dance/transition either **offline to sprite sheets** (bake, like Dead Cells) **or live in Three.js** on the UI. Live 3D means **idle↔dance blends in the 3D animation system** (real blend tree, BPM-reactive) and you never store pixels.
- **B2 (2.5D parts in 3D):** the cut-out parts from Pipeline A, but placed on **billboarded planes in Three.js** with a bone hierarchy — gets you depth-correct bob/tilt and lets the *renderer* do lighting on the gloss.

**Generated vs coded:**
- *Generated:* canonical still (paid, once). For B1, optionally one **image-to-3D** pass (fal has image-to-3d models) to bootstrap a mesh — but expect to hand-clean it; AI meshes are rough. Possibly a few nano-banana views (front/side) to guide modeling.
- *Coded/local:* the Three.js scene, rig, blend tree, energy/BPM mapping, ACES tonemap + envmap so the gloss reads, BiRefNet not even needed if rendered on transparent canvas.

**How blending works:** Native 3D animation blending (idle clip ↔ dance clip weighted by `energy`), or baked sprite-sheet states + authored transition sheets if you prefer the §1.1 discrete model. Live 3D is the smoothest and **most on-model** (single mesh).

**Rough cost:** generation **~$0.04 + optional image-to-3D (a few cents to ~$0.10)**, then **$0** at runtime. Main cost is **modeling/rig effort**, not money.

**Failure modes:** (1) **Modeling effort** — getting the 3D gremlin to match the beloved 2D look is real work; AI image-to-3D output will *not* be on-model out of the box and needs cleanup (this is the place B can secretly *re-introduce* the drift problem if you trust the auto-mesh). (2) Matching the glossy AI-render aesthetic in a real-time renderer takes lookdev (envmap, fresnel, tonemap). (3) Heaviest upfront effort of the three.

---

### Pipeline C — "Key-pose generation + AI inbetweening" (cheapest to *start*, riskiest on-model)

**Idea:** Don't rig anything. **Generate a small number of on-model key poses** of the gremlin via `nano-banana edit` (which is *much* more on-model than free-generation because it **edits the same source image** rather than re-rolling identity), then **interpolate between keys** to make clips, and **interpolate between clips** for the idle↔dance ramp.

**Generated vs coded:**
- *Generated (paid):* e.g. idle-low / idle-high (breathe extremes), dance-A / dance-B / dance-C (bounce extremes, head-bob), a couple of reaction poses. Maybe **6–12 nano-banana edits** total. Using `nano-banana edit` with the canonical still as the input image + "same character, identical cap/horns/fang, now bouncing with knees bent" keeps identity far better than text-to-image.
- *Coded/local:* **FILM/RIFE** (local or fal — fal FILM is ~$0.0013/sec, negligible) to tween between the key poses into loops; **ToonCrafter** (local, free on MPS, or a HF space) for the *hard* transitions where RIFE would ghost; BiRefNet matte every frame; ffmpeg to assemble; a **pixel-crossfade-free** energy ramp done by **switching which interpolated clip plays + RIFE-tweening across the boundary** (NOT alpha-crossfading two clips — that ghosts).

**How blending works:** This is the weak spot. You have *clips*, and blending clips of *pixels* is the ghosting trap. The least-bad answer: author an explicit **transition key-pose** (idle-rest → "getting into it" breakdown → dance-start) and **RIFE/ToonCrafter through those keys**, i.e. treat the transition as its *own* short generated+interpolated clip (the §1.6 "breakdown" idea). Energy then selects *which* pre-baked clip (idle / transition / dance) to be in and where.

**Rough cost:** **~$0.25–$0.50 one-time** (6–12 nano-banana edits) + near-zero interpolation. Cheapest money-wise to reach a first moving result.

**Failure modes:** (1) **On-model drift in the *tweens*** — keys are on-model but RIFE blurs glossy cartoons and ToonCrafter can hallucinate; the fang/horns can smear mid-transition. **This is the exact failure the brief warns about.** (2) No *live* reactivity — you're playing pre-baked clips, so BPM-sync is by playback-rate only, and energy granularity is limited to your clip set. (3) Re-baking for any tweak. Good for a **fast prototype / mood test**, shaky as the production engine.

---

### (Honorable mention) Pipeline D — "Fighting-game floor"

Hand-author (or nano-banana-edit) a handful of **discrete loops** (idle, dance) + **two bespoke transition clips** (idle→dance, dance→idle), state-machine swap on energy threshold. **No true blend**, but bulletproof on-model and trivial. Keep as the **guaranteed-shippable fallback** if A/B rigging stalls.

---

## 4. RECOMMENDATION

**Lead with Pipeline A (code cut-out rig), with Pipeline B (Three.js render-from-one-object) as the upgrade path, and keep D as the floor. Treat C only as a throwaway prototype, never the engine.**

Reasoning:
- **It wins our non-negotiable corner the same way the industry did.** A and B both **generate the character once and animate by transform**, so they **structurally cannot drift off-model** — the thing that keeps burning us is eliminated by construction, not fought frame-by-frame. C and all AI-native approaches re-generate appearance and therefore re-open the drift wound exactly where we can least afford it (mid-transition).
- **It blends the way we asked for, ghost-free.** Blending **bone/keyform parameters** (Spine/Live2D/UbiArt's whole reason to exist) gives a clean idle↔dance ramp driven by a single `energy` float + BPM playback-rate — no pixel crossfade, no ghosting. This is the Mecanim blend-tree concept applied to one rigged art set.
- **It's the cheapest at scale.** ~$0.04–$0.50 of generation *once*, then **$0 forever** and **$0 per state we add later** (new dance, walk, reaction = more authored keyforms, no new gen). C keeps costing per re-bake; image-to-video costs per clip.
- **A before B** because A is pure web code with no modeling/lookdev burden and ships on the dark UI immediately; B is strictly better motion (true depth, correct gloss lighting, real 3D blend) but costs real modeling effort and risks re-introducing drift via auto-meshing — so it's the *earned* upgrade, not the start.
- Our motions are **subtle by design** (breathe/sway/bob), which is precisely the regime where 2.5D cut-out rigs look best and their failure mode (extreme-pose seams/gloss breakage) never triggers.

Concretely, the **smallest first step** is: generate ONE clean canonical gremlin (limbs slightly separated), BiRefNet-matte it, cut ~8 parts, build a PixiJS/`pixi-spine` (or hand-rolled Canvas) bone rig with idle + dance keyforms and an `energy` blend, wire energy/BPM to the audio analyser. No further generation needed to prove the whole loop.

---

## 5. Open questions for the human (decide these to choose A vs B vs hybrid)

**A.** **Cut-out (2D parts, Pipeline A) or true 3D (Pipeline B)?** i.e. do we accept a *subtle puppet* look (cheap, fast, ghost-free, ships now) — or invest in modeling a real 3D gremlin for correct depth + moving gloss highlights (best motion, more effort, risks auto-mesh drift)? The gremlin being "glossy-3D" pulls toward B; "cheap + ship now" pulls toward A.

**B.** **How big is the motion range, really?** If it's *only* idle-breathe + dance-bob + small reactions, a 2D cut-out rig (A) is plenty and B is over-engineering. If we want walk/run/big jumps/turnarounds later, B's single-3D-asset pays off and avoids re-cutting. *What's the 12-month animation roadmap?*

**C.** **Is BPM/energy reactivity LIVE (runtime-reactive to the actual track) or PRE-BAKED?** Live ⇒ we need a real runtime rig (A or B), because pre-rendered clips can't blend continuously to arbitrary energy. Pre-baked-clips-are-fine ⇒ Pipeline C or D become viable and cheaper to start. This single answer eliminates half the option space.

*(Secondary: do we want to spend ~30 min testing ToonCrafter locally on two gremlin key poses to see if its inbetweens stay on-model? It's free on MPS and would de-risk/kill Pipeline C empirically rather than by argument.)*

---

## Sources (web-verified)

- Dead Cells 3D→2D sprite pipeline — [GameDeveloper: Art Design Deep Dive](https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-), [Game Anim 2018](https://www.gameanim.com/2018/01/31/dead-cells-3d-pipeline-2d-animation/)
- Spine (skeletal, mesh deform, blend/layer) — [esotericsoftware.com](https://esotericsoftware.com/), [Spine In Depth](http://en.esotericsoftware.com/spine-in-depth), [spine-runtimes](https://github.com/esotericsoftware/spine-runtimes)
- Hollow Knight is frame-by-frame PNG, NOT Spine — [Team Cherry: Inside the Mind of a Bug](https://www.teamcherry.com.au/blog/inside-the-mind-of-a-bug-unity-and-playmaker), [Made with Unity: Hollow Knight](https://unity.com/made-with-unity/hollow-knight)
- Unity Mecanim state machines & blend trees — [Unity Manual: Animation State Machines](https://docs.unity3d.com/6000.3/Documentation/Manual/AnimationStateMachines.html), [Unity Manual: Blend Trees](https://docs.unity3d.com/Manual/class-BlendTree.html)
- Live2D Cubism deformers / keyform interpolation — [Live2D: About Deformers](https://docs.live2d.com/en/cubism-editor-manual/deformer/), [Warp Deformer](https://docs.live2d.com/en/cubism-editor-manual/making-and-placement-of-warp-deformer/)
- UbiArt Framework / GenAnim (Rayman Origins, Ancel) — [Wikipedia: UbiArt Framework](https://en.wikipedia.org/wiki/UbiArt_Framework), [GameDeveloper: Ancel open-sourcing UbiArt](https://www.gamedeveloper.com/business/ubisoft-s-ancel-planning-to-open-up-i-rayman-origins-i-tech)
- Fighting-game instant-state-swap design / anticipation-action-recovery — [Rivals Workshop: Anticipation, Action, Recovery](https://www.rivalslib.com/workshop_guide/art/anticipation_action_recovery.html), [Rantala HD-2D-character thesis](https://www.theseus.fi/bitstream/handle/10024/59254/Rantala_Tuula.pdf)
- Richard Williams pose-to-pose / breakdowns — [The Animator's Survival Kit (Internet Archive)](https://archive.org/details/TheAnimatorsSurvivalKitRichardWilliams)
- RIFE / FILM interpolation + cartoon artifacts — [RIFE vs FILM comparison](https://apatero.com/blog/rife-vs-film-video-frame-interpolation-comparison-2025), [Cartoon line inbetweening (arXiv)](https://arxiv.org/html/2309.16643)
- ToonCrafter generative cartoon interpolation — [ToonCrafter project page](https://doubiiu.github.io/projects/ToonCrafter/), [arXiv 2405.17933](https://arxiv.org/html/2405.17933v1), [GitHub Doubiiu/ToonCrafter](https://github.com/Doubiiu/ToonCrafter)
- AI pose-driven consistency limits — [AnimateDiff+ControlNet consistency](https://oboe.com/learn/generative-video-character-consistency-with-comfyui-1yy44sc/animatediff-and-controlnet-o3k5zc), [Animate Anyone (arXiv 2311.17117)](https://arxiv.org/html/2311.17117v2)
- fal models/pricing (live-pulled, not memory): `fal-ai/gemini-25-flash-image/edit` (nano-banana) ≈ **$0.0398/img**; `fal-ai/nano-banana-pro/edit` ≈ **$0.15/img**; `fal-ai/film/video` ≈ **$0.0013/sec**; `fal-ai/amt-interpolation`, `fal-ai/pika/v2.2/pikaframes`, `fal-ai/ltx23-trainer-v2/interpolate` available for keyframe interpolation.
