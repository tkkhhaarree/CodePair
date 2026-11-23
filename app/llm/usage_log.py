"""Append one JSON line per LLM call to logs/llm_calls.jsonl.

JSONL = one JSON object per line. Easy to append to, and easy to load later
for cost reports (one line = one call). Langfuse tracing replaces this in M4.
"""

import json
from pathlib import Path

# app/llm/usage_log.py -> parents[2] is the repo root
LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "llm_calls.jsonl"


def write(record: dict) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:  # "a" = append
        fh.write(json.dumps(record) + "\n")
