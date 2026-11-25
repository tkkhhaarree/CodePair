"""Post-filter tests: plain code, no LLM call."""

from app.lint import LintFinding
from app.reviewer.filter import filter_comments
from app.schemas import ReviewComment

COMMENTABLE = {("src/x.py", 12), ("src/x.py", 40), ("src/x.py", 41)}
RUFF = [
    LintFinding("src/x.py", 12, "F401", "`os` imported but unused"),
    LintFinding("src/x.py", 40, "B006", "Do not use mutable data structures for argument defaults"),
]


def comment(file: str, line: int, message: str) -> ReviewComment:
    return ReviewComment(
        file=file, line=line, severity="major", category="logic-bug",
        message=message, suggested_fix=None,
    )


def test_keeps_valid_comment():
    kept, dropped = filter_comments([comment("src/x.py", 41, "off by one")], COMMENTABLE, RUFF)
    assert len(kept) == 1 and dropped == []


def test_drops_file_not_in_diff():
    _, dropped = filter_comments([comment("src/other.py", 5, "bug")], COMMENTABLE, RUFF)
    assert "not in the diff" in dropped[0].reason


def test_drops_line_not_in_diff():
    _, dropped = filter_comments([comment("src/x.py", 99, "bug")], COMMENTABLE, RUFF)
    assert "line 99" in dropped[0].reason


def test_normalises_b_prefix():
    kept, _ = filter_comments([comment("b/src/x.py", 41, "bug")], COMMENTABLE, RUFF)
    assert kept[0].file == "src/x.py"


def test_option_a_drops_same_topic_on_ruff_line():
    _, dropped = filter_comments(
        [comment("src/x.py", 12, "`os` is imported but never used")], COMMENTABLE, RUFF
    )
    assert "repeats ruff F401" in dropped[0].reason


def test_option_a_keeps_different_bug_on_ruff_line():
    # Same line as ruff's B006, but about a different problem: must be kept.
    kept, dropped = filter_comments(
        [comment("src/x.py", 40, "`path` is not checked for None; load(None) raises TypeError")],
        COMMENTABLE, RUFF,
    )
    assert len(kept) == 1 and dropped == []
