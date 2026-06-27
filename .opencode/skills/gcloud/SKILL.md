---
name: gcloud
description: Configure & manage Google Cloud from the terminal (enable APIs, service accounts, API keys, IAM) instead of the console. Project/creds in central/.env. Use for any GCP admin/setup (e.g. turning on Vision API for reverse-image search).
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# gcloud — Google Cloud admin from the CLI

`gcloud` does everything the GCP console does — enabling APIs, service accounts, API
keys, IAM, billing, projects. Prefer it over the web UI, and over the (newer, narrower)
Google Cloud MCP, which only covers data-plane services (Cloud Run, SQL, BigQuery,
Maps, GKE, GCE) and not the admin operations below. The runtime program (e.g. Muser
calling the Vision API) is separate code — this skill is only for *configuring* GCP.

## Install (if `gcloud` is missing)

```bash
brew install --cask google-cloud-sdk
# add to ~/.zshrc (the cask doesn't touch PATH):
source "/opt/homebrew/share/google-cloud-sdk/path.zsh.inc"
source "/opt/homebrew/share/google-cloud-sdk/completion.zsh.inc"
```

## Credentials

`~/dev/central/.env` (gitignored, mode 600). Load before SDK/API use:

```bash
set -a && source ~/dev/central/.env && set +a
```

Variables:
- `GOOGLE_CLOUD_PROJECT` — default project id.
- `GOOGLE_APPLICATION_CREDENTIALS` — absolute path to a service-account JSON key (the
  standard ADC var). The key *file* lives outside the repo (e.g. `~/.config/gcloud/`),
  never in `.env` or git — `.env` holds only its path.
- `GCP_VISION_API_KEY` — a restricted API key, for simple key-auth services like Vision.

## Auth model (read this first)

`gcloud` runs under the user's own login. **`gcloud auth login` is interactive (opens a
browser) — the agent cannot run it.** If `gcloud auth list` shows no active account, ask
the user to run it themselves in-session:

```
! gcloud auth login
! gcloud auth application-default login   # for local SDK/ADC, if needed
```

Once authed, the agent runs every gcloud command non-interactively under that account.
Always check state first:

```bash
gcloud auth list --format="value(account)"
gcloud config get-value project
gcloud projects list --format=json
```

Use `--format=json` everywhere so output is parseable, not scraped.

## Common admin recipes

```bash
gcloud config set project PROJECT_ID

# Enable an API (idempotent)
gcloud services enable vision.googleapis.com
gcloud services list --enabled --format="value(config.name)"

# Service account + role
gcloud iam service-accounts create muser-vision --display-name "Muser Vision"
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member "serviceAccount:muser-vision@PROJECT_ID.iam.gserviceaccount.com" \
  --role roles/serviceusage.serviceUsageConsumer

# Service-account key -> file outside git, path into central/.env
gcloud iam service-accounts keys create ~/.config/gcloud/muser-vision.json \
  --iam-account muser-vision@PROJECT_ID.iam.gserviceaccount.com
# then set GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/muser-vision.json in central/.env

# API key (for Vision etc.), restricted to one API
gcloud services api-keys create --display-name "muser-vision" \
  --api-target=service=vision.googleapis.com --format="value(response.keyString)"
# store the printed key as GCP_VISION_API_KEY in central/.env
```

### Vision reverse-image (Web Detection) — what Muser needs

```bash
gcloud services enable vision.googleapis.com
# then a restricted API key (above) → GCP_VISION_API_KEY → call images:annotate WEB_DETECTION
```

## Safety / conventions

- **Confirm before** anything that creates billable resources, links/changes billing, or
  deletes. Cloud is a *system* (not reversible like git) — be conservative, say what a
  command will do before running it.
- **Never echo secrets**: don't `cat` an SA key file or print an API key into the
  conversation/logs beyond writing it once into `central/.env` (mode 600, gitignored).
  Put the SA key *file* outside the repo; `.env` holds the path or the API key string.
- **Restrict keys**: scope API keys to the one API that needs them (`--api-target`),
  not unrestricted.
- Prefer **idempotent** ops (`services enable` is safe to re-run); check existence with
  `--format=json` before creating duplicates.
