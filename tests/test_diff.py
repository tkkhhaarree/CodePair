from pathlib import Path

from app.diff import added_lines, commentable_lines, format_for_llm, parse_diff

SMALL_DIFF = """\
diff --git a/pkg/mod.py b/pkg/mod.py
index 111..222 100644
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -10,4 +10,5 @@ def f():
     a = 1
-    b = 2
+    b = 3
+    c = 4

     return a
\\ No newline at end of file
"""


def test_line_numbers():
    files = parse_diff(SMALL_DIFF)
    assert len(files) == 1
    lines = files[0].hunks[0].lines
    # (kind, old_no, new_no) for each line, in order
    assert [(ln.kind, ln.old_no, ln.new_no) for ln in lines] == [
        ("context", 10, 10),
        ("remove", 11, None),
        ("add", None, 11),
        ("add", None, 12),
        ("context", 12, 13),  # blank line with the space stripped
        ("context", 13, 14),
    ]


def test_commentable_lines_skip_removed():
    files = parse_diff(SMALL_DIFF)
    assert commentable_lines(files) == {("pkg/mod.py", n) for n in (10, 11, 12, 13, 14)}


def test_added_lines_only_plus_lines():
    assert added_lines(parse_diff(SMALL_DIFF)) == {("pkg/mod.py", 11), ("pkg/mod.py", 12)}


def test_format_for_llm_shows_numbers():
    text = format_for_llm(parse_diff(SMALL_DIFF))
    assert "   11 +     b = 3" in text
    assert "      -     b = 2" in text  # removed line: no number


def test_new_file():
    diff = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+x = 1\n+y = 2\n"
    files = parse_diff(diff)
    assert files[0].is_new and files[0].path == "new.py"
    assert commentable_lines(files) == {("new.py", 1), ("new.py", 2)}


def test_real_pr_01_bug_line_is_commentable():
    diff = Path("evals/prs/pr_01.diff").read_text(encoding="utf-8")
    files = parse_diff(diff)
    assert ("src/marshmallow/fields.py", 786) in commentable_lines(files)
    line = next(
        ln for h in files[0].hunks for ln in h.lines if ln.new_no == 786 and ln.kind == "add"
    )
    assert "max_items" in line.text
