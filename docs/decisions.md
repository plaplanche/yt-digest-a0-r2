# Decisions

Choices the spec leaves open, one dated line each.

- 2026-10-16: `node/` is built with hatchling; ruff selects rules E, F, W, I, B, UP with line length 100; mypy and pytest are configured in `node/pyproject.toml`.
- 2026-10-16: `worker/` lints with ESLint flat config (`@eslint/js` recommended + `typescript-eslint` strict, `no-explicit-any` as error); Vitest runs `worker/tests/**/*.test.ts`.
- 2026-10-16: the `contracts` check passes with a message while `scripts/contracts.sh` does not exist; once it exists it installs both packages' dependencies and runs `./scripts/contracts.sh --check`.
- 2026-10-16: `lint` runs shellcheck on every `*.sh` file under `scripts/`, found with `find`.
