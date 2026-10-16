"""End-to-end tests: the command as a subprocess, with the fake extractor and a local
SponsorBlock server."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import SponsorBlockServer

import yt_digest_node
from yt_digest_node.contracts.log_event_schema import LogEvent
from yt_digest_node.contracts.transcript_result_schema import TranscriptResult

COMMAND = Path(sys.executable).parent / "yt-digest-node"
FIXTURES = Path(__file__).parent / "fixtures" / "ytdlp"
SPONSOR_VTT = FIXTURES / "sponsorVid1" / "en.manual.vtt"
CONFIG_VARS = (
    "TRANSCRIPT_LANGS",
    "MAX_WORDS",
    "PAGE_WORDS",
    "SPONSORBLOCK_URL",
    "FETCHER_FAKE_YTDLP",
    "FAKE_YTDLP_DIR",
    "YT_DELAY_SECONDS",
)


def command(server: SponsorBlockServer, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    base = {key: value for key, value in os.environ.items() if key not in CONFIG_VARS}
    base.update(FETCHER_FAKE_YTDLP="1", FAKE_YTDLP_DIR=str(FIXTURES), SPONSORBLOCK_URL=server.url)
    return subprocess.run(
        [str(COMMAND), "transcript", *args],
        env={**base, **env},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def result(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert process.returncode == 0, process.stderr
    TranscriptResult.model_validate_json(process.stdout)
    output: dict[str, Any] = json.loads(process.stdout)
    return output


def logs(process: subprocess.CompletedProcess[str]) -> list[dict[str, Any]]:
    lines = [json.loads(line) for line in process.stderr.splitlines()]
    for line in lines:
        LogEvent.model_validate(line)
    assert lines[0]["event"] == "service.started"
    assert lines[0]["attrs"] == {"version": yt_digest_node.__version__}
    assert [line["event"] for line in lines].count("fetch.transcript") == 1
    return lines


def fetch_line(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    line = logs(process)[-1]
    assert line["event"] == "fetch.transcript"
    assert isinstance(line["attrs"].pop("duration_ms"), int)
    return line


def empty(video_id: str, status: str) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "status": status,
        "lang": None,
        "source": None,
        "word_count": 0,
        "truncated": False,
        "sponsor_ratio": None,
        "pages": [],
    }


def test_ok_with_sponsor_cuts(server: SponsorBlockServer) -> None:
    server.body = json.dumps([{"segment": [4, 6], "category": "sponsor"}]).encode()
    process = command(server, "sponsorVid1", "--request-id", "req-42")
    assert result(process) == {
        "video_id": "sponsorVid1",
        "status": "ok",
        "lang": "en",
        "source": "manual",
        "word_count": 9,
        "truncated": False,
        "sponsor_ratio": 0.1,
        "pages": ["alpha bravo charlie delta\n\necho foxtrot\n\ngolf hotel india"],
    }
    events = [line["event"] for line in logs(process)]
    assert events == ["service.started", "sponsorblock.call", "fetch.transcript"]
    line = fetch_line(process)
    assert (line["request_id"], line["video_id"]) == ("req-42", "sponsorVid1")
    assert line["attrs"] == {
        "outcome": "ok",
        "source": "manual",
        "words": 9,
        "pages": 1,
        "sponsor_ratio": 0.1,
        "sponsorblock": "ok",
    }


def test_log_lines_hold_no_transcript_text(server: SponsorBlockServer) -> None:
    server.body = json.dumps([{"segment": [4, 6]}]).encode()
    process = command(server, "sponsorVid1", "--request-id", "req-42")
    assert result(process)["status"] == "ok"
    words = SPONSOR_VTT.read_text(encoding="utf-8").split()
    words = [word for word in words if word.isalpha() and word != "WEBVTT"]
    assert len(words) == 12
    for word in words:
        assert word not in process.stderr
    assert "zulu" not in process.stdout


def test_max_words_and_page_words_come_from_the_environment(server: SponsorBlockServer) -> None:
    server.status = 404
    paged = result(command(server, "sponsorVid1", PAGE_WORDS="4"))
    assert paged["pages"] == [
        "alpha bravo charlie delta",
        "zulu yankee xray echo",
        "foxtrot\n\ngolf hotel india",
    ]
    assert (paged["word_count"], paged["truncated"], paged["sponsor_ratio"]) == (12, False, 0)
    truncated = result(command(server, "sponsorVid1", MAX_WORDS="4"))
    assert truncated["pages"] == ["alpha bravo\n\n[…]\n\nhotel india"]
    assert (truncated["word_count"], truncated["truncated"]) == (4, True)


def test_sponsorblock_error_gives_a_null_ratio(server: SponsorBlockServer) -> None:
    server.status = 500
    process = command(server, "sponsorVid1")
    output = result(process)
    assert (output["status"], output["word_count"], output["sponsor_ratio"]) == ("ok", 12, None)
    assert fetch_line(process)["attrs"]["sponsorblock"] == "error"


def test_langs_order(server: SponsorBlockServer) -> None:
    default = result(command(server, "frAutoEnMan"))
    assert (default["lang"], default["source"], default["pages"]) == ("en", "manual", ["hello"])
    from_env = result(command(server, "frAutoEnMan", TRANSCRIPT_LANGS="fr"))
    assert (from_env["lang"], from_env["source"], from_env["pages"]) == ("fr", "auto", ["bonjour"])
    from_flag = result(command(server, "frAutoEnMan", "--langs", "fr", TRANSCRIPT_LANGS="en"))
    assert (from_flag["lang"], from_flag["source"]) == ("fr", "auto")


@pytest.mark.parametrize(
    ("video_id", "status"),
    [
        ("onlyGerman1", "no_transcript"),
        ("unavailVid1", "unavailable"),
        ("missingVid1", "unavailable"),
        ("blockedVid1", "blocked"),
    ],
)
def test_statuses_other_than_ok(server: SponsorBlockServer, video_id: str, status: str) -> None:
    process = command(server, video_id, "--request-id", "req-7")
    assert result(process) == empty(video_id, status)
    line = fetch_line(process)
    assert (line["request_id"], line["video_id"]) == ("req-7", video_id)
    assert line["attrs"] == {
        "outcome": status,
        "source": None,
        "words": 0,
        "pages": 0,
        "sponsor_ratio": None,
        "sponsorblock": None,
    }
    assert server.paths == []


@pytest.mark.parametrize(
    ("args", "env"),
    [
        (("short",), {}),
        (("dQw4w9WgXcQ!",), {}),
        ((), {}),
        (("sponsorVid1", "--langs", ","), {}),
        (("sponsorVid1",), {"MAX_WORDS": "many"}),
        (("sponsorVid1",), {"FAKE_YTDLP_DIR": ""}),
    ],
)
def test_bad_argument_exits_2_without_a_result(
    server: SponsorBlockServer, args: tuple[str, ...], env: dict[str, str]
) -> None:
    process = command(server, *args, **env)
    assert process.returncode == 2
    assert process.stdout == ""
    assert server.paths == []
