"""OpenAI Chat Completions adapter for any OpenAI-compatible endpoint (ADR-0003, spec LLM)."""

from __future__ import annotations

import time
from typing import Any

import openai

from umr.domain import Usage
from umr.llm.base import LlmError, LlmProvider, LlmResult, ProviderConfig, StructuredOutput, token_limit_error
from umr.llm.calllog import CallRecord
from umr.llm.config import get_api_key
from umr.llm.cost import cost_usd
from umr.llm.jsonparse import extract_json
from umr.llm.structured import schema_instruction

# Local servers ignore the key, but the SDK insists on one.
_NO_KEY = "not-needed"


class OpenAICompatibleProvider(LlmProvider):
    """OpenAI, Gemini, Mistral, OpenRouter, Groq, Ollama, LM Studio, vLLM, llama.cpp ...

    Config `extra` keys: `max_tokens_param` (`max_tokens` | `max_completion_tokens`, default `max_tokens`),
    `extra_body` (dict passed through to the request), `max_retries` (default 2).
    """

    def __init__(self, config: ProviderConfig, client: Any | None = None):
        super().__init__(config)
        if client is None:
            key = get_api_key(config)
            client = openai.OpenAI(api_key=key or _NO_KEY, base_url=config.base_url, timeout=config.timeout_s,
                                   max_retries=int(config.extra.get("max_retries", 2)))
        self.client = client

    def build_request(self, *, system: str, cache_prefix: str, prompt: str, schema: dict[str, Any],
                      schema_name: str) -> dict[str, Any]:
        cfg = self.config
        mode = cfg.structured_output
        instruction = prompt
        if mode in (StructuredOutput.JSON_OBJECT, StructuredOutput.PROMPT):
            instruction = f"{prompt}\n\n{schema_instruction(schema)}"
        # prefix first, so automatic prefix caching (OpenAI, Gemini, local KV caches) reuses the manuals
        user = f"{cache_prefix}\n\n{instruction}" if cache_prefix else instruction
        request: dict[str, Any] = {
            "model": cfg.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            str(cfg.extra.get("max_tokens_param", "max_tokens")): cfg.max_output_tokens,
        }
        if cfg.temperature is not None:
            request["temperature"] = cfg.temperature
        if mode == StructuredOutput.JSON_SCHEMA:
            request["response_format"] = {"type": "json_schema", "json_schema": {
                "name": schema_name, "schema": schema, "strict": False}}
        elif mode == StructuredOutput.JSON_OBJECT:
            request["response_format"] = {"type": "json_object"}
        extra_body = cfg.extra.get("extra_body")
        if isinstance(extra_body, dict) and extra_body:
            request["extra_body"] = extra_body
        return request

    def complete(self, *, system: str, cache_prefix: str, prompt: str, schema: dict[str, Any],
                 schema_name: str = "findings") -> LlmResult:
        request = self.build_request(system=system, cache_prefix=cache_prefix, prompt=prompt, schema=schema,
                                     schema_name=schema_name)
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        record = CallRecord(self.name, "openai-compatible", f"{base}/chat/completions", self.config.model,
                            request).start()
        t0 = time.perf_counter()
        try:
            response = self.client.chat.completions.create(**request)
        except openai.APIStatusError as e:
            record.failed(error=e, duration_s=time.perf_counter() - t0, status_code=e.status_code,
                          body=_response_body(e))
            raise LlmError(f"{self.name}: HTTP {e.status_code} from {base}: {e.message}") from e
        except openai.APITimeoutError as e:
            record.failed(error=e, duration_s=time.perf_counter() - t0)
            raise LlmError(f"{self.name}: request timed out after {self.config.timeout_s:.0f} s "
                           f"(raise timeout_s in the provider config for slow local models)") from e
        except openai.APIConnectionError as e:
            record.failed(error=e, duration_s=time.perf_counter() - t0)
            raise LlmError(f"{self.name}: cannot connect to {base}: {e}") from e
        except openai.OpenAIError as e:
            record.failed(error=e, duration_s=time.perf_counter() - t0)
            raise LlmError(f"{self.name}: {type(e).__name__}: {e}") from e
        duration = time.perf_counter() - t0
        if not getattr(response, "choices", None):
            record.failed(error=LlmError("response has no choices"), duration_s=duration, body=response)
            raise LlmError(f"{self.name}: response has no choices")
        choice = response.choices[0]
        message = choice.message
        text = message.content or ""
        usage = self.usage_from(response, duration)
        record.ok(raw_text=text, response=response, duration_s=duration, input_tokens=usage.input_tokens,
                  output_tokens=usage.output_tokens, finish_reason=getattr(choice, "finish_reason", None))
        data = extract_json(text)
        if data is None and getattr(choice, "finish_reason", None) == "length":
            details = getattr(getattr(response, "usage", None), "completion_tokens_details", None)
            raise token_limit_error(self.name, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                                    max_output_tokens=self.config.max_output_tokens,
                                    reasoning_tokens=int(getattr(details, "reasoning_tokens", 0) or 0))
        return LlmResult(data=data, raw_text=text, usage=usage,
                         model=getattr(response, "model", "") or self.config.model)

    def usage_from(self, response: Any, duration_s: float) -> Usage:
        u = getattr(response, "usage", None)
        prompt_tokens = int(getattr(u, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(u, "completion_tokens", 0) or 0)
        details = getattr(u, "prompt_tokens_details", None)
        cached = int(getattr(details, "cached_tokens", 0) or 0)
        cost = cost_usd(self.config.price_per_mtok, uncached_input=max(prompt_tokens - cached, 0),
                        output=output_tokens, cache_read=cached)
        return Usage(input_tokens=prompt_tokens, output_tokens=output_tokens, cached_tokens=cached,
                     cost_usd=cost, duration_s=duration_s, calls=1)


def _response_body(e: openai.APIStatusError) -> Any:
    """The server's error body: what local servers put their real error message in."""
    body = getattr(e, "body", None)
    if body is not None:
        return body
    try:
        return e.response.text
    except Exception:  # pragma: no cover
        return None
