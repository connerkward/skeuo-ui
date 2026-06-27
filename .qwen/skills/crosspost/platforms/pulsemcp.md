# PulseMCP (MCP Server Directory)

https://pulsemcp.com

18,000+ server directory, updated daily. PulseMCP is a **read-only aggregator** — it pulls from the Official MCP Registry automatically. The fastest path to a listing is publishing to the Official Registry; PulseMCP ingests from it daily and processes weekly. Direct URL submission and email correction are also available.

## Submission method

Three paths, in order of preference:

1. **Official MCP Registry (preferred)** — publish via `mcp-publisher` CLI; PulseMCP auto-ingests within a week. No separate PulseMCP account needed.
2. **Direct URL submission** — paste a GitHub repo URL (or subfolder/website) at https://pulsemcp.com/submit. Browser required; no API.
3. **Email correction** — for adjustments to an existing listing, or if it has been over a week since Official Registry publication: hello@pulsemcp.com

No write API exists. The REST API at https://pulsemcp.com/api is read-only.

## Auth / env vars

No API key for submission. The `mcp-publisher` CLI authenticates to the **Official MCP Registry** (not PulseMCP itself) via GitHub OAuth, GitHub OIDC, DNS verification, or HTTP verification.

## server.json fields (Official Registry)

Required fields in `server.json`:

| Field | Notes |
|---|---|
| `name` | Namespaced: `io.github.username/server-name` for GitHub auth |
| `description` | Short description of the server |
| `repository.url` | GitHub repo URL |
| `repository.source` | `"github"` |
| `version` | Semver |
| `packages[].registryType` | `npm`, `pypi`, `nuget`, `oci`, `mcpb` |
| `packages[].identifier` | Package name on the registry |
| `packages[].version` | Package version |
| `packages[].transport.type` | `stdio` or `http` |

Optional: `packages[].environmentVariables[]` with `name`, `description`, `isRequired`, `isSecret`, `format`.

Schema: `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`

## PulseMCP listing metadata

Each listing shows: server name, provider/author, description, Official/Community/Anthropic classification, estimated weekly visitors, release date, GitHub repo link + star count.

## How to submit (Official Registry path)

1. Add `"mcpName": "io.github.username/server-name"` to `package.json` (for npm; other package types differ — see https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx).
2. Publish the package to npm (or PyPI/NuGet/etc.) first — the registry stores metadata only, not artifacts.
3. Install `mcp-publisher`:
   ```bash
   brew install mcp-publisher
   # or
   curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/
   ```
4. Generate `server.json` in the repo root:
   ```bash
   mcp-publisher init
   # edit server.json — set name, description, version, packages
   ```
5. Authenticate:
   ```bash
   mcp-publisher login github
   # opens https://github.com/login/device — enter the printed code
   ```
6. Publish:
   ```bash
   mcp-publisher publish
   ```
7. Verify on Official Registry:
   ```bash
   curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.username/server-name"
   ```
8. PulseMCP picks it up automatically within ~1 week. If not, email hello@pulsemcp.com.

## How to submit (direct URL path — browser required)

1. Go to https://pulsemcp.com/submit
2. Select "MCP Server"
3. Paste the GitHub repo URL (or subfolder, or standalone website URL)
4. Submit

## Troubleshooting

- `"Registry validation failed"` → package is missing the ownership marker (`mcpName` in `package.json` for npm)
- `"You do not have permission to publish"` → server name prefix doesn't match auth method; with GitHub auth, name must start with `io.github.your-username/`
- Listed but metadata is wrong → email hello@pulsemcp.com with corrections
