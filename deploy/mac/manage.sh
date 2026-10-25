#!/usr/bin/env bash
set -euo pipefail
DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${XIAOZHI_MAC_ENV_FILE:-$DEPLOY_DIR/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Private environment file is missing. Copy .env.example to .env and follow deploy/mac/README.md.\n' >&2
  exit 1
fi
# Parse with Compose, not `source`: values are configuration, not shell code.
# Profiles are explicit: start management first, then opt in to --profile voice.
exec docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/compose.yaml" "$@"
