"""Claude implementation of call_structured. The only file that imports `anthropic`.

To switch provider, write another module with the same call_structured()
signature and change the import in app/llm/__init__.py.
"""

import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from app.llm import usage_log
from app.llm.pricing import cost_usd

Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass
class CallLog:
    """What we record about every call, successful or not."""

    timestamp: str
    agent: str
    model: str
    effort: str
    input_tokens: int = 0
    output_tokens: int = 0  # includes the model's thinking tokens
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = 0.0
    latency_s: float = 0.0
    stop_reason: str | None = None
    ok: bool = True
    error: str | None = None


class LLMError(Exception):
    """The call did not produce a valid object. `.log` says what it cost and why."""

    def __init__(self, message: str, log: CallLog):
        super().__init__(message)
        self.log = log


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    """Create the client once, on first use (reads ANTHROPIC_API_KEY from .env)."""
    global _client
    if _client is None:
        load_dotenv()
        _client = anthropic.Anthropic()  # the SDK retries 429/5xx errors twice by itself
    return _client


# [T: BaseModel] makes this a generic function (TypeScript: <T extends BaseModel>).
# T = whatever Pydantic class the caller passes: pass ReviewResult, get a ReviewResult back.
def call_structured[T: BaseModel](
    *,
    agent: str,
    system: str,
    user: str,
    output_type: type[T],
    model: str,
    max_tokens: int = 16000,
    effort: Effort = "medium",
) -> tuple[T, CallLog]:
    """Ask the model for an answer shaped like `output_type`. Every call is logged.

    Returns (parsed object, log). Raises LLMError if the call fails, is cut off,
    is refused, or does not validate - after logging it.
    """
    log = CallLog(
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        agent=agent,
        model=model,
        effort=effort,
    )
    # Same conversion messages.parse() does internally: Pydantic class -> the
    # JSON Schema dialect the API accepts. The API then constrains decoding to it.
    schema = anthropic.transform_schema(output_type.model_json_schema())

    start = time.perf_counter()
    try:
        response = _get_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        )
    except anthropic.APIError as e:  # network, auth, rate limit, bad request...
        log.latency_s = round(time.perf_counter() - start, 2)
        log.ok, log.error = False, f"{type(e).__name__}: {e}"
        usage_log.write(asdict(log))
        raise LLMError(f"API call failed: {log.error}", log) from e

    # 1. Record usage and cost first, so even failed calls are logged.
    log.latency_s = round(time.perf_counter() - start, 2)
    usage = response.usage
    log.input_tokens = usage.input_tokens
    log.output_tokens = usage.output_tokens
    log.cache_read_tokens = usage.cache_read_input_tokens or 0
    log.cache_write_tokens = usage.cache_creation_input_tokens or 0
    log.cost_usd = cost_usd(
        model, log.input_tokens, log.output_tokens, log.cache_write_tokens, log.cache_read_tokens
    )
    log.stop_reason = response.stop_reason

    # 2. Then check why it stopped, then validate.
    parsed: T | None = None
    if response.stop_reason == "max_tokens":
        log.error = f"output cut off at max_tokens={max_tokens}"
    elif response.stop_reason == "refusal":
        log.error = "model refused"
    else:
        # content holds thinking blocks and the text block; the JSON is in the text.
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            parsed = output_type.model_validate_json(text)
        except ValidationError as e:
            log.error = f"output failed validation ({e.error_count()} errors)"

    log.ok = parsed is not None
    usage_log.write(asdict(log))
    if parsed is None:
        raise LLMError(log.error or "no output", log)
    return parsed, log
