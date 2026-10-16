#!/usr/bin/env bash
# Node tests: pytest on node/tests/ (the contracts.sh test also needs worker/'s generator).
set -euo pipefail
cd "$(dirname "$0")/../.."

uv sync --locked --project node
(cd worker && npm ci --no-audit --no-fund)
uv run --locked --directory node pytest tests
