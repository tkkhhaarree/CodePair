"""Smoke test: one tiny real API call. Costs well under 1 cent.

Run: python -m app.llm
"""

import os

from dotenv import load_dotenv
from pydantic import BaseModel

from app.llm import call_structured
from app.llm.usage_log import LOG_PATH


class Answer(BaseModel):
    answer: int
    explanation: str


load_dotenv()
parsed, log = call_structured(
    agent="smoke-test",
    system="You answer arithmetic questions briefly.",
    user="What is 2 + 2?",
    output_type=Answer,
    model=os.environ.get("REVIEWER_MODEL", "claude-sonnet-5-5"),
    max_tokens=2000,
    effort="low",
)
print("parsed :", parsed)
print("tokens :", log.input_tokens, "in /", log.output_tokens, "out")
print(f"cost   : ${log.cost_usd:.5f}   latency: {log.latency_s}s   stop: {log.stop_reason}")
print("logged to:", LOG_PATH)
