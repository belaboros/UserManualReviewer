"""Native Claude Messages API adapter: explicit prompt caching and structured outputs (ADR-0003, spec LLM)."""

from __future__ import annotations

import threading
import time
from typing import Any

import anthropic

from umr.domain import Usage
from umr.llm.base import LlmError, LlmProvider, LlmResult, ProviderConfig, StructuredOutput
from umr.llm.config import get_api_key
from umr.llm.cost import ANTHROPIC_CACHE_READ_FACTOR, ANTHROPIC_CACHE_WRITE_FACTOR, cost_usd
from umr.llm.jsonparse import extract_json
from umr.llm.structured import schema_instruction, strict_schema


class AnthropicProvider(LlmProvider):
    """Claude via the official `anthropic` SDK.

    The manuals go in the first user content block with an ephemeral `cache_control` breakpoint, so the
    system prompt and the manuals are cached and reused by every check of a run. The instruction comes in
    a second block after the breakpoint.

    Config notes: `temperature` is sent only when set explicitly in the config file (current Claude models
    reject sampling parameters). `extra.effort` (low | medium | high | xhigh | max) goes to
    `output_config.effort`; `extra.max_retries` (default 2).
    """

    def __init__(self, config: ProviderConfig, client: Any | None = None):
        super().__init__(config)
        if client is None:
            key = get_api_key(config)
            kwargs: dict[str, Any] = {"timeout": config.timeout_s,
                                      "max_retries": int(config.extra.get("max_retries", 2))}
            if key:
                kwargs["api_key"] = key
            if config.base_url:
                kwargs["base_url"] = config.base_url
            client = anthropic.Anthropic(**kwargs)
        self.client = client
        self._native_schema = config.structured_output == StructuredOutput.JSON_SCHEMA
        self._lock = threading.Lock()

    def build_request(self, *, system: str, cache_prefix: str, prompt: str, schema: dict[str, Any],
                      native_schema: bool) -> dict[str, Any]:
        cfg = self.config
        instruction = prompt if native_schema else f"{prompt}\n\n{schema_instruction(schema)}"
        content: list[dict[str, Any]] = []
        if cache_prefix:
            content.append({"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}})
        content.append({"type": "text", "text": instruction})
        request: dict[str, Any] = {
            "model": cfg.model,
            "max_tokens": cfg.max_output_tokens,
            "system": [{"type": "text", "text": system}],
            "messages": [{"role": "user", "content": content}],
        }
        output_config: dict[str, Any] = {}
        if native_schema:
            output_config["format"] = {"type": "json_schema", "schema": strict_schema(schema)}
        if cfg.extra.get("effort"):
            output_config["effort"] = str(cfg.extra["effort"])
        if output_config:
            request["output_config"] = output_config
        if cfg.temperature is not None and "temperature" in cfg.model_fields_set:
            # anthropic SDK 1.x has no sampling parameters any more; older models still accept them
            request["extra_body"] = {"temperature": cfg.temperature}
        return request

    def _send(self, request: dict[str, Any]) -> Any:
        try:
            return self.client.messages.create(**request)
        except anthropic.APIStatusError as e:
            raise _StatusError(e) from e
        except anthropic.APITimeoutError as e:
            raise LlmError(f"{self.name}: request timed out after {self.config.timeout_s:.0f} s") from e
        except anthropic.APIConnectionError as e:
            raise LlmError(f"{self.name}: cannot connect to the Anthropic API: {e}") from e
        except anthropic.AnthropicError as e:
            raise LlmError(f"{self.name}: {type(e).__name__}: {e}") from e

    def complete(self, *, system: str, cache_prefix: str, prompt: str, schema: dict[str, Any],
                 schema_name: str = "findings") -> LlmResult:
        with self._lock:
            native = self._native_schema
        t0 = time.perf_counter()
        try:
            response = self._send(self.build_request(system=system, cache_prefix=cache_prefix, prompt=prompt,
                                                     schema=schema, native_schema=native))
        except _StatusError as e:
            if not (native and e.status_code == 400 and _mentions_structured_output(e.message)):
                raise e.as_llm_error(self.name) from e
            # model or SDK rejects native structured output: fall back to the schema in the prompt
            with self._lock:
                self._native_schema = False
            try:
                response = self._send(self.build_request(system=system, cache_prefix=cache_prefix,
                                                         prompt=prompt, schema=schema, native_schema=False))
            except _StatusError as e2:
                raise e2.as_llm_error(self.name) from e2
        duration = time.perf_counter() - t0
        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None)
            raise LlmError(f"{self.name}: the model declined the request"
                           + (f" (category: {category})" if category else ""))
        text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")
        return LlmResult(data=extract_json(text), raw_text=text, usage=self.usage_from(response, duration),
                         model=getattr(response, "model", "") or self.config.model)

    def usage_from(self, response: Any, duration_s: float) -> Usage:
        u = getattr(response, "usage", None)
        uncached = int(getattr(u, "input_tokens", 0) or 0)
        output = int(getattr(u, "output_tokens", 0) or 0)
        read = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        write = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        cost = cost_usd(self.config.price_per_mtok, uncached_input=uncached, output=output, cache_read=read,
                        cache_write=write, cache_read_factor=ANTHROPIC_CACHE_READ_FACTOR,
                        cache_write_factor=ANTHROPIC_CACHE_WRITE_FACTOR)
        # input_tokens is the whole prompt (uncached + written + read), as for OpenAI-compatible providers
        return Usage(input_tokens=uncached + read + write, output_tokens=output, cached_tokens=read,
                     cost_usd=cost, duration_s=duration_s, calls=1)


_STRUCTURED_HINTS = ("output_config", "output_format", "format", "schema", "structured")


def _mentions_structured_output(message: str) -> bool:
    text = message.lower()
    return any(h in text for h in _STRUCTURED_HINTS)


class _StatusError(Exception):
    def __init__(self, error: anthropic.APIStatusError):
        super().__init__(str(error))
        self.status_code = error.status_code
        self.message = error.message

    def as_llm_error(self, name: str) -> LlmError:
        return LlmError(f"{name}: HTTP {self.status_code} from the Anthropic API: {self.message}")
