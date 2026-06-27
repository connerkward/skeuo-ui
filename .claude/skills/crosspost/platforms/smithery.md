# Smithery (MCP Server Registry)

https://smithery.ai

## Auth

- Smithery account required. Sign up at https://smithery.ai.
- CLI uses OAuth browser login; no env var needed for interactive use.
- For non-interactive/CI publishing, generate a service token:
  ```
  smithery auth token
  ```
  Store as `SMITHERY_API_KEY`. Pass via `Authorization: Bearer $SMITHERY_API_KEY` header when using the REST API directly.

## Submission method

Two paths depending on server type:

**A. stdio server (GitHub repo)**
Add a `smithery.yaml` to the repo root, then publish via CLI or the web UI at https://smithery.ai/new. Smithery builds and hosts it as an MCPB bundle.

**B. URL-based / hosted server**
If the server already runs publicly with Streamable HTTP transport, publish its URL directly — no `smithery.yaml` needed.

## smithery.yaml format (stdio servers)

Place in repo root:

```yaml
# smithery.yaml
startCommand:
  type: stdio
  configSchema:
    type: object
    required:
      - apiKey          # list any required env/config params
    properties:
      apiKey:
        type: string
        description: API key for the service.
  commandFunction: |-
    (config) => ({ command: 'node', args: ['dist/index.js'], env: { API_KEY: config.apiKey } })
```

- `type`: `stdio` or `http`
- `configSchema`: JSON Schema — fields here become the install-time config form Smithery shows users
- `commandFunction`: JS arrow function (string-literal); returns `{ command, args, env }`
- Optional `build.dockerBuildPath` if using Docker

## How to publish

### Install CLI (requires Node.js 20+)

```bash
npm install -g smithery@latest
```

### Authenticate

```bash
smithery auth login          # browser OAuth — do once
smithery auth whoami         # verify
```

### Publish a stdio server (from repo root)

```bash
smithery mcp publish . -n @your-org/your-server-name
```

Or publish a prebuilt bundle:

```bash
smithery mcp publish ./server.mcpb -n your-org/your-server-name
```

### Publish a URL-based server

```bash
smithery mcp publish "https://your-server.com/mcp" -n @your-org/your-server-name
```

With a config schema:

```bash
smithery mcp publish "https://your-server.com/mcp" \
  -n @your-org/your-server-name \
  --config-schema '{"type":"object","properties":{"apiKey":{"type":"string"}}}'
```

### Via web UI (browser required)

1. Go to https://smithery.ai/new
2. Enter the GitHub repo URL or hosted server URL
3. Complete the publish flow (fills in metadata, sets visibility)

## Server metadata

Smithery auto-scans the server for tools/prompts/resources. If scanning fails (e.g. auth-gated), add a static card at `/.well-known/mcp/server-card.json`:

```json
{
  "serverInfo": { "name": "Your Server", "version": "1.0.0" },
  "tools": [{ "name": "my_tool", "description": "Does X" }],
  "authentication": { "required": true, "schemes": ["oauth2"] }
}
```

Only `serverInfo` is required; `tools`, `resources`, `prompts`, `authentication` are optional.

## REST API (programmatic)

Base URL: `https://api.smithery.ai`

Create/register a server (idempotent):
```
PUT /servers/{namespace%2Fserver-name}
Authorization: Bearer $SMITHERY_API_KEY
Content-Type: application/json

{ "displayName": "My Server", "description": "Does X" }
```

Publish a release:
```
PUT /servers/{namespace%2Fserver-name}/releases
Authorization: Bearer $SMITHERY_API_KEY
Content-Type: multipart/form-data

payload=<DeployPayload JSON>   # required
bundle=<file>                  # for stdio releases
module=<file>                  # for hosted JS releases
```

Returns `202 Accepted` with `{ deploymentId, status, mcpUrl }`.

## Notes

- Namespace must exist and be owned by your account before publishing.
- After publish, visit your server page → **Settings → Verification** for official-vendor verification.
- Smithery scans with `User-Agent: SmitheryBot/1.0 (+https://smithery.ai)`.
- No GitHub topic auto-discovery confirmed — explicit publish step is required.
