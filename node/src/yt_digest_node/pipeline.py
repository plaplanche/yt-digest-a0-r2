"""The transcript pipeline: configuration and the steps from a video id to a result (spec 5)."""

import time
from collections.abc import Mapping
from dataclasses import dataclass

from yt_digest_node.cleaning import paragraphs, parse_vtt
from yt_digest_node.contracts.transcript_result_schema import (
    TranscriptResult,
    TranscriptSource,
    TranscriptStatus,
)
from yt_digest_node.extractors import Extractor, Failure, choose_track
from yt_digest_node.log import emit
from yt_digest_node.pages import count_words, paginate, truncate
from yt_digest_node.sponsorblock import SponsorBlockState, fetch_segments, sponsor_ratio

DEFAULT_LANGS = "fr,en"
DEFAULT_MAX_WORDS = 60000
DEFAULT_PAGE_WORDS = 12000
DEFAULT_SPONSORBLOCK_URL = "https://sponsor.ajay.app"


def parse_langs(value: str) -> tuple[str, ...]:
    """A comma-separated language list such as `fr,en`; an empty list raises ValueError."""
    langs = tuple(lang.strip() for lang in value.split(",") if lang.strip())
    if not langs:
        raise ValueError(f"invalid language list {value!r}")
    return langs


def _int_at_least(env: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = minimum - 1
    if value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}, not {raw!r}")
    return value


@dataclass(frozen=True)
class Config:
    """The environment variables of spec 5.1, except those of the extractor."""

    langs: tuple[str, ...]
    max_words: int
    page_words: int
    sponsorblock_url: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        """Read the configuration; an invalid value raises ValueError."""
        return cls(
            langs=parse_langs(env.get("TRANSCRIPT_LANGS", DEFAULT_LANGS)),
            max_words=_int_at_least(env, "MAX_WORDS", DEFAULT_MAX_WORDS, 2),
            page_words=_int_at_least(env, "PAGE_WORDS", DEFAULT_PAGE_WORDS, 1),
            sponsorblock_url=env.get("SPONSORBLOCK_URL", DEFAULT_SPONSORBLOCK_URL),
        )


def _empty(video_id: str, status: TranscriptStatus) -> TranscriptResult:
    return TranscriptResult(
        video_id=video_id,
        status=status,
        lang=None,
        source=None,
        word_count=0,
        truncated=False,
        sponsor_ratio=None,
        pages=[],
    )


def _transcript(
    video_id: str, config: Config, extractor: Extractor, request_id: str | None
) -> tuple[TranscriptResult, SponsorBlockState | None]:
    extraction = extractor.extract(video_id)
    if isinstance(extraction, Failure):
        return _empty(video_id, TranscriptStatus(extraction.value)), None
    track = choose_track(extraction.tracks, config.langs)
    if track is None:
        return _empty(video_id, TranscriptStatus.no_transcript), None
    sponsorblock = fetch_segments(video_id, config.sponsorblock_url, request_id=request_id)
    text, truncated = truncate(
        paragraphs(parse_vtt(track.vtt), sponsorblock.segments), config.max_words
    )
    pages = paginate(text, config.page_words)
    result = TranscriptResult(
        video_id=video_id,
        status=TranscriptStatus.ok,
        lang=track.lang,
        source=TranscriptSource(track.source.value),
        word_count=sum(
            count_words(paragraph) for page in pages for paragraph in page.split("\n\n")
        ),
        truncated=truncated,
        sponsor_ratio=(
            None
            if sponsorblock.state is SponsorBlockState.error
            else sponsor_ratio(sponsorblock.segments, extraction.duration)
        ),
        pages=pages,
    )
    return result, sponsorblock.state


def run(
    video_id: str, config: Config, extractor: Extractor, request_id: str | None = None
) -> TranscriptResult:
    """Produce the transcript result of one video and log `fetch.transcript`."""
    started = time.monotonic()
    result, sponsorblock = _transcript(video_id, config, extractor, request_id)
    emit(
        "fetch.transcript",
        request_id=request_id,
        video_id=video_id,
        attrs={
            "outcome": result.status.value,
            "source": None if result.source is None else result.source.value,
            "words": result.word_count,
            "pages": len(result.pages),
            "sponsor_ratio": result.sponsor_ratio,
            "sponsorblock": None if sponsorblock is None else sponsorblock.value,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return result
