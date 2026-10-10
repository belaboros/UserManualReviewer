"""CompareService: run or reuse two review runs and match their findings (spec COMPARE, ADR-0010)."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from umr.app.matching import QUOTE_SIMILARITY, location_overlap, pair_best
from umr.app.review import ProgressEvent, ReviewCancelled, ReviewService
from umr.domain import Finding, Journey, Location, ReviewRun
from umr.llm.base import LlmProvider
from umr.storage import RunStore

SideProgress = Callable[[str, ProgressEvent], None]


@dataclass
class Comparison:
    run_a: ReviewRun
    run_b: ReviewRun
    both: list[tuple[Finding, Finding]]  # (finding of A, finding of B), in A's order
    only_a: list[Finding]
    only_b: list[Finding]

    @property
    def agreement(self) -> float:
        """Share of all distinct findings that both runs reported (1.0 when neither reported anything)."""
        total = len(self.both) + len(self.only_a) + len(self.only_b)
        return len(self.both) / total if total else 1.0


def _strong(a: Sequence[Location], b: Sequence[Location], quote_similarity: float) -> bool:
    """Every location of each finding is matched by a location of the other."""
    return (location_overlap(a, b, quote_similarity) == len(b)
            and location_overlap(b, a, quote_similarity) == len(a))


class CompareService:
    def __init__(self, review: ReviewService | None = None, run_store: RunStore | None = None,
                 quote_similarity: float = QUOTE_SIMILARITY):
        self.review = review or ReviewService()
        self.run_store = run_store  # when set, runs started by run_and_compare are saved
        self.quote_similarity = quote_similarity

    def compare_runs(self, run_a: ReviewRun, run_b: ReviewRun) -> Comparison:
        fa, fb = run_a.findings, run_b.findings
        qs = self.quote_similarity
        # pass 1: same category and matching locations
        first = pair_best([f.locations for f in fa], [f.locations for f in fb],
                          allowed=lambda i, j: fa[i].category == fb[j].category, quote_similarity=qs)
        # pass 2: leftovers of any category whose locations match strongly
        rest_a = [fa[i] for i in first.only_a]
        rest_b = [fb[j] for j in first.only_b]
        second = pair_best([f.locations for f in rest_a], [f.locations for f in rest_b],
                           allowed=lambda i, j: _strong(rest_a[i].locations, rest_b[j].locations, qs),
                           quote_similarity=qs)
        pairs = [(i, j) for i, j in first.pairs]
        pairs += [(first.only_a[i], first.only_b[j]) for i, j in second.pairs]
        pairs.sort()
        paired_a = {i for i, _ in pairs}
        paired_b = {j for _, j in pairs}
        return Comparison(run_a=run_a, run_b=run_b, both=[(fa[i], fb[j]) for i, j in pairs],
                          only_a=[f for i, f in enumerate(fa) if i not in paired_a],
                          only_b=[f for j, f in enumerate(fb) if j not in paired_b])

    def run_and_compare(self, journey: Journey, check_ids: list[str] | None, provider_a: LlmProvider,
                        provider_b: LlmProvider, progress: SideProgress | None = None,
                        cancel: threading.Event | None = None) -> Comparison:
        """Run both reviews concurrently; progress receives ("A" | "B", event)."""
        cancel = cancel or threading.Event()
        notify = progress or (lambda side, e: None)

        def run(side: str, provider: LlmProvider) -> ReviewRun:
            try:
                return self.review.review(journey, check_ids, provider,
                                          progress=lambda e: notify(side, e), cancel=cancel)
            except BaseException:
                cancel.set()  # stop the other side too
                raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(run, "A", provider_a)
            fut_b = pool.submit(run, "B", provider_b)
            errors = [f.exception() for f in (fut_a, fut_b)]
        real = [e for e in errors if e is not None and not isinstance(e, ReviewCancelled)]
        if real:
            raise real[0]
        if any(errors):
            raise ReviewCancelled()
        run_a, run_b = fut_a.result(), fut_b.result()
        if self.run_store is not None:
            self.run_store.save(run_a)
            self.run_store.save(run_b)
        return self.compare_runs(run_a, run_b)
