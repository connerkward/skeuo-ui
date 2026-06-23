# skeuo.fm mascot — TRANSITION / BLENDING mechanics research

*Deep dive into HOW smooth transitions between 2D animation states actually work — the transition layer only, not the asset-pipeline survey (that's in [`anim-pipeline-ideation.md`](file:///tmp/cdtex/anim-pipeline-ideation.md)). Goal: a concrete transition architecture for one on-model mascot that ramps idle ↔ dance, driven continuously by a music `energy`/BPM signal, in the browser. All named techniques/people/talks web-verified; sources at bottom. No assertions from memory on vendor specifics.*

**The case, restated for this layer:** one rig (the cut-out / 2.5D gremlin from the prior brief), two principal states (idle, dance), a continuous control parameter `energy ∈ [0,1]` derived from the audio, plus BPM. We must (a) ramp between idle and dance with no hard cut and **no ghosting**, (b) react continuously to `energy`, (c) land the dance **on the beat**. Everything below is judged against that.

---

## TL;DR recommendation (3 sentences)

Drive the rig with a **single `energy` blend parameter** that does a **weighted pose blend** (a 1D blend tree, Spine/Live2D-style) between an idle keyform set and a dance keyform set — because we blend **bone/parameter transforms, not pixels, this is ghost-free by construction** — and layer a small **additive** "bounce/head-bob" track scaled by `energy` on top. Smooth the raw audio `energy` with a **critically-damped spring** (the same `1 - e^(-dt/τ)` envelope we already use for the CD spin) so it never jitters, and drive the dance clip's **phase from a beat clock** (BPM → phase advance, snapped at each detected beat) so the bounce lands on-beat instead of free-running. Use **inertialization** (Bollo / Gears of War 4) only for the *discrete, interruptible* events (idle→reaction→idle), not for the continuous idle↔dance ramp — for a continuous param the blend-tree weight already does the job and inertialization adds machinery we don't need; crossfade-of-clips and authored transition clips are the fallbacks, not the spine.

---

## 1. Crossfade / dissolve between clips

**What it is.** Play out animation A while fading in animation B over a fixed *mix duration*; weight goes A=1→0, B=0→1. The canonical 2D-rig implementation is **Spine's `AnimationStateData`**: `setDefaultMix(0.1)` or per-pair `setMix("walk","jump",0.2)`, overridable per-playback via `TrackEntry.mixDuration`. When `AnimationState` changes the current animation it *"will automatically mix (crossfade) between the animations using the mix durations… resulting in smooth animation transitions"* ([Spine docs](http://esotericsoftware.com/spine-applying-animations)).

**Why it ghosts for sprites but not for skeletal.** This is the load-bearing distinction. A crossfade is just `out = (1-w)·A + w·B`. If A and B are **pixel rasters**, that average is a literal *double-exposure* — both drawings visible at once at w=0.5 → the "ghost." If A and B are **bone transforms** (a rotation angle, a translation, a Live2D parameter value), the average is `angle = (1-w)·angleA + w·angleB` — a single, well-defined intermediate pose, *one* coherent drawing, no double image. Spine's `alpha` parameter (0 = setup pose, 1 = animation pose) blends *into the pose*, not into the framebuffer. **This is the entire reason a rigged character can do what a sprite sheet cannot.**

**Where it breaks even for skeletal.** Crossfade is a *blind average of two poses on the same timeline phase*. If A and B are **dissimilar** (idle arms-down vs dance arms-up) the midpoint can be a nonsense in-between (arms sticking straight out, foot through the floor) — the classic "blend two un-alike poses → garbage" failure. It also has no notion of *velocity*: it ignores how fast the source was moving, so an interrupt mid-motion can produce a velocity discontinuity (a visible "pop" in speed even if the pose is continuous). And during the mix you must evaluate **both** clips (2× cost) — relevant at scale, not for our one rig.

**Applicability to us.** Usable but not ideal as the *primary* idle↔dance mechanism: idle and dance poses are deliberately *dissimilar*, which is exactly crossfade's weak spot, and a crossfade gives a fixed-duration A→B *event*, not a *continuous* response to `energy`. Good for **discrete** transitions (e.g. snap to a reaction pose). For the continuous ramp, a blend tree (§2) is the better framing of the same math.

## 2. Animation blend trees / 1D & 2D blend spaces (Unity Mecanim, Unreal)

**What it is.** A float parameter selects a *weighted blend* of several clips placed at thresholds along an axis. Unity: *"1D Blend Trees use one float parameter… the proximity of [its] value to the Motion Thresholds determines the weight of each Animation Clip… The blending… is handled using linear interpolation"* ([Unity 1D Blending](https://docs.unity3d.com/Manual/BlendTree-1DBlending.html), [Blend Trees](https://docs.unity3d.com/Manual/class-BlendTree.html)). 2D blend spaces blend on two params (e.g. move X/Y) — Simple Directional, Freeform Directional, Freeform Cartesian variants ([Unity 2D Blending](https://docs.unity3d.com/Manual/BlendTree-2DBlending.html)).

**How our `energy` maps.** Directly: a **1D blend tree on `energy`** with `idle` clip at threshold 0 and `dance` clip at threshold 1. At `energy=0.3` the runtime emits a pose that is 70% idle / 30% dance — a genuine in-between "swaying a little, starting to move," not idle-with-dance-faded-over-it. This is the cleanest framing of "continuous music-reactive ramp." If later we want low-energy-sway vs high-energy-bounce vs a different groove, add thresholds (0 idle, 0.5 groove, 1 full-dance) or go 2D (`energy` × `mood`).

**The "blend similar poses only" rule.** Blend trees only look good when the clips being blended are **structurally similar and phase-aligned** — walk↔run works because both are 2-beat locomotion cycles with feet in roughly the same place; the engine even *time-scales* them to a common normalized phase so the feet don't slip. Idle and dance are *not* naturally phase-aligned (idle is a slow breathe, dance is a fast bounce). **Implication for us:** either (a) author idle and dance to share a compatible base pose / phase so the 0.3-blend reads cleanly, or (b) don't blend their *full bodies* — keep the body on idle and put the dance energy in an **additive layer** (§4). (b) is more robust and is what the recommendation uses.

**Applicability.** This is the conceptual spine of the whole design. The risk is purely the similarity rule; we mitigate it with additive layering rather than fighting it with a full-body blend.

## 3. Transition / linking clips (the fighting-game + Spine way)

**What it is.** Instead of *computing* the in-between, an animator *authors* a bespoke bridge clip: idle→dance "getting into it" (rocks back, then launches into the bounce) and dance→idle "settling" (a couple of decaying bobs, then rest). Fighting games live on this: each state has hand-drawn anticipation/recovery frames *baked into the clip* so the bridge is a designed motion, not an average. Richard Williams' "breakdown" pose is the same idea — *the transition is authored, not averaged.*

**When authored transitions beat blending.** When the start and end poses are **far apart** or the transition has **character** that an average can't express. A computed crossfade idle→dance just smears between two static-ish poses; an *authored* "getting into it" can have a wind-up, a weight shift, an accent — personality. Cost: it's hand-work per transition pair, and it's a *discrete* A→B event, so it doesn't natively give continuous `energy` granularity (you trigger it at a threshold).

**Applicability to us.** High value as a **garnish on top of the blend**, low value as the *engine*. The honest sweet spot: let the blend tree (§2) + additive (§4) carry the *continuous* ramp, but trigger a short **authored "getting into it" accent** when `energy` crosses a threshold upward (and a "settling" accent on the way down), played as an additive one-shot on a higher track. That buys the fighting-game personality without giving up continuous reactivity. This is also the **guaranteed-shippable floor**: if rig-blending stalls, two authored loops + two authored transition clips + a state machine always works (Pipeline D in the prior brief).

## 4. Additive / layered animation

**What it is.** A *delta* clip applied on top of a base. Unity computes the additive clip as *"the difference between the first frame in the animation clip and the current frame, then applies this difference on top of all other playing animations"* — the first frame (or a `SetAdditiveReferencePose`) is the reference that gets subtracted out, leaving only the *motion relative to rest* ([Unity Animation Layers](https://docs.unity3d.com/Manual/AnimationLayers.html), [SetAdditiveReferencePose](https://docs.unity3d.com/ScriptReference/AnimationUtility.SetAdditiveReferencePose.html)). Spine does the equivalent with **tracks**: higher-numbered tracks apply on top of lower ones, and a track's `alpha` scales its contribution — *"blend tracks by adjusting a higher track's alpha… progressive limping as damage increases"* ([Spine docs](http://esotericsoftware.com/spine-applying-animations)). Arc System Works / ozz-animation use the same additive-delta model.

**Why additive composes without ghosting.** Because it adds **deltas of transforms**, not blended absolute poses or pixels. `pose = base_pose + alpha·(additive_delta)`. The base stays fully intact and readable; the additive only *nudges*. There's no averaging of two competing full poses, so there's no "which state am I in" ambiguity and no double-image. Scaling `alpha` from 0→1 smoothly dials the nudge in.

**Applicability to us — this is the key insight for the continuous ramp.** Keep the **body on the idle loop always** (so it's never a half-broken blend), and put the dance as an **additive "energy" layer**: a bounce on the root, a head-bob on the neck, a cap-tilt, scaled by `alpha = energy`. At `energy=0` it's pure idle; at `energy=1` it's idle + full bounce = the dance; in between it's a continuous, always-coherent groove. No dissimilar-pose blend problem (§2's rule sidestepped), no ghost (it's transform deltas), and `energy` maps to `alpha` with zero ambiguity. This is more robust than a full-body idle↔dance blend tree for our exact "subtle, on-model, music-reactive" regime.

## 5. Inertial blending / inertialization (Bollo, GDC 2018)

**What it is.** David Bollo (The Coalition / Microsoft), **"Inertialization: High-Performance Animation Transitions in *Gears of War* [4]," GDC 2018** ([GDC Vault](https://www.gdcvault.com/play/1025331/Inertialization-High-Performance-Animation-Transitions), [PDF](https://media.gdcvault.com/gdc2018/presentations/bollo_david_inertialization_high_performance.pdf), [Game Anim writeup](https://www.gameanim.com/2019/11/02/high-performance-animation-in-gears-of-war-4/)). Instead of crossfading two clips, you **snapshot the difference (offset) between the source pose and the target clip at the instant of transition**, then **decay that offset to zero over a short blend time using a curve** — applied as a *post-process on top of the target clip*. Verified mechanics ([Unreal/inertialization writeup](https://banming.github.io/GameEngine/Unreal/animation/Inertialization.html)):

- Curve is a **quintic polynomial** `P(t) = A·t⁵ + B·t⁴ + C·t³ + D·t² + v₀·t + x₀`.
- `CalcInertial(x0, v0, t, t1)`: `x0` = pose offset magnitude at transition start, `v0` = how fast that offset was changing (captured **velocity/momentum** from the outgoing motion), `t` = elapsed, `t1` = blend duration.
- Boundary conditions at `t = t1`: **offset, velocity, AND acceleration all reach zero** → C2-continuous landing, no pop.
- **Only the target animation is evaluated during the transition** (*"In the transition period only the target state is evaluated"*) — the source is gone; you just decay its remembered offset. That's why it's **~half the cost of a crossfade** (which evaluates both clips) and the cost is fixed regardless of how many transitions chain.

**Why it's smoother + handles arbitrary interrupts.** It carries **velocity** across the cut, so interrupting mid-motion doesn't pop the speed (crossfade ignores velocity). And because the "offset" is just *current-pose minus target* re-snapshotted whenever a transition fires, you can interrupt a transition with another transition at any frame and it stays continuous — ideal for fast, unpredictable state changes (dodge→hit→idle).

**Applicability to us.** **Worth it only for the discrete events, not the continuous ramp.** Our idle↔dance is a *continuous parameter*, and a blend-tree weight / additive alpha already gives smooth continuous response with far less machinery — inertialization solves the *discrete-cut-with-momentum* problem we don't principally have. Where it *does* earn its place: **reaction one-shots** (eye-pop, fang-grin, a beat-drop hit) that fire at unpredictable times and must return to whatever the body is doing without a pop — inertializing those returns is cleaner than crossfading them. Verdict: implement the continuous ramp without it; keep it in pocket for interruptible reaction events if/when we add them.

## 6. Pose/parameter interpolation in the 2D-rig stacks (the closest analog)

**Live2D Cubism** — the VTuber standard, and the **closest analog to our music signal**. You author **keyforms** at parameter extremes (e.g. `ParamAngleX` at −30/0/+30, `ParamMouthOpen` 0→1) and *"the shape is automatically interpolated between the keys"* ([About Parameters](https://docs.live2d.com/en/cubism-editor-manual/parameter/), [Keyforms](https://docs.live2d.com/en/cubism-editor-manual/keyform-xydirection/)). At runtime a **continuous live signal** (face tracking: head angle, mouth, blink) drives those parameters and the mesh deforms smoothly between keyforms. The standard VTuber param set is `Head X/Y, Body X/Y, Mouth Open, Mouth Form, Eye Blink L/R` ([viverse guide](https://news.viverse.com/post/rig-2d-vtuber-model-live2d-cubism)). **This is exactly our situation with the signal swapped:** instead of face-tracking → params, it's **music energy/BPM → params** (`energy` → bounce amount, beat-phase → bob phase). VTuber rigs already prove a continuous noisy live signal can drive a 2D rig smoothly — *the smoothing they apply to jittery tracking data is the same smoothing we need on jittery audio energy* (§7).

**Spine** — `AnimationState` with **tracks** (layering) + **mixDuration** (crossfade) + `alpha` (blend depth), covered in §1/§4. Blends bone transforms; ghost-free. `pixi-spine` runs it in the browser.

**DragonBones** — open-source bone+mesh equivalent, same interpolate-transforms model, web runtime. Functionally interchangeable with Spine for our purposes; free.

**Takeaway:** all three blend **interpolated parameters/transforms**, which is *why* they're smooth and ghost-free, and Live2D's "continuous live signal → driven parameters" is the precise pattern to copy — our `energy`/beat-phase are just two more driven parameters.

## 7. Easing / timing of the transition itself

This is the layer that decides whether it *feels* right, and it's where our existing CD-spin envelope already lives.

**Smoothing the `energy` param (critically-damped spring).** Raw audio energy is jittery; feeding it straight to the rig makes the mascot twitch. Smooth it toward the target with a **critically-damped spring** (damping ratio ζ=1 — *"reaches equilibrium as fast as possible without oscillating"*, [RyanJuckett](https://www.ryanjuckett.com/damped-springs/), [keijiro/SmoothingTest](https://github.com/keijiro/SmoothingTest)). The cheap, robust form is the exponential envelope we already use:

```
energy += (energy_target - energy) * (1 - exp(-dt / tau));   // tau ≈ 0.15–0.30 s
```

For a springier, velocity-aware response (slight follow-through), use the full 2nd-order critically-damped update (semi-implicit, stable):
```
// ω = 2/tau  (so half-life ≈ 0.35·tau); ζ = 1
energy_vel += (-2*ω*energy_vel - ω*ω*(energy - energy_target)) * dt;
energy     += energy_vel * dt;
```
The first (1st-order) is plenty for a single 0→1 knob and matches the existing CD-spin code; reach for the 2nd-order only if you want the mascot to overshoot-settle into a groove.

**BPM → playback rate.** Map detected BPM to the dance clip's speed so the bounce period equals the beat period: `clipRate = (BPM / 60) / clipLoopsPerSecondAtRate1`. Simpler and more robust: don't scale a clip's rate at all — **drive the dance phase directly from a beat clock** (below), which is inherently tempo-correct.

**Beat-phase alignment (land the dance on the beat).** Free-running the dance loop will drift off the music. Instead, maintain a **beat phase** `φ ∈ [0,1)` advanced by tempo and *re-synced on each detected beat*:
```
phi += (BPM/60) * dt;            // advance by beats-per-second
phi -= floor(phi);               // wrap
// on a detected beat (onset): gently pull phi toward 0 (don't hard-snap → pop)
if (beatDetected) phi += (0 - phi) * 0.25;   // or phase-lock via a PLL
```
Then the bounce uses `bob = sin(2π·φ) * energy` so the **down-beat of the bounce coincides with the musical beat**. A hard snap on every beat pops; a partial pull (or a phase-locked loop) corrects drift smoothly. Use easing inside a single bounce (e.g. a fast-down/slow-up ease, not a pure sine) for a more "weighted" dance feel.

**Easing of the ramp itself.** The `energy` smoothing *is* the ramp easing — no separate tween needed. If a discrete transition clip is triggered (§3), ease its alpha in/out with a standard cubic (`easeInOutCubic`) over its mixDuration.

## 8. Motion matching / pose matching (brief — overkill)

**What it is.** No state machine or blend tree; every frame (or every few), build a *query feature vector* (current pose + desired trajectory) and search a **large motion-capture database** for the best-matching frame, then jump there and play forward. First shipped in **Ubisoft's *For Honor*** (Simon Clavet, GDC 2016: [Game Anim](https://www.gameanim.com/2016/05/03/motion-matching-ubisofts-honor/), [GDC Vault](https://gdcvault.com/play/1023280/Motion-Matching-and-The-Road)); later *Last of Us 2*; *Learned Motion Matching* (Daniel Holden, Ubisoft La Forge) compresses the DB with a neural net.

**Why it's overkill for us.** It exists to animate **rich locomotion over arbitrary trajectories from a huge mocap corpus** without hand-authoring transitions — its whole value is *"no need to structure clips in graphs… or explicitly create transitions."* We have **two states, one rig, a single 1D control param, and zero mocap.** There's no trajectory to match, no database to search, and the cost (a feature DB + per-frame nearest-neighbour search + a lot of source animation) buys us nothing a 1D blend + additive layer doesn't already give. Mentioned for completeness; do not build.

---

## Comparison table

| Technique | How it achieves smoothness | Ghost-free? | Continuous-param native? | Carries velocity / interrupt-safe | Cost / effort | Fit for skeuo idle↔dance |
|---|---|---|---|---|---|---|
| **Crossfade clips** (Spine `mixDuration`) | avg of two poses over mix time | ✅ for skeletal (avg transforms); ❌ for raw sprites | ✖ (fixed A→B event) | ✖ ignores velocity | low; 2× eval during mix | **Secondary** — fine for discrete cuts, weak for dissimilar idle/dance |
| **Blend tree 1D/2D** (Mecanim) | float-weighted interp of clips | ✅ (interp transforms) | ✅✅ native | ✖ | low | **Core framing** — but obey "blend similar poses only" |
| **Authored transition clip** (fighting-game / Williams breakdown) | a *designed* bridge, not an average | ✅ | ✖ (triggered event) | n/a | hand-work per pair | **Garnish + floor** — accent on threshold cross; bulletproof fallback |
| **Additive / layered** (Mecanim layers, Spine tracks, ozz) | adds transform *deltas* on a base | ✅✅ (no full-pose averaging) | ✅✅ (`alpha = energy`) | ✖ | low | **★ Primary mechanism** for the energy ramp |
| **Inertialization** (Bollo GDC18) | decay pose-offset via quintic, target-only eval | ✅ + velocity-continuous | ✖ (discrete cut, made smooth) | ✅✅ best-in-class | low runtime, some impl | **Reactions only** — overkill for the continuous ramp |
| **Live2D / Spine param interp** | interpolate driven *parameters/keyforms* | ✅✅ | ✅✅ (driven by live signal) | ✖ | rig authoring | **★ The model to copy** (face-track → swap for music signal) |
| **Spring / exp smoothing** (RyanJuckett) | `1-e^(-dt/τ)` envelope on the param | n/a (it's the input) | ✅✅ | ✅ (2nd-order) | trivial | **★ Required** on `energy`; we already use it for CD spin |
| **Motion matching** (For Honor) | per-frame DB nearest-neighbour | ✅ | ✖ | ✅ | very high | **Do not build** — needs mocap corpus + trajectory we don't have |

---

## RECOMMENDED TRANSITION ARCHITECTURE

**One sentence:** body stays on the idle loop forever; a music-driven **additive groove layer** (bounce + head-bob + cap-tilt) is scaled by a **spring-smoothed `energy`** and **phase-locked to a beat clock**, with optional **authored "getting-into-it / settling" accents** at the energy thresholds, and **inertialization reserved for unpredictable reaction one-shots**.

### What we blend (and what we deliberately don't)
- **Base track (always 100%):** the idle loop. Never blended away → never a half-broken dissimilar-pose average → the §2 "blend similar poses only" trap is sidestepped entirely.
- **Additive groove track:** delta of (dance pose − idle/rest reference), applied on top with `alpha = energy_smoothed`. At energy 0 → invisible; at 1 → full dance. This is the continuous ramp, ghost-free because it's transform deltas (§4).
- **Accent track (optional, one-shot):** authored "getting into it" on rising threshold, "settling" on falling — additive on a higher track, eased in/out (§3).
- **Reaction track (future):** eye-pop / fang-grin / beat-drop hits, triggered at unpredictable times, returned to base via **inertialization** so they don't pop (§5).

### The update loop (pseudocode)
```js
// --- per-frame, dt seconds ---

// 1) RAW audio → energy target  (audio analyser: RMS/flux in a musical band, normalised)
const energyTarget = clamp01(analyser.energy01());     // 0..1
const bpm          = analyser.bpm();                    // smoothed tempo estimate
const beatNow      = analyser.beatJustFired();          // onset/beat detector → bool

// 2) SMOOTH energy — critically-damped spring (same family as the CD-spin envelope)
const TAU = 0.22;                                       // s; lower = snappier, higher = floatier
energy += (energyTarget - energy) * (1 - Math.exp(-dt / TAU));

// 3) BEAT CLOCK — phase advances by tempo, gently pulled to beat on each onset (no hard snap)
phi += (bpm / 60) * dt;                                 // beats elapsed this frame
phi -= Math.floor(phi);                                 // wrap to [0,1)
if (beatNow) phi += (0 - phi) * 0.25;                   // soft phase-lock (or a proper PLL)

// 4) GROOVE = additive deltas, scaled by energy, phased by the beat
const bob   = easedBounce(phi);                         // 0..1, fast-down/slow-up (not pure sin)
rig.add('root.y',   amp.bounce  * energy * bob);        // body bounce, on-beat
rig.add('neck.rot', amp.headbob * energy * Math.sin(TAU2 * phi));
rig.add('cap.rot',  amp.captilt * energy * Math.sin(TAU2 * phi + 0.5));
// 'rig.add' = additive transform delta on top of the base idle pose for this frame

// 5) ACCENTS (optional) — authored one-shots at threshold crossings
if (rose(energy, 0.55))  accents.play('getting_into_it');  // additive, eased
if (fell(energy, 0.35))  accents.play('settling');

// 6) (future) REACTIONS — inertialized return so they never pop
//    on trigger: snapshot (currentPose - reactionClip) offset+velocity,
//    decay to 0 over ~0.2s via the quintic CalcInertial(x0,v0,t,t1).

rig.apply();   // base idle  +  Σ additive deltas  → one coherent pose, drawn once
```

### Why this is ghost-free, on-model, and on-beat
- **Ghost-free:** every contribution is a **transform/parameter delta on a single rig** (§4/§6). We never average two pixel rasters and never average two *dissimilar full poses*. The frame is always one coherent drawing.
- **On-model:** one rig from one canonical generation (prior brief). Nothing is re-generated per frame, so it cannot drift.
- **Continuous & smooth:** `energy` is spring-smoothed (§7), and it maps to a single `alpha` — no jitter, no pop, no discrete steps the eye can catch.
- **On-beat:** the bounce phase is driven by a **beat clock** that's softly phase-locked to detected beats, so the down-beat of the bounce coincides with the music; `easedBounce` gives it weight instead of a limp sine.

### Why NOT the alternatives as the spine
- **Full-body idle↔dance blend tree:** would hit the dissimilar-pose trap (§2); additive sidesteps it.
- **Crossfade of two clips:** fixed-duration event, not continuous; ignores velocity (§1).
- **Inertialization as the ramp:** solves discrete-cut-with-momentum, which the continuous param doesn't need; kept for reactions (§5).
- **Motion matching:** no corpus, no trajectory, pure overkill (§8).

---

## Open decisions for the human (2–3 that need a call)

**A. Full-body blend vs additive-only for the ramp.** Recommendation is **additive groove on a permanent idle base** (robust, sidesteps the dissimilar-pose problem). The alternative — a true 1D blend tree idle↔dance — gives a more *total* transformation at full energy (the whole body re-poses, not just a bounce added) but requires authoring idle and dance to be blend-compatible. **Decide:** is "idle + escalating bounce/bob" enough dance, or do you want the body to fundamentally re-pose at high energy (arms up, different stance)? If the latter, we author a blend-compatible dance and use §2 *in addition to* the additive layer.

**B. Beat sync source & strictness.** Should the dance be **strictly locked to a live beat detector** (best musicality, but onset detection in-browser is noisy and a bad detection can lurch the mascot), or run on a **smoothed BPM clock with only gentle correction** (steadier, slightly looser to the actual transients)? Recommendation leans gentle-correction (the `phi += (0-phi)*0.25` soft pull) for robustness; a true PLL is more work. **Decide:** how tight to the transients vs how forgiving of detector errors.

**C. Do we need reactions / inertialization at all in v1?** The continuous ramp needs none of §5. Reactions (eye-pop on a drop, fang-grin) are a *later* polish layer and are the only thing that justifies building the inertialization path. **Decide:** ship v1 as idle+groove only (no inertialization code), or scope reactions in now?

*(Secondary, not blocking: `TAU` for the energy spring and the soft-lock gain `0.25` are feel parameters — best dialed by eye in a lookdev slider studio against a real track, not guessed. A tiny slider demo would settle both in minutes.)*

---

## Sources (web-verified)

- **Inertialization — David Bollo, GDC 2018** — [GDC Vault: Inertialization](https://www.gdcvault.com/play/1025331/Inertialization-High-Performance-Animation-Transitions) · [slides PDF](https://media.gdcvault.com/gdc2018/presentations/bollo_david_inertialization_high_performance.pdf) · [Game Anim writeup](https://www.gameanim.com/2019/11/02/high-performance-animation-in-gears-of-war-4/) · [quintic/CalcInertial mechanics](https://banming.github.io/GameEngine/Unreal/animation/Inertialization.html)
- **Spine mixing / tracks / mixDuration / alpha** — [Applying Animations](http://esotericsoftware.com/spine-applying-animations) · [AnimationStateData](https://nadako.github.io/hxspine/spine/AnimationStateData.html)
- **Unity Mecanim blend trees** — [1D Blending](https://docs.unity3d.com/Manual/BlendTree-1DBlending.html) · [2D Blending](https://docs.unity3d.com/Manual/BlendTree-2DBlending.html) · [Blend Trees](https://docs.unity3d.com/Manual/class-BlendTree.html)
- **Additive / layered animation** — [Unity Animation Layers](https://docs.unity3d.com/Manual/AnimationLayers.html) · [SetAdditiveReferencePose](https://docs.unity3d.com/ScriptReference/AnimationUtility.SetAdditiveReferencePose.html) · [ozz-animation additive blending](https://guillaumeblanc.github.io/ozz-animation/samples/additive/)
- **Live2D Cubism parameters / keyform interpolation** — [About Parameters](https://docs.live2d.com/en/cubism-editor-manual/parameter/) · [Keyforms](https://docs.live2d.com/en/cubism-editor-manual/keyform-xydirection/) · [VTuber rig param set](https://news.viverse.com/post/rig-2d-vtuber-model-live2d-cubism)
- **Critically-damped spring / exponential smoothing** — [RyanJuckett: Damped Springs](https://www.ryanjuckett.com/damped-springs/) · [keijiro/SmoothingTest](https://github.com/keijiro/SmoothingTest) · [Math Proofs: Critically Damped Spring Smoothing](http://mathproofs.blogspot.com/2013/07/critically-damped-spring-smoothing.html)
- **Motion matching** — [Game Anim: Motion Matching in For Honor](https://www.gameanim.com/2016/05/03/motion-matching-ubisofts-honor/) · [GDC Vault: Motion Matching & the Road to Next-Gen](https://gdcvault.com/play/1023280/Motion-Matching-and-The-Road) · [Learned Motion Matching (Holden, Ubisoft La Forge)](https://theorangeduck.com/media/uploads/other_stuff/Learned_Motion_Matching.pdf)
</content>
</invoke>
