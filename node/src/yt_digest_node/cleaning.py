"""Transcript cleaning: from VTT text to paragraphs of clean text (spec section 5.4)."""

import html
import re
from collections.abc import Sequence
from dataclasses import dataclass

_TIMING = re.compile(r"^\s*(\S+)\s+-->\s+(\S+)")
_TIMESTAMP = re.compile(r"^(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})$")
_IGNORED_BLOCKS = ("NOTE", "STYLE", "REGION")
_TAG = re.compile(r"<[^>]*>")
_ANNOTATION = re.compile(r"\[[^\]]*\]")
_WHITESPACE = re.compile(r"\s+")
_PARAGRAPH_GAP_MS = 2000


@dataclass(frozen=True)
class Cue:
    """One VTT cue: start and end in seconds, and its raw text lines."""

    start: float
    end: float
    lines: tuple[str, ...]


def _seconds(timestamp: str) -> float:
    match = _TIMESTAMP.match(timestamp)
    if match is None:
        raise ValueError(f"invalid VTT timestamp {timestamp!r}")
    hours, minutes, seconds, millis = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_vtt(text: str) -> list[Cue]:
    """Parse VTT text into cues, ignoring the header, NOTE, STYLE and REGION blocks and cue
    settings (step 1)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").split("\n")
    blocks: list[list[str]] = [[]]
    for line in lines:
        if line:
            blocks[-1].append(line)
        elif blocks[-1]:
            blocks.append([])
    cues: list[Cue] = []
    for index, block in enumerate(blocks):
        if not block or (index == 0 and block[0].startswith("WEBVTT")):
            continue
        first_word = block[0].split(maxsplit=1)[:1]
        if first_word and first_word[0] in _IGNORED_BLOCKS:
            continue
        timing = next((i for i, line in enumerate(block[:2]) if "-->" in line), None)
        if timing is None:
            continue
        match = _TIMING.match(block[timing])
        if match is None:
            continue
        start, end = match.groups()
        cues.append(Cue(_seconds(start), _seconds(end), tuple(block[timing + 1 :])))
    return cues


def clean_line(line: str) -> str:
    """Remove inline tags, decode HTML entities, remove bracketed annotations, collapse
    whitespace and trim (step 3)."""
    line = _TAG.sub("", line)
    line = html.unescape(line)
    line = _ANNOTATION.sub("", line)
    return _WHITESPACE.sub(" ", line).strip()


def _in_segment(cue: Cue, segments: Sequence[tuple[float, float]]) -> bool:
    midpoint = (cue.start + cue.end) / 2
    return any(start <= midpoint < end for start, end in segments)


def paragraphs(cues: Sequence[Cue], segments: Sequence[tuple[float, float]]) -> list[str]:
    """Turn cues into paragraphs (steps 2 to 5): drop cues in a sponsor segment, clean the
    lines, drop empty and repeated lines, and start a paragraph after a gap of 2.0 s or more."""
    result: list[list[str]] = []
    previous_line: str | None = None
    previous_end: float | None = None
    for cue in cues:
        if _in_segment(cue, segments):
            continue
        kept: list[str] = []
        for raw in cue.lines:
            line = clean_line(raw)
            if line and line != previous_line:
                kept.append(line)
                previous_line = line
        if not kept:
            continue
        gap_ms = None if previous_end is None else round((cue.start - previous_end) * 1000)
        if gap_ms is None or gap_ms >= _PARAGRAPH_GAP_MS:
            result.append([])
        result[-1].extend(kept)
        previous_end = cue.end
    return [" ".join(paragraph) for paragraph in result]
