"""Spec LLM: OpenAI-compatible adapter (requests, structured output modes, usage, errors)."""

import json
from typing import Any

import httpx2
import openai
import pytest

from umr.llm import Adapter, LlmError, Price, ProviderConfig, StructuredOutput
from umr.llm.openai_compat import OpenAICompatibleProvider

SCHEMA = {"type": "object", "properties": {"findings": {"type": "array"}}, "required": ["findings"]}


def completion(content: str | None, usage: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": "c1", "object": "chat.completion", "created": 0, "model": "test-model",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
            "usage": usage or {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200}}


class Recorder:
    """Mock HTTP transport for the real OpenAI SDK."""

    def __init__(self, responses: list[httpx2.Response]):
        self.responses = responses
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        return self.responses[min(len(self.bodies), len(self.responses)) - 1]


def provider(mode: StructuredOutput, rec: Recorder, **cfg: Any) -> OpenAICompatibleProvider:
    config = ProviderConfig(name="t", adapter=Adapter.OPENAI_COMPATIBLE, model="test-model",
                            base_url="http://localhost:9/v1", structured_output=mode, **cfg)
    client = openai.OpenAI(api_key="x", base_url=config.base_url, max_retries=0,
                           http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(rec)))
    return OpenAICompatibleProvider(config, client=client)


def call(p: OpenAICompatibleProvider):
    return p.complete(system="SYS", cache_prefix="MANUALS", prompt="TASK", schema=SCHEMA, schema_name="findings")


def test_AC_LLM_07_json_schema_mode_sends_response_format():
    rec = Recorder([httpx2.Response(200, json=completion('{"findings": []}'))])
    result = call(provider(StructuredOutput.JSON_SCHEMA, rec))
    body = rec.bodies[0]
    assert body["response_format"] == {"type": "json_schema", "json_schema": {
        "name": "findings", "schema": SCHEMA, "strict": False}}
    assert result.data == {"findings": []}
    assert "JSON Schema" not in body["messages"][1]["content"]


def test_AC_LLM_08_json_object_mode_describes_schema_in_prompt():
    rec = Recorder([httpx2.Response(200, json=completion('{"findings": [1]}'))])
    result = call(provider(StructuredOutput.JSON_OBJECT, rec))
    body = rec.bodies[0]
    assert body["response_format"] == {"type": "json_object"}
    user = body["messages"][1]["content"]
    assert user.startswith("MANUALS\n\nTASK") and json.dumps(SCHEMA, sort_keys=True) in user
    assert result.data == {"findings": [1]}


def test_AC_LLM_09_prompt_mode_extracts_json_from_text():
    text = "<think>let me reason {not json}</think>\nHere you go:\n```json\n{\"findings\": [2]}\n```\nDone."
    rec = Recorder([httpx2.Response(200, json=completion(text))])
    result = call(provider(StructuredOutput.PROMPT, rec))
    assert "response_format" not in rec.bodies[0]
    assert "JSON Schema" in rec.bodies[0]["messages"][1]["content"]
    assert result.data == {"findings": [2]} and result.raw_text == text


def test_AC_LLM_09_unparseable_text_gives_no_data():
    rec = Recorder([httpx2.Response(200, json=completion("I cannot answer that."))])
    result = call(provider(StructuredOutput.PROMPT, rec))
    assert result.data is None


def test_AC_LLM_10_message_layout_and_temperature():
    rec = Recorder([httpx2.Response(200, json=completion("{}"))] * 2)
    call(provider(StructuredOutput.JSON_SCHEMA, rec))
    body = rec.bodies[0]
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"] == "SYS"
    assert body["messages"][1]["content"] == "MANUALS\n\nTASK"
    assert body["temperature"] == 0.0 and body["max_tokens"] == 16000
    call(provider(StructuredOutput.JSON_SCHEMA, rec, temperature=None,
                  extra={"max_tokens_param": "max_completion_tokens", "extra_body": {"num_ctx": 8192}}))
    body = rec.bodies[1]
    assert "temperature" not in body and "max_tokens" not in body
    assert body["max_completion_tokens"] == 16000 and body["num_ctx"] == 8192


def test_AC_LLM_11_usage_and_cost_with_cached_tokens():
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 100_000, "total_tokens": 1_100_000,
             "prompt_tokens_details": {"cached_tokens": 400_000}}
    rec = Recorder([httpx2.Response(200, json=completion("{}", usage))])
    p = provider(StructuredOutput.JSON_SCHEMA, rec,
                 price_per_mtok=Price(input=2.0, output=10.0, cache_read=0.5))
    u = call(p).usage
    assert (u.input_tokens, u.output_tokens, u.cached_tokens, u.calls) == (1_000_000, 100_000, 400_000, 1)
    # 600k uncached * 2 + 400k cached * 0.5 + 100k out * 10 = 1.2 + 0.2 + 1.0
    assert u.cost_usd == pytest.approx(2.4)
    assert u.duration_s >= 0


def test_AC_LLM_11_cache_read_defaults_to_input_price():
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 0, "total_tokens": 1_000_000,
             "prompt_tokens_details": {"cached_tokens": 500_000}}
    rec = Recorder([httpx2.Response(200, json=completion("{}", usage))])
    p = provider(StructuredOutput.JSON_SCHEMA, rec, price_per_mtok=Price(input=1.0, output=1.0))
    assert call(p).usage.cost_usd == pytest.approx(1.0)


def test_AC_LLM_15_http_error_becomes_readable_llm_error():
    rec = Recorder([httpx2.Response(401, json={"error": {"message": "Invalid API key", "type": "auth"}})])
    with pytest.raises(LlmError, match=r"t: HTTP 401 .*Invalid API key"):
        call(provider(StructuredOutput.JSON_SCHEMA, rec))


def test_AC_LLM_15_connection_error_becomes_llm_error():
    def boom(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    config = ProviderConfig(name="t", adapter=Adapter.OPENAI_COMPATIBLE, model="m", base_url="http://localhost:9/v1")
    client = openai.OpenAI(api_key="x", base_url=config.base_url, max_retries=0,
                           http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(boom)))
    with pytest.raises(LlmError, match="cannot connect"):
        call(OpenAICompatibleProvider(config, client=client))


def test_AC_LLM_15_rate_limit_is_retried_by_the_sdk():
    rec = Recorder([httpx2.Response(429, json={"error": {"message": "slow down"}}, headers={"retry-after": "0"}),
                    httpx2.Response(200, json=completion('{"findings": []}'))])
    config = ProviderConfig(name="t", adapter=Adapter.OPENAI_COMPATIBLE, model="m", base_url="http://localhost:9/v1")
    client = openai.OpenAI(api_key="x", base_url=config.base_url, max_retries=2,
                           http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(rec)))
    result = call(OpenAICompatibleProvider(config, client=client))
    assert result.data == {"findings": []} and len(rec.bodies) == 2


def test_AC_LLM_19_duration_and_calls_set():
    rec = Recorder([httpx2.Response(200, json=completion("{}"))])
    u = call(provider(StructuredOutput.JSON_SCHEMA, rec)).usage
    assert u.calls == 1 and u.duration_s > 0
