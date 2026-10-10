"""Fake provider for tests: returns canned responses keyed by schema name or prompt substring.

A response may be a dict/list (returned as parsed JSON), a string (parsed tolerantly; invalid JSON gives
`data=None`, like a real adapter), an exception instance (raised), or a list wrapped in `Sequence(...)`
whose items are returned one per call.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from umr.domain import Usage
from umr.llm.base import Adapter, LlmProvider, LlmResult, ProviderConfig
from umr.llm.jsonparse import extract_json

Responder = Callable[[str, str, str], Any]


class Sequence:
    """Responses returned one after the other; the last one repeats."""

    def __init__(self, *items: Any):
        self.items = list(items)
        self.index = 0

    def next(self) -> Any:
        item = self.items[min(self.index, len(self.items) - 1)]
        self.index += 1
        return item


class FakeProvider(LlmProvider):
    def __init__(self, responses: dict[str, Any] | Responder | None = None, name: str = "fake",
                 config: ProviderConfig | None = None):
        super().__init__(config or ProviderConfig(name=name, adapter=Adapter.FAKE, model="fake-model"))
        self.responses = responses or {}
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system: str, cache_prefix: str, prompt: str, schema: dict[str, Any],
                 schema_name: str = "findings") -> LlmResult:
        self.calls.append({"system": system, "cache_prefix": cache_prefix, "prompt": prompt,
                           "schema_name": schema_name})
        if callable(self.responses):
            data = self.responses(system, cache_prefix, prompt)
        else:
            data = None
            for key, value in self.responses.items():
                if key == schema_name or key in prompt:
                    data = value
                    break
            if data is None:
                data = {"findings": []}
        if isinstance(data, Sequence):
            data = data.next()
        if isinstance(data, BaseException):
            raise data
        text = data if isinstance(data, str) else json.dumps(data)
        parsed = extract_json(text) if isinstance(data, str) else data
        return LlmResult(data=parsed, raw_text=text, model="fake-model",
                         usage=Usage(input_tokens=self.estimate_tokens(cache_prefix + prompt),
                                     output_tokens=self.estimate_tokens(text), calls=1))
