"""Spec LLM: call log of every request and response (AC-LLM-22..27)."""

import json
import logging
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import openai
import pytest

from umr import cli
from umr.llm import Adapter, LlmError, ProviderConfig, StructuredOutput, calllog
from umr.llm.anthropic_native import AnthropicProvider
from umr.llm.openai_compat import OpenAICompatibleProvider

SCHEMA = {"type": "object", "properties": {"findings": {"type": "array"}}, "required": ["findings"]}


def completion(content: str) -> dict[str, Any]:
    return {"id": "c1", "object": "chat.completion", "created": 0, "model": "local-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 7, "total_tokens": 57}}


def openai_provider(handler: Any, key: str = "x") -> OpenAICompatibleProvider:
    config = ProviderConfig(name="local-lmstudio", adapter=Adapter.OPENAI_COMPATIBLE, model="local-model",
                            base_url="http://localhost:1234/v1", structured_output=StructuredOutput.JSON_SCHEMA)
    client = openai.OpenAI(api_key=key, base_url=config.base_url, max_retries=0, timeout=2,
                           http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    return OpenAICompatibleProvider(config, client=client)


def entries() -> list[dict[str, Any]]:
    path = calllog.log_file()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def call(p: Any) -> Any:
    return p.complete(system="SYS", cache_prefix="MANUALS", prompt="TASK", schema=SCHEMA)


def test_AC_LLM_22_request_logged_with_url_model_and_body():
    call(openai_provider(lambda r: httpx2.Response(200, json=completion('{"findings": []}'))))
    req = entries()[0]
    assert req["event"] == "request" and req["provider"] == "local-lmstudio"
    assert req["url"] == "http://localhost:1234/v1/chat/completions" and req["model"] == "local-model"
    assert req["request"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert req["request"]["messages"][1]["content"].startswith("MANUALS\n\nTASK")
    assert req["request"]["response_format"]["type"] == "json_schema"


def test_AC_LLM_22_anthropic_request_logged():
    def handler(r: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={
            "id": "m1", "type": "message", "role": "assistant", "model": "claude-test", "stop_reason": "end_turn",
            "content": [{"type": "text", "text": '{"findings": []}'}],
            "usage": {"input_tokens": 10, "output_tokens": 3}})

    config = ProviderConfig(name="claude", adapter=Adapter.ANTHROPIC, model="claude-test")
    client = anthropic.Anthropic(api_key="sk-ant-secret", max_retries=0,
                                 http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    call(AnthropicProvider(config, client=client))
    req, resp = entries()
    assert req["url"] == "https://api.anthropic.com/v1/messages" and req["request"]["model"] == "claude-test"
    assert resp["event"] == "response" and resp["raw_text"] == '{"findings": []}'
    assert resp["finish_reason"] == "end_turn"
    assert "sk-ant-secret" not in calllog.log_file().read_text(encoding="utf-8")


def test_AC_LLM_23_response_logged_with_same_call_id():
    call(openai_provider(lambda r: httpx2.Response(200, json=completion('{"findings": [1]}'))))
    req, resp = entries()
    assert resp["call_id"] == req["call_id"] and resp["event"] == "response"
    assert resp["raw_text"] == '{"findings": [1]}' and resp["finish_reason"] == "stop"
    assert resp["response"]["usage"]["prompt_tokens"] == 50 and resp["duration_s"] >= 0


def test_AC_LLM_24_http_error_logs_status_and_server_body(capsys: pytest.CaptureFixture[str]):
    body = {"error": "Trying to keep the first 5210 tokens when context the overflows. "
                     "However, the model is loaded with context length of only 4096 tokens"}
    p = openai_provider(lambda r: httpx2.Response(400, json=body))
    with pytest.raises(LlmError, match="HTTP 400 from http://localhost:1234/v1"):
        call(p)
    err = entries()[1]
    assert err["event"] == "error" and err["status_code"] == 400
    assert "context length of only 4096" in json.dumps(err["response_body"])


def test_AC_LLM_24_connection_error_logged():
    def refuse(r: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused")

    with pytest.raises(LlmError, match="cannot connect"):
        call(openai_provider(refuse))
    err = entries()[1]
    assert err["event"] == "error" and err["error_type"] == "APIConnectionError"


def test_AC_LLM_24_cli_names_log_file(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    def boom(args: Any) -> int:
        raise LlmError("local-lmstudio: HTTP 400")

    monkeypatch.setattr(cli, "cmd_checks", boom)
    assert cli.main(["checks"]) == 3
    assert str(calllog.log_file()) in capsys.readouterr().err


def test_AC_LLM_25_summaries_on_umr_llm_logger(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="umr.llm"):
        call(openai_provider(lambda r: httpx2.Response(200, json=completion('{"findings": []}'))))
    lines = [r.getMessage() for r in caplog.records if r.name == "umr.llm"]
    assert any("POST http://localhost:1234/v1/chat/completions" in m for m in lines)
    assert any("OK in" in m and '{"findings": []}' in m for m in lines)


def test_AC_LLM_25_cli_verbose_prints_summaries(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(cli, "cmd_checks", lambda args: logging.getLogger("umr.llm").info("→ hello") or 0)
    logger = logging.getLogger("umr.llm")
    before = list(logger.handlers)
    try:
        cli.main(["-v", "checks"])
    finally:
        for h in logger.handlers[len(before):]:
            logger.removeHandler(h)
    assert "→ hello" in capsys.readouterr().err


def test_AC_LLM_26_providers_test_ok_and_failed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    ok = openai_provider(lambda r: httpx2.Response(200, json=completion('{"ok": true}')))
    monkeypatch.setattr(cli, "_provider", lambda name, f: ok)
    assert cli.main(["providers", "--test", "local-lmstudio"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("OK: local-lmstudio") and str(calllog.log_file()) in out
    assert entries()[0]["request"]["response_format"]["json_schema"]["name"] == "ping"

    bad = openai_provider(lambda r: httpx2.Response(404, json={"error": "model not found"}))
    monkeypatch.setattr(cli, "_provider", lambda name, f: bad)
    assert cli.main(["providers", "--test", "local-lmstudio"]) == 3
    err = capsys.readouterr().err
    assert err.startswith("FAILED: local-lmstudio: HTTP 404") and str(calllog.log_file()) in err


def test_AC_LLM_27_keys_redacted_and_log_can_be_disabled(monkeypatch: pytest.MonkeyPatch):
    call(openai_provider(lambda r: httpx2.Response(200, json=completion("{}")), key="sk-very-secret"))
    assert "sk-very-secret" not in calllog.log_file().read_text(encoding="utf-8")
    record = calllog.CallRecord("p", "a", "u", "m", {"api_key": "sk-1", "nested": [{"Authorization": "Bearer x"}]})
    record.start()
    text = calllog.log_file().read_text(encoding="utf-8")
    assert "sk-1" not in text and "Bearer x" not in text and "<redacted>" in text

    monkeypatch.setenv("UMR_LLM_LOG", "0")
    size = calllog.log_file().stat().st_size
    call(openai_provider(lambda r: httpx2.Response(200, json=completion("{}"))))
    assert calllog.log_file().stat().st_size == size


def test_AC_LLM_27_unwritable_log_never_breaks_a_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("UMR_LOG_DIR", str(blocker / "logs"))
    result = call(openai_provider(lambda r: httpx2.Response(200, json=completion('{"findings": []}'))))
    assert result.data == {"findings": []}



def truncated(content: str, out: int, reasoning: int = 0) -> dict[str, Any]:
    body = completion(content)
    body["choices"][0]["finish_reason"] = "length"
    body["usage"] = {"prompt_tokens": 4316, "completion_tokens": out, "total_tokens": 4316 + out,
                     "completion_tokens_details": {"reasoning_tokens": reasoning}}
    return body


def test_AC_LLM_28_small_server_context_is_named_and_not_retried():
    from pydantic import BaseModel

    from umr.llm.structured import complete_validated

    class Out(BaseModel):
        findings: list[Any]

    calls = []

    def handler(r: httpx2.Request) -> httpx2.Response:
        calls.append(r)
        return httpx2.Response(200, json=truncated("", 3876, reasoning=3876))

    with pytest.raises(LlmError, match=r"ran out of context.*about 8,192 tokens.*Context Length") as exc:
        complete_validated(openai_provider(handler), system="S", cache_prefix="M", prompt="T", model_cls=Out)
    assert "3,876 of them reasoning" in str(exc.value)
    assert len(calls) == 1


def test_AC_LLM_28_output_limit_reached_suggests_max_output_tokens():
    p = openai_provider(lambda r: httpx2.Response(200, json=truncated('{"findings": [', 16000)))
    with pytest.raises(LlmError, match=r"reached max_output_tokens \(16,000\)"):
        call(p)


def test_AC_LLM_28_complete_json_despite_length_is_accepted():
    p = openai_provider(lambda r: httpx2.Response(200, json=truncated('{"findings": []}', 10)))
    assert call(p).data == {"findings": []}
