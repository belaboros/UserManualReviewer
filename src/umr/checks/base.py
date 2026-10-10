"""Check interface and registry (ADR-0006)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from umr.domain import Category, Finding, Journey, Scope, Tier, Usage

if TYPE_CHECKING:
    from umr.llm.base import LlmProvider


@dataclass
class CheckContext:
    journey: Journey
    provider: LlmProvider | None = None
    usage: Usage = field(default_factory=Usage)


class Check(ABC):
    id: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    tier: ClassVar[Tier]
    scope: ClassVar[Scope]
    categories: ClassVar[tuple[Category, ...]]

    def applies_to(self, journey: Journey) -> bool:
        return self.scope != Scope.JOURNEY or len(journey.manuals) >= 2

    @abstractmethod
    def run(self, ctx: CheckContext) -> list[Finding]: ...


class CheckRegistry:
    _checks: ClassVar[dict[str, type[Check]]] = {}

    @classmethod
    def register(cls, check_cls: type[Check]) -> type[Check]:
        cls._checks[check_cls.id] = check_cls
        return check_cls

    @classmethod
    def all(cls) -> list[type[Check]]:
        _load_builtin_checks()
        return list(cls._checks.values())

    @classmethod
    def get(cls, check_id: str) -> type[Check]:
        _load_builtin_checks()
        if check_id not in cls._checks:
            raise KeyError(f"Unknown check '{check_id}'. Known: {', '.join(sorted(cls._checks))}")
        return cls._checks[check_id]

    @classmethod
    def ids(cls, tier: Tier | None = None) -> list[str]:
        return [c.id for c in cls.all() if tier is None or c.tier == tier]


register = CheckRegistry.register


def _load_builtin_checks() -> None:
    import umr.checks.llm  # noqa: F401
    import umr.checks.rules  # noqa: F401
