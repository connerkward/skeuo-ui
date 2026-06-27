---
name: crosspost
description: Optional human-gated, preview-first, semi-autonomous multi-platform social-media posting — one piece of content reshaped per platform's rules and pushed to HN, Reddit, X, Discord, LinkedIn, Bluesky (+ project registries). Use when the user wants to announce, share, cross-post, or distribute something. Flow is draft → preview → human approves → post.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Crosspost

**Purpose:** optional human-gated, preview-first, **semi-autonomous multi-platform
social-media posting**. The agent reshapes one piece of content per platform and posts;
the human gates it at the preview. Flow: `draft → preview → approve → post`.

The skill's files live in this directory. Load `CLAUDE.md` for full instructions, then read
the relevant `platforms/<platform>.md` file(s) for the target platforms. Open `preview.html`
in a browser for the preview page.

Published publicly as `connerkward/crosspost` via the [[publish-skill]] skill — central is
the source of truth; the public repo is a sanitized publish target.

Auth credentials come from env vars — see each platform doc. Never log or commit credentials.

For discoverability/AI-citation strategy (canonical-first, consistent entity name + definition across spokes), see [[geo-seo]] — this skill is the posting mechanics; geo-seo is the why/what.
