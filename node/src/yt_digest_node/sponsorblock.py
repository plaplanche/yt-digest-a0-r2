"""SponsorBlock: fetch a video's sponsor segments and compute its sponsor ratio (spec 5.3)."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from yt_digest_node.log import emit

CATEGORIES = ("sponsor", "selfpromo", "interaction")
TIMEOUT_SECONDS = 10.0


class SponsorBlockState(StrEnum):
    """How the call went: `ok` (200), `none` (404) or `error` (anything else)."""

    ok = "ok"
    none = "none"
    error = "error"


@dataclass(frozen=True)
class SponsorBlockResult:
    """The segments, as `(start, end)` pairs in seconds, and the state of the call."""

    segments: tuple[tuple[float, float], ...]
    state: SponsorBlockState


def _url(base_url: str, video_id: str) -> str:
    query = urllib.parse.urlencode(
        {"videoID": video_id, "categories": json.dumps(list(CATEGORIES), separators=(",", ":"))}
    )
    return f"{base_url.rstrip('/')}/api/skipSegments?{query}"


def _parse(body: bytes) -> tuple[tuple[float, float], ...]:
    items = json.loads(body)
    if not isinstance(items, list):
        raise ValueError("SponsorBlock answer is not a JSON array")
    segments: list[tuple[float, float]] = []
    for item in items:
        start, end = item["segment"]
        segments.append((float(start), float(end)))
    return tuple(segments)


def fetch_segments(
    video_id: str,
    base_url: str,
    *,
    request_id: str | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> SponsorBlockResult:
    """Call SponsorBlock for one video and log `sponsorblock.call`; never raises."""
    started = time.monotonic()
    status = 0
    result = SponsorBlockResult((), SponsorBlockState.error)
    try:
        with urllib.request.urlopen(_url(base_url, video_id), timeout=timeout) as response:
            status = response.status
            body = response.read()
        if status == 200:
            result = SponsorBlockResult(_parse(body), SponsorBlockState.ok)
    except urllib.error.HTTPError as error:
        status = error.code
        if status == 404:
            result = SponsorBlockResult((), SponsorBlockState.none)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    emit(
        "sponsorblock.call",
        level="warn" if result.state is SponsorBlockState.error else "info",
        request_id=request_id,
        video_id=video_id,
        attrs={
            "status": status,
            "segments": len(result.segments),
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return result


def sponsor_ratio(segments: Sequence[tuple[float, float]], duration: float) -> float:
    """Length of the union of the segments clipped to [0, duration], over the duration, rounded
    to 3 decimals; 0 when there is no segment or no duration."""
    if duration <= 0:
        return 0.0
    clipped = sorted((max(start, 0.0), min(end, duration)) for start, end in segments)
    total = 0.0
    covered_to = 0.0
    for start, end in clipped:
        start = max(start, covered_to)
        if end > start:
            total += end - start
            covered_to = end
    return round(total / duration, 3)
