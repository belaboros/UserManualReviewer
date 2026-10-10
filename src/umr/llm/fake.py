"""Fake provider for tests: returns canned responses keyed by schema name or prompt substring."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from umr.domain import Usage
from umr.llm.base import Adapter, LlmProvider, LlmResult, ProviderConfig

Responder = Callable[[str, str, str], Any]


class FakeProvider(LlmProvider):
    def __init__(self, responses: dict[str, Any] | Responder | None = None, name: str = "fake"):
        super().__init__(ProviderConfig(name=name, adapter=Adapter.FAKE, model="fake-model"))
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
        text = data if isinstance(data, str) else json.dumps(data)
        parsed = json.loads(text) if isinstance(data, str) else data
        return LlmResult(data=parsed, raw_text=text, model="fake-model",
                         usage=Usage(input_tokens=self.estimate_tokens(cache_prefix + prompt),
                                     output_tokens=self.estimate_tokens(text), calls=1))
