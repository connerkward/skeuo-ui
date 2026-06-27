# Entity consistency — worked example

The GEO payoff comes from describing ONE entity the SAME way everywhere, anchored to
one canonical URL. Hold two things constant across all spokes:

1. **Entity name** (exact string).
2. **Definition** in "X is a Y that does Z" form.

Vary only the surrounding hook/tone/length per platform.

## Example: a tool called `mcp-apple-notes`

- **Entity name (constant):** `mcp-apple-notes`
- **Definition (constant):** "mcp-apple-notes is an MCP server that exports Apple
  Notes to Markdown."
- **Canonical (constant):** the GitHub repo URL.

### GitHub README (canonical)
```markdown
# mcp-apple-notes

mcp-apple-notes is an MCP server that exports Apple Notes to Markdown.
```

### Hacker News (Show HN)
> **Show HN: mcp-apple-notes – an MCP server that exports Apple Notes to Markdown**
>
> I built mcp-apple-notes to get my notes out of Apple's silo… [link to repo]

### Reddit (r/ClaudeAI or similar)
> I made **mcp-apple-notes**, an MCP server that exports Apple Notes to Markdown.
> Decodes the NoteStore protobuf locally, no cloud. Repo: [link]

### Twitter/X
> mcp-apple-notes: an MCP server that exports Apple Notes to Markdown. Local-only,
> protobuf-decoded. [link]

### Discord
> Dropped **mcp-apple-notes** — an MCP server that exports Apple Notes to Markdown.
> [link]

## What stayed identical
- The string `mcp-apple-notes` (never "the notes exporter", "my MCP", etc.).
- The clause "an MCP server that exports Apple Notes to Markdown."
- Every spoke links to the same canonical repo URL.

## What varied (correctly)
- Hook, length, platform-norm framing (Show HN title format, Reddit detail, tweet
  brevity).

## Why it works
A model crawling HN + Reddit + Twitter + the README sees the same name + same
definition + same canonical link from four independent sources. That cross-source
corroboration is what makes it resolve `mcp-apple-notes` as a real, well-defined
entity and cite it. Inconsistent naming/definition fractures the signal — the model
sees four vaguely-related things instead of one corroborated entity.
