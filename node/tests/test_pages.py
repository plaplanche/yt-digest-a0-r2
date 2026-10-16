from yt_digest_node.pages import MARKER, count_words, paginate, truncate


def words(start: int, end: int) -> str:
    return " ".join(f"w{i}" for i in range(start, end + 1))


# Truncation


def test_25_words_with_max_10_keep_the_first_5_and_last_5_around_the_marker() -> None:
    text, truncated = truncate([words(1, 8), words(9, 20), words(21, 25)], 10)
    assert text == [words(1, 5), MARKER, words(21, 25)]
    assert truncated is True
    assert sum(count_words(paragraph) for paragraph in text) == 10


def test_truncation_keeps_the_paragraph_breaks_inside_the_kept_words() -> None:
    text, truncated = truncate(["a b", "c d e f", "g h", "i"], 6)
    assert text == ["a b", "c", MARKER, "g h", "i"]
    assert truncated is True


def test_odd_max_keeps_half_rounded_down_on_each_side() -> None:
    text, _ = truncate([words(1, 20)], 11)
    assert text == [words(1, 5), MARKER, words(16, 20)]


def test_text_at_the_limit_is_not_truncated() -> None:
    assert truncate([words(1, 4), words(5, 10)], 10) == ([words(1, 4), words(5, 10)], False)


def test_marker_is_not_a_word() -> None:
    assert count_words(MARKER) == 0
    assert count_words("a  b\tc") == 3


# Pages


def test_paragraphs_are_grouped_into_pages_of_at_most_5_words_and_a_12_word_one_is_cut() -> None:
    paragraphs = ["a b", "c d e", "f", words(1, 12), "g h"]
    pages = paginate(paragraphs, 5)
    assert pages == [
        "a b\n\nc d e",
        "f",
        words(1, 5),
        words(6, 10),
        "w11 w12\n\ng h",
    ]
    assert all(0 < len(page.split()) <= 5 for page in pages)
    assert " ".join(pages).split() == " ".join(paragraphs).split()


def test_pages_joined_give_back_the_text_when_no_paragraph_is_cut() -> None:
    paragraphs = ["a b c", "d e", "f g h i", "j"]
    pages = paginate(paragraphs, 5)
    assert pages == ["a b c\n\nd e", "f g h i\n\nj"]
    assert "\n\n".join(pages) == "\n\n".join(paragraphs)


def test_marker_stays_on_the_page_it_follows() -> None:
    assert paginate(["a b", MARKER, "c d"], 2) == [f"a b\n\n{MARKER}", "c d"]


def test_no_text_gives_no_page() -> None:
    assert paginate([], 5) == []
