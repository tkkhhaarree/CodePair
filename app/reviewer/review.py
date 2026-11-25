"""review_diff(): the whole single-pass review, as one function.

diff -> ruff (code) -> one LLM call (judgement) -> post-filter (code) -> ReviewOutput.
The CLI, the M2 eval and later the API all call this.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from app.diff import commentable_lines, format_for_llm, parse_diff
from app.lint import LintFinding, lint_diff
from app.llm import CallLog, call_structured
from app.reviewer.filter import DroppedComment, filter_comments
from app.reviewer.prompt import SYSTEM_PROMPT, build_user_message
from app.schemas import ReviewComment, ReviewResult

EFFORTS = ("low", "medium", "high", "xhigh", "max")


@dataclass
class ReviewOutput:
    summary: str
    comments: list[ReviewComment]  # LLM comments that passed the post-filter
    dropped: list[DroppedComment]  # LLM comments the post-filter removed, with reasons
    ruff: list[LintFinding]  # linter findings on added lines (shown, not scored)
    log: CallLog  # tokens, cost, latency of the LLM call


def review_diff(diff: str, title: str = "", description: str = "") -> ReviewOutput:
    """Review one PR. Raises PatchError (diff doesn't fit the base) or LLMError."""
    load_dotenv()
    model = os.environ.get("REVIEWER_MODEL", "claude-sonnet-5-5")
    effort = os.environ.get("REVIEWER_EFFORT", "medium")
    if effort not in EFFORTS:
        raise ValueError(f"REVIEWER_EFFORT must be one of {EFFORTS}, got {effort!r}")

    files = parse_diff(diff)

    # 1. Code for rules: ruff on the PR's rebuilt code. Also proves the diff applies.
    ruff = lint_diff(diff)

    # 2. LLM for judgement: one call with the numbered diff, PR text and ruff findings.
    user = build_user_message(title, description, format_for_llm(files), ruff)
    result, log = call_structured(
        agent="reviewer",
        system=SYSTEM_PROMPT,
        user=user,
        output_type=ReviewResult,
        model=model,
        effort=effort,
    )

    # 3. Code again: drop comments that break rules we can check.
    kept, dropped = filter_comments(result.comments, commentable_lines(files), ruff)

    return ReviewOutput(result.summary, kept, dropped, ruff, log)
