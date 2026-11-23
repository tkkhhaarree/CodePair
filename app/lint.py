"""Run ruff on the files a diff changes, and keep only findings on added lines.

Ruff needs real files, but a diff only has fragments. So we rebuild the PR's
version of the code: take the base branch out of git into a temp folder, then
apply the diff on top. Ruff only reads the code (never runs it), so this is
safe outside the sandbox.
"""

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.diff import added_lines, parse_diff

BASE_REF = "demo-main"  # the branch every PR diff is made against


@dataclass
class LintFinding:
    file: str
    line: int
    code: str  # ruff rule code, e.g. "F401" (unused import)
    message: str


class PatchError(Exception):
    """The diff does not apply to the base code (wrong base or broken diff)."""


def build_pr_tree(repo: Path, base_ref: str, diff_text: str, dest: Path) -> None:
    """Write the base code into dest, then apply the diff on top of it."""
    # 1. Base code straight from git (not the working folder). autocrlf=false
    #    keeps LF line endings, so the LF diff applies cleanly on Windows too.
    archive = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "archive", "--format=tar", base_ref],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(dest, filter="data")  # "data" blocks unsafe paths like ../

    # 2. Apply the diff. `git apply` is all-or-nothing: if any hunk's context
    #    lines don't match the base, nothing is changed and it exits non-zero.
    applied = subprocess.run(
        ["git", "apply", "-"],  # "-" = read the patch from stdin
        cwd=dest,
        input=diff_text.encode("utf-8"),
        capture_output=True,
        check=False,  # we check returncode ourselves to raise a clear PatchError
    )
    if applied.returncode != 0:
        raise PatchError(applied.stderr.decode("utf-8", errors="replace").strip())


def run_ruff(tree: Path, files: list[str]) -> list[LintFinding]:
    """Run ruff on the given files (paths relative to tree), using the repo's own config."""
    result = subprocess.run(
        [
            sys.executable, "-m", "ruff", "check",
            "--no-fix",  # marshmallow's config has fix = true; we only want to report
            "--exit-zero",  # exit 0 even when there are findings; non-zero = ruff crashed
            "--output-format", "json",
            *files,
        ],
        cwd=tree,
        capture_output=True,
        text=True,
        check=False,  # we check returncode ourselves
    )
    if result.returncode != 0:
        raise RuntimeError(f"ruff failed: {result.stderr.strip()}")

    findings = []
    for item in json.loads(result.stdout):
        rel = Path(item["filename"]).resolve().relative_to(tree.resolve()).as_posix()
        findings.append(
            LintFinding(
                file=rel,
                line=item["location"]["row"],
                code=item["code"] or "syntax-error",  # syntax errors have no rule code
                message=item["message"],
            )
        )
    return findings


def lint_diff(diff_text: str, repo: Path | None = None, base_ref: str = BASE_REF) -> list[LintFinding]:
    """Ruff findings that are on lines this diff added."""
    if repo is None:
        load_dotenv()
        repo = Path(os.environ["TARGET_REPO_PATH"])

    files = parse_diff(diff_text)
    py_files = [f.path for f in files if f.path.endswith(".py") and not f.is_deleted]
    if not py_files:
        return []

    # TemporaryDirectory deletes the folder when the `with` block ends, even on errors.
    with tempfile.TemporaryDirectory(prefix="codepair_lint_") as tmp:
        tree = Path(tmp)
        build_pr_tree(repo, base_ref, diff_text, tree)
        findings = run_ruff(tree, py_files)

    added = added_lines(files)
    return [f for f in findings if (f.file, f.line) in added]


if __name__ == "__main__":
    # Run: python -m app.lint evals/prs/pr_01.diff
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    results = lint_diff(text)
    for f in results:
        print(f"{f.file}:{f.line}  {f.code}  {f.message}")
    print(f"{len(results)} ruff finding(s) on added lines")
