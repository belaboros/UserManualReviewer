"""Base class for LLM checks: prompt layout, context budget and fallback splitting (spec PROMPT)."""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import ClassVar

from umr.checks.base import Check, CheckContext
from umr.checks.llm.prompting import (
    SYSTEM_PROMPT,
    FindingsResponse,
    build_instruction,
    page_header,
    render_corpus,
    to_findings,
)
from umr.domain import Finding, Journey, Manual, Page, Scope, Tier
from umr.llm.base import LlmError, LlmProvider
from umr.llm.structured import complete_validated

BUDGET_RATIO = 0.7  # share of the model's context the prompt may use


@dataclass
class PromptUnit:
    """One LLM call: which manuals (and optionally which pages) the corpus block contains."""

    manuals: list[Manual]
    pages: list[Page] | None = None
    note: str = ""

    def corpus(self, journey: Journey) -> str:
        return render_corpus(journey, manuals=self.manuals, pages=self.pages)


def budget_tokens(provider: LlmProvider) -> int:
    return int(provider.config.context_tokens * BUDGET_RATIO)


class LlmCheck(Check):
    tier: ClassVar[Tier] = Tier.LLM
    task: ClassVar[str]  # the check instruction, placed after the corpus

    # ----- hooks -----

    def accept(self, finding: Finding) -> bool:
        """Findings without a location cannot be verified and are dropped."""
        return bool(finding.locations)

    # ----- planning -----

    def _fits(self, provider: LlmProvider, journey: Journey, unit: PromptUnit) -> bool:
        text = SYSTEM_PROMPT + unit.corpus(journey) + self.instruction(unit)
        return provider.estimate_tokens(text) <= budget_tokens(provider)

    def _page_groups(self, provider: LlmProvider, journey: Journey, manuals: list[Manual],
                     note: str) -> list[PromptUnit]:
        """Pack the pages of `manuals` greedily into groups that fit the budget (a too-big page goes alone)."""
        base = provider.estimate_tokens(SYSTEM_PROMPT + render_corpus(journey, manuals=manuals, pages=[])
                                        + self.instruction(PromptUnit(manuals, [], note)))
        limit = budget_tokens(provider)
        groups: list[list[Page]] = []
        current: list[Page] = []
        used = base
        for m in manuals:
            for page in m.pages:
                cost = provider.estimate_tokens(page_header(page, m) + "\n" + page.plain_text + "\n")
                if current and used + cost > limit:
                    groups.append(current)
                    current, used = [], base
                current.append(page)
                used += cost
        if current:
            groups.append(current)
        units = []
        for n, pages in enumerate(groups, 1):
            group_note = (f"{note} You see page group {n} of {len(groups)} only; other pages exist."
                          if len(groups) > 1 else note)
            units.append(PromptUnit(manuals, pages, group_note.strip()))
        return units

    def plan(self, journey: Journey, provider: LlmProvider) -> list[PromptUnit]:
        if self.scope == Scope.MANUAL:
            units: list[PromptUnit] = []
            for m in journey.manuals:
                unit = PromptUnit([m], note=f"Review only the manual '{m.id}'.")
                units += [unit] if self._fits(provider, journey, unit) else self._page_groups(
                    provider, journey, [m], unit.note)
            return units
        full = PromptUnit(list(journey.manuals))
        if self._fits(provider, journey, full):
            return [full]
        if len(journey.manuals) < 2:
            return self._page_groups(provider, journey, list(journey.manuals), "")
        units = []
        for a, b in itertools.combinations(journey.manuals, 2):
            note = (f"The full set has {len(journey.manuals)} manuals; you see only '{a.id}' and '{b.id}'. "
                    "Report only problems visible in these two.")
            unit = PromptUnit([a, b], note=note)
            units += [unit] if self._fits(provider, journey, unit) else self._page_groups(
                provider, journey, [a, b], note)
        return units

    def instruction(self, unit: PromptUnit) -> str:
        return build_instruction(self.task, self.categories, scope_note=unit.note)

    # ----- run -----

    def run(self, ctx: CheckContext) -> list[Finding]:
        provider = ctx.provider
        if provider is None:
            raise LlmError(f"Check '{self.id}' needs an LLM provider")
        findings: list[Finding] = []
        for unit in self.plan(ctx.journey, provider):
            result = complete_validated(provider, system=SYSTEM_PROMPT, cache_prefix=unit.corpus(ctx.journey),
                                        prompt=self.instruction(unit), model_cls=FindingsResponse,
                                        stats=ctx.llm_stats, usage=ctx.usage)
            found = to_findings(result.data, check_id=self.id, categories=self.categories,
                                source=provider.name, journey=ctx.journey)
            findings += [f for f in found if self.accept(f)]
        return _dedupe(findings)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    out = []
    for f in findings:
        key = (str(f.category), tuple(sorted((loc.page_id, _norm(loc.quote)) for loc in f.locations)))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out
