"""load_pr tests. `tmp_path` is a pytest fixture: pytest sees the argument name and
passes in a fresh empty temporary folder for each test."""

import json

from app.reviewer.load import load_pr


def test_reads_diff_title_and_description(tmp_path):
    (tmp_path / "pr_99.diff").write_text("--- a/x.py\n+++ b/x.py\n", encoding="utf-8")
    meta = {"title": "Fix x", "description": "Fixes x.", "bugs": [{"line": 3}]}
    (tmp_path / "pr_99.json").write_text(json.dumps(meta), encoding="utf-8")

    pr = load_pr(tmp_path / "pr_99.diff")

    assert pr.diff == "--- a/x.py\n+++ b/x.py\n"
    assert pr.title == "Fix x"
    assert pr.description == "Fixes x."
    assert not hasattr(pr, "bugs")  # the answer key must not come through


def test_no_json_gives_empty_title_and_description(tmp_path):
    (tmp_path / "pasted.diff").write_text("diff text", encoding="utf-8")
    pr = load_pr(str(tmp_path / "pasted.diff"))  # also accepts a plain string path
    assert (pr.diff, pr.title, pr.description) == ("diff text", "", "")


def test_missing_keys_default_to_empty(tmp_path):
    (tmp_path / "pr_98.diff").write_text("d", encoding="utf-8")
    (tmp_path / "pr_98.json").write_text(json.dumps({"title": "Only a title"}), encoding="utf-8")
    pr = load_pr(tmp_path / "pr_98.diff")
    assert (pr.title, pr.description) == ("Only a title", "")
