"""Hand-built findings, runs and a tiny LLM check for the compare and eval tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import ClassVar

from umr.checks import Check, CheckContext
from umr.domain import (
    Category,
    Finding,
    LlmCallStats,
    Location,
    ReviewRun,
    Scope,
    Severity,
    Tier,
    Usage,
)


def loc(page: str, line: int | None = None, quote: str = "", end: int | None = None) -> Location:
    manual_id, _, path = page.partition("/")
    return Location(manual_id=manual_id, page_path=path, line_start=line, line_end=end or line, quote=quote,
                    verified=line is not None)


def finding(category: Category | str, *locations: Location, severity: Severity = Severity.MAJOR,
            check_id: str = "test-llm", source: str = "fake", fid: str = "", verified: bool = True,
            title: str = "t") -> Finding:
    return Finding(id=fid, check_id=check_id, category=Category(category), severity=severity, title=title,
                   locations=list(locations), source=source, verified=verified)


def run(*findings: Finding, model: str = "fake", stats: LlmCallStats | None = None,
        started: datetime | None = None, usage: Usage | None = None) -> ReviewRun:
    fs = list(findings)
    for n, f in enumerate(fs, 1):
        f.id = f.id or f"F{n:03d}"
    return ReviewRun(id=uuid.uuid4().hex, started_at=started or datetime.now(UTC), journey_name="j",
                     journey_path="j", checks=["test-llm"], model=model, findings=fs,
                     llm_stats=stats or LlmCallStats(), usage=usage or Usage())


class FindingsCheck(Check):
    """Test-only LLM check: asks the provider for {"findings": [...]} and turns them into findings."""

    id: ClassVar[str] = "test-llm"
    title: ClassVar[str] = "Test LLM check"
    description: ClassVar[str] = "test only"
    tier: ClassVar[Tier] = Tier.LLM
    scope: ClassVar[Scope] = Scope.JOURNEY
    categories: ClassVar[tuple[Category, ...]] = tuple(Category)

    def applies_to(self, journey: object) -> bool:  # type: ignore[override]
        return True

    def run(self, ctx: CheckContext) -> list[Finding]:
        assert ctx.provider is not None
        result = ctx.provider.complete(system="s", cache_prefix="manuals", prompt="find problems",
                                       schema={}, schema_name="findings")
        ctx.usage.add(result.usage)
        ctx.llm_stats.calls += 1
        data = result.data
        if not isinstance(data, dict) or "findings" not in data:
            ctx.llm_stats.failed += 1
            raise ValueError("invalid output")
        ctx.llm_stats.valid_first_try += 1
        out = []
        for item in data["findings"]:
            out.append(Finding(check_id=self.id, category=Category(item["category"]),
                               severity=Severity(item["severity"]), title=item.get("title", "x"),
                               source=ctx.provider.name,
                               locations=[Location(manual_id=lc["page"].split("/", 1)[0],
                                                   page_path=lc["page"].split("/", 1)[1], quote=lc["quote"])
                                          for lc in item["locations"]]))
        return out
