import io
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from yt_digest_node.extractors import (
    Extraction,
    Failure,
    FakeExtractor,
    Source,
    Track,
    YtDlpExtractor,
    choose_track,
    extractor_from_env,
    parse_delay,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ytdlp"
LANGS = ("fr", "en")


def track(lang: str, source: Source) -> Track:
    return Track(lang, source, f"WEBVTT {lang} {source}")


# Fake extractor


def test_fake_missing_directory_is_unavailable() -> None:
    assert FakeExtractor(FIXTURES).extract("missingVid1") is Failure.unavailable


def test_fake_meta_status_blocked_is_blocked() -> None:
    assert FakeExtractor(FIXTURES).extract("blockedVid1") is Failure.blocked


def test_fake_meta_status_unavailable_is_unavailable_despite_tracks() -> None:
    assert FakeExtractor(FIXTURES).extract("unavailVid1") is Failure.unavailable


def test_fake_reads_duration_and_tracks() -> None:
    result = FakeExtractor(FIXTURES).extract("frAutoEnMan")
    assert isinstance(result, Extraction)
    assert result.duration == 95.5
    assert {(t.lang, t.source) for t in result.tracks} == {
        ("en", Source.manual),
        ("fr", Source.auto),
    }
    en = next(t for t in result.tracks if t.lang == "en")
    assert en.vtt == (FIXTURES / "frAutoEnMan" / "en.manual.vtt").read_text()


def test_fake_ignores_files_not_named_lang_source_vtt(tmp_path: Path) -> None:
    video = tmp_path / "otherFiles1"
    video.mkdir()
    (video / "meta.json").write_text('{"duration": 10}')
    (video / "fr.vtt").write_text("WEBVTT")
    (video / "fr.forced.vtt").write_text("WEBVTT")
    (video / "en.manual.txt").write_text("WEBVTT")
    (video / "en.manual.vtt").write_text("WEBVTT")
    result = FakeExtractor(tmp_path).extract("otherFiles1")
    assert isinstance(result, Extraction)
    assert [(t.lang, t.source) for t in result.tracks] == [("en", Source.manual)]


# Track choice


def test_choice_manual_in_a_later_language_beats_auto_in_the_first() -> None:
    result = FakeExtractor(FIXTURES).extract("frAutoEnMan")
    assert isinstance(result, Extraction)
    chosen = choose_track(result.tracks, LANGS)
    assert chosen is not None
    assert (chosen.lang, chosen.source) == ("en", Source.manual)


def test_choice_only_other_language_is_no_transcript() -> None:
    result = FakeExtractor(FIXTURES).extract("onlyGerman1")
    assert isinstance(result, Extraction)
    assert choose_track(result.tracks, LANGS) is None


def test_choice_follows_language_order_within_a_source() -> None:
    tracks = [track("en", Source.manual), track("fr", Source.manual)]
    chosen = choose_track(tracks, LANGS)
    assert chosen is not None and chosen.lang == "fr"
    chosen = choose_track(tracks, ("en", "fr"))
    assert chosen is not None and chosen.lang == "en"


def test_choice_falls_back_to_auto_in_language_order() -> None:
    tracks = [track("de", Source.manual), track("en", Source.auto), track("fr", Source.auto)]
    chosen = choose_track(tracks, LANGS)
    assert chosen is not None
    assert (chosen.lang, chosen.source) == ("fr", Source.auto)


# yt-dlp extractor, with yt-dlp replaced by a stub


class StubYoutubeDL:
    """Records the options and URLs; answers with `info` or raises `error`."""

    def __init__(self, info: dict[str, Any] | None = None, error: str | None = None) -> None:
        self.info = info or {}
        self.error = error
        self.options: dict[str, object] | None = None
        self.calls: list[str] = []

    def __call__(self, options: dict[str, object]) -> "StubYoutubeDL":
        self.options = options
        return self

    def __enter__(self) -> "StubYoutubeDL":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        assert download is False
        self.calls.append(url)
        if self.error is not None:
            raise DownloadError(self.error)
        return self.info

    def urlopen(self, req: str) -> io.BytesIO:
        self.calls.append(req)
        return io.BytesIO(f"WEBVTT {req}".encode())


INFO = {
    "duration": 212,
    "subtitles": {
        "en": [{"ext": "json3", "url": "en-json3"}, {"ext": "vtt", "url": "en-manual"}],
        "de": [{"ext": "vtt", "url": "de-manual"}],
    },
    "automatic_captions": {"fr": [{"ext": "vtt", "url": "fr-auto"}]},
}


def extractor(stub: StubYoutubeDL, sleeps: list[float]) -> YtDlpExtractor:
    return YtDlpExtractor(LANGS, (2.0, 5.0), ydl_factory=stub, sleep=sleeps.append)


def test_ytdlp_options() -> None:
    stub = StubYoutubeDL(INFO)
    extractor(stub, []).extract("dQw4w9WgXcQ")
    assert stub.options is not None
    assert stub.options["skip_download"] is True
    assert stub.options["writesubtitles"] is True
    assert stub.options["writeautomaticsub"] is True
    assert stub.options["subtitlesformat"] == "vtt"
    assert not {"cookiefile", "cookiesfrombrowser"} & stub.options.keys()


def test_ytdlp_returns_duration_and_vtt_tracks_of_the_languages() -> None:
    stub = StubYoutubeDL(INFO)
    result = extractor(stub, []).extract("dQw4w9WgXcQ")
    assert result == Extraction(
        212.0,
        (
            Track("en", Source.manual, "WEBVTT en-manual"),
            Track("fr", Source.auto, "WEBVTT fr-auto"),
        ),
    )
    assert stub.calls == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "en-manual", "fr-auto"]


def test_ytdlp_waits_a_random_delay_before_each_request() -> None:
    sleeps: list[float] = []
    stub = StubYoutubeDL(INFO)
    extractor(stub, sleeps).extract("dQw4w9WgXcQ")
    assert len(sleeps) == len(stub.calls) == 3
    assert all(2.0 <= s <= 5.0 for s in sleeps)


@pytest.mark.parametrize(
    "message",
    [
        "ERROR: [youtube] dQw4w9WgXcQ: Private video. Sign in if you've been granted access",
        "ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm your age",
        "ERROR: [youtube] dQw4w9WgXcQ: This video has been removed by the uploader",
        "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable",
    ],
)
def test_ytdlp_unavailable_errors(message: str) -> None:
    result = extractor(StubYoutubeDL(error=message), []).extract("dQw4w9WgXcQ")
    assert result is Failure.unavailable


@pytest.mark.parametrize("apostrophe", ["'", "’"])
def test_ytdlp_bot_check_is_blocked(apostrophe: str) -> None:
    message = f"ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm you{apostrophe}re not a bot"
    result = extractor(StubYoutubeDL(error=message), []).extract("dQw4w9WgXcQ")
    assert result is Failure.blocked


# Configuration


def test_parse_delay() -> None:
    assert parse_delay("2-5") == (2.0, 5.0)
    assert parse_delay("0") == (0.0, 0.0)
    with pytest.raises(ValueError):
        parse_delay("5-2")
    with pytest.raises(ValueError):
        parse_delay("soon")


def test_env_selects_fake_extractor() -> None:
    env = {"FETCHER_FAKE_YTDLP": "1", "FAKE_YTDLP_DIR": str(FIXTURES), "YT_DELAY_SECONDS": "9"}
    chosen = extractor_from_env(env, LANGS)
    assert isinstance(chosen, FakeExtractor)
    assert chosen.directory == FIXTURES


def test_env_fake_extractor_requires_its_directory() -> None:
    with pytest.raises(ValueError):
        extractor_from_env({"FETCHER_FAKE_YTDLP": "1"}, LANGS)


def test_env_defaults_to_ytdlp_extractor_with_delay() -> None:
    chosen = extractor_from_env({}, LANGS)
    assert isinstance(chosen, YtDlpExtractor)
    assert chosen.delay == (2.0, 5.0)
    assert chosen.langs == LANGS
    chosen = extractor_from_env({"YT_DELAY_SECONDS": "1-3"}, LANGS)
    assert isinstance(chosen, YtDlpExtractor)
    assert chosen.delay == (1.0, 3.0)
