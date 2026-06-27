# LinkedIn

## Auth
- LinkedIn API via OAuth 2.0 (3-legged)
- Requires a LinkedIn app at https://www.linkedin.com/developers/apps
- Env: `LINKEDIN_ACCESS_TOKEN` (after OAuth flow)
- Scopes needed: `w_member_social` (posting), `r_liteprofile` (get author URN)

## API
- Posts API (v2): POST `https://api.linkedin.com/rest/posts`
- Headers: `Authorization: Bearer <token>`, `LinkedIn-Version: 202401`, `Content-Type: application/json`

## Content format
- Text posts: up to 3000 chars
- Supports articles (link shares), images, documents
- No markdown — plain text with line breaks
- Hashtags work: `#opensource #mcp`

## How to post

**Simplest path — browser (no app/token):** post via the web composer using the
shared [../browser-posting.md](../browser-posting.md) flow (`https://www.linkedin.com/feed/?shareActive=true`).
Use the API below only if you want unattended posting and have a valid token.

### Text + link post (API)
1. Get your person URN: GET `https://api.linkedin.com/v2/userinfo` → use `sub` as author ID.
2. POST to `https://api.linkedin.com/rest/posts`:
```json
{
  "author": "urn:li:person:<person-id>",
  "commentary": "Post text here\n\n#hashtag",
  "visibility": "PUBLIC",
  "distribution": {
    "feedDistribution": "MAIN_FEED"
  },
  "content": {
    "article": {
      "source": "https://...",
      "title": "Article title",
      "description": "Short description"
    }
  },
  "lifecycleState": "PUBLISHED"
}
```
3. 201 response = success. `x-restli-id` header has the post URN.

### Text-only post
Same as above but omit the `content` field.

## Notes
- LinkedIn OAuth tokens expire. May need refresh flow.
- Good for professional/developer audience announcements.
- Tone: more formal than Twitter, less formal than a blog post.
- humanwhocodes/crosspost MCP server supports LinkedIn — could use that instead of raw API.
