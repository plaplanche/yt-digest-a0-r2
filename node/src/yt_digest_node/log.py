"""Structured logging: one JSON line per event on standard error (spec section 4.4)."""

import sys
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from yt_digest_node.contracts.log_event_schema import LogEvent


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def emit(event: str, level: str = "info", **fields: Any) -> None:
    """Write one log line, validated against the log event contract.

    `fields` are `request_id`, `video_id` and `attrs`; `request_id` and `video_id` are left out
    when None. An event outside the catalogue, or an unknown field, raises ValueError.
    """
    line: dict[str, Any] = {"ts": _now(), "level": level, "service": "node", "event": event}
    line["attrs"] = fields.pop("attrs", {})
    line.update({key: value for key, value in fields.items() if value is not None})
    try:
        model = LogEvent.model_validate(line)
    except ValidationError as error:
        raise ValueError(f"invalid log event {event!r}: {error}") from error
    sys.stderr.write(model.model_dump_json(exclude_unset=True) + "\n")
