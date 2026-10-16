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
- 2026-10-16: cleaning lives in `yt_digest_node/cleaning.py`: `parse_vtt(text) -> list[Cue]` (`Cue` holds `start` and `end` in seconds and the raw text lines) and `paragraphs(cues, segments) -> list[str]`, segments being `(start, end)` pairs in seconds.
- 2026-10-16: VTT blocks are separated by empty lines only, so the whitespace-only lines of YouTube auto tracks stay inside their cue (and are then dropped as empty); a block is a cue when its first or second line holds `-->`.
- 2026-10-16: inline tags are removed with one pattern, `<[^>]*>`; bracketed annotations with `\[[^\]]*\]`.
- 2026-10-16: a cue whose lines are all dropped (empty or duplicates) is not a kept cue for the paragraph gap; the gap is compared in whole milliseconds so that float rounding cannot turn 2.0 s into 1.999… s.
- 2026-10-16: SponsorBlock lives in `yt_digest_node/sponsorblock.py`: `fetch_segments(video_id, base_url, request_id=None) -> SponsorBlockResult` (segments as `(start, end)` pairs, `state` `ok`/`none`/`error`) using `urllib.request` (no new dependency), and `sponsor_ratio(segments, duration)`; turning `error` into a null `sponsor_ratio` is left to the pipeline.
- 2026-10-16: a 200 whose body is not a JSON array of items with `segment: [start, end]` counts as `error` (logged with status 200 and 0 segments); `sponsorblock.call` is logged at `info` for `ok` and `none`, `warn` for `error`.
- 2026-10-16: `sponsor_ratio` is 0 when the duration is 0 or less; Python's `round(x, 3)` does the rounding.
- 2026-10-16: extractors live in `yt_digest_node/extractors.py`: `Extractor.extract(video_id) -> Extraction | Failure` (`Extraction` holds `duration` and `Track`s of `lang`, `source`, `vtt`), `FakeExtractor`, `YtDlpExtractor`, `extractor_from_env(env, langs)` (raises `ValueError` when `FETCHER_FAKE_YTDLP=1` without `FAKE_YTDLP_DIR`) and `choose_track(tracks, langs) -> Track | None`, None meaning `no_transcript`.
- 2026-10-16: the fake extractor requires `meta.json` in an existing video directory; files not named `<lang>.<manual|auto>.vtt` are ignored; it never waits, which is how the delay is forced to 0.
- 2026-10-16: yt-dlp is a runtime dependency of `node/` (no type stubs: mypy ignores its missing imports); `quiet` and `no_warnings` are added to the options of 5.2 so that yt-dlp writes nothing on standard output.
- 2026-10-16: the yt-dlp extractor downloads only the `vtt` entries of `subtitles` (manual) and `automatic_captions` (auto) for the requested languages, through `YoutubeDL.urlopen`, and waits the random delay before `extract_info` and before each of those downloads.
- 2026-10-16: a yt-dlp `DownloadError` whose message contains "not a bot" (either apostrophe) is `blocked`; every other `DownloadError` (private, age-restricted, removed, unavailable) is `unavailable`.
- 2026-10-16: `YT_DELAY_SECONDS` is `low-high` or one number, in seconds; a negative or reversed range raises `ValueError`.
- 2026-10-16: truncation and pages live in `yt_digest_node/pages.py` (`truncate(paragraphs, max_words) -> (paragraphs, truncated)`, `paginate(paragraphs, page_words) -> pages`, `count_words`); the `[…]` marker is a paragraph of 0 words, so it always joins the page holding the words before it.
- 2026-10-16: a paragraph longer than `PAGE_WORDS` is cut into pieces of `PAGE_WORDS` words (the last one shorter), and the pieces are then grouped like whole paragraphs.
- 2026-10-16: the pipeline lives in `yt_digest_node/pipeline.py` (`Config.from_env(env)`, `run(video_id, config, extractor, request_id)`), the command in `yt_digest_node/cli.py` (argparse, entry point `yt_digest_node.cli:main`).
- 2026-10-16: `MAX_WORDS` must be an integer of at least 2 (so each side of the truncation keeps a word) and `PAGE_WORDS` of at least 1; an invalid configuration value, an empty language list or a missing `FAKE_YTDLP_DIR` exits 2 like a bad argument, with a plain message on standard error and no log line.
- 2026-10-16: SponsorBlock is only called once a track is chosen; for `no_transcript`, `unavailable` and `blocked`, `fetch.transcript` has `source`, `sponsor_ratio` and `sponsorblock` null.
- 2026-10-16: `fetch.transcript` is logged at `info` whatever the outcome; its `duration_ms` covers the whole pipeline; `service.started` carries the `request_id` too.
- 2026-10-16: the SponsorBlock stand-in server of the tests lives in `node/tests/conftest.py` (the `server` fixture), shared by the SponsorBlock, pipeline and command tests.
