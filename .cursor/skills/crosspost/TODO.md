# TODO

## Platforms to add

- [ ] **Instagram** — stories and feed posts
  - Auth: Instagram Graph API (Meta) — business/creator account + Facebook app, OAuth long-lived token
  - Posts: image/video feed posts via the Content Publishing API (`/{ig-user-id}/media` → `/media_publish`)
  - Stories: supported for business accounts via the Stories endpoint; requires a publicly reachable media URL
  - Constraints: image-first (no text-only posts), caption limits, hashtag handling, media hosting requirement
  - Add `platforms/instagram.md` once the auth flow and endpoints are confirmed

## Image + link posts / link thumbnails

Two distinct mechanisms to support and document properly — currently glossed over:

- **Image + link in one post** vs. **link post with auto-fetched thumbnail** (`og:image` / `twitter:card` unfurl).

- [ ] Document per-platform link-unfurl / thumbnail rules in the platform docs:
  - HN: link = title+URL only, no media, no thumbnail
  - Reddit: link posts auto-thumbnail from OG; image post is a separate type
  - Twitter/X: image and link card are **mutually exclusive** — attaching an image suppresses the card; bare URL unfurls a `twitter:card` thumbnail
  - Discord: embed has both `image` (large) and `thumbnail` (small) fields, set explicitly; bare-URL content auto-unfurls OG
  - LinkedIn: article share carries/fetches a thumbnail from source URL
- [ ] Fix `preview.html` to match real behavior:
  - Twitter: show image OR link card, not both
  - Render an actual thumbnail in the Twitter/Discord/LinkedIn link cards (simulate `og:image`), not just domain+title text
  - Optional: fetch/preview the real OG image from the entered URL

## Live-fire test findings (2026-06-12) — preview ≠ reality

Posted the crosspost announcement to X (@dingo_works) + Discord (#primary, Star Gods),
then compared the live posts to `preview.html`. Confirmed gaps:

- [ ] **Process is backwards.** Posted BEFORE previewing. The flow MUST be
  **draft → preview (`preview.html`) → human approves → post**. The skill needs to
  enforce preview-and-approve as a gate, not an afterthought.
- [ ] **X link card** — real X renders a **large image OG card** (GitHub's preview)
  and **strips the URL out of the body**; preview shows a small text-only card and
  keeps the URL inline. Fix both in the preview.
- [ ] **Discord embed** — real Discord unfurls the URL into an embed whose
  title/description come from the **page's OG data**, NOT the post body; preview
  builds the embed from the entered title/body. Fetch real OG for the embed.
- [ ] **Skill must be content-agnostic** — handle whatever an agent wants to post
  (any title/body/image/link/intent), not just project announcements.

## Skill flow to bake in (from the live test)

- [ ] Document the working browser flow in the skill: real-keystroke typing for X's
  and Discord's React composers (`form_input` doesn't fire onChange); Discord posts
  under the server **nickname**; Reddit is open-prefilled-URL + manual submit
  (reddit.com blocked in the Chrome tool); X is browser (API pay-per-use paywalled).
