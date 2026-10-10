"""Helpers for the GUI tests: stub checks, fake evaluation service, hand-built runs and results."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from umr.app import ReviewService
from umr.app.evaluation import CategoryMetrics, EvalMetrics, EvalResult, ExpectedFinding
from umr.checks import Check, CheckContext
from umr.domain import (
    Category,
    Finding,
    Location,
    ReviewRun,
    Scope,
    Score,
    Severity,
    Tier,
    Usage,
)
from umr.storage.evals import EvalStore

if TYPE_CHECKING:
    from umr.gui.main_window import MainWindow

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "samples" / "shopflow" / "journey.yaml"
QUOTE = "You can add up to 50 line items to one order."
WORKER_THREADS: list[str] = []


class StubValueCheck(Check):
    id = "stub-value"
    title = "Stub value check"
    description = "Reports one quoted value on the order page."
    tier = Tier.RULE
    scope = Scope.JOURNEY
    categories = (Category.VALUE_CONFLICT,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        WORKER_THREADS.append(threading.current_thread().name)
        return [Finding(check_id=self.id, category=Category.VALUE_CONFLICT, severity=Severity.MAJOR,
                        title="Line item limit differs", explanation="The limit is 50 here but 40 elsewhere.",
                        suggested_fix="Use one limit everywhere.",
                        locations=[Location(manual_id="order-capturing", page_path="02-creating-an-order.md",
                                            quote=QUOTE)])]


class StubLinkCheck(Check):
    id = "stub-link"
    title = "Stub link check"
    description = "Reports a broken link on the dispatch page."
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.BROKEN_LINK,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        return [Finding(check_id=self.id, category=Category.BROKEN_LINK, severity=Severity.MINOR,
                        title="Broken link to 'returns.html'", explanation="The target does not exist.",
                        locations=[Location(manual_id="delivery", page_path="dispatch.html", line_start=12,
                                            line_end=12)])]


class StubLlmCheck(Check):
    id = "stub-llm"
    title = "Stub LLM check"
    description = "Asks the model; reports an invented quote."
    tier = Tier.LLM
    scope = Scope.JOURNEY
    categories = (Category.CONTRADICTION,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        assert ctx.provider is not None
        ctx.usage.add(Usage(input_tokens=1200, output_tokens=300, cost_usd=0.0123, calls=1))
        return [Finding(check_id=self.id, category=Category.CONTRADICTION, severity=Severity.CRITICAL,
                        title="Invented contradiction", explanation="Quoted text does not exist.",
                        source=ctx.provider.name, confidence=0.6,
                        locations=[Location(manual_id="delivery", page_path="dispatch.html",
                                            quote="this sentence is not in any manual at all")])]


class FailingCheck(Check):
    id = "stub-fail"
    title = "Failing check"
    description = "Always raises."
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.DUPLICATE,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        raise RuntimeError("boom in stub")


class EmptyCheck(Check):
    id = "stub-empty"
    title = "Empty check"
    description = "Never finds anything."
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.DUPLICATE,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        return []


class SlowCheck(Check):
    """Blocks until `release` is set, so a test can cancel while the review runs."""

    id = "stub-slow"
    title = "Slow check"
    description = "Waits for the test."
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.DUPLICATE,)
    started: ClassVar[threading.Event] = threading.Event()
    release: ClassVar[threading.Event] = threading.Event()

    def run(self, ctx: CheckContext) -> list[Finding]:
        SlowCheck.started.set()
        SlowCheck.release.wait(10)
        return []


DEFAULT_STUBS: list[type[Check]] = [StubValueCheck, StubLinkCheck, StubLlmCheck]


class StubReviewService(ReviewService):
    def __init__(self, stubs: list[type[Check]]):
        super().__init__()
        self.stubs = stubs

    def resolve_checks(self, check_ids: list[str] | None, provider: Any) -> list[type[Check]]:
        classes = [c for c in self.stubs if not check_ids or c.id in check_ids]
        if provider is None:
            classes = [c for c in classes if c.tier == Tier.RULE]
        return classes


def make_eval_result(model: str = "fake-a", score: float = 72.5, recall: float = 0.6,
                     started: datetime | None = None, cost: float = 0.42) -> EvalResult:
    return EvalResult(
        id=f"{model}-{score}", model=model, benchmark="shopflow", key_version="1", repeat=1, include_rules=False,
        started_at=started or datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        metrics=EvalMetrics(recall=recall, precision=0.8, f1=0.69, category_accuracy=0.9, severity_accuracy=0.75,
                            verified_quote_rate=0.95, valid_output_rate=1.0, stability=None),
        eval_score=score,
        per_category=[
            CategoryMetrics(category="contradiction", expected=5, found=4, reported=5, recall=0.8, precision=0.8,
                            f1=0.8),
            CategoryMetrics(category="journey-gap", expected=4, found=1, reported=2, recall=0.25, precision=0.5,
                            f1=0.33),
        ],
        missed=[ExpectedFinding(id="J3", category=Category.JOURNEY_GAP, severity=Severity.MAJOR,
                                title="Returns are never documented")],
        unexpected=[Finding(check_id="contradictions", category=Category.CONTRADICTION, severity=Severity.MINOR,
                            title="Possibly real extra problem", source=model)],
        matched=[("C1", "F001")], usage=Usage(input_tokens=50_000, output_tokens=4_000, cost_usd=cost),
        duration_s=93.0, run_ids=["r1"])


class FakeEvalService:
    def __init__(self, store: EvalStore):
        self.store = store
        self.calls: list[dict[str, Any]] = []

    def benchmarks(self) -> list[str]:
        return ["shopflow"]

    def evaluate(self, provider: Any, benchmark: str = "shopflow", repeat: int = 1, include_rules: bool = False,
                 progress: Callable[..., None] | None = None, cancel: Any = None) -> EvalResult:
        self.calls.append({"provider": provider.name, "benchmark": benchmark, "repeat": repeat,
                           "include_rules": include_rules, "thread": threading.current_thread().name})
        result = make_eval_result(model=provider.name, score=81.0)
        self.store.save(result)
        return result


def make_run(model: str | None, findings: list[Finding], value: float = 88.0, minutes: float = 1.5,
             cost: float = 0.0) -> ReviewRun:
    start = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
    for n, f in enumerate(findings, 1):
        f.id = f.id or f"F{n:03d}"
    return ReviewRun(id=f"run-{model}", started_at=start, finished_at=start + timedelta(minutes=minutes),
                     journey_name="ShopFlow order to delivery", journey_path=str(SAMPLE), checks=["x"],
                     model=model, findings=findings,
                     scores=[Score(level=Scope.JOURNEY, target="set", value=value, penalty=1, word_count=1000,
                                   finding_count=len(findings))],
                     usage=Usage(input_tokens=1000, output_tokens=200, cost_usd=cost))


def run_review(qtbot: Any, window: MainWindow, timeout: int = 15000) -> ReviewRun:
    with qtbot.waitSignal(window.review_finished, timeout=timeout) as blocker:
        window.start_review()
    run = blocker.args[0]
    assert isinstance(run, ReviewRun)
    return run
