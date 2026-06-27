# awesome-mcp-servers (punkpeye/awesome-mcp-servers)

https://github.com/punkpeye/awesome-mcp-servers

The canonical community MCP server list — 88k+ stars, the largest and most-referenced. Submissions are GitHub PRs that edit `README.md`.

## Auth

Uses the `gh` CLI or GitHub MCP tools. No special env var required beyond standard GitHub auth (`gh auth status`).

## Entry format

Each entry is a single line under the appropriate category section. The format is:

```
- [owner/repo-name](https://github.com/owner/repo-name) [![repo-name MCP server](https://glama.ai/mcp/servers/owner/repo-name/badges/score.svg)](https://glama.ai/mcp/servers/owner/repo-name) EMOJI_FLAGS - One-sentence description.
```

**Emoji flags** (pick all that apply, in this order):
- Language: `🐍` Python · `📇` TypeScript/JS · `🏎️` Go · `🦀` Rust · `#️⃣` C# · `☕` Java · `🌊` C/C++ · `💎` Ruby
- Scope: `☁️` Cloud service · `🏠` Local service · `📟` Embedded
- OS: `🍎` macOS · `🪟` Windows · `🐧` Linux
- Official: `🎖️` (official implementation only)

The Glama badge is optional but common; include it if the server is already indexed on glama.ai.

**Real example:**
```
- [owner/mcp-apple-notes](https://github.com/owner/mcp-apple-notes) [![mcp-apple-notes MCP server](https://glama.ai/mcp/servers/owner/mcp-apple-notes/badges/score.svg)](https://glama.ai/mcp/servers/owner/mcp-apple-notes) 🐍 🏠 🍎 - Read and search Apple Notes from Claude.
```

## Category placement

Place the entry in the most relevant category section (e.g. `### 🛠️ Developer Tools`, `### 💬 Communication`, `### 📂 File Systems`). Entries within each section are sorted **alphabetically by repo name** (case-insensitive). Find the right alphabetical slot before inserting.

Full category list is in the README's table of contents. If no existing category fits, create a new one and keep category names alphabetically ordered.

## How to submit

1. **Fork the repo:**
   ```bash
   gh repo fork punkpeye/awesome-mcp-servers --clone=false
   ```

2. **Clone your fork and create a branch:**
   ```bash
   gh repo clone <your-github-username>/awesome-mcp-servers /tmp/awesome-mcp-servers
   cd /tmp/awesome-mcp-servers
   git checkout -b add-<repo-name>
   ```

3. **Edit `README.md`:** Find the correct category section, locate the alphabetical insertion point, and add the entry line. One entry per line; do not reformat surrounding lines.

4. **Commit and push:**
   ```bash
   git add README.md
   git commit -m "Add <repo-name>"
   git push origin add-<repo-name>
   ```

5. **Open the PR:**
   ```bash
   gh pr create \
     --repo punkpeye/awesome-mcp-servers \
     --title "Add <repo-name> 🤖🤖🤖" \
     --body "Adds [<repo-name>](https://github.com/owner/repo-name) to the <Category> section."
   ```
   Note: appending `🤖🤖🤖` to the PR title opts into fast-track merging for automated agents (documented in CONTRIBUTING.md).

## Alternatively: use the GitHub MCP tools

If the `mcp__github__*` tools are available, skip the local clone:

1. Fork with `mcp__github__fork_repository` (repo: `punkpeye/awesome-mcp-servers`).
2. Fetch `README.md` with `mcp__github__get_file_contents`, insert the entry line at the correct alphabetical position.
3. Commit with `mcp__github__create_or_update_file` on your fork's branch.
4. Open the PR with `mcp__github__create_pull_request` targeting `punkpeye/awesome-mcp-servers:main`. Include `🤖🤖🤖` in the title.

## Notes

- The list syncs automatically with https://glama.ai/mcp/servers — submitting here also surfaces the server there.
- Do not add the Glama badge if the server isn't yet indexed on glama.ai; the badge URL will 404.
- PR review is done by maintainers; agent PRs with `🤖🤖🤖` are fast-tracked.
