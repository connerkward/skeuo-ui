---
name: verify-app-setting
description: Verify a GUI setting's exact location before telling the user where to click. Use WHENEVER your response is about to contain a directive like "go to Preferences → …", "open Settings and toggle …", "it's under the X menu", "click the Y tab" — for ANY app (Resolve, Figma, Blender, Chrome, macOS System Settings, an IDE, a web app). Memory of app UIs is stale and version-drifted; confirm the path via web search for the user's specific version, and check edition/plan gating, before sending.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# verify-app-setting — confirm GUI paths before sending them

The GUI-navigation corollary of `verify-outputs-rule`: don't claim a location you haven't
confirmed against the real artifact (here, the app's actual version). A wrong "go to
X → Y → Z" wastes the user's time hunting for something that isn't there.

## The trigger

Any directive that sends the user clicking through a UI — "go to Preferences → …",
"open Settings and toggle …", "it's under the X menu", "click the Y tab" — for any app
with a UI.

This fired on a concrete failure (2026-06-13, DaVinci Resolve): the agent recited
"Preferences → System → General → External scripting using" from memory. The user replied
"i dont see that." The path was roughly right but unverified, and the agent hadn't checked
(a) the exact wording/tab for the user's version nor (b) that the option is **edition-gated**
(Studio-only) — so the user couldn't have found it regardless.

## What "verified" requires

1. **Know the version first.** Determine the exact app version/edition before searching
   (from disk: `defaults read <app>/Contents/Info.plist CFBundleShortVersionString`,
   `--version`, package metadata, the About box, or ask). UI paths differ across major
   versions; don't search generically.
2. **Web-search the path for that version.** Confirm the exact menu/tab/section names and
   nesting. Prefer official docs or version-dated sources; treat a path from a different
   major version as unconfirmed.
3. **Check edition / platform / plan gating.** Many settings exist only in a paid tier
   (Studio vs free), an OS variant, a feature flag, or an admin role. If the option is
   gated and the user's build doesn't qualify, say so — "this is Studio-only, you won't
   see it in the free version" — instead of sending them hunting for something that can't
   appear.
4. **State the version you verified against.** "In Resolve 20.x: …" so a mismatch is visible.

## Don'ts

- No settings path from training-data memory without a search.
- No generic path that ignores the user's version when versions differ.
- Don't omit edition/plan gating when the option is gated — "not seeing it" is often
  *because* it's gated, not because they looked wrong.
- Don't send the user clicking before you've confirmed; one verified instruction beats
  three guesses.

## The one-line test

"Did I confirm this exact path for the user's specific app version via search, and check
whether their edition even exposes it?" If no — search first.
