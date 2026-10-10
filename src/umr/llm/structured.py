"""Validated structured output with one retry (architecture section 10, spec LLM)."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from umr.domain import LlmCallStats, Usage
from umr.llm.base import LlmError, LlmProvider

_UNSUPPORTED_KEYS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                     "minLength", "maxLength", "pattern", "minItems", "maxItems", "uniqueItems"}


def schema_instruction(schema: dict[str, Any]) -> str:
    """Text appended to the prompt when the provider cannot enforce a JSON schema itself."""
    return ("Respond with a single JSON object only, no prose and no code fences. "
            "It must match this JSON Schema:\n" + json.dumps(schema, sort_keys=True))


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Copy of a Pydantic JSON schema reduced to what strict structured-output APIs accept.

    Every object gets `additionalProperties: false`; numeric, string and array constraints are removed
    (they are still enforced by Pydantic validation after the call).
    """
    out = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in list(node):
                if key in _UNSUPPORTED_KEYS:
                    del node[key]
            if node.get("type") == "object" or "properties" in node:
                node["additionalProperties"] = False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(out)
    return out


@dataclass
class ValidatedResult[T: BaseModel]:
    data: T
    usage: Usage
    valid_first_try: bool
    retried: bool


def _coerce(data: Any, model_cls: type[BaseModel]) -> Any:
    """Wrap a bare list into the model's only list field (weak models sometimes drop the wrapper)."""
    if isinstance(data, list):
        fields = list(model_cls.model_fields)
        if len(fields) == 1:
            return {fields[0]: data}
    return data


def _validate[T: BaseModel](data: Any, raw_text: str, model_cls: type[T]) -> tuple[T | None, str]:
    if data is None:
        snippet = raw_text.strip()[:300] or "(empty response)"
        return None, f"The answer was not valid JSON. It started with: {snippet}"
    try:
        return model_cls.model_validate(_coerce(data, model_cls)), ""
    except ValidationError as e:
        return None, f"The JSON did not match the schema: {e}"


def complete_validated[T: BaseModel](
    provider: LlmProvider, *, system: str, cache_prefix: str, prompt: str, model_cls: type[T],
    schema_name: str = "findings", stats: LlmCallStats | None = None, usage: Usage | None = None,
) -> ValidatedResult[T]:
    """Call the provider and validate the answer with `model_cls`.

    On invalid output the call is repeated once with the validation error appended to the prompt
    (the cached prefix stays identical). Still invalid, or a provider failure, raises `LlmError`.
    `stats` and `usage`, when given, are updated even when the call fails.
    """
    schema = model_cls.model_json_schema()
    total = Usage()
    if stats is not None:
        stats.calls += 1

    def call(p: str) -> tuple[T | None, str]:
        try:
            result = provider.complete(system=system, cache_prefix=cache_prefix, prompt=p, schema=schema,
                                       schema_name=schema_name)
        except LlmError:
            if stats is not None:
                stats.failed += 1
            raise
        except Exception as e:  # an adapter bug must still be reported as an LLM error
            if stats is not None:
                stats.failed += 1
            raise LlmError(f"{provider.name}: {type(e).__name__}: {e}") from e
        total.add(result.usage)
        if usage is not None:
            usage.add(result.usage)
        return _validate(result.data, result.raw_text, model_cls)

    parsed, error = call(prompt)
    if parsed is not None:
        if stats is not None:
            stats.valid_first_try += 1
        return ValidatedResult(parsed, total, valid_first_try=True, retried=False)
    retry_prompt = (f"{prompt}\n\nYOUR PREVIOUS ANSWER WAS INVALID. {error}\n"
                    "Answer again with only a JSON object that matches the schema.")
    parsed, error2 = call(retry_prompt)
    if parsed is not None:
        if stats is not None:
            stats.retried += 1
        return ValidatedResult(parsed, total, valid_first_try=False, retried=True)
    if stats is not None:
        stats.failed += 1
    raise LlmError(f"{provider.name}: invalid structured output after one retry. {error2[:500]}")
