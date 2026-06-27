# Discord

## Auth
- Webhook URL per channel — no bot token needed for simple posting
- Env: `DISCORD_WEBHOOK_URL` (or multiple: `DISCORD_WEBHOOK_<NAME>`)

## API
- POST to the webhook URL with JSON body
- No auth headers needed — the URL itself is the secret

## Content format
- Supports embeds (rich cards with title, description, URL, color, fields, thumbnail)
- Plain text content up to 2000 chars
- Markdown supported in descriptions

## How to post
1. POST to webhook URL with `Content-Type: application/json`
2. Body for embed:
```json
{
  "embeds": [{
    "title": "Post title",
    "url": "https://...",
    "description": "Body text with **markdown**",
    "color": 5814783
  }]
}
```
3. 204 response = success. No response body.

## Notes
- Can configure multiple webhooks for different servers/channels
- Specify which Discord channel/server when requesting a Discord post
