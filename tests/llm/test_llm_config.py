"""Spec LLM: provider config file, API keys, provider factory."""

from pathlib import Path

import pytest

from umr.llm import Adapter, LlmError, ProviderConfig, ProviderConfigError, StructuredOutput
from umr.llm.anthropic_native import AnthropicProvider
from umr.llm.config import get_api_key, is_local_url, load_env, load_providers, make_provider
from umr.llm.fake import FakeProvider
from umr.llm.openai_compat import OpenAICompatibleProvider

REPO = Path(__file__).resolve().parents[2]


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "llm-providers.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_AC_LLM_01_example_config_loads():
    configs = load_providers(REPO / "config" / "llm-providers.example.yaml", load_dotenv_files=False)
    names = [c.name for c in configs]
    assert "claude-opus" in names and "local-ollama" in names
    ollama = next(c for c in configs if c.name == "local-ollama")
    assert ollama.adapter == Adapter.OPENAI_COMPATIBLE
    assert ollama.structured_output == StructuredOutput.JSON_OBJECT
    assert ollama.context_tokens == 32768
    claude = next(c for c in configs if c.name == "claude-opus")
    assert claude.price_per_mtok.cache_read == 0.20 and claude.price_per_mtok.cache_write == 5.00
    gpt = next(c for c in configs if c.name == "gpt")
    assert gpt.temperature is None


def test_AC_LLM_02_invalid_field_names_provider_field_and_line(tmp_path):
    p = write(tmp_path, "providers:\n  - name: ok\n    adapter: anthropic\n    model: m\n"
                        "  - name: broken\n    adapter: openai-compatible\n    model: m\n"
                        "    structured_output: xml\n")
    with pytest.raises(ProviderConfigError) as e:
        load_providers(p, load_dotenv_files=False)
    msg = str(e.value)
    assert "provider 'broken'" in msg and "structured_output" in msg and ":8:" in msg


def test_AC_LLM_02_missing_required_field(tmp_path):
    p = write(tmp_path, "providers:\n  - name: nomodel\n    adapter: anthropic\n")
    with pytest.raises(ProviderConfigError, match="provider 'nomodel'.*field 'model'"):
        load_providers(p, load_dotenv_files=False)


def test_AC_LLM_02_bad_yaml_and_bad_top_level(tmp_path):
    with pytest.raises(ProviderConfigError, match="invalid YAML"):
        load_providers(write(tmp_path, "providers: [\n"), load_dotenv_files=False)
    with pytest.raises(ProviderConfigError, match="providers"):
        load_providers(write(tmp_path, "- a\n"), load_dotenv_files=False)
    with pytest.raises(ProviderConfigError, match="not found"):
        load_providers(tmp_path / "missing.yaml", load_dotenv_files=False)


def test_AC_LLM_03_duplicate_names_rejected(tmp_path):
    p = write(tmp_path, "providers:\n  - {name: a, adapter: anthropic, model: m}\n"
                        "  - {name: a, adapter: openai-compatible, model: n}\n")
    with pytest.raises(ProviderConfigError, match="duplicate provider name 'a'"):
        load_providers(p, load_dotenv_files=False)


def test_AC_LLM_21_unknown_field_rejected(tmp_path):
    p = write(tmp_path, "providers:\n  - name: typo\n    adapter: anthropic\n    model: m\n"
                        "    strutured_output: prompt\n")
    with pytest.raises(ProviderConfigError, match=r":5: provider 'typo': unknown field 'strutured_output'"):
        load_providers(p, load_dotenv_files=False)


def test_AC_LLM_04_api_key_read_from_env(monkeypatch):
    monkeypatch.setenv("UMR_TEST_KEY", "sk-test")
    cfg = ProviderConfig(name="x", adapter=Adapter.OPENAI_COMPATIBLE, model="m",
                         base_url="https://api.example.com/v1", api_key_env="UMR_TEST_KEY")
    assert get_api_key(cfg) == "sk-test"


def test_AC_LLM_04_api_key_read_from_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("UMR_TEST_DOTENV_KEY", raising=False)
    (tmp_path / ".env").write_text("UMR_TEST_DOTENV_KEY=from-dotenv\n", encoding="utf-8")
    load_env(tmp_path)
    cfg = ProviderConfig(name="x", adapter=Adapter.ANTHROPIC, model="m", api_key_env="UMR_TEST_DOTENV_KEY")
    try:
        assert get_api_key(cfg) == "from-dotenv"
    finally:
        monkeypatch.delenv("UMR_TEST_DOTENV_KEY", raising=False)


def test_AC_LLM_05_saas_without_key_is_clear_error(monkeypatch):
    monkeypatch.delenv("UMR_UNSET_KEY", raising=False)
    cfg = ProviderConfig(name="gpt", adapter=Adapter.OPENAI_COMPATIBLE, model="m",
                         base_url="https://api.openai.com/v1", api_key_env="UMR_UNSET_KEY")
    with pytest.raises(LlmError, match="gpt.*UMR_UNSET_KEY is not set"):
        get_api_key(cfg)
    no_env = ProviderConfig(name="claude", adapter=Adapter.ANTHROPIC, model="m")
    with pytest.raises(LlmError, match="claude.*needs an API key"):
        get_api_key(no_env)


def test_AC_LLM_05_local_server_needs_no_key(monkeypatch):
    monkeypatch.delenv("UMR_UNSET_KEY", raising=False)
    for url in ("http://localhost:11434/v1", "http://127.0.0.1:1234/v1", "http://192.168.1.20:8000/v1"):
        assert is_local_url(url)
        cfg = ProviderConfig(name="local", adapter=Adapter.OPENAI_COMPATIBLE, model="m", base_url=url)
        assert get_api_key(cfg) is None
        cfg2 = cfg.model_copy(update={"api_key_env": "UMR_UNSET_KEY"})
        assert get_api_key(cfg2) is None
    assert not is_local_url("https://api.openai.com/v1")


def test_AC_LLM_06_make_provider_by_adapter(monkeypatch):
    monkeypatch.setenv("UMR_TEST_KEY", "k")
    oa = make_provider(ProviderConfig(name="o", adapter=Adapter.OPENAI_COMPATIBLE, model="m",
                                      base_url="http://localhost:11434/v1"))
    an = make_provider(ProviderConfig(name="a", adapter=Adapter.ANTHROPIC, model="m", api_key_env="UMR_TEST_KEY"))
    fk = make_provider(ProviderConfig(name="f", adapter=Adapter.FAKE, model="m"))
    assert isinstance(oa, OpenAICompatibleProvider) and oa.name == "o"
    assert isinstance(an, AnthropicProvider) and an.name == "a"
    assert isinstance(fk, FakeProvider) and fk.name == "f"


def test_AC_LLM_15_client_uses_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("UMR_TEST_KEY", "k")
    oa = make_provider(ProviderConfig(name="o", adapter=Adapter.OPENAI_COMPATIBLE, model="m", timeout_s=42,
                                      base_url="http://localhost:1234/v1", extra={"max_retries": 3}))
    an = make_provider(ProviderConfig(name="a", adapter=Adapter.ANTHROPIC, model="m", timeout_s=17,
                                      api_key_env="UMR_TEST_KEY"))
    assert oa.client.timeout == 42 and oa.client.max_retries == 3
    assert an.client.timeout == 17 and an.client.max_retries == 2
