"""Spec LLM: validated structured output with one retry; JSON extraction."""

import pytest
from pydantic import BaseModel

from umr.domain import LlmCallStats, Usage
from umr.llm import LlmError, complete_validated
from umr.llm.fake import FakeProvider, Sequence
from umr.llm.jsonparse import extract_json, strip_reasoning
from umr.llm.structured import strict_schema


class Answer(BaseModel):
    items: list[int]


def run(provider: FakeProvider, stats: LlmCallStats, usage: Usage):
    return complete_validated(provider, system="S", cache_prefix="P", prompt="Q", model_cls=Answer,
                              stats=stats, usage=usage)


def test_AC_LLM_16_valid_first_try():
    fake = FakeProvider(lambda s, p, q: {"items": [1, 2]})
    stats, usage = LlmCallStats(), Usage()
    result = run(fake, stats, usage)
    assert result.data.items == [1, 2] and result.valid_first_try and not result.retried
    assert (stats.calls, stats.valid_first_try, stats.retried, stats.failed) == (1, 1, 0, 0)
    assert usage.calls == 1 and result.usage.calls == 1
    assert fake.calls[0]["schema_name"] == "findings"


def test_AC_LLM_16_bare_list_is_wrapped():
    fake = FakeProvider(lambda s, p, q: [3])
    assert run(fake, LlmCallStats(), Usage()).data.items == [3]


def test_AC_LLM_17_invalid_output_retried_once_with_error():
    responses = Sequence("not json at all", {"items": [5]})
    fake = FakeProvider(lambda s, p, q: responses.next())
    stats, usage = LlmCallStats(), Usage()
    result = run(fake, stats, usage)
    assert result.data.items == [5] and result.retried and not result.valid_first_try
    assert len(fake.calls) == 2
    assert fake.calls[1]["cache_prefix"] == "P"  # prefix unchanged, so the cache still hits
    assert fake.calls[1]["prompt"].startswith("Q\n\nYOUR PREVIOUS ANSWER WAS INVALID")
    assert "not valid JSON" in fake.calls[1]["prompt"]
    assert (stats.calls, stats.valid_first_try, stats.retried, stats.failed) == (1, 0, 1, 0)
    assert usage.calls == 2


def test_AC_LLM_17_schema_mismatch_error_is_in_retry_prompt():
    responses = Sequence({"items": "x"}, {"items": [1]})
    fake = FakeProvider(lambda s, p, q: responses.next())
    run(fake, LlmCallStats(), Usage())
    assert "did not match the schema" in fake.calls[1]["prompt"] and "items" in fake.calls[1]["prompt"]


def test_AC_LLM_18_still_invalid_raises_and_counts_failure():
    fake = FakeProvider(lambda s, p, q: "{broken")
    stats, usage = LlmCallStats(), Usage()
    with pytest.raises(LlmError, match="invalid structured output after one retry"):
        run(fake, stats, usage)
    assert len(fake.calls) == 2
    assert (stats.calls, stats.valid_first_try, stats.retried, stats.failed) == (1, 0, 0, 1)
    assert usage.calls == 2  # usage of failed calls is still recorded


def test_AC_LLM_18_provider_error_counts_failure():
    fake = FakeProvider(lambda s, p, q: LlmError("HTTP 500"))
    stats = LlmCallStats()
    with pytest.raises(LlmError, match="HTTP 500"):
        run(fake, stats, Usage())
    assert (stats.calls, stats.failed) == (1, 1) and len(fake.calls) == 1


def test_AC_LLM_09_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json("<think>{\"no\": 1} hmm</think>\n{\"a\": 3}") == {"a": 3}
    assert extract_json("Sure! The answer is {\"a\": 4} as requested.") == {"a": 4}
    assert extract_json("[1, 2]") == [1, 2]
    assert extract_json("reasoning without opening tag</think>{\"a\": 5}") == {"a": 5}
    assert extract_json("nothing here") is None
    assert extract_json("") is None
    assert strip_reasoning("<thinking>x</thinking> y") == "y"


def test_AC_LLM_12_strict_schema_for_native_structured_output():
    schema = strict_schema({"type": "object", "properties": {"n": {"type": "number", "minimum": 0},
                                                            "s": {"type": "string", "maxLength": 3}},
                            "$defs": {"X": {"properties": {"a": {"type": "integer"}}}}})
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["X"]["additionalProperties"] is False
    assert "minimum" not in schema["properties"]["n"] and "maxLength" not in schema["properties"]["s"]
