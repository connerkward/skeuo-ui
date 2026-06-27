# Cline MCP Marketplace

https://github.com/cline/mcp-marketplace

## Submission method

GitHub issue via the official issue template (`mcp-server-submission.yml`). No PR needed — the Cline team handles adding the server to the marketplace after approval.

## Auth / env vars

No API key needed. Requires a GitHub account with permission to open issues on `cline/mcp-marketplace`.

## Asset requirements

- **Logo:** 400×400 PNG. Upload directly in the issue (drag-and-drop) or provide a direct URL.
- **README.md:** Must contain clear installation instructions — Cline uses this to autonomously install the server. Verify this actually works (required checkbox).
- **llms-install.md** (optional): Extra install guidance for complex setups, multi-step env config, or when README alone is insufficient.

## Approval criteria

Cline reviews for:
- Community adoption (GitHub stars, engagement, ecosystem presence)
- Developer credibility (established orgs/maintainers preferred)
- Project maturity (code quality, docs, maintenance activity)
- Security (extra scrutiny for financial/crypto-adjacent tools)

Review turnaround: typically a couple of days.

## Step-by-step

1. Prepare assets: have the GitHub repo URL and a 400×400 PNG logo ready.
2. Ensure `README.md` (or `llms-install.md`) covers install end-to-end — test by feeding it to Cline and watching it self-install.
3. Open the submission issue:

```bash
gh issue create \
  --repo cline/mcp-marketplace \
  --title "[Server Submission]: <server-name>" \
  --label "server-submission" \
  --body "$(cat <<'EOF'
### GitHub Repository URL

https://github.com/<owner>/<repo>

### Logo Image

<URL to 400×400 PNG, or note that it will be attached>

### Installation Testing

- [x] I have tested that Cline can successfully set up this server using only the README.md and/or llms-install.md file
- [x] The server is stable and ready for public use

### Additional Information

<optional: special setup requirements, dependencies, etc.>
EOF
)"
```

Or use the web form directly:
https://github.com/cline/mcp-marketplace/issues/new?template=mcp-server-submission.yml

4. Attach the 400×400 PNG logo to the issue body (drag-and-drop in the GitHub UI, or paste a direct image URL).
5. Wait for Cline team review (~2 days). Approved servers are added to the marketplace listings and become one-click installable by Cline users.
