"""CLI: python -m app.reviewer evals/prs/pr_01.diff"""

import sys
import textwrap

from app.lint import PatchError
from app.llm import LLMError
from app.reviewer.load import load_pr
from app.reviewer.review import review_diff


def indent(text: str) -> str:
    """Wrap long text at 96 characters and indent it under its comment."""
    return textwrap.fill(text, width=96, initial_indent="    ", subsequent_indent="    ")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m app.reviewer <path/to/pr.diff>")
        return 2

    pr = load_pr(sys.argv[1])
    print(f"PR: {pr.title or '(no title)'}\n")

    try:
        out = review_diff(pr.diff, pr.title, pr.description)
    except PatchError as e:
        print(f"The diff does not apply to the base branch:\n{e}")
        return 1
    except LLMError as e:
        print(f"Review failed: {e}  (cost so far: ${e.log.cost_usd or 0:.4f})")
        return 1

    print("Summary:")
    print(indent(out.summary))

    print(f"\nComments ({len(out.comments)}):")
    for c in sorted(out.comments, key=lambda c: (c.file, c.line)):
        print(f"\n  [{c.severity}] {c.file}:{c.line}  ({c.category})")
        print(indent(c.message))
        if c.suggested_fix:
            print(indent(f"Fix: {c.suggested_fix}"))

    print(f"\nRuff findings on added lines ({len(out.ruff)}):")
    for f in out.ruff:
        print(f"  {f.file}:{f.line}  {f.code}  {f.message}")

    print(f"\nDropped by post-filter ({len(out.dropped)}):")
    for d in out.dropped:
        print(f"  {d.comment.file}:{d.comment.line}  - {d.reason}")

    log = out.log
    print(
        f"\nModel: {log.model} (effort {log.effort})  |  tokens: {log.input_tokens} in / "
        f"{log.output_tokens} out  |  cost: ${log.cost_usd or 0:.4f}  |  {log.latency_s}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
