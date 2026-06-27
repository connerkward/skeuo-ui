---
name: "restraint-rule"
id: "restraint-01"
description: "The best part is no part. Default to NOT building; focus on what not to build; demand a clear, present purpose before adding any artifact (code, skill, rule, tool, feature, abstraction)."
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
# Restraint — the best part is no part

The default answer to "should I build this?" is **no**, until a clear, present purpose forces a yes. Every artifact — a line of code, a skill, a rule, a script, a feature, an abstraction — is a standing liability: it must be read, maintained, kept consistent, and it competes for context. Subtraction is the first move, not the last.

- **Lead with what NOT to build.** Before proposing *how* to build something, decide whether it should exist at all — and say the case against first. "We could add X" is not a reason to add X.
- **No build without a concrete, present purpose.** Not "might be useful," not "for completeness," not "while we're here." If the need is speculative, don't build the router until it actually mis-routes. (YAGNI.)
- **Doing nothing is a valid, often correct outcome.** A review that ends in "change nothing — here's why" succeeded. Don't manufacture changes to look productive; proposing a build and then rejecting it on scrutiny is the job working, not failing.
- **An abstraction must remove more than it adds.** Centralizing, merging, or generalizing only earns its keep when the machinery it introduces costs less than the duplication/complexity it removes. A stable 3-line duplication can beat a shared dependency.
- **Question the ask.** If asked to build something whose purpose isn't clear, push back and ask *why* before building (see `personal-chat-rule` reduce-sycophancy). Adding is easy and feels productive — that is the trap.
- **Smallest thing that works.** Extend or point to what exists over creating new; a pointer over a copy; a cue over a prescription; a one-liner over a section.

This generalizes the code-level "Simplify and delete / Best Part is No Part" in `software-engineering-rule` to **all** artifacts and to the build/no-build decision itself. On any conflict about whether to add vs. remove, bias toward remove.
