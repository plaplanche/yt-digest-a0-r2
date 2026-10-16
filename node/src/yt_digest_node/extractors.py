"""Extractors: a video's duration and subtitle tracks, and the choice of one track (spec 5.2)."""

import json
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

DEFAULT_DELAY = "2-5"
WATCH_URL = "https://www.youtube.com/watch?v="


class Source(StrEnum):
    """Where a track comes from: uploaded by the author (`manual`) or generated (`auto`)."""

    manual = "manual"
    auto = "auto"


class Failure(StrEnum):
    """Why an extractor got no tracks."""

    unavailable = "unavailable"
    blocked = "blocked"


@dataclass(frozen=True)
class Track:
    lang: str
    source: Source
    vtt: str


@dataclass(frozen=True)
class Extraction:
    """A video's duration in seconds and its subtitle tracks."""

    duration: float
    tracks: tuple[Track, ...]


class Extractor(Protocol):
    def extract(self, video_id: str) -> Extraction | Failure: ...


class FakeExtractor:
    """Reads `<directory>/<video_id>/`: `meta.json` and one `<lang>.<manual|auto>.vtt` per track."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def extract(self, video_id: str) -> Extraction | Failure:
        video_dir = self.directory / video_id
        if not video_dir.is_dir():
            return Failure.unavailable
        meta = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
        if "status" in meta:
            return Failure(meta["status"])
        tracks: list[Track] = []
        for path in sorted(video_dir.glob("*.vtt")):
            lang, _, source = path.stem.rpartition(".")
            if lang and source in Source.__members__:
                tracks.append(Track(lang, Source(source), path.read_text(encoding="utf-8")))
        return Extraction(float(meta["duration"]), tuple(tracks))


class YoutubeDLLike(Protocol):
    """The part of `yt_dlp.YoutubeDL` the extractor uses, so tests can pass a stub."""

    def __enter__(self) -> "YoutubeDLLike": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> object: ...

    def extract_info(self, url: str, download: bool = ...) -> Any: ...

    def urlopen(self, req: str) -> Any: ...


YT_DLP_OPTIONS: Mapping[str, object] = {
    "skip_download": True,
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitlesformat": "vtt",
    "quiet": True,
    "no_warnings": True,
}


def parse_delay(value: str) -> tuple[float, float]:
    """`YT_DELAY_SECONDS`: a range `low-high`, or one number, in seconds."""
    low, _, high = value.partition("-")
    bounds = (float(low), float(high or low))
    if bounds[0] < 0 or bounds[1] < bounds[0]:
        raise ValueError(f"invalid delay range {value!r}")
    return bounds


def _failure(error: DownloadError) -> Failure:
    message = str(error).lower().replace("’", "'")
    return Failure.blocked if "not a bot" in message else Failure.unavailable


class YtDlpExtractor:
    """yt-dlp as a library, fetching the VTT tracks of the languages asked for.

    A random delay within `delay` seconds is waited before each request to YouTube.
    """

    def __init__(
        self,
        langs: Sequence[str],
        delay: tuple[float, float],
        *,
        ydl_factory: Callable[[dict[str, object]], YoutubeDLLike] = YoutubeDL,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.langs = tuple(langs)
        self.delay = delay
        self.ydl_factory = ydl_factory
        self.sleep = sleep

    def _wait(self) -> None:
        self.sleep(random.uniform(*self.delay))

    def extract(self, video_id: str) -> Extraction | Failure:
        try:
            with self.ydl_factory(dict(YT_DLP_OPTIONS)) as ydl:
                self._wait()
                info = ydl.extract_info(WATCH_URL + video_id, download=False)
                tracks: list[Track] = []
                for source, key in (
                    (Source.manual, "subtitles"),
                    (Source.auto, "automatic_captions"),
                ):
                    available: dict[str, list[dict[str, Any]]] = info.get(key) or {}
                    for lang in self.langs:
                        url = next(
                            (f["url"] for f in available.get(lang, []) if f.get("ext") == "vtt"),
                            None,
                        )
                        if url is not None:
                            self._wait()
                            vtt = ydl.urlopen(url).read().decode("utf-8")
                            tracks.append(Track(lang, source, vtt))
        except DownloadError as error:
            return _failure(error)
        return Extraction(float(info.get("duration") or 0), tuple(tracks))


def extractor_from_env(env: Mapping[str, str], langs: Sequence[str]) -> Extractor:
    """The fake extractor when `FETCHER_FAKE_YTDLP=1` (no delay), else the yt-dlp extractor."""
    if env.get("FETCHER_FAKE_YTDLP") == "1":
        directory = env.get("FAKE_YTDLP_DIR")
        if not directory:
            raise ValueError("FAKE_YTDLP_DIR is required when FETCHER_FAKE_YTDLP=1")
        return FakeExtractor(Path(directory))
    return YtDlpExtractor(langs, parse_delay(env.get("YT_DELAY_SECONDS", DEFAULT_DELAY)))


def choose_track(tracks: Sequence[Track], langs: Sequence[str]) -> Track | None:
    """The first track found trying `manual` tracks in language order, then `auto` ones; None
    means `no_transcript`."""
    for source in (Source.manual, Source.auto):
        for lang in langs:
            for track in tracks:
                if track.source is source and track.lang == lang:
                    return track
    return None
