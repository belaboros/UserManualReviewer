"""Access to app-layer services that may not be present in every build.

The provider config, comparison and evaluation layers are optional for the GUI: when one is missing the
GUI still opens and says what is unavailable instead of crashing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from umr.llm.base import LlmProvider

PROVIDERS_FILE = Path("config/llm-providers.yaml")
PROVIDERS_EXAMPLE = Path("config/llm-providers.example.yaml")


def _same(provider: LlmProvider) -> LlmProvider:
    return provider


@dataclass
class ProviderCatalog:
    """Names of configured providers and a way to build each one on demand."""

    factories: dict[str, Callable[[], LlmProvider]] = field(default_factory=dict)
    notice: str = ""

    def names(self) -> list[str]:
        return list(self.factories)

    def make(self, name: str) -> LlmProvider:
        return self.factories[name]()

    @classmethod
    def from_providers(cls, providers: dict[str, LlmProvider], notice: str = "") -> ProviderCatalog:
        return cls({name: partial(_same, p) for name, p in providers.items()}, notice)

    @classmethod
    def load(cls, config_file: Path = PROVIDERS_FILE, example_file: Path = PROVIDERS_EXAMPLE) -> ProviderCatalog:
        try:
            from umr.llm.config import load_providers, make_provider
        except ImportError:
            return cls(notice="LLM provider support is not available in this build — only rule checks can run.")
        notice = ""
        path = config_file
        if not path.exists():
            if not example_file.exists():
                return cls(notice=f"No {config_file} found — only rule checks can run.")
            path = example_file
            notice = (f"Using {example_file} because {config_file} does not exist. "
                      "API keys are read from the environment variables it names (api_key_env).")
        try:
            configs = load_providers(path)
        except Exception as e:  # show the problem, keep the GUI usable
            return cls(notice=f"Could not read {path}: {e}")
        factories: dict[str, Callable[[], LlmProvider]] = {cfg.name: partial(make_provider, cfg) for cfg in configs}
        return cls(factories, notice)


def make_compare_service(review: Any = None) -> Any | None:
    try:
        from umr.app.compare import CompareService
    except ImportError:
        return None
    return CompareService(review=review)


def make_eval_service() -> Any | None:
    try:
        from umr.app.evaluation import EvalService
    except ImportError:
        return None
    return EvalService()


def make_eval_store() -> Any | None:
    try:
        from umr.storage.evals import EvalStore
    except ImportError:
        return None
    return EvalStore()


def leaderboard(results: list[Any]) -> list[Any]:
    try:
        from umr.app.evaluation import leaderboard as lb
    except ImportError:
        return sorted(results, key=lambda r: -float(getattr(r, "eval_score", 0.0)))
    return list(lb(results))
