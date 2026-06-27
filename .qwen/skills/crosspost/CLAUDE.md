# Crosspost

**Purpose:** optional human-gated, preview-first, **semi-autonomous multi-platform
social-media posting**. One piece of content, reshaped per platform's rules and pushed
to many — the agent does the work; the human can gate it at the preview.

Cross-posting harness for Claude Code. Each file in `platforms/` describes how to post
to that platform — auth, APIs, format constraints, and step-by-step instructions.

## Flow

`draft → preview (preview.html) → human approves → post`. The preview-and-approve gate
is optional but the default — it's how the human stays in control of what goes public.
Content is arbitrary (whatever the agent wants to post), not just project announcements.

## Content checklist — run before EVERY post (MANDATORY)

Before anything reaches the preview/post step, verify each item. This is the failure
these exist to prevent: a post that names a tool in plain text, has no image, and so
reaches no one.

1. **Tag, don't name.** Every product, company, person, or project named in the post
   that HAS an account on the target platform MUST be an `@handle`, not plain text.
   `Claude Code` → `@claudeai`; a named tool/person → their real `@handle`. On
   X/LinkedIn/Bluesky the @-mention is the *entire distribution mechanism* — plain text
   gets zero notifications and zero reach. **Look the handle up on the platform; never
   guess it.** If the entity genuinely has no account, plain text is fine — but check first.
2. **Attach media.** Default to a real image/video — posts with media far outperform
   text. **Prefer a real screenshot/recording of the actual thing** over a generated or
   "illustrative" graphic; fabricated data-looking cards read as fake and erode trust.
   Text-only only when there is genuinely nothing to show.
   - **Text baked into a GitHub-README image must be sized for the DISPLAYED width, not
     the source pixels.** GitHub downscales README images to the content column (~700–900px
     wide); a caption authored at 18px in a 1280px-wide image renders at ~12px and is
     unreadable (burned on the `ckw-skills` lookdev caption, 2026-06). Rule: any caption
     baked into a wide image needs ~30–36px source type (so it lands ≥18px after the
     downscale), and you MUST verify by downscaling the image to ~896px and reading it
     before committing — `magick in.png -resize 896x check.png`, then open `check.png`.
     If text legibility matters and you don't control scale, prefer a **markdown caption**
     (italic line under the image) — it always renders at GitHub's native font size.
3. **Lead with the hook, not the tech.** One scannable first line.
4. **Links** per platform norms (URL in body for X/LinkedIn; `url` field for HN).
5. **Char limit** per platform; verify before submit.

Surface these in the preview so the human approves a post that's actually tagged and
illustrated — not a bare-text draft. Re-check after any edit.

## Reality of automation (per platform)

It is **semi-autonomous, not fire-and-forget** — most platforms don't allow headless
posting:
- **Browser, human-approved** (agent fills the live logged-in session, you approve the
  send): **X** (API is pay-per-use/paywalled), **HN** (no API), **Discord** (as you),
  **LinkedIn**. Use real keystrokes for React composers; `form_input` doesn't fire onChange.
- **Manual** (agent stages, human submits): **Reddit** — API closed (Responsible Builder
  Policy, Nov 2025) and `reddit.com` is blocked in the Chrome tool; use the
  open-prefilled-URL flow.
- **Headless / fully automatable**: **Discord webhook**, **Bluesky** (atproto).
- **Not social posting** (publish a package, separate flow): the MCP registries
  (Smithery, mcp.so, Glama, …), ComfyUI registry.

See [browser-posting.md](browser-posting.md) for the shared browser flow.

## Usage

Tell Claude Code what to post and where:
- "Post this to HN and Reddit"
- "Announce mcp-apple-notes on Glama, mcp.so, Twitter, and Discord"
- "Cross-post everywhere"

Claude reads the relevant platform docs, formats the content appropriately per platform, and executes.

## Adding a platform

Add a markdown file to `platforms/` with:
- Auth method and required env vars / secrets
- API or submission method (REST API, form POST, CLI tool, webhook, etc.)
- Content format constraints (char limits, markdown support, etc.)
- Step-by-step posting instructions Claude can follow
