"""Spec LLM: native Claude adapter (caching layout, structured output, fallback, usage, errors)."""

import json
from typing import Any

import anthropic
import httpx2
import pytest

from umr.llm import Adapter, LlmError, Price, ProviderConfig, StructuredOutput
from umr.llm.anthropic_native import AnthropicProvider

SCHEMA = {"type": "object", "properties": {
    "findings": {"type": "array", "items": {"type": "object", "properties": {
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}}}}}, "required": ["findings"]}


def message(text: str, usage: dict[str, Any] | None = None, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-test",
            "content": [{"type": "thinking", "thinking": "", "signature": "s"}, {"type": "text", "text": text}],
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": usage or {"input_tokens": 100, "output_tokens": 50,
                               "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}


class Recorder:
    def __init__(self, responses: list[httpx2.Response]):
        self.responses = responses
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        return self.responses[min(len(self.bodies), len(self.responses)) - 1]


def provider(rec: Recorder, **cfg: Any) -> AnthropicProvider:
    config = ProviderConfig(name="claude", adapter=Adapter.ANTHROPIC, model="claude-test", **cfg)
    client = anthropic.Anthropic(api_key="x", max_retries=0,
                                 http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(rec)))
    return AnthropicProvider(config, client=client)


def call(p: AnthropicProvider):
    return p.complete(system="SYS", cache_prefix="MANUALS", prompt="TASK", schema=SCHEMA)


def test_AC_LLM_12_request_caches_manuals_block_and_uses_native_schema():
    rec = Recorder([httpx2.Response(200, json=message('{"findings": []}'))])
    result = call(provider(rec))
    body = rec.bodies[0]
    assert body["system"] == [{"type": "text", "text": "SYS"}]
    content = body["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "MANUALS", "cache_control": {"type": "ephemeral"}}
    assert content[1] == {"type": "text", "text": "TASK"}
    fmt = body["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False
    item = fmt["schema"]["properties"]["findings"]["items"]
    assert item["additionalProperties"] is False and "minimum" not in item["properties"]["confidence"]
    assert "temperature" not in body  # default temperature is not sent to Claude
    assert result.data == {"findings": []}


def test_AC_LLM_12_effort_and_explicit_temperature():
    rec = Recorder([httpx2.Response(200, json=message("{}"))])
    call(provider(rec, temperature=0.0, extra={"effort": "low"}))
    assert rec.bodies[0]["output_config"]["effort"] == "low"
    assert rec.bodies[0]["temperature"] == 0.0


def test_AC_LLM_12_prompt_mode_puts_schema_in_instruction():
    rec = Recorder([httpx2.Response(200, json=message('```json\n{"findings": [1]}\n```'))])
    result = call(provider(rec, structured_output=StructuredOutput.PROMPT))
    body = rec.bodies[0]
    assert "output_config" not in body
    assert "JSON Schema" in body["messages"][0]["content"][1]["text"]
    assert result.data == {"findings": [1]}


def test_AC_LLM_13_falls_back_to_prompt_json_when_schema_rejected():
    rec = Recorder([httpx2.Response(400, json={"type": "error", "error": {
                        "type": "invalid_request_error", "message": "output_config.format is not supported"}}),
                    httpx2.Response(200, json=message('{"findings": []}'))])
    p = provider(rec)
    assert call(p).data == {"findings": []}
    assert "output_config" in rec.bodies[0] and "output_config" not in rec.bodies[1]
    assert "JSON Schema" in rec.bodies[1]["messages"][0]["content"][1]["text"]
    call(p)  # remembered: no second attempt with the schema
    assert "output_config" not in rec.bodies[2]


def test_AC_LLM_13_other_bad_requests_are_not_retried():
    rec = Recorder([httpx2.Response(400, json={"type": "error", "error": {
        "type": "invalid_request_error", "message": "prompt is too long"}})])
    with pytest.raises(LlmError, match="HTTP 400.*prompt is too long"):
        call(provider(rec))
    assert len(rec.bodies) == 1


def test_AC_LLM_14_usage_includes_cache_read_and_write():
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000,
             "cache_read_input_tokens": 2_000_000, "cache_creation_input_tokens": 400_000}
    rec = Recorder([httpx2.Response(200, json=message("{}", usage))])
    p = provider(rec, price_per_mtok=Price(input=4.0, output=20.0, cache_read=0.2, cache_write=5.0))
    u = call(p).usage
    assert u.input_tokens == 3_400_000 and u.cached_tokens == 2_000_000 and u.output_tokens == 100_000
    # 1M*4 + 0.1M*20 + 2M*0.2 + 0.4M*5 = 4 + 2 + 0.4 + 2
    assert u.cost_usd == pytest.approx(8.4)
    assert u.calls == 1 and u.duration_s > 0


def test_AC_LLM_14_default_cache_prices():
    usage = {"input_tokens": 0, "output_tokens": 0,
             "cache_read_input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000}
    rec = Recorder([httpx2.Response(200, json=message("{}", usage))])
    u = call(provider(rec, price_per_mtok=Price(input=2.0, output=10.0))).usage
    assert u.cost_usd == pytest.approx(0.2 + 2.5)


def test_AC_LLM_15_errors_become_readable_llm_errors():
    rec = Recorder([httpx2.Response(529, json={"type": "error", "error": {
        "type": "overloaded_error", "message": "Overloaded"}})])
    with pytest.raises(LlmError, match="claude: HTTP 529 .*Overloaded"):
        call(provider(rec))


def test_AC_LLM_20_refusal_raises_llm_error():
    rec = Recorder([httpx2.Response(200, json=message("", stop_reason="refusal"))])
    with pytest.raises(LlmError, match="declined"):
        call(provider(rec))
