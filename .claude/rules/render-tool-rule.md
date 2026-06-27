---
name: "render-tool-rule"
id: "render-tool-01"
description: "For 3D visualization/lookdev/preview renders, default to web/WebGL (Three.js); treat Blender as opt-in, only when the browser genuinely can't do it and after confirming."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# 3D rendering — prefer web/WebGL, treat Blender as opt-in

When a task needs 3D visualization, lookdev, a beauty/preview render, a turntable, or a
viewer, **default to web-based rendering (Three.js / WebGL in the browser)**. Do NOT reach
for Blender (or any heavy DCC) as the default, even when a Blender MCP is connected.

**Why:** web 3D has no app dependency, runs headless and scriptable (Playwright can drive
and screenshot it), iterates in seconds, and is the stack the user actually builds in
(the `lookdev` studios are Three.js). Blender adds a launch step, a connection dependency,
and a context switch the user has repeatedly declined.

**How to apply:**
- Real geometry rendered *well* in Three.js beats an AI image model's reinterpretation of a
  screenshot (which reads as fake) and beats spinning up Blender. Push the web renderer:
  `ACESFilmicToneMapping`, image-based lighting (`PMREMGenerator` + `RoomEnvironment` or an
  HDRI), PBR materials with `envMapIntensity`, a `SpotLight` with penumbra/shadows for raking
  light, a dark backdrop, optional grain/vignette/bloom post. That ceiling is high enough for
  most presentation shots.
- For a real backdrop, composite the web render onto a real photo rather than launching Blender.

**Reach for Blender ONLY when** the user explicitly asks for it, OR the task genuinely needs
something the browser can't do — offline path-traced photoreal output at print quality, heavy
physics/cloth/fluid sim, sculpting, or large mesh/boolean operations — **and even then, confirm
first.** Don't infer Blender from "make it look real"; make the web render look real instead.

Related: [[web-dev-rule]] (web isolation), [[browser-tool-routing-rule]] (which browser tool).
