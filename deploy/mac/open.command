#!/usr/bin/env bash
set -euo pipefail
DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
# Starting management leaves an already-running voice service untouched.
bash "$DEPLOY_DIR/manage.sh" up -d db redis web
python3 - <<'PY'
import json
import time
import urllib.request

deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8002/xiaozhi/user/pub-config", timeout=3
        ) as response:
            if json.load(response).get("code") == 0:
                break
    except Exception:
        pass
    time.sleep(2)
else:
    raise SystemExit("Management API did not become ready; inspect this project's containers.")
PY
open http://127.0.0.1:8002
