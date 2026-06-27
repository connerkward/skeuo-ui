# Hacker News

## Auth
- **No official API for posting.** Primary path is **Claude-in-Chrome** driving your live, logged-in HN session — no stored credentials. HN wants Show HNs posted by a human; automated/headless submission risks penalizing the account, so the final submit is human-approved.
- Fallback (not recommended): cookie-based session via `HN_USERNAME` / `HN_PASSWORD` — fragile and bot-flagged. Only if you knowingly accept the risk.

## Submission
- HN only supports **link posts** (title + URL) or **text posts** (title + body, no URL).
- Title: max ~80 chars. No clickbait. Factual, neutral tone. HN moderators will edit titles that editorialize.
- URL: the primary content. HN is a link aggregator.
- "Show HN:" prefix when sharing something you built. Required format: `Show HN: <title>`

## How to post (Claude-in-Chrome)
Follow the shared flow in [../browser-posting.md](../browser-posting.md) (real session, human-approves-submit, React-input gotcha). HN specifics:
1. Load the chrome tools; `tabs_context_mcp` to find/confirm the user is logged into news.ycombinator.com (else open a tab and let them log in).
2. `navigate` to `https://news.ycombinator.com/submit`.
3. Fill `title`, and `url` (link post) **or** `text` (text post) via `form_input`. Apply the `Show HN: ` prefix when sharing something built.
4. **Confirm with the user, then** click submit. Read the resulting page; capture and return the new post URL.

## Fallback (cookie session, not recommended)
1. POST to `https://news.ycombinator.com/login` with `acct`/`pw`; capture the `user` cookie.
2. GET `/submit` with the cookie; extract the `fnid` hidden field.
3. POST to `/r` with `fnid`, `fnop=submit-page`, `title`, `url` (or `text`).
4. Follow the redirect to the new post URL. Fragile and bot-flagged — prefer the Chrome path.

## Notes
- HN rate-limits submissions. Don't post more than a few per day.
- Best posting times: ~9-11am ET on weekdays.
- Don't self-promote excessively — mix in other interesting content.
