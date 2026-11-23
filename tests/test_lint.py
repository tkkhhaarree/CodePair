"""These tests use the real demo repo (TARGET_REPO_PATH in .env)."""

import os

import pytest
from dotenv import load_dotenv

from app.lint import PatchError, lint_diff

load_dotenv()
pytestmark = pytest.mark.skipif(
    not os.environ.get("TARGET_REPO_PATH"), reason="TARGET_REPO_PATH not set"
)

# Adds an unused import on new line 7 of utils.py.
UNUSED_IMPORT_DIFF = """\
--- a/src/marshmallow/utils.py
+++ b/src/marshmallow/utils.py
@@ -5,3 +5,4 @@
 import datetime as dt
 import inspect
+import os
 import typing
"""


def test_finds_ruff_issue_on_added_line():
    findings = lint_diff(UNUSED_IMPORT_DIFF)
    assert [(f.file, f.line, f.code) for f in findings] == [
        ("src/marshmallow/utils.py", 7, "F401")
    ]


def test_broken_diff_raises_patch_error():
    # Context line does not match the base file, so the patch must be refused.
    broken = UNUSED_IMPORT_DIFF.replace(" import inspect", " import inspectx")
    with pytest.raises(PatchError):
        lint_diff(broken)
