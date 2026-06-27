---
name: docs
description: Doc authoring, compression, and frontmatter. Use when creating, editing, or compressing docs; or marking files human-reviewed.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

- **One place per fact.** Everywhere else: "See X." DRY.
- **Prefer generated over written.** Script from one source → output; change source once.
- **Code as truth.** Link, don't summarize. Minimize nesting; short files.
- **Minimalism:** Only necessary code/signatures; avoid prose and greetings. High information-to-token ratio.
- **De-verbosify:** Remove passive voice, "I will now...". Bulleted technical lists.

**Public-facing pages / READMEs:** apply [[geo-seo]] — H1 = entity name, a one-line "X is a Y that does Z" definition directly under it, a TLDR/FAQ, and schema.org JSON-LD. Don't duplicate that guidance here.

**Human-reviewed frontmatter:** Add or update at top of Markdown: `human-reviewed-at: YYYY-MM-DD`, `human-reviewed-by: <human-id>`. If frontmatter exists, only add/update those two keys; preserve others. If none, insert new block. human-id e.g. connerward (ask if not provided).
