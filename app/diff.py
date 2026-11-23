"""Parse unified diffs (`git diff` output) into files, hunks and lines.

A diff only gives one start line number per hunk; every other line number is
implicit (count down, skipping removed lines). This module makes each line's
number explicit, so the LLM can read it and our code can check it.
"""

import re
import sys
from dataclasses import dataclass, field
from typing import Literal

LineKind = Literal["add", "remove", "context"]

# Matches "@@ -728,21 +728,31 @@ class List(...)". The ",21" counts are optional:
# "@@ -5 +5 @@" means a count of 1.
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class DiffLine:
    kind: LineKind
    text: str
    old_no: int | None  # line number in the old file (None for added lines)
    new_no: int | None  # line number in the new file (None for removed lines)


@dataclass
class Hunk:
    header: str
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    is_new: bool = False
    is_deleted: bool = False
    hunks: list[Hunk] = field(default_factory=list)


def _clean_path(raw: str) -> str | None:
    """'a/src/x.py' -> 'src/x.py'; '/dev/null' -> None (file did not exist)."""
    path = raw.split("\t")[0].strip()  # some tools add a tab + timestamp
    if path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path


def parse_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    current: FileDiff | None = None
    hunk: Hunk | None = None
    old_path: str | None = None
    old_no = new_no = 0  # next line number in the old / new file
    old_left = new_left = 0  # lines the hunk header says are still to come

    for raw in text.splitlines():
        # Inside a hunk, read exactly as many lines as the header promised.
        # Counting (instead of looking at the first character only) means a
        # removed line like "--- foo" is not mistaken for a file header.
        if hunk is not None and (old_left > 0 or new_left > 0):
            if raw.startswith("\\"):  # "\ No newline at end of file"
                continue
            sign, body = raw[:1], raw[1:]
            if sign == "+":
                hunk.lines.append(DiffLine("add", body, None, new_no))
                new_no += 1
                new_left -= 1
            elif sign == "-":
                hunk.lines.append(DiffLine("remove", body, old_no, None))
                old_no += 1
                old_left -= 1
            elif sign in (" ", ""):  # some tools strip the space on blank lines
                hunk.lines.append(DiffLine("context", body, old_no, new_no))
                old_no += 1
                new_no += 1
                old_left -= 1
                new_left -= 1
            else:
                raise ValueError(f"Unexpected line inside hunk: {raw!r}")
            continue

        # Outside a hunk: file headers and hunk headers.
        if raw.startswith("diff --git "):
            current, hunk, old_path = None, None, None
        elif raw.startswith("--- "):
            old_path = _clean_path(raw[4:])
        elif raw.startswith("+++ "):
            new_path = _clean_path(raw[4:])
            current = FileDiff(
                path=new_path or old_path or "",
                is_new=old_path is None,
                is_deleted=new_path is None,
            )
            files.append(current)
        elif raw.startswith("@@") and current is not None:
            match = HUNK_HEADER.match(raw)
            if match is None:
                raise ValueError(f"Bad hunk header: {raw!r}")
            old_no = int(match.group(1))
            old_left = int(match.group(2) or 1)
            new_no = int(match.group(3))
            new_left = int(match.group(4) or 1)
            hunk = Hunk(header=raw)
            current.hunks.append(hunk)
        # Anything else ("index ...", "new file mode", "\ No newline...") is skipped.

    return files


def format_for_llm(files: list[FileDiff]) -> str:
    """The diff with each line's NEW line number in front, e.g. '  786 + code'.

    Removed lines get no number: they do not exist in the new file.
    """
    signs = {"add": "+", "remove": "-", "context": " "}
    out: list[str] = []
    for f in files:
        status = " (new file)" if f.is_new else " (deleted)" if f.is_deleted else ""
        out.append(f"=== {f.path}{status} ===")
        for h in f.hunks:
            out.append(h.header)
            for line in h.lines:
                number = "" if line.new_no is None else str(line.new_no)
                out.append(f"{number:>5} {signs[line.kind]} {line.text}")
        out.append("")
    return "\n".join(out)


def commentable_lines(files: list[FileDiff]) -> set[tuple[str, int]]:
    """Every (file, new line number) shown in the diff: added and context lines.

    Removed lines have new_no=None, so they are left out automatically.
    """
    return {
        (f.path, line.new_no)
        for f in files
        for h in f.hunks
        for line in h.lines
        if line.new_no is not None
    }


def added_lines(files: list[FileDiff]) -> set[tuple[str, int]]:
    """Only the (file, new line number) pairs the PR added or changed ('+' lines)."""
    return {
        (f.path, line.new_no)
        for f in files
        for h in f.hunks
        for line in h.lines
        if line.kind == "add"
    }


if __name__ == "__main__":
    # Lets you run: python -m app.diff evals/prs/pr_01.diff
    with open(sys.argv[1], encoding="utf-8") as fh:
        parsed = parse_diff(fh.read())
    print(format_for_llm(parsed))
    print(f"{len(commentable_lines(parsed))} commentable lines in {len(parsed)} file(s)")
