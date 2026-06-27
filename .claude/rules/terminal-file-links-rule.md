---
name: "terminal-file-links-rule"
id: "term-links-01"
description: "Every file path, folder, or URL the user might open must be a clickable markdown link (default file://); every SendUserFile delivery must be paired with file:// links in the same message."
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

# Referencing files & locations — ALWAYS make them clickable (default `file://`)

> **NEVER POST A NON-CLICKABLE URL OR PATH. NO EXCEPTIONS.** Every URL (`http(s)://`,
> `file://`, tailnet/`.ts.net`, `.local`, localhost) and every file/folder path you put
> in a message MUST be a markdown link `[label](url)` — never bare text, never in
> backticks/code-spans as the *only* form. Backticks are not clickable; a code-span URL
> is a violation. Before sending any message, scan it for `http`, `file:`, `/Users/`,
> `localhost`, `.ts.net`, `.local` appearing outside a `](...)` and convert each to a
> link. This has been violated and the user is angry about it — treat it as a hard gate.

Any time you cite a file path, folder, or URL the user might want to open, render it
as a **clickable markdown link**. Never emit a bare, unlinked path or location — if it
points somewhere, it must be clickable.

## Sending files (SendUserFile / attachments) — ALWAYS pair with clickable links

> **BINDING PROCEDURE — NO EXCEPTIONS.** A `SendUserFile` call is INCOMPLETE until the
> same message also contains a clickable `file://` link for every file sent. The link is
> part of the delivery, not an optional extra. Before you end any turn that called
> `SendUserFile`, re-read your message and confirm a `file://` link exists for each file.
> If a link is missing, the delivery has FAILED — add it. A chip with no link is a bug.

When you deliver files to the user — `SendUserFile`, or any mechanism that renders a
file "chip"/attachment — those chips are **NOT openable on their own** in the user's
terminal (they show a name + size, no link). The chip is the *delivery*; a clickable
`file://` link is the only way the user can actually **open** the file. So:

- **Every file you send must also appear as a clickable `file://` link in the message
  text.** One link per file (or a folder link if you sent a whole set). No exceptions.
- **This has been violated repeatedly and the user is angry about it.** Treat it as a
  reflex: the moment you write a `SendUserFile` call, write the matching `file://`
  link(s) in the prose in the same breath. Do not "deliver now, link later."
- Original failure: a `SendUserFile` batch showed chips (`baseline-1…`, `withskill-…`)
  with **no way to open them**. Repeat failure: a single `galref-a.png` sent with no
  link. NEVER present files — chip or bare path — without accompanying clickable links.
- Order doesn't matter (links before or after the send), but they must be in the same
  turn as the delivery.

## Default form: `file://`

- **A file** → link to the file itself. Clicking opens it in the default app
  (Preview, browser, editor):

  `[seat-buck.jpg](file:///Users/conner/dev/portfolio-2026/assets/mercedes-fuzzy-input/seat-buck.jpg)`

- **A folder** → link with a trailing slash. Clicking opens Finder at that folder:

  `[mercedes-fuzzy-input/](file:///Users/conner/dev/portfolio-2026/assets/mercedes-fuzzy-input/)`

- **A web location** → ordinary markdown link (`[label](https://…)`). Same rule:
  never paste a bare URL as plain text when it can be a link.

Rules for the URI:
- **Absolute paths only**, URL-encoded where needed (spaces → `%20`, etc.). The
  scheme is `file://` + the absolute path, so it begins `file:///` (three slashes).
- The link **label** can be the filename, a partial path, or any short descriptor —
  it just has to be clickable. The href carries the full absolute path.
- Applies everywhere you cite a location: tables, lists, prose, search/result dumps.

## When the user needs the file *highlighted* in Finder (not just opened)

A `file://` link to a file *opens* it; it does not reveal-and-select it in Finder.
macOS has no URI that highlights a file, and cmux only fires `open <uri>` for standard
schemes — so no clickable link can highlight. When highlighting matters, **don't hand
over a command — just do it**: run `open -R "<abs path>"` yourself via the Bash tool.
It executes locally on the user's Mac and pops Finder with the file selected, zero
clicks from them.

- **Reveal-on-intent.** When the user clearly wants to inspect/open a specific file,
  run `open -R` yourself. Don't auto-reveal every path you mention in passing — that
  spams Finder windows. Cite-in-passing → clickable `file://` link; clear intent to
  open → run `open -R`.

## Why `file://` is the default and not `open -R`

`open -R` is a *command*, not a URI, so it can't be a one-click link — the user would
have to type `!` to run it. A `file://` link is genuinely one click. So: links for
references (always clickable), `open -R` run by the agent only when the user needs the
file revealed-and-highlighted.

(cmux note, tested 2026-05: custom schemes like `reveal://` do NOT work — cmux only
opens `file://`/`http`. Don't chase a clickable reveal-and-highlight; it isn't possible
here. `file://` link to open, agent-run `open -R` to highlight.)
