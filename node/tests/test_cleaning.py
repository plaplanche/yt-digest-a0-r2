from pathlib import Path

import pytest

from yt_digest_node.cleaning import Cue, clean_line, paragraphs, parse_vtt

FIXTURES = Path(__file__).parent / "fixtures" / "vtt"


def load(name: str) -> list[Cue]:
    return parse_vtt((FIXTURES / name).read_text(encoding="utf-8"))


# Step 1: parsing


def test_parse_ignores_header_note_style_region_and_cue_settings() -> None:
    assert load("manual.vtt") == [
        Cue(1.0, 3.0, ("Bonjour à tous,",)),
        Cue(3.5, 5.0, ("<v Marie>bienvenue dans <i>cette</i> vidéo.</v>",)),
        Cue(7.0, 9.0, ("Un écart de deux secondes",)),
        Cue(10.9, 12.0, ("ne coupe pas", "le paragraphe à 1,9 s.")),
        Cue(60.0, 62.5, ("<b>Fin</b>.",)),
    ]


def test_parse_keeps_whitespace_lines_inside_auto_cues() -> None:
    cues = load("auto.vtt")
    assert len(cues) == 5
    assert cues[0] == Cue(
        0.0,
        2.0,
        (" ", "so<00:00:00.400><c> today</c><00:00:00.800><c> we</c><00:00:01.200><c> talk</c>"),
    )
    assert cues[1] == Cue(2.0, 2.01, ("so today we talk", " "))


def test_parse_reads_hours_crlf_and_bom() -> None:
    text = "﻿WEBVTT\r\n\r\n01:02:03.004 --> 01:02:05.000\r\nhello\r\n"
    assert parse_vtt(text) == [Cue(3723.004, 3725.0, ("hello",))]


# Step 3: cleaning each line


def test_clean_line_removes_inline_timestamps_and_class_tags() -> None:
    raw = "about<00:00:02.500><c.colorE5E5E5> rolling</c><00:00:03.000><c> captions</c>"
    assert clean_line(raw) == "about rolling captions"


def test_clean_line_removes_style_and_voice_tags() -> None:
    assert clean_line("<v Marie>bienvenue dans <i>cette</i> <u>belle</u> <b>vidéo</b>.</v>") == (
        "bienvenue dans cette belle vidéo."
    )


def test_clean_line_decodes_entities_after_removing_tags() -> None:
    assert clean_line("Tom &amp; Jerry &lt;3") == "Tom & Jerry <3"


@pytest.mark.parametrize("annotation", ["[Musique]", "[Applause]"])
def test_clean_line_removes_bracketed_annotations(annotation: str) -> None:
    assert clean_line(f"merci {annotation} beaucoup") == "merci beaucoup"
    assert clean_line(annotation) == ""


def test_clean_line_collapses_whitespace_and_trims() -> None:
    assert clean_line("  caf&eacute;&nbsp;&nbsp;  au \t lait ") == "café au lait"


def test_annotations_fixture() -> None:
    assert paragraphs(load("annotations.vtt"), []) == ["Tom & Jerry <3 café au lait"]


# Step 4: empty lines and rolling duplicates


def test_rolling_duplicates_and_empty_lines_are_dropped() -> None:
    assert paragraphs(load("auto.vtt"), []) == [
        "so today we talk about rolling captions and duplicates"
    ]


def test_only_a_line_equal_to_the_previous_kept_line_is_dropped() -> None:
    cues = [Cue(0.0, 1.0, ("oui", "non")), Cue(1.0, 2.0, ("oui", "oui"))]
    assert paragraphs(cues, []) == ["oui non oui"]


# Step 5: paragraphs


def test_manual_fixture_paragraphs() -> None:
    assert paragraphs(load("manual.vtt"), []) == [
        "Bonjour à tous, bienvenue dans cette vidéo.",
        "Un écart de deux secondes ne coupe pas le paragraphe à 1,9 s.",
        "Fin.",
    ]


def test_gap_of_2_0_s_starts_a_paragraph_and_1_9_s_does_not() -> None:
    cues = [Cue(0.0, 1.1, ("un",)), Cue(3.1, 4.0, ("deux",)), Cue(5.9, 6.0, ("trois",))]
    assert paragraphs(cues, []) == ["un", "deux trois"]


def test_gap_is_measured_from_the_last_kept_cue() -> None:
    cues = [Cue(0.0, 1.0, ("un",)), Cue(1.5, 2.5, ("[Musique]",)), Cue(3.0, 4.0, ("deux",))]
    assert paragraphs(cues, []) == ["un", "deux"]


def test_no_cue_gives_no_paragraph() -> None:
    assert paragraphs([], []) == []


# Step 2: sponsor segments (start inclusive, end exclusive on the cue midpoint)


def test_cues_whose_midpoint_lies_in_a_segment_are_dropped() -> None:
    cues = [
        Cue(0.0, 2.0, ("avant",)),  # midpoint 1.0: segment start, dropped
        Cue(2.0, 4.0, ("dedans",)),  # midpoint 3.0: dropped
        Cue(4.0, 6.0, ("après",)),  # midpoint 5.0: segment end, kept
    ]
    assert paragraphs(cues, [(1.0, 5.0)]) == ["après"]
