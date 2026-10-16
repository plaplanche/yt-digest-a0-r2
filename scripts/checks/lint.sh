#!/usr/bin/env bash
# Lint check: ruff, ruff format and mypy on node/; tsc and ESLint on worker/; shellcheck on scripts/.
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "-- python"
uv sync --locked --project node
uv run --locked --directory node ruff check
uv run --locked --directory node ruff format --check
uv run --locked --directory node mypy --strict

echo "-- typescript"
(cd worker && npm ci --no-audit --no-fund && npx tsc --noEmit && npx eslint .)

echo "-- shell"
mapfile -t scripts < <(find scripts -name '*.sh' -type f | sort)
uvx --from shellcheck-py shellcheck "${scripts[@]}"
