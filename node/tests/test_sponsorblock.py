import json
import socket
import urllib.parse
from typing import Any

import pytest
from conftest import SponsorBlockServer

from yt_digest_node.sponsorblock import (
    SponsorBlockState,
    fetch_segments,
    sponsor_ratio,
)

VIDEO_ID = "dQw4w9WgXcQ"


def log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    line: dict[str, Any] = json.loads(lines[0])
    assert line["event"] == "sponsorblock.call"
    assert line["video_id"] == VIDEO_ID
    assert isinstance(line["attrs"].pop("duration_ms"), int)
    return line


def test_200_returns_the_segments(
    server: SponsorBlockServer, capsys: pytest.CaptureFixture[str]
) -> None:
    server.body = json.dumps(
        [
            {"segment": [10.5, 20], "category": "sponsor", "UUID": "a"},
            {"segment": [30, 35.25], "category": "selfpromo", "UUID": "b"},
        ]
    ).encode()
    result = fetch_segments(VIDEO_ID, server.url, request_id="req-1")
    assert result.state is SponsorBlockState.ok
    assert result.segments == ((10.5, 20.0), (30.0, 35.25))
    line = log_line(capsys)
    assert line["request_id"] == "req-1"
    assert line["level"] == "info"
    assert line["attrs"] == {"status": 200, "segments": 2}


def test_request_names_the_video_and_the_three_categories(server: SponsorBlockServer) -> None:
    fetch_segments(VIDEO_ID, server.url + "/")
    path, _, query = server.paths[0].partition("?")
    assert path == "/api/skipSegments"
    assert urllib.parse.parse_qs(query) == {
        "videoID": [VIDEO_ID],
        "categories": ['["sponsor","selfpromo","interaction"]'],
    }
    assert "%5B%22sponsor%22" in query


def test_404_means_no_segments(
    server: SponsorBlockServer, capsys: pytest.CaptureFixture[str]
) -> None:
    server.status = 404
    server.body = b"Not Found"
    result = fetch_segments(VIDEO_ID, server.url)
    assert result.state is SponsorBlockState.none
    assert result.segments == ()
    line = log_line(capsys)
    assert line["level"] == "info"
    assert line["attrs"] == {"status": 404, "segments": 0}


def test_500_is_an_error(server: SponsorBlockServer, capsys: pytest.CaptureFixture[str]) -> None:
    server.status = 500
    result = fetch_segments(VIDEO_ID, server.url)
    assert result.state is SponsorBlockState.error
    assert result.segments == ()
    line = log_line(capsys)
    assert line["level"] == "warn"
    assert line["attrs"] == {"status": 500, "segments": 0}


def test_malformed_200_is_an_error(
    server: SponsorBlockServer, capsys: pytest.CaptureFixture[str]
) -> None:
    server.body = b'{"segment": [1, 2]}'
    result = fetch_segments(VIDEO_ID, server.url)
    assert result.state is SponsorBlockState.error
    assert result.segments == ()
    assert log_line(capsys)["attrs"] == {"status": 200, "segments": 0}


def test_connection_refused_is_an_error_with_status_0(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    result = fetch_segments(VIDEO_ID, f"http://127.0.0.1:{port}")
    assert result.state is SponsorBlockState.error
    assert result.segments == ()
    line = log_line(capsys)
    assert line["level"] == "warn"
    assert line["attrs"] == {"status": 0, "segments": 0}


def test_ratio_is_0_without_segments() -> None:
    assert sponsor_ratio([], 100.0) == 0.0


def test_ratio_counts_overlapping_segments_once() -> None:
    assert sponsor_ratio([(10.0, 30.0), (20.0, 40.0), (25.0, 35.0)], 100.0) == 0.3


def test_ratio_clips_segments_to_the_video() -> None:
    assert sponsor_ratio([(-5.0, 10.0), (90.0, 150.0)], 100.0) == 0.2
    assert sponsor_ratio([(120.0, 150.0)], 100.0) == 0.0


def test_ratio_is_rounded_to_3_decimals() -> None:
    assert sponsor_ratio([(0.0, 1.0)], 3.0) == 0.333
    assert sponsor_ratio([(0.0, 2.0)], 3.0) == 0.667
