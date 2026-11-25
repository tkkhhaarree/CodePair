"""Post-filter: code that checks the LLM's comments against rules code can verify.

A prompt asks; this enforces. Dropped comments are kept with a reason, so we can
measure how often the model breaks the rules.
"""

import re
from dataclasses import dataclass

from app.lint import LintFinding
from app.schemas import ReviewComment


@dataclass
class DroppedComment:
    comment: ReviewComment
    reason: str


def _normalise_path(path: str) -> str:
    """The model sometimes writes 'b/src/x.py' or './src/x.py'; the diff says 'src/x.py'."""
    path = path.strip().replace("\\", "/")
    for prefix in ("./", "a/", "b/"):
        path = path.removeprefix(prefix)  # removes it only if the string starts with it
    return path


def _repeats_ruff(comment: ReviewComment, findings: list[LintFinding]) -> LintFinding | None:
    """Option A: same file and line as a ruff finding AND about the same thing.

    "Same thing" = the comment mentions ruff's rule code (e.g. F401) or a name ruff
    put in backticks in its message (e.g. `os` in "`os` imported but unused").
    """
    for f in findings:
        if (f.file, f.line) != (comment.file, comment.line):
            continue
        names = re.findall(r"`([^`]+)`", f.message)  # text between backticks
        if f.code in comment.message or any(name in comment.message for name in names):
            return f
    return None


def filter_comments(
    comments: list[ReviewComment],
    commentable: set[tuple[str, int]],
    ruff_findings: list[LintFinding],
) -> tuple[list[ReviewComment], list[DroppedComment]]:
    """Split the LLM's comments into (kept, dropped-with-reason).

    commentable   = set of (file, line) pairs shown in the diff, e.g. {("src/x.py", 12), ...}
    ruff_findings = the PR's ruff findings (passed on to _repeats_ruff)
    """
    # TODO 1: make the set of file paths that appear in `commentable`
    #         (each item is a (file, line) pair - you only want the file part).
    files = {file for file, _ in commentable}
    # TODO 2: start two empty lists: kept and dropped.
    kept = []
    dropped = []
    # TODO 3: for each comment:
    for comment in comments:
        #   a. fix its path with _normalise_path(). Pydantic objects shouldn't be changed
        #      in place, so make a copy: comment.model_copy(update={"file": new_path})
        normalized_path = _normalise_path(comment.file)
        comment = comment.model_copy(update={"file": normalized_path})
        #   b. file not in the diff's files      -> dropped, reason "file <file> is not in the diff"
        if normalized_path not in files:
            dropped.append(
                DroppedComment(comment=comment, reason=f"file {comment.file} is not in the diff")
            )
        #   c. (file, line) not in commentable    -> dropped, reason "line <line> is not shown in the diff"
        elif (comment.file, comment.line) not in commentable:
            dropped.append(
                DroppedComment(
                    comment=comment, reason=f"line {comment.line} is not shown in the diff"
                )
            )
        #   d. _repeats_ruff(...) returns a finding -> dropped, reason "repeats ruff <code> on line <line>"
        elif (dup := _repeats_ruff(comment=comment, findings=ruff_findings)) is not None:
            dropped.append(
                DroppedComment(
                    comment=comment, reason=f"repeats ruff {dup.code} on line {dup.line}"
                )
            )
        #   e. otherwise                           -> kept
        else:
            kept.append(comment)
    #   A dropped item is DroppedComment(comment, reason).
    # TODO 4: return both lists, kept first.
    return (kept, dropped)
