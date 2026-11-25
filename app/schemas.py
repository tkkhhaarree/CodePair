"""Data shapes shared by the agents.

The reviewer must answer in exactly these shapes (structured output), so the
rest of the code never has to parse free text.
"""

from typing import Literal

from pydantic import BaseModel, Field

# A Literal type allows only these exact strings (like a TypeScript union type).
Severity = Literal["critical", "major", "minor", "nit"]

Category = Literal[
    "logic-bug",
    "edge-case",
    "error-handling",
    "breaking-change",
    "security",
    "performance",
    "design",
    "tests",
    "other",
]


class ReviewComment(BaseModel):
    """One comment the reviewer leaves on one line of the diff."""

    file: str = Field(description="File path exactly as in the diff header, e.g. src/pkg/mod.py")
    line: int = Field(description="Line number in the NEW version of the file. Must be a line shown in the diff.")
    severity: Severity = Field(description="critical = wrong results or crash; nit = style only")
    category: Category
    message: str = Field(description="What is wrong, and a concrete input or case where it fails.")
    suggested_fix: str | None = Field(description="Short code or description of the fix, or null.")


class JudgeVerdict(BaseModel):
    """The eval judge's answer to one yes/no question.

    `reason` comes BEFORE `yes` on purpose: the model writes fields in order, so it
    reasons first and decides second (instead of deciding, then justifying).
    """

    reason: str = Field(description="One or two sentences explaining the decision.")
    yes: bool = Field(description="The answer to the question asked.")


class ReviewResult(BaseModel):
    """Everything the reviewer returns for one PR."""

    summary: str = Field(description="One or two sentences on the PR overall.")
    comments: list[ReviewComment]
