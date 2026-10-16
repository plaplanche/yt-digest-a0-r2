import json
from typing import Any

import pytest
from conftest import SponsorBlockServer

from yt_digest_node.contracts.transcript_result_schema import TranscriptStatus
from yt_digest_node.extractors import Extraction, Failure, Source, Track
from yt_digest_node.pipeline import (
    DEFAULT_SPONSORBLOCK_URL,
    Config,
    parse_langs,
    run,
)

VIDEO_ID = "abcdefghijk"


class StubExtractor:
    def __init__(self, extraction: Extraction | Failure) -> None:
        self.extraction = extraction

    def extract(self, video_id: str) -> Extraction | Failure:
        return self.extraction


def vtt(*cues: str) -> str:
    blocks = [
        f"00:00:{2 * i:02d}.000 --> 00:00:{2 * i + 2:02d}.000\n{c}" for i, c in enumerate(cues)
    ]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def config(url: str, **overrides: Any) -> Config:
    values: dict[str, Any] = {
        "langs": ("en",),
        "max_words": 60000,
        "page_words": 12000,
        "sponsorblock_url": url,
    }
    return Config(**{**values, **overrides})


def fetch_line(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    line: dict[str, Any] = lines[-1]
    assert line["event"] == "fetch.transcript"
    return line


# Configuration


def test_defaults() -> None:
    assert Config.from_env({}) == Config(("fr", "en"), 60000, 12000, DEFAULT_SPONSORBLOCK_URL)


def test_environment_overrides_the_defaults() -> None:
    env = {
        "TRANSCRIPT_LANGS": "de, en",
        "MAX_WORDS": "10",
        "PAGE_WORDS": "5",
        "SPONSORBLOCK_URL": "http://127.0.0.1:9",
    }
    assert Config.from_env(env) == Config(("de", "en"), 10, 5, "http://127.0.0.1:9")


@pytest.mark.parametrize(
    "env",
    [
        {"MAX_WORDS": "ten"},
        {"MAX_WORDS": "1"},
        {"PAGE_WORDS": "0"},
        {"TRANSCRIPT_LANGS": " , "},
    ],
)
def test_invalid_values_raise(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        Config.from_env(env)


def test_parse_langs() -> None:
    assert parse_langs("fr,en") == ("fr", "en")


# Pipeline


def test_25_words_with_max_10_are_truncated_to_10(server: SponsorBlockServer) -> None:
    text = " ".join(f"w{i}" for i in range(1, 26))
    extractor = StubExtractor(Extraction(60.0, (Track("en", Source.manual, vtt(text)),)))
    result = run(VIDEO_ID, config(server.url, max_words=10), extractor)
    assert result.truncated is True
    assert result.word_count == 10
    assert result.pages == ["w1 w2 w3 w4 w5\n\n[…]\n\nw21 w22 w23 w24 w25"]


def test_sponsor_segments_are_cut_and_give_the_ratio(
    server: SponsorBlockServer, capsys: pytest.CaptureFixture[str]
) -> None:
    server.body = json.dumps([{"segment": [2, 4]}]).encode()
    extractor = StubExtractor(
        Extraction(20.0, (Track("en", Source.auto, vtt("one", "promo", "two")),))
    )
    result = run(VIDEO_ID, config(server.url), extractor, "req-9")
    assert result.status is TranscriptStatus.ok
    assert (result.lang, result.source) == ("en", "auto")
    assert result.pages == ["one\n\ntwo"]
    assert result.sponsor_ratio == 0.1
    line = fetch_line(capsys)
    assert line["request_id"] == "req-9"
    assert line["video_id"] == VIDEO_ID
    assert line["attrs"]["sponsorblock"] == "ok"


def test_sponsorblock_error_gives_a_null_ratio_and_an_otherwise_normal_result(
    server: SponsorBlockServer, capsys: pytest.CaptureFixture[str]
) -> None:
    server.status = 500
    extractor = StubExtractor(Extraction(20.0, (Track("en", Source.manual, vtt("one")),)))
    result = run(VIDEO_ID, config(server.url), extractor)
    assert result.status is TranscriptStatus.ok
    assert result.sponsor_ratio is None
    assert result.pages == ["one"]
    assert fetch_line(capsys)["attrs"]["sponsorblock"] == "error"


def test_sponsorblock_404_gives_a_ratio_of_0(server: SponsorBlockServer) -> None:
    server.status = 404
    extractor = StubExtractor(Extraction(20.0, (Track("en", Source.manual, vtt("one")),)))
    result = run(VIDEO_ID, config(server.url), extractor)
    assert result.sponsor_ratio == 0.0


@pytest.mark.parametrize("failure", list(Failure))
def test_failure_gives_its_status_without_calling_sponsorblock(
    server: SponsorBlockServer, failure: Failure
) -> None:
    result = run(VIDEO_ID, config(server.url), StubExtractor(failure))
    assert result.status.value == failure.value
    assert server.paths == []


def test_no_matching_track_is_no_transcript(server: SponsorBlockServer) -> None:
    extractor = StubExtractor(Extraction(20.0, (Track("de", Source.manual, vtt("eins")),)))
    result = run(VIDEO_ID, config(server.url), extractor)
    assert result.status is TranscriptStatus.no_transcript
    assert server.paths == []
