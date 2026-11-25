"""Load a PR to review: the diff, plus title and description if a JSON file sits next to it.

Only title and description are returned. The eval labels in the JSON (`bugs`,
`related_files`, proof paths) are never passed on, so the reviewer can't see
the answer key.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PRInput:
    diff: str
    title: str = ""
    description: str = ""


def load_pr(diff_path: str | Path) -> PRInput:
    """Return the diff, plus title and description from the JSON file next to it (if any).

    pr_01.diff  ->  reads pr_01.diff, and pr_01.json if it exists.
    Never return anything else from the JSON (no `bugs`!).
    """
    # TODO 1: turn diff_path into a Path object (it may arrive as a plain string).
    diff_path_obj = Path(diff_path)

    # TODO 2: read the diff file's text (use encoding="utf-8").
    diff_content = diff_path_obj.read_text(encoding="utf-8")

    # TODO 3: build the path of the JSON file: same name, ".json" instead of ".diff".
    json_path = diff_path_obj.with_suffix(".json")

    # TODO 4: if that JSON file does not exist, return a PRInput with only the diff.
    if not json_path.exists():
        return PRInput(diff=diff_content, title="", description="")

    # TODO 5: otherwise read the JSON text and turn it into a dict (json.loads).
    json_content = json_path.read_text(encoding="utf-8")
    json_dict = json.loads(json_content)
    # TODO 6: return a PRInput with the diff, the title and the description.
    # If "title" or "description" is missing from the JSON, use "" instead.
    return PRInput(
        diff=diff_content,
        title=json_dict.get("title") or "",
        description=json_dict.get("description") or "",
    )
