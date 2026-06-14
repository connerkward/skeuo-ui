#!/usr/bin/env bash
# Build the signed + notarized Skeuo.app / .dmg for macOS.
#
# Tauri signs and notarizes automatically when these env vars are present, so
# this script's only job is to populate them and run `tauri build`:
#
#   APPLE_SIGNING_IDENTITY   "Developer ID Application: <Name> (<TEAMID>)"
#   APPLE_ID                 your Apple ID email
#   APPLE_PASSWORD           an app-specific password (appleid.apple.com → Sign-In & Security)
#   APPLE_TEAM_ID            your 10-char team id
#
# Provide them via the environment or a gitignored .env (NEVER commit them).
# If the signing identity is absent, we still build an UNSIGNED app for local
# testing and say so loudly.
set -euo pipefail
cd "$(dirname "$0")/.."

# Load secrets from a local .env if present (gitignored). Standard Apple creds.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

# Auto-detect the Developer ID Application identity if not already set.
if [ -z "${APPLE_SIGNING_IDENTITY:-}" ]; then
  APPLE_SIGNING_IDENTITY="$(security find-identity -p codesigning -v 2>/dev/null \
    | grep -o '"Developer ID Application:[^"]*"' | head -1 | tr -d '"')" || true
  export APPLE_SIGNING_IDENTITY
fi

if [ -z "${APPLE_SIGNING_IDENTITY:-}" ]; then
  echo "⚠️  No 'Developer ID Application' identity found — building UNSIGNED."
  echo "    Install your Developer ID cert in the login keychain to sign."
else
  echo "🔏 Signing as: $APPLE_SIGNING_IDENTITY"
  if [ -z "${APPLE_ID:-}" ] || [ -z "${APPLE_PASSWORD:-}" ] || [ -z "${APPLE_TEAM_ID:-}" ]; then
    echo "⚠️  APPLE_ID / APPLE_PASSWORD / APPLE_TEAM_ID not all set — will sign but NOT notarize."
    echo "    Gatekeeper will still warn until the app is notarized."
  else
    echo "📝 Notarizing with Apple ID: $APPLE_ID (team $APPLE_TEAM_ID)"
  fi
fi

# --target aarch64 by default (Apple Silicon). Pass args through, e.g.
#   scripts/build-desktop.sh --target universal-apple-darwin
npm run tauri:build -- "$@"

echo
echo "✅ Done. Artifacts under src-tauri/target/release/bundle/{macos,dmg}/"
