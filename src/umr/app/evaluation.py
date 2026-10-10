"""EvalService: score a model's review runs against a benchmark answer key (spec EVAL, ADR-0013)."""

from __future__ import annotations

import dataclasses
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, Field

from umr.app.matching import QUOTE_SIMILARITY, pair_best
from umr.app.review import ProgressEvent, ReviewService
from umr.app.verify import locate_quote
from umr.checks import CheckRegistry
from umr.domain import SEVERITY_ORDER, Category, Finding, Journey, Location, ReviewRun, Severity, Tier, Usage
from umr.ingest import load_journey
from umr.llm.base import LlmProvider
from umr.storage import RunStore

if TYPE_CHECKING:
    from umr.storage.evals import EvalStore

DEFAULT_WEIGHTS = {"f1": 0.50, "verified_quote_rate": 0.20, "category_accuracy": 0.15, "valid_output_rate": 0.15}


# ---------- answer key ----------


class ExpectedLocation(BaseModel):
    page: str  # "<manual_id>/<page_path>"
    quote: str


class ExpectedFinding(BaseModel):
    id: str
    category: Category
    severity: Severity
    title: str
    locations: list[ExpectedLocation] = Field(default_factory=list)
    accept_categories: list[Category] = Field(default_factory=list)
    tier: Tier = Tier.LLM

    def accepts(self, category: Category) -> bool:
        return category == self.category or category in self.accept_categories


class AnswerKey(BaseModel):
    version: str
    benchmark: str
    findings: list[ExpectedFinding] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> AnswerKey:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)


# ---------- results ----------


class CategoryMetrics(BaseModel):
    category: str
    expected: int
    found: int
    reported: int
    recall: float
    precision: float
    f1: float


class EvalMetrics(BaseModel):
    recall: float
    precision: float
    f1: float
    category_accuracy: float
    severity_accuracy: float
    verified_quote_rate: float
    valid_output_rate: float
    stability: float | None = None


class EvalResult(BaseModel):
    id: str
    model: str
    benchmark: str
    key_version: str
    started_at: datetime
    repeat: int
    include_rules: bool
    metrics: EvalMetrics
    eval_score: float
    per_category: list[CategoryMetrics]
    missed: list[ExpectedFinding]
    unexpected: list[Finding]
    matched: list[tuple[str, str]]  # (expected id, finding id)
    usage: Usage
    duration_s: float
    run_ids: list[str]


class EvalConfig(BaseModel):
    score_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    quote_similarity: float = QUOTE_SIMILARITY
    benchmarks: dict[str, dict[str, str]] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> EvalConfig:
        if not path.exists():
            return cls(benchmarks={"shopflow": {"journey": "samples/shopflow/journey.yaml",
                                                "answer_key": "samples/shopflow/expected-findings.yaml"}})
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(score_weights=data.get("score_weights") or dict(DEFAULT_WEIGHTS),
                   quote_similarity=(data.get("match") or {}).get("quote_similarity", QUOTE_SIMILARITY),
                   benchmarks=data.get("benchmarks") or {})


# ---------- metric helpers ----------


def _ratio(num: float, den: float, empty: float) -> float:
    return num / den if den else empty


def _f1(recall: float, precision: float) -> float:
    return 2 * recall * precision / (recall + precision) if recall + precision else 0.0


def _recall_precision(found: int, expected: int, correct: int, reported: int) -> tuple[float, float]:
    """Recall is 1.0 when nothing was expected; precision is 1.0 only when nothing was expected or reported."""
    recall = _ratio(found, expected, 1.0)
    precision = _ratio(correct, reported, 1.0 if expected == 0 else 0.0)
    return recall, precision


def severity_credit(expected: Severity, reported: Severity) -> float:
    diff = abs(SEVERITY_ORDER.index(expected) - SEVERITY_ORDER.index(reported))
    return 1.0 if diff == 0 else 0.5 if diff == 1 else 0.0


def _category_rank(expected: ExpectedFinding, reported: Finding) -> int:
    return 2 if reported.category == expected.category else 1 if expected.accepts(reported.category) else 0


def finding_tier(finding: Finding) -> Tier:
    """Tier of the check that reported the finding (registry first, then the finding's source)."""
    try:
        return CheckRegistry.get(finding.check_id).tier
    except KeyError:
        return Tier.RULE if finding.source == "rule" else Tier.LLM


@dataclasses.dataclass
class _RunScore:
    metrics: EvalMetrics
    per_category: list[CategoryMetrics]
    found_ids: set[str]
    missed: list[ExpectedFinding]
    unexpected: list[Finding]
    matched: list[tuple[str, str]]


def expected_locations(journey: Journey, expected: ExpectedFinding) -> list[Location]:
    """Turn answer-key locations into domain locations with line numbers found via `locate_quote`."""
    out = []
    for loc in expected.locations:
        manual_id, _, page_path = loc.page.partition("/")
        location = Location(manual_id=manual_id, page_path=page_path, quote=loc.quote)
        page = journey.page(loc.page)
        span = locate_quote(page, loc.quote) if page else None
        if span:
            location.line_start, location.line_end = span
            location.verified = True
        out.append(location)
    return out


def score_run_against_key(run: ReviewRun, key: AnswerKey, journey: Journey, include_rules: bool = False,
                          quote_similarity: float = QUOTE_SIMILARITY) -> _RunScore:
    expected = [e for e in key.findings if include_rules or e.tier == Tier.LLM]
    reported = [f for f in run.findings if include_rules or finding_tier(f) == Tier.LLM]
    exp_locs = [expected_locations(journey, e) for e in expected]
    # category is ignored for matching; the exact, then an accepted category only breaks ties
    pairing = pair_best(exp_locs, [f.locations for f in reported],
                        preferred=lambda i, j: _category_rank(expected[i], reported[j]),
                        quote_similarity=quote_similarity)
    pairs = [(expected[i], reported[j]) for i, j in pairing.pairs]
    recall, precision = _recall_precision(len(pairs), len(expected), len(pairs), len(reported))
    metrics = EvalMetrics(
        recall=recall, precision=precision, f1=_f1(recall, precision),
        category_accuracy=_ratio(sum(e.accepts(f.category) for e, f in pairs), len(pairs), 0.0),
        severity_accuracy=_ratio(sum(severity_credit(e.severity, f.severity) for e, f in pairs), len(pairs), 0.0),
        verified_quote_rate=_ratio(sum(f.verified for f in reported), len(reported), 0.0),
        valid_output_rate=run.llm_stats.valid_output_rate)
    matched_reported = {id(f) for _, f in pairs}
    categories = sorted({str(e.category) for e in expected} | {str(f.category) for f in reported})
    per_category = []
    for cat in categories:
        n_exp = sum(1 for e in expected if e.category == cat)
        n_found = sum(1 for e, _ in pairs if e.category == cat)
        cat_reported = [f for f in reported if f.category == cat]
        n_correct = sum(1 for f in cat_reported if id(f) in matched_reported)
        r, p = _recall_precision(n_found, n_exp, n_correct, len(cat_reported))
        per_category.append(CategoryMetrics(category=cat, expected=n_exp, found=n_found,
                                            reported=len(cat_reported), recall=r, precision=p, f1=_f1(r, p)))
    return _RunScore(metrics=metrics, per_category=per_category, found_ids={e.id for e, _ in pairs},
                     missed=[expected[i] for i in pairing.only_a],
                     unexpected=[reported[j] for j in pairing.only_b],
                     matched=[(e.id, f.id) for e, f in pairs])


def eval_score(metrics: EvalMetrics, weights: dict[str, float]) -> float:
    total = sum(w * float(getattr(metrics, name)) for name, w in weights.items())
    return round(100.0 * total, 1)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _average(scores: list[_RunScore], expected_ids: list[str]) -> tuple[EvalMetrics, list[CategoryMetrics]]:
    fields = ["recall", "precision", "f1", "category_accuracy", "severity_accuracy", "verified_quote_rate",
              "valid_output_rate"]
    avg = {name: _mean([float(getattr(s.metrics, name)) for s in scores]) for name in fields}
    stability = None
    if len(scores) >= 2:
        always = [eid for eid in expected_ids if all(eid in s.found_ids for s in scores)]
        stability = _ratio(len(always), len(expected_ids), 1.0)
    metrics = EvalMetrics(**avg, stability=stability)
    by_cat: dict[str, list[CategoryMetrics]] = {}
    for s in scores:
        for c in s.per_category:
            by_cat.setdefault(c.category, []).append(c)
    n = len(scores)
    per_category = []
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        # a category missing from a run counts as zero found/reported, keeping recall and precision rules
        expected = max(r.expected for r in rows)
        pad = n - len(rows)
        empty_recall, empty_precision = _recall_precision(0, expected, 0, 0)
        recall = _mean([r.recall for r in rows] + [empty_recall] * pad)
        precision = _mean([r.precision for r in rows] + [empty_precision] * pad)
        per_category.append(CategoryMetrics(
            category=cat, expected=expected, found=round(sum(r.found for r in rows) / n),
            reported=round(sum(r.reported for r in rows) / n), recall=recall, precision=precision,
            f1=_mean([r.f1 for r in rows] + [_f1(empty_recall, empty_precision)] * pad)))
    return metrics, per_category


# ---------- service ----------


class EvalService:
    def __init__(self, config_path: Path = Path("config/eval.yaml"), review: ReviewService | None = None,
                 store: EvalStore | None = None, repo_root: Path | None = None,
                 run_store: RunStore | None = None):
        self.config_path = config_path
        self.config = EvalConfig.load(config_path)
        self.repo_root = repo_root or config_path.resolve().parent.parent
        self.review = review or ReviewService()
        if store is None:
            from umr.storage.evals import EvalStore
            store = EvalStore()
        self.store = store
        self.run_store = run_store or RunStore()
        self._journeys: dict[str, Journey] = {}
        self._keys: dict[str, AnswerKey] = {}

    def benchmarks(self) -> list[str]:
        return list(self.config.benchmarks)

    def _path(self, benchmark: str, field: str) -> Path:
        if benchmark not in self.config.benchmarks:
            raise KeyError(f"Unknown benchmark '{benchmark}'. Known: {', '.join(self.benchmarks())}")
        path = Path(self.config.benchmarks[benchmark][field])
        return path if path.is_absolute() else self.repo_root / path

    def journey(self, benchmark: str) -> Journey:
        if benchmark not in self._journeys:
            self._journeys[benchmark] = load_journey(self._path(benchmark, "journey"))
        return self._journeys[benchmark]

    def answer_key(self, benchmark: str) -> AnswerKey:
        if benchmark not in self._keys:
            self._keys[benchmark] = AnswerKey.load(self._path(benchmark, "answer_key"))
        return self._keys[benchmark]

    def evaluate(self, provider: LlmProvider, benchmark: str = "shopflow", repeat: int = 1,
                 include_rules: bool = False, progress: Callable[[ProgressEvent], None] | None = None,
                 cancel: threading.Event | None = None) -> EvalResult:
        """Run `repeat` reviews with the provider on the benchmark journey, save them and score them."""
        notify = progress or (lambda e: None)
        journey = self.journey(benchmark)
        self.answer_key(benchmark)  # fail before spending tokens if the key is broken
        check_ids = None if include_rules else ["llm"]
        runs = []
        for n in range(1, max(1, repeat) + 1):
            prefix = f"Run {n}/{max(1, repeat)}"

            def forward(e: ProgressEvent, prefix: str = prefix) -> None:
                notify(dataclasses.replace(e, message=f"{prefix}: {e.message}" if e.message else prefix))

            run = self.review.review(journey, check_ids, provider, progress=forward, cancel=cancel,
                                     journey_path=self._path(benchmark, "journey"))
            self.run_store.save(run)
            runs.append(run)
        result = self.score_runs(runs, benchmark, include_rules)
        self.store.save(result)
        return result

    def score_runs(self, runs: list[ReviewRun], benchmark: str = "shopflow",
                   include_rules: bool = False) -> EvalResult:
        """Score existing runs against the benchmark key; no LLM calls, nothing saved."""
        if not runs:
            raise ValueError("score_runs needs at least one review run")
        key = self.answer_key(benchmark)
        journey = self.journey(benchmark)
        qs = self.config.quote_similarity
        scores = [score_run_against_key(r, key, journey, include_rules, qs) for r in runs]
        expected_ids = [e.id for e in key.findings if include_rules or e.tier == Tier.LLM]
        metrics, per_category = _average(scores, expected_ids)
        usage = Usage()
        duration = 0.0
        for r in runs:
            usage.add(r.usage)
            duration += ((r.finished_at - r.started_at).total_seconds() if r.finished_at
                         else r.usage.duration_s)
        last = scores[-1]
        return EvalResult(
            id=uuid.uuid4().hex, model=runs[-1].model or "rules", benchmark=benchmark, key_version=key.version,
            started_at=min(r.started_at for r in runs) if runs else datetime.now(UTC), repeat=len(runs),
            include_rules=include_rules, metrics=metrics,
            eval_score=eval_score(metrics, self.config.score_weights), per_category=per_category,
            missed=last.missed, unexpected=last.unexpected, matched=last.matched, usage=usage,
            duration_s=round(duration, 3), run_ids=[r.id for r in runs])


def leaderboard(results: list[EvalResult]) -> list[EvalResult]:
    """Latest result per (model, benchmark, key version), best eval score first."""
    latest: dict[tuple[str, str, str], EvalResult] = {}
    for r in results:
        k = (r.model, r.benchmark, r.key_version)
        if k not in latest or r.started_at > latest[k].started_at:
            latest[k] = r
    return sorted(latest.values(), key=lambda r: (-r.eval_score, -r.started_at.timestamp()))
