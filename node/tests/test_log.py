import json
import re

import pytest

from yt_digest_node.contracts.log_event_schema import LogEventName
from yt_digest_node.log import emit


def test_emit_writes_one_json_line_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    emit(
        LogEventName.sponsorblock_call,
        request_id="req-1",
        video_id="dQw4w9WgXcQ",
        attrs={"status": 200, "segments": 2, "duration_ms": 41},
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", line.pop("ts"))
    assert line == {
        "level": "info",
        "service": "node",
        "event": "sponsorblock.call",
        "request_id": "req-1",
        "video_id": "dQw4w9WgXcQ",
        "attrs": {"status": 200, "segments": 2, "duration_ms": 41},
    }


def test_emit_leaves_out_missing_identifiers(capsys: pytest.CaptureFixture[str]) -> None:
    emit("service.started", level="debug", request_id=None, attrs={"version": "0.1.0"})
    line = json.loads(capsys.readouterr().err)
    assert set(line) == {"ts", "level", "service", "event", "attrs"}
    assert line["level"] == "debug"


def test_emit_rejects_an_event_outside_the_catalogue(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ValueError, match="transcript.text"):
        emit("transcript.text")
    assert capsys.readouterr().err == ""


def test_emit_rejects_an_unknown_field() -> None:
    with pytest.raises(ValueError):
        emit("service.started", text="hello")


def test_emit_rejects_an_unknown_level() -> None:
    with pytest.raises(ValueError):
        emit("service.started", level="fatal")
