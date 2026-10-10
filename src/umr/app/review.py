"""ReviewService: orchestrates one review run (architecture section 6)."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from umr.app.verify import verify_finding
from umr.checks import Check, CheckContext, CheckRegistry
from umr.domain import CheckError, CheckResult, Finding, Journey, ReviewRun, Tier, Usage
from umr.llm.base import LlmProvider
from umr.scoring import ScoringConfig, score_run


@dataclass
class ProgressEvent:
    kind: str  # "started" | "check_started" | "check_finished" | "finished"
    check_id: str | None = None
    done: int = 0
    total: int = 0
    result: CheckResult | None = None
    message: str = ""


ProgressCallback = Callable[[ProgressEvent], None]


class ReviewCancelled(Exception):
    pass


def _run_check(check: Check, ctx: CheckContext) -> CheckResult:
    t0 = time.perf_counter()
    try:
        findings = check.run(ctx)
        error = None
    except Exception as e:  # a failing check never aborts the run
        findings, error = [], f"{type(e).__name__}: {e}"
    return CheckResult(check_id=check.id, tier=check.tier, findings=findings, usage=ctx.usage,
                       error=error, duration_s=time.perf_counter() - t0)


class ReviewService:
    def __init__(self, scoring: ScoringConfig | None = None):
        self.scoring = scoring or ScoringConfig()

    def resolve_checks(self, check_ids: list[str] | None, provider: LlmProvider | None) -> list[type[Check]]:
        if not check_ids or check_ids == ["all"]:
            classes = CheckRegistry.all()
        elif check_ids == ["rules"]:
            classes = [c for c in CheckRegistry.all() if c.tier == Tier.RULE]
        elif check_ids == ["llm"]:
            classes = [c for c in CheckRegistry.all() if c.tier == Tier.LLM]
        else:
            classes = [CheckRegistry.get(c) for c in check_ids]
        if provider is None:
            classes = [c for c in classes if c.tier == Tier.RULE]
        return classes

    def review(self, journey: Journey, check_ids: list[str] | None = None, provider: LlmProvider | None = None,
               progress: ProgressCallback | None = None, cancel: threading.Event | None = None,
               journey_path: Path | None = None) -> ReviewRun:
        notify = progress or (lambda e: None)
        cancel = cancel or threading.Event()
        classes = self.resolve_checks(check_ids, provider)
        checks = [c() for c in classes]
        checks = [c for c in checks if c.applies_to(journey)]
        run = ReviewRun(id=uuid.uuid4().hex, started_at=datetime.now(UTC), journey_name=journey.name,
                        journey_path=str(journey_path or journey.root_path), checks=[c.id for c in checks],
                        model=provider.name if provider and any(c.tier == Tier.LLM for c in checks) else None,
                        scoring=self.scoring.model_dump(mode="json"))
        total = len(checks)
        notify(ProgressEvent("started", total=total))
        results: list[CheckResult] = []
        lock = threading.Lock()

        def finish(result: CheckResult) -> None:
            with lock:
                results.append(result)
                notify(ProgressEvent("check_finished", check_id=result.check_id, done=len(results),
                                     total=total, result=result))

        for check in [c for c in checks if c.tier == Tier.RULE]:
            if cancel.is_set():
                raise ReviewCancelled()
            notify(ProgressEvent("check_started", check_id=check.id, done=len(results), total=total))
            finish(self._post(journey, _run_check(check, CheckContext(journey=journey))))

        llm_checks = [c for c in checks if c.tier == Tier.LLM]
        if llm_checks and provider is not None:
            workers = max(1, provider.config.max_concurrency)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {}
                for check in llm_checks:
                    notify(ProgressEvent("check_started", check_id=check.id, done=len(results), total=total))
                    ctx = CheckContext(journey=journey, provider=provider, usage=Usage())
                    futures[pool.submit(_run_check, check, ctx)] = check
                for fut in as_completed(futures):
                    if cancel.is_set():
                        for f in futures:
                            f.cancel()
                        raise ReviewCancelled()
                    finish(self._post(journey, fut.result()))

        order = {c.id: i for i, c in enumerate(checks)}
        results.sort(key=lambda r: order[r.check_id])
        run.findings = self._dedupe([f for r in results for f in r.findings])
        for n, f in enumerate(run.findings, 1):
            f.id = f"F{n:03d}"
        for r in results:
            run.usage.add(r.usage)
            run.check_durations[r.check_id] = round(r.duration_s, 3)
            if r.error:
                run.errors.append(CheckError(check_id=r.check_id, message=r.error))
        run.scores = score_run(journey, run.findings, self.scoring)
        run.finished_at = datetime.now(UTC)
        notify(ProgressEvent("finished", done=total, total=total))
        return run

    @staticmethod
    def _post(journey: Journey, result: CheckResult) -> CheckResult:
        for f in result.findings:
            verify_finding(journey, f)
        return result

    @staticmethod
    def _dedupe(findings: list[Finding]) -> list[Finding]:
        seen: set[str] = set()
        out = []
        for f in findings:
            if f.fingerprint in seen:
                continue
            seen.add(f.fingerprint)
            out.append(f)
        return out
