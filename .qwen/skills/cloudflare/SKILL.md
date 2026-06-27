---
name: cloudflare
description: Cloudflare REST API operations (Web Analytics/RUM site management, account info). Token in central/.env. Use when working with CF resources outside the Developer-Platform MCP scope.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Cloudflare

The Cloudflare MCP tools loaded in `claude.ai` only cover the Developer Platform (D1, KV, R2, Hyperdrive, Workers, docs search). Anything outside that — Web Analytics/RUM, Zones, DNS, Account Settings — goes through the REST API directly.

## Credentials

`~/dev/central/.env` (gitignored, mode 600). Load before any API call:

```bash
set -a && source ~/dev/central/.env && set +a
```

Variables:
- `CLOUDFLARE_API_TOKEN` — User API token created at https://dash.cloudflare.com/profile/api-tokens. As of 2026-06-13 scoped `Cloudflare Pages: Edit` + `Zone DNS: Edit` + `Zone: Read` (for Pages deploys + custom-domain CNAMEs, e.g. war-room.ward.run). **Note:** this replaced the earlier `Account Settings: Edit` token — if a RUM/Web-Analytics call returns an auth error, the token may need `Account Settings: Edit` (or `Web Analytics: Edit`) added back. Must be a **User** token, not account-owned (account-owned tokens can't hold Zone permissions).
- `CLOUDFLARE_ACCOUNT_ID` — the personal account ID.

## Auth header

```bash
curl -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" ...
```

Never pass the token as a literal string in the command — always via env var so it doesn't land in shell history.

## Web Analytics (RUM) site management

CF Web Analytics is the JS-pixel product (separate from Cloudflare DNS analytics, which only sees DNS queries). Gives page views, referrers, browser/OS/device, visit duration. No cookies, no consent banner.

### Create a site

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/rum/site_info" \
  -d '{"host":"<hostname>","auto_install":false}'
```

- `auto_install: false` for sites where you'll paste the beacon snippet manually (any site behind gray-cloud DNS or hosted off Cloudflare — GitHub Pages, Vercel, Netlify, etc.).
- `auto_install: true` only for orange-cloud sites where CF can inject the beacon at the edge.

Response includes `site_tag` — that's the value to paste into the beacon snippet's `data-cf-beacon` token.

### Beacon snippet

```html
<script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "<site_tag>"}'></script>
```

Place in `<head>`. The `defer` attribute means it doesn't block HTML parsing.

### List sites

```bash
curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/rum/site_info/list"
```

### Delete a site

```bash
curl -sS -X DELETE -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/rum/site_info/<site_tag>"
```

## Common pitfalls

- "Account Analytics: Read" permission does NOT grant RUM site creation. For RUM CRUD you need either `Web Analytics: Edit` (if visible in the token UI) or `Account Settings: Edit` as a working broader fallback.
- Cloudflare's REST API returns `{"success": true/false, "result": ..., "errors": [...]}` envelope. Always check `success`, not just HTTP status — auth failures sometimes return 200 with `success: false`.
- `host` in the create-site body should be bare hostname (`bas.run`), not a URL.

## Other Cloudflare scopes (when needed)

- **DNS records:** `GET/POST /zones/{zone_id}/dns_records`
- **Zones list:** `GET /zones`
- **Cache purge:** `POST /zones/{zone_id}/purge_cache` body `{"purge_everything":true}`

For any of these, scope the token narrowly to the needed permission rather than reusing the broad RUM token.

## Redirect Rules (apex → another domain)

To redirect a hostname (e.g. an apex) to another URL, use a **dynamic Redirect Rule** — works on
proxied (orange-cloud) hosts and takes precedence over the origin. The current `.env` token CAN create
these (verified 2026-06-17). PUT the phase entrypoint with **only** a `rules` array (no `name`/`kind`/
`phase` fields — those error):

```bash
curl -sS -X PUT "${AUTH[@]}" \
  "https://api.cloudflare.com/client/v4/zones/$ZID/rulesets/phases/http_request_dynamic_redirect/entrypoint" \
  -d '{"rules":[{"action":"redirect","action_parameters":{"from_value":{"status_code":301,
       "target_url":{"value":"https://connerkward.dev"},"preserve_query_string":false}},
       "expression":"(http.host eq \"ward.run\") or (http.host eq \"www.ward.run\")",
       "description":"...","enabled":true}]}'
```

Scope the `expression` to **exact hosts** (`http.host eq "..."`) so subdomains are untouched. PUT
**replaces** the whole entrypoint ruleset — to add a rule, fetch existing rules first and include them.

**Active redirects (machine-config record):**
- `ward.run` + `www.ward.run` → `https://connerkward.dev` (301), zone `ward.run`, created 2026-06-17.
  Apex was a Squarespace site ("nothing"); `slides.ward.run` / `war-room.ward.run` are separate and
  unaffected. **Reverse:** PUT the same entrypoint with `{"rules":[]}` (or delete the rule in dash →
  Rules → Redirect Rules).
