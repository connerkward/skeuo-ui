# Twitter / X

## Auth — primary path is the browser (free)
- **Posting goes through Claude-in-Chrome on the logged-in x.com session.** No credits, no secrets needed for posting.
- Reason: new X developer accounts enroll in **pay-per-use** (`console.x.com`) — the API charges credits per request and has **no free posting tier**. A POST with $0 balance returns `402 CreditsDepleted`. Verified 2026-06-12 on app `conner-crosspost` / @dingo_works. (The old developer-portal "Free 500/mo" tier no longer applies to new signups.)

## How to post (Claude-in-Chrome)
Follow the shared flow in [../browser-posting.md](../browser-posting.md) (real session, human-approves-submit, React-input gotcha). X specifics:
1. `tabs_context_mcp` to confirm the user is logged into x.com (else open a tab and let them log in).
2. `navigate` to `https://x.com/compose/post`.
3. Type the tweet body into the composer. Mind the 280-char limit.
4. **Confirm with the user, then** click **Post**. Capture and return the tweet URL.

## API fallback (only if credits purchased)
The OAuth 1.0a app is already configured (Read+Write) with creds in `.env`; read-auth verified. It will post **only once the pay-per-use balance is funded** (`console.x.com` → Billing → Credits). Then:
- POST `https://api.twitter.com/2/tweets`, OAuth 1.0a signed, body `{ "text": "..." }`
- Env: `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET`
- The helper supports it: `scripts/post.py twitter --text "<tweet>" [--reply-to <id>]` — prints the tweet URL, or `402 CreditsDepleted` until funded.

## Content format
- 280 char limit
- URLs count as ~23 chars regardless of actual length (t.co wrapping)
- Hashtags, mentions, and media supported; no markdown — plain text only
- **Run the Content checklist in [../CLAUDE.md](../CLAUDE.md) first.** Especially: **tag
  entities as `@handles`, never plain text** (e.g. `Claude Code` → `@claudeai`) — the
  @-mention is the only thing that creates reach/notifications — and **attach a real
  screenshot** of the actual thing, not a generated/illustrative card.
- Threads: reply to your own tweet with `reply.in_reply_to_tweet_id` (API) or the reply UI (browser)

## Notes
- For project announcements, format: short description + URL + 1-2 relevant hashtags
- Thread for longer announcements: first tweet is the hook, subsequent tweets add detail
