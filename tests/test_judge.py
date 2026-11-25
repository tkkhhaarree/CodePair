"""diff_excerpt tests (no LLM call)."""

from app.diff import parse_diff
from evals.judge import diff_excerpt
from tests.test_diff import SMALL_DIFF

# SMALL_DIFF, numbered:
#    10       a = 1
#       -     b = 2      <- removed; position = last numbered line before it = 10
#    11 +     b = 3
#    12 +     c = 4
#    13
#    14       return a


def test_excerpt_around_line_11_radius_1():
    text = diff_excerpt(parse_diff(SMALL_DIFF), "pkg/mod.py", 11, radius=1)
    assert text.splitlines() == [
        "   10       a = 1",
        "      -     b = 2",
        "   11 +     b = 3",
        "   12 +     c = 4",
    ]


def test_excerpt_removed_line_follows_previous_number():
    # Around line 14 with radius 1: lines 13 and 14 only; the removed line (position 10) is out.
    text = diff_excerpt(parse_diff(SMALL_DIFF), "pkg/mod.py", 14, radius=1)
    assert [ln.strip() for ln in text.splitlines()] == ["13", "14       return a"]


def test_excerpt_other_file_is_empty():
    assert diff_excerpt(parse_diff(SMALL_DIFF), "other.py", 11) == ""
