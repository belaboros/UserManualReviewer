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
