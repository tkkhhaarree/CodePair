"""The only door to the LLM.

Every agent (reviewer, judge, developer) calls call_structured() from here and
never imports a provider SDK itself. Swapping provider = changing this import.
"""

from app.llm.claude import CallLog, LLMError, call_structured

__all__ = ["CallLog", "LLMError", "call_structured"]
