"""Load `config/llm-providers.yaml`, read API keys, build providers (ADR-0004, spec LLM)."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from umr.llm.base import Adapter, LlmError, LlmProvider, ProviderConfig


class ProviderConfigError(LlmError):
    """The provider config file is missing, malformed or invalid."""


_LOCAL_HOSTS = {"localhost", "host.docker.internal", "0.0.0.0"}


def is_local_url(base_url: str | None) -> bool:
    """True for servers on this machine or the local network (no API key needed)."""
    if not base_url:
        return False
    host = (urlparse(base_url).hostname or "").lower()
    if host in _LOCAL_HOSTS or host.endswith(".local") or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def load_env(*folders: Path) -> None:
    """Load `.env` files (without overriding variables that are already set)."""
    seen: set[Path] = set()
    for folder in (*folders, Path.cwd()):
        env = (folder / ".env").resolve()
        if env in seen:
            continue
        seen.add(env)
        if env.is_file():
            load_dotenv(env, override=False)


def _line_of(node: yaml.Node | None) -> int | None:
    return node.start_mark.line + 1 if node is not None else None


def _provider_nodes(text: str) -> list[yaml.MappingNode | None]:
    """YAML nodes of each provider entry, for line numbers in error messages."""
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return []
    if not isinstance(root, yaml.MappingNode):
        return []
    for key, value in root.value:
        if key.value == "providers" and isinstance(value, yaml.SequenceNode):
            return [n if isinstance(n, yaml.MappingNode) else None for n in value.value]
    return []


def _field_line(node: yaml.MappingNode | None, field: str) -> int | None:
    if node is None:
        return None
    for key, value in node.value:
        if key.value == field:
            return _line_of(value)
    return _line_of(node)


def load_providers(path: Path, *, load_dotenv_files: bool = True) -> list[ProviderConfig]:
    """Read and validate the provider list. Errors name the line, the provider and the field."""
    path = Path(path)
    if load_dotenv_files:
        load_env(path.resolve().parent, path.resolve().parent.parent)
    if not path.is_file():
        raise ProviderConfigError(f"Provider config not found: {path} (copy config/llm-providers.example.yaml)")
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise ProviderConfigError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("providers"), list):
        raise ProviderConfigError(f"{path}: expected a top-level 'providers:' list")
    nodes = _provider_nodes(text)
    known = set(ProviderConfig.model_fields)
    configs: list[ProviderConfig] = []
    names: dict[str, int] = {}
    for i, entry in enumerate(data["providers"]):
        node = nodes[i] if i < len(nodes) else None
        line = _line_of(node)
        where = f"{path}:{line}" if line else str(path)
        if not isinstance(entry, dict):
            raise ProviderConfigError(f"{where}: provider #{i + 1} must be a mapping")
        label = f"provider '{entry['name']}'" if entry.get("name") else f"provider #{i + 1}"
        unknown = sorted(set(entry) - known)
        if unknown:
            fline = _field_line(node, unknown[0])
            raise ProviderConfigError(
                f"{path}:{fline}: {label}: unknown field '{unknown[0]}' (known: {', '.join(sorted(known))})")
        try:
            cfg = ProviderConfig.model_validate(entry)
        except ValidationError as e:
            err = e.errors()[0]
            field = ".".join(str(p) for p in err["loc"]) or "?"
            fline = _field_line(node, str(err["loc"][0])) if err["loc"] else line
            raise ProviderConfigError(f"{path}:{fline}: {label}: field '{field}': {err['msg']}") from e
        if cfg.name in names:
            raise ProviderConfigError(
                f"{where}: duplicate provider name '{cfg.name}' (first defined as provider #{names[cfg.name]})")
        names[cfg.name] = i + 1
        configs.append(cfg)
    if not configs:
        raise ProviderConfigError(f"{path}: no providers defined")
    return configs


def get_api_key(cfg: ProviderConfig) -> str | None:
    """API key from the environment variable named in `api_key_env`.

    Local servers may have no key (None is returned); a SaaS endpoint without a key is an error.
    """
    if cfg.adapter == Adapter.FAKE:
        return None
    local = is_local_url(cfg.base_url)
    if cfg.api_key_env:
        value = os.environ.get(cfg.api_key_env, "").strip()
        if value:
            return value
        if local:
            return None
        raise LlmError(f"Provider '{cfg.name}': environment variable {cfg.api_key_env} is not set. "
                       f"Set it in your environment or in a .env file.")
    if local:
        return None
    endpoint = cfg.base_url or ("the Anthropic API" if cfg.adapter == Adapter.ANTHROPIC else "the OpenAI API")
    raise LlmError(f"Provider '{cfg.name}': {endpoint} needs an API key, but no api_key_env is configured.")


def make_provider(cfg: ProviderConfig, **kwargs: Any) -> LlmProvider:
    """Create the provider for `cfg.adapter`. Extra keyword arguments go to the provider (e.g. `client=`)."""
    if cfg.adapter == Adapter.OPENAI_COMPATIBLE:
        from umr.llm.openai_compat import OpenAICompatibleProvider
        return OpenAICompatibleProvider(cfg, **kwargs)
    if cfg.adapter == Adapter.ANTHROPIC:
        from umr.llm.anthropic_native import AnthropicProvider
        return AnthropicProvider(cfg, **kwargs)
    if cfg.adapter == Adapter.FAKE:
        from umr.llm.fake import FakeProvider
        return FakeProvider(config=cfg, **kwargs)
    raise LlmError(f"Provider '{cfg.name}': unknown adapter '{cfg.adapter}'")


def find_provider(configs: list[ProviderConfig], name: str) -> ProviderConfig:
    for cfg in configs:
        if cfg.name == name:
            return cfg
    raise LlmError(f"Unknown provider '{name}'. Configured: {', '.join(c.name for c in configs)}")
