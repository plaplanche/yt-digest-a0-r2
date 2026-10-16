from typing import Any

import pytest
from pydantic import ValidationError

from yt_digest_node.contracts.log_event_schema import LogEvent, LogEventName
from yt_digest_node.contracts.transcript_result_schema import TranscriptResult

RESULT: dict[str, Any] = {
    "video_id": "dQw4w9WgXcQ",
    "status": "ok",
    "lang": "fr",
    "source": "manual",
    "word_count": 3,
    "truncated": False,
    "sponsor_ratio": 0.125,
    "pages": ["un deux trois"],
}

LOG_LINE: dict[str, Any] = {
    "ts": "2026-10-16T08:30:00.123Z",
    "level": "info",
    "service": "node",
    "event": "sponsorblock.call",
    "request_id": "req-1",
    "video_id": "dQw4w9WgXcQ",
    "attrs": {"status": 200, "segments": 2, "duration_ms": 41},
}


def test_valid_result_is_accepted() -> None:
    assert TranscriptResult.model_validate(RESULT).model_dump(mode="json") == RESULT


@pytest.mark.parametrize(
    "change",
    [
        {"text": "hello"},
        {"video_id": "short"},
        {"video_id": "dQw4w9WgXc!"},
        {"status": "failed"},
    ],
    ids=["extra-field", "short-video-id", "bad-char-video-id", "bad-status"],
)
def test_invalid_result_is_rejected(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        TranscriptResult.model_validate(RESULT | change)


def test_valid_log_line_is_accepted() -> None:
    assert LogEvent.model_validate(LOG_LINE).model_dump(mode="json") == LOG_LINE


def test_log_line_with_unknown_event_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LogEvent.model_validate(LOG_LINE | {"event": "transcript.text"})


def test_catalogue_is_a_str_enum() -> None:
    assert [str(name) for name in LogEventName] == [
        "service.started",
        "fetch.transcript",
        "sponsorblock.call",
    ]
