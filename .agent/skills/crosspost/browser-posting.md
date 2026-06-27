# Browser posting (Claude-in-Chrome)

Shared semi-manual flow for platforms with no usable API, an API behind a
paywall/approval, or where you'd rather not store credentials. Claude fills the
web composer in **your real logged-in browser**; **you approve and click submit.**
No stored secrets.

## When this is the right path
- **HN** — no posting API exists.
- **X / Twitter** — API works but new accounts are pay-per-use (credits); browser is free. See [platforms/twitter.md](platforms/twitter.md).
- **LinkedIn** — instead of the OAuth app + token, post via the web composer.
- Any web composer the tool can reach (Bluesky, Mastodon, etc.).

Prefer a real API where one is free and headless: **Discord** (webhook) and
**Bluesky** (atproto app password) don't need the browser. Use this flow only
when the API path is worse.

## Not available here
- **Reddit** — `reddit.com` is **blocked in the Claude-in-Chrome tool** (domain-wide).
  There is no browser path for Reddit through this tool. See [platforms/reddit.md](platforms/reddit.md).

## Rules
- **Real session only.** Claude-in-Chrome is the only tool with your logged-in
  identity. Confirm you're logged in before composing; never log in on your behalf.
- **Human approves the submit.** Publishing is a confirmed action — Claude fills and
  verifies, then asks before the final Post/Submit click.
- **No CAPTCHAs.** If one appears, stop and hand back to the human.

## Procedure
1. Load chrome tools; `tabs_context_mcp` first to see tabs and confirm login. Open a
   new tab (`tabs_create_mcp`) for the task rather than reusing the user's working tabs.
2. `navigate` to the platform's compose URL (below).
3. Fill fields, then **screenshot to verify** the content before doing anything else.
4. **Confirm with the user**, then click submit.
5. Read the result page; return the new post URL as a clickable link.

## React controlled-input gotcha (important)
Many modern composers (the X dev console, lots of SPAs) use React controlled
inputs. Setting a value with `form_input` writes the DOM value but **does not fire
React's `onChange`** — React still thinks the field is empty and leaves the submit
button disabled. Same for checkboxes set via `form_input`: they look checked but
re-render to unchecked.

**Fix:** drive inputs with **real keystrokes** — `left_click` the field, `cmd+a` to
select, then `type`. Toggle checkboxes with a real `left_click`, not `form_input`.
Re-screenshot and confirm the submit button is enabled before clicking.

## Compose URLs / per-platform notes
| Platform | Compose URL | Notes |
|---|---|---|
| X / Twitter | `https://x.com/compose/post` | 280 chars, plain text |
| Hacker News | `https://news.ycombinator.com/submit` | title + url **or** text; `Show HN:` prefix; ~80-char neutral title |
| LinkedIn | `https://www.linkedin.com/feed/?shareActive=true` | 3000 chars; opens the share composer |
| Bluesky | `https://bsky.app/` → composer | 300 chars (API is easier — prefer it) |
| Mastodon | your instance `/home` → composer | 500 chars typical |

## Reading the result
Capture the canonical post URL from the page after submit and return it as a
clickable link so the user can open it. If the page doesn't redirect to the post,
read the timeline / profile to find the new item's URL.
