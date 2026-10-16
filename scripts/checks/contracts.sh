#!/usr/bin/env bash
# Contracts check: generated files must match contracts/ (passes while scripts/contracts.sh does not exist).
set -euo pipefail
cd "$(dirname "$0")/../.."

if [[ ! -e scripts/contracts.sh ]]; then
  echo "scripts/contracts.sh does not exist yet: nothing to check"
  exit 0
fi
uv sync --locked --project node
(cd worker && npm ci --no-audit --no-fund)
./scripts/contracts.sh --check
