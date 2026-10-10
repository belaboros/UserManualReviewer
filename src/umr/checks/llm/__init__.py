"""LLM-tier checks (ADR-0006). Importing this package registers them."""

from umr.checks.llm import consistency, contradictions, journey, procedures, terminology  # noqa: F401
from umr.checks.llm.llm_check import LlmCheck, PromptUnit

__all__ = ["LlmCheck", "PromptUnit"]
