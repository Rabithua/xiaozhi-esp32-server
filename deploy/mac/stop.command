#!/usr/bin/env bash
set -euo pipefail
DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
bash "$DEPLOY_DIR/manage.sh" --profile voice stop
printf 'Local services stopped; database volumes and private configuration are retained.\n'
