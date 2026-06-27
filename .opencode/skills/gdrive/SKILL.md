---
name: gdrive
description: Google Drive from the CLI via rclone on lappy-heavy — copy/sync/ls files, and back up skeuo-ui generated skin components to Drive. Use for any headless/scripted Google Drive transfer or backup. The interactive claude.ai Google Drive MCP connector is the alternative for in-chat browsing/reading, but it cannot do automated/scheduled backups.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# gdrive — Google Drive from the CLI (rclone)

`rclone` is the CLI for Google Drive on this machine. Use it for any **automated /
headless / scriptable** Drive transfer — copy, sync, mirror, list. For **interactive,
in-chat** Drive use (search/read/create a file while chatting) the claude.ai **Google
Drive MCP connector** is the alternative; it is OAuth'd to the user's account but is
**not usable for scheduled or scripted backups** — that's what rclone is for.

## Install (if missing)

```bash
brew install rclone
```

## The `gdrive` remote — finishing OAuth (ONE manual step)

The remote `gdrive` (type `drive`, scope `drive`) is **scaffolded** in
`~/.config/rclone/rclone.conf` but has **no OAuth token** until the user authorizes it
once in a browser. The agent **cannot** do this headlessly (it requires the user's
Google login + consent — never enter the user's password or complete their OAuth flow).

Finish it (the user runs this; it opens a browser):

```bash
rclone config reconnect gdrive:
# equivalently, interactive: `rclone config` → edit `gdrive` → "y" auto-config → authorize
```

Verify it took:

```bash
rclone listremotes          # → gdrive:
rclone about gdrive:        # shows quota once authorized (errors "empty token" before auth)
rclone lsd gdrive:          # lists top-level Drive folders
```

The OAuth token lives in `~/.config/rclone/rclone.conf` — outside any git repo, the
standard non-tracked rclone location (compliant with security-rule: secrets never in a
git-tracked path).

### Why not a fully-headless service account?

A service-account (`service_account_file`) remote would avoid the browser step, but it
is **not feasible for this account**: rclone SAs can only reliably write to a **Shared
Drive (Team Drive)**, which requires **Google Workspace**. `conner.k.ward@gmail.com` is a
**consumer Gmail** account (no org, no Shared Drives — confirmed: GCP project
`muser-2605300220` has no parent org). An SA writing to a shared *My Drive* folder
consumes the **SA's own** Drive quota (0 without Workspace) → uploads fail with
`storageQuotaExceeded`. So OAuth (the one browser step above) is the correct path here.
Revisit the SA path only if the account ever moves to Workspace + a Shared Drive.

## Everyday usage

```bash
rclone ls    gdrive:somefolder            # list files (recursive) with sizes
rclone lsd   gdrive:                       # list directories
rclone copy  ./local-dir gdrive:dest       # upload (never deletes on remote)
rclone sync  ./local-dir gdrive:dest       # MIRROR (deletes remote files not present locally)
rclone copy  gdrive:dest ./local-dir       # download
rclone --dry-run sync ...                  # preview; always dry-run a sync first
rclone copy ... --progress --transfers 8   # progress + parallelism
```

`sync` is destructive on the destination (it mirrors). Use `copy` when you only want to
add/update and never delete. Dry-run any `sync` before the real run.

## Skin-component backup (the primary use case)

Back up skeuo-ui's locally-generated skin artifacts to Drive as a **secondary, portable
backup**. The **canonical** cloud archive is already **Cloudflare R2** (`skins/<id>/` in
prod) — Drive is a convenience copy, not the source of truth.

- **Source:** `~/dev/skeuo-ui/public/generated/` — per skin `<id>`:
  `<id>-paint.png`, `-frame.png`, `-template.json`, `-meta.json`, `-layout.json`,
  `-sprite-*.png`.
- **Dest:** `gdrive:skeuo-skins/`

Run the script (in `scripts/` next to this file):

```bash
~/dev/central/skills/gdrive/scripts/backup-skeuo-skins.sh            # mirror (sync)
~/dev/central/skills/gdrive/scripts/backup-skeuo-skins.sh --copy     # add/update only, never delete
~/dev/central/skills/gdrive/scripts/backup-skeuo-skins.sh --dry-run  # preview
```

The script fails loud with the exact reconnect command if `gdrive:` isn't authorized
yet. Override the source dir with `SKEUO_GENERATED_DIR=...` if needed.

## Interactive alternative — claude.ai Google Drive MCP

For in-chat Drive work (search a doc, read/create a file mid-conversation) use the
claude.ai **Google Drive connector** tools (`mcp__claude_ai_Google_Drive__*`:
`search_files`, `read_file_content`, `create_file`, …). It's OAuth'd to the user's
account and good for one-off interactive reads/writes — but it is **not** a backup tool
(no sync/mirror, not scriptable headlessly). Backups → rclone.
