"""OpenAI Chat Completions adapter for any OpenAI-compatible endpoint (ADR-0003, spec LLM)."""

from __future__ import annotations

import time
from typing import Any

import openai

from umr.domain import Usage
from umr.llm.base import LlmError, LlmProvider, LlmResult, ProviderConfig, StructuredOutput
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
        t0 = time.perf_counter()
        try:
            response = self.client.chat.completions.create(**request)
        except openai.APIStatusError as e:
            raise LlmError(f"{self.name}: HTTP {e.status_code} from {self.config.base_url or 'OpenAI'}: "
                           f"{e.message}") from e
        except openai.APITimeoutError as e:
            raise LlmError(f"{self.name}: request timed out after {self.config.timeout_s:.0f} s") from e
        except openai.APIConnectionError as e:
            raise LlmError(f"{self.name}: cannot connect to {self.config.base_url or 'OpenAI'}: {e}") from e
        except openai.OpenAIError as e:
            raise LlmError(f"{self.name}: {type(e).__name__}: {e}") from e
        duration = time.perf_counter() - t0
        if not getattr(response, "choices", None):
            raise LlmError(f"{self.name}: response has no choices")
        message = response.choices[0].message
        text = message.content or ""
        return LlmResult(data=extract_json(text), raw_text=text, usage=self.usage_from(response, duration),
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
