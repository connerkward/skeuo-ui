---
name: "motion-preference-rule"
id: "motion-pref-01"
description: "In personal/local projects, ignore OS-level reduced-motion (prefers-reduced-motion) and ship animations at full intended behavior; honor it for public/multi-user projects."
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

# Motion preference — ignore OS-level reduced-motion in personal projects

Do not honor `prefers-reduced-motion: reduce` (the CSS media query) or any
equivalent OS-level "Reduce Motion" flag in personal/local projects. Ship
animations at their full intended behavior.

**Why:** the user's OS-level Reduce Motion is set for system chrome reasons,
not as a directive about every app's UI. Auto-suppressing animations
silently hides the polish that was the point of writing them — and produces
the "I see no difference" failure mode (see Muser 2026-06-03 session: card
entrance was invisible until the `@media (prefers-reduced-motion: reduce)`
override got stripped). Cosmetic motion ≤300 ms with no parallax / no large
3D rotation / no rapid color flash is below the WCAG-vestibular threshold
that the flag exists to protect against, so honoring it for that motion is
over-cautious.

**How to apply:** when authoring CSS animations in personal-project front-ends:

- Don't add `@media (prefers-reduced-motion: reduce) { ... }` blocks.
- If existing code has them, remove them (they're silently suppressing the
  designed behavior on the user's machine).
- This rule covers macOS *AppleReduceMotion*, iOS *Reduce Motion*, Windows
  *Show animations*, Android *Animator duration scale*, and any browser
  setting that maps to the `prefers-reduced-motion: reduce` media query.

**Exception — public-facing or multi-user projects:** if the codebase is or
will be used by people other than the author (a shipped product, an OSS
library, an internal tool with multiple users), the WCAG trade-off applies
normally: honor `prefers-reduced-motion: reduce`, and either disable
animations or replace them with opacity-only fades. The shortcut here is
"personal tool, my OS, my call" — it doesn't generalize.

**Still avoid regardless of preference:** parallax scrolling, large
viewport-spanning transforms (3D rotations, big scales), strobing/flashing
≥3 Hz, infinite spinning above 1 Hz outside loading indicators. These can
trigger vestibular reactions independent of the flag and don't fit
Cosmos-aligned restraint anyway.
