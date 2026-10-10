"""LLM provider interface (architecture section 10, ADR-0003)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from umr.domain import Usage


class Adapter(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai-compatible"
    FAKE = "fake"


class StructuredOutput(StrEnum):
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    PROMPT = "prompt"


class Price(BaseModel):
    """USD per million tokens."""

    input: float = 0.0
    output: float = 0.0
    cache_read: float | None = None
    cache_write: float | None = None


class ProviderConfig(BaseModel):
    name: str
    adapter: Adapter
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    structured_output: StructuredOutput = StructuredOutput.JSON_SCHEMA
    context_tokens: int = 128_000
    max_output_tokens: int = 16_000
    max_concurrency: int = 4
    temperature: float | None = 0.0
    timeout_s: float = 300.0
    price_per_mtok: Price = Field(default_factory=Price)
    extra: dict[str, Any] = Field(default_factory=dict)


class LlmError(Exception):
    pass


class LlmResult(BaseModel):
    data: Any = None  # parsed JSON (validated against the schema by the caller)
    raw_text: str = ""
    usage: Usage = Field(default_factory=Usage)
    model: str = ""


class LlmProvider(ABC):
    """Sends one prompt and returns parsed JSON.

    The prompt is split so providers can cache the stable part:
    `cache_prefix` (the manuals, identical for every check of a run) comes first,
    `prompt` (the check instruction) comes after it.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def complete(self, *, system: str, cache_prefix: str, prompt: str, schema: dict[str, Any],
                 schema_name: str = "findings") -> LlmResult: ...

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4 + 1


def token_limit_error(name: str, *, input_tokens: int, output_tokens: int, max_output_tokens: int,
                      reasoning_tokens: int = 0) -> LlmError:
    """The model stopped at a token limit before writing a usable answer (AC-LLM-28).

    Retrying would hit the same limit, so this is reported at once with what to change.
    """
    used = f"{input_tokens:,} in + {output_tokens:,} out tokens"
    if reasoning_tokens:
        used += f", {reasoning_tokens:,} of them reasoning"
    if output_tokens < max_output_tokens * 0.95:
        total = input_tokens + output_tokens
        return LlmError(
            f"{name}: the model ran out of context before it wrote the answer ({used}). It stopped below "
            f"max_output_tokens ({max_output_tokens:,}), so the server's context length is about {total:,} "
            f"tokens. Load the model with a larger context, at least 32k (LM Studio: model load settings, "
            f"Context Length; Ollama: num_ctx), and set context_tokens in the provider config to match.")
    return LlmError(
        f"{name}: the model reached max_output_tokens ({max_output_tokens:,}) before it wrote the answer "
        f"({used}). Raise max_output_tokens in the provider config, or lower the reasoning effort.")
