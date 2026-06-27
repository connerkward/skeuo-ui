# Reddit

> **Self-service API access is closed (Reddit "Responsible Builder Policy", ~Nov 11 2025).**
> Creating a new "script" app at `prefs/apps` no longer yields working credentials — new OAuth
> apps require **manual pre-approval** via a Developer Support request (describe use case,
> subreddits, volume; ~7-day review). Personal cross-post/announce bots generally **do not
> qualify**. Only credentials minted **before Nov 2025** are grandfathered and still work.
> reddit.com is also blocked in the Claude-in-Chrome tool, so there is **no agent-automatable
> path** for new accounts. Practical options: (a) reuse a pre-Nov-2025 app's creds below;
> (b) post to Reddit **manually** in your own browser; (c) skip Reddit.

## Auth (only works with grandfathered pre-Nov-2025 credentials)
- If you have an **existing** script app from before Nov 2025: https://www.reddit.com/prefs/apps
- Env: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`
- 2FA accounts: append the current OTP to the password (`password:123456`) — expires fast, poor for automation.

## API
- OAuth token: POST `https://www.reddit.com/api/v1/access_token` with `grant_type=password`, username, password. Basic auth header with client_id:client_secret.
- Submit: POST `https://oauth.reddit.com/api/submit` with bearer token.

## Semi-automated manual flow (no API, no Chrome tool)
Since the API is closed and `reddit.com` is blocked in Claude-in-Chrome, get as far
as possible without either: **open the prefilled submit page in the user's real
(logged-in) browser** with the macOS `open` command, and stage the body/image so the
user only has to paste/attach and click **Post**.

```bash
# Link post — title + url prefill reliably via query params:
open "https://www.reddit.com/r/<subreddit>/submit?title=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "TITLE")&url=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "URL")"

# Text/self post — body (selftext) prefill is unreliable on new Reddit, so put the
# body on the clipboard for a one-paste fill, and open the page with the title set:
printf '%s' "BODY MARKDOWN" | pbcopy
open "https://www.reddit.com/r/<subreddit>/submit?title=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "TITLE")"
```

- **Title + link prefill** via the URL; **body** goes on the clipboard (paste once).
- **Images/attachments cannot be prefilled** — stage the file at a known path and hand
  it to the user (clickable `file://` link) to drag in. The user attaches + clicks Post.
- Public post text in a query string is fine; never put sensitive data there.

## Content types (API — grandfathered creds only)
- **Link post**: `kind=link`, `title`, `url`, `sr` (subreddit)
- **Self post**: `kind=self`, `title`, `text` (markdown body), `sr`
- **Cross-post**: `kind=crosspost`, `crosspost_fullname` (original post t3_id)

## How to post
Use the helper (handles password grant + submit, reads `.env`):

```
scripts/post.py reddit --sr <subreddit> --title "<title>" --url <url>       # link post
scripts/post.py reddit --sr <subreddit> --title "<title>" --text "<body>"   # self post
```

It prints the new post's permalink on success. By hand:
1. Get OAuth token via password grant.
2. POST to `/api/submit` with fields: `api_type=json`, `kind`, `sr`, `title`, `url` or `text`.
3. Response JSON has `data.url` — the permalink to the new post.

## Notes
- Each subreddit has its own rules. Check before posting.
- Common targets: r/selfhosted, r/opensource, r/programming, r/machinelearning, r/comfyui, r/StableDiffusion
- Specify subreddit(s) when requesting a Reddit post.
- Flair may be required — check subreddit rules.
