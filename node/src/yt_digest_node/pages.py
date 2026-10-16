"""Truncation and pages: from clean paragraphs to the pages of the result (spec 5.5 and 5.6)."""

from collections.abc import Sequence

MARKER = "[…]"


def count_words(paragraph: str) -> int:
    """Whitespace-separated tokens; the truncation marker is not a word."""
    return 0 if paragraph == MARKER else len(paragraph.split())


def truncate(paragraphs: Sequence[str], max_words: int) -> tuple[list[str], bool]:
    """When the text has more than `max_words` words, keep the first and the last
    `max_words // 2` words with their paragraph breaks, around a `[…]` paragraph."""
    words = [paragraph.split() for paragraph in paragraphs]
    if sum(len(paragraph) for paragraph in words) <= max_words:
        return list(paragraphs), False
    keep = max_words // 2
    head = _first_words(words, keep)
    tail = [p[::-1] for p in reversed(_first_words([p[::-1] for p in reversed(words)], keep))]
    return [" ".join(p) for p in head] + [MARKER] + [" ".join(p) for p in tail], True


def _first_words(words: list[list[str]], count: int) -> list[list[str]]:
    """The first `count` words, still split into their paragraphs."""
    taken: list[list[str]] = []
    for paragraph in words:
        if count <= 0:
            break
        taken.append(paragraph[:count])
        count -= len(taken[-1])
    return [paragraph for paragraph in taken if paragraph]


def paginate(paragraphs: Sequence[str], page_words: int) -> list[str]:
    """Group paragraphs into pages of at most `page_words` words, cutting a longer paragraph at
    word boundaries; paragraphs of a page are joined by a blank line and no page is empty."""
    pieces: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if count_words(paragraph) > page_words:
            pieces.extend(
                " ".join(words[i : i + page_words]) for i in range(0, len(words), page_words)
            )
        elif words:
            pieces.append(paragraph)
    pages: list[list[str]] = []
    used = 0
    for piece in pieces:
        count = count_words(piece)
        if not pages or used + count > page_words:
            pages.append([])
            used = 0
        pages[-1].append(piece)
        used += count
    return ["\n\n".join(page) for page in pages]
