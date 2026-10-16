# Decisions

Choices the spec leaves open, one dated line each.

- 2026-10-16: `node/` is built with hatchling; ruff selects rules E, F, W, I, B, UP with line length 100; mypy and pytest are configured in `node/pyproject.toml`.
- 2026-10-16: `worker/` lints with ESLint flat config (`@eslint/js` recommended + `typescript-eslint` strict, `no-explicit-any` as error); Vitest runs `worker/tests/**/*.test.ts`.
- 2026-10-16: the `contracts` check passes with a message while `scripts/contracts.sh` does not exist; once it exists it installs both packages' dependencies and runs `./scripts/contracts.sh --check`.
- 2026-10-16: `lint` runs shellcheck on every `*.sh` file under `scripts/`, found with `find`.
- 2026-10-16: contracts are generated with `datamodel-code-generator` (Python, `--use-specialized-enum` for `StrEnum`, then `ruff check --fix` and `ruff format`) and `json-schema-to-typescript` (TypeScript); each generated TS file also exports its schema as a constant for runtime validation. Python modules are named after the schema file (`log_event_schema.py`, `transcript_result_schema.py`).
- 2026-10-16: TypeScript validates at runtime with `@cfworker/json-schema` (no code generation with `eval`, so it runs in Workers), through `worker/src/validate.ts`.
- 2026-10-16: the log event schema types `attrs` as a free object; the per-event attributes of the catalogue and the service of each event are not enforced by the schema in lot 1.
- 2026-10-16: `ts` is checked with a pattern (`YYYY-MM-DDTHH:MM:SS.mmmZ`), not `format`, so both languages enforce it the same way.
- 2026-10-16: `emit` leaves out `request_id` and `video_id` when they are None, and defaults `attrs` to `{}`; `log` takes `level`, `request_id`, `video_id` and `attrs` in `fields`, defaults `level` to `info` and writes with `console.log`.
- 2026-10-16: `contracts.sh` reads `CONTRACTS_ROOT` (default: the repository) as the tree holding schemas and generated files, so its `--check` is tested on a copy; `test-node` therefore also runs `npm ci` in `worker/`.
