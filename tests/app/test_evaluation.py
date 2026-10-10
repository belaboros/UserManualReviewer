"""Tests for EVAL (SPECIFICATIONS/EVAL-llm-evaluation.md)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from umr.app.evaluation import (
    AnswerKey,
    EvalMetrics,
    EvalResult,
    EvalService,
    ExpectedFinding,
    leaderboard,
)
from umr.app.review import ProgressEvent, ReviewCancelled, ReviewService
from umr.checks import Check
from umr.domain import Category, LlmCallStats, Severity, Tier, Usage
from umr.llm.base import LlmProvider
from umr.llm.fake import FakeProvider
from umr.storage import EvalStore, RunStore

from .helpers import FindingsCheck, finding, loc, run

REPO = Path(__file__).resolve().parents[2]
JOURNEY = REPO / "samples" / "shopflow" / "journey.yaml"
P1 = "order-capturing/02-creating-an-order.md"
P2 = "delivery/dispatch.html"
C2_A = "An order can be cancelled only while it has the status Submitted."
C2_B = "Orders can be cancelled at any time until they reach the status Shipped"

MINI_KEY = {
    "version": "7",
    "benchmark": "mini",
    "findings": [
        {"id": "C2", "category": "contradiction", "severity": "major", "title": "cancel",
         "accept_categories": ["inconsistency"],
         "locations": [{"page": P1, "quote": C2_A}, {"page": P2, "quote": C2_B}]},
        {"id": "G4", "category": "journey-gap", "severity": "major", "title": "address hold",
         "accept_categories": ["missing-error-path"],
         "locations": [{"page": P2, "quote": "The parcel is moved to the Address hold shelf."}]},
        {"id": "X28", "category": "value-conflict", "severity": "minor", "title": "timeout",
         "accept_categories": ["inconsistency"],
         "locations": [{"page": "order-capturing/01-getting-started.md",
                        "quote": "Your session ends after 15 minutes of inactivity."},
                       {"page": "order-capturing/04-troubleshooting.md",
                        "quote": "Sessions expire after 30 minutes of inactivity."}]},
        {"id": "X19", "category": "undefined-term", "severity": "minor", "title": "SLA",
         "locations": [{"page": "delivery/picking.html",
                        "quote": "Orders close to breaching the picking SLA are shown in red."}]},
        {"id": "R2", "category": "broken-anchor", "severity": "minor", "title": "anchor", "tier": "rule",
         "locations": [{"page": P1, "quote": "To apply a discount, see Discount codes."}]},
    ],
}


def _write_config(tmp_path: Path, weights: dict[str, float] | None = None) -> Path:
    key = tmp_path / "key.yaml"
    key.write_text(yaml.safe_dump(MINI_KEY, allow_unicode=True), encoding="utf-8")
    cfg = {"score_weights": weights or {"f1": 0.5, "verified_quote_rate": 0.2, "category_accuracy": 0.15,
                                        "valid_output_rate": 0.15},
           "match": {"quote_similarity": 0.8},
           "benchmarks": {"mini": {"journey": str(JOURNEY), "answer_key": str(key)}}}
    path = tmp_path / "eval.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


class _Review(ReviewService):
    def __init__(self) -> None:
        super().__init__()
        self.requested: list[list[str] | None] = []

    def resolve_checks(self, check_ids: list[str] | None, provider: LlmProvider | None) -> list[type[Check]]:
        self.requested.append(check_ids)
        return [FindingsCheck]


@pytest.fixture
def service(tmp_path: Path) -> EvalService:
    return EvalService(_write_config(tmp_path), review=_Review(), store=EvalStore(tmp_path / "evals"),
                       run_store=RunStore(tmp_path / "runs"))


def _c2(category: str = "contradiction", severity: Severity = Severity.MAJOR, verified: bool = True):
    return finding(category, loc(P1, 57, C2_A), loc(P2, 35, C2_B), severity=severity, verified=verified)


def _g4(category: str = "journey-gap", severity: Severity = Severity.MAJOR, verified: bool = True):
    return finding(category, loc(P2, 9, "The parcel is moved to the Address hold shelf."), severity=severity,
                   verified=verified)


def _unexpected(verified: bool = True):
    return finding("stale-version", loc(P1, 3, "flow in ShopFlow 3.2"), severity=Severity.MINOR, verified=verified)


# ---------- answer key ----------


def test_AC_EVAL_01_answer_key_loads_with_defaults(tmp_path: Path) -> None:
    _write_config(tmp_path)
    key = AnswerKey.load(tmp_path / "key.yaml")
    assert key.version == "7" and key.benchmark == "mini" and len(key.findings) == 5
    by_id = {f.id: f for f in key.findings}
    assert by_id["C2"].tier == Tier.LLM and by_id["R2"].tier == Tier.RULE
    assert by_id["X19"].accept_categories == []
    assert by_id["C2"].locations[0].page == P1


def test_AC_EVAL_01_answer_key_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        ExpectedFinding.model_validate({"id": "Z", "category": "nonsense", "severity": "major", "title": "t",
                                        "locations": []})


# ---------- matching and metrics ----------


def test_AC_EVAL_02_matching_ignores_category_and_category_accuracy_uses_accepted(service: EvalService) -> None:
    r = service.score_runs([run(_c2("inconsistency"), _g4("terminology"))], "mini")
    assert sorted(e for e, _ in r.matched) == ["C2", "G4"]
    assert r.metrics.category_accuracy == pytest.approx(0.5)


def test_AC_EVAL_03_recall_precision_f1_overall_and_per_category(service: EvalService) -> None:
    r = service.score_runs([run(_c2(), _g4(), _unexpected())], "mini")
    assert r.metrics.recall == pytest.approx(0.5)
    assert r.metrics.precision == pytest.approx(2 / 3)
    assert r.metrics.f1 == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))
    cats = {c.category: c for c in r.per_category}
    assert cats["contradiction"].expected == 1 and cats["contradiction"].found == 1
    assert cats["contradiction"].recall == 1.0 and cats["contradiction"].precision == 1.0
    assert cats["value-conflict"].found == 0 and cats["value-conflict"].recall == 0.0
    assert cats["stale-version"].expected == 0 and cats["stale-version"].reported == 1
    assert cats["stale-version"].precision == 0.0
    assert "broken-anchor" not in cats  # rule-tier entry excluded by default
    assert {m.id for m in r.missed} == {"X28", "X19"}
    assert [f.category for f in r.unexpected] == [Category.STALE_VERSION]


def test_AC_EVAL_03_nothing_reported_scores_zero(service: EvalService) -> None:
    r = service.score_runs([run()], "mini")
    assert r.metrics.recall == 0.0 and r.metrics.precision == 0.0 and r.metrics.f1 == 0.0
    assert r.metrics.category_accuracy == 0.0 and r.metrics.verified_quote_rate == 0.0


def test_AC_EVAL_04_severity_accuracy_exact_and_one_level_off(service: EvalService) -> None:
    x28 = finding("value-conflict", loc("order-capturing/01-getting-started.md", 31),
                  loc("order-capturing/04-troubleshooting.md", 17), severity=Severity.CRITICAL)
    r = service.score_runs([run(_c2(severity=Severity.MAJOR), _g4(severity=Severity.CRITICAL), x28)], "mini")
    # C2 exact = 1, G4 major->critical = 0.5, X28 minor->critical (two levels) = 0
    assert r.metrics.severity_accuracy == pytest.approx(0.5)


def test_AC_EVAL_05_verified_quote_rate_and_valid_output_rate(service: EvalService) -> None:
    stats = LlmCallStats(calls=4, valid_first_try=3, retried=1)
    r = service.score_runs([run(_c2(), _g4(verified=False), _unexpected(), stats=stats)], "mini")
    assert r.metrics.verified_quote_rate == pytest.approx(2 / 3)
    assert r.metrics.valid_output_rate == pytest.approx(0.75)


def test_AC_EVAL_06_rule_tier_excluded_by_default_included_on_request(service: EvalService) -> None:
    rule = finding("broken-anchor", loc(P1, 19), check_id="no-such-rule", source="rule")
    default = service.score_runs([run(_c2(), rule)], "mini")
    assert default.metrics.recall == pytest.approx(1 / 4) and default.metrics.precision == 1.0
    assert not default.include_rules
    everything = service.score_runs([run(_c2(), rule)], "mini", include_rules=True)
    assert everything.metrics.recall == pytest.approx(2 / 5) and everything.metrics.precision == 1.0
    assert ("R2", rule.id) in everything.matched and everything.include_rules


def test_AC_EVAL_07_eval_score_uses_configured_weights(service: EvalService, tmp_path: Path) -> None:
    runs = [run(_c2(), _g4("terminology"), _unexpected(verified=False),
                stats=LlmCallStats(calls=2, valid_first_try=1))]
    r = service.score_runs(runs, "mini")
    m = r.metrics
    expected = 100 * (0.5 * m.f1 + 0.2 * m.verified_quote_rate + 0.15 * m.category_accuracy
                      + 0.15 * m.valid_output_rate)
    assert r.eval_score == round(expected, 1)
    (tmp_path / "w").mkdir()
    only_f1 = EvalService(_write_config(tmp_path / "w", {"f1": 1.0}), store=EvalStore(tmp_path / "e"))
    assert only_f1.score_runs(runs, "mini").eval_score == round(100 * m.f1, 1)


def test_AC_EVAL_08_repeats_are_averaged_with_stability(service: EvalService) -> None:
    first = run(_c2(), _g4())
    last = run(_c2(), _unexpected())
    r = service.score_runs([first, last], "mini")
    assert r.repeat == 2 and r.run_ids == [first.id, last.id]
    assert r.metrics.recall == pytest.approx((0.5 + 0.25) / 2)
    assert r.metrics.precision == pytest.approx((1.0 + 0.5) / 2)
    assert r.metrics.stability == pytest.approx(1 / 4)  # only C2 found in every repeat
    assert {m.id for m in r.missed} == {"G4", "X28", "X19"}  # from the last run
    assert len(r.unexpected) == 1
    assert service.score_runs([first], "mini").metrics.stability is None


def test_AC_EVAL_09_evaluate_runs_review_and_saves_runs_and_result(service: EvalService, tmp_path: Path) -> None:
    def respond(system: str, prefix: str, prompt: str) -> object:
        return {"findings": [{"category": "contradiction", "severity": "major", "title": "cancel",
                              "locations": [{"page": P1, "quote": C2_A}, {"page": P2, "quote": C2_B}]},
                             {"category": "terminology", "severity": "minor", "title": "made up",
                              "locations": [{"page": P1, "quote": "this sentence is not in the manual at all"}]}]}

    events: list[ProgressEvent] = []
    provider = FakeProvider(respond, name="local-model")
    r = service.evaluate(provider, "mini", repeat=2, progress=events.append)
    assert r.model == "local-model" and r.benchmark == "mini" and r.key_version == "7" and r.repeat == 2
    assert r.matched[0][0] == "C2"
    assert r.metrics.recall == pytest.approx(0.25) and r.metrics.precision == pytest.approx(0.5)
    assert r.metrics.verified_quote_rate == pytest.approx(0.5)
    assert r.metrics.valid_output_rate == 1.0 and r.metrics.stability == pytest.approx(0.25)
    assert r.usage.calls == 2 and len(provider.calls) == 2
    assert len(RunStore(tmp_path / "runs").list()) == 2
    saved = EvalStore(tmp_path / "evals").load_all()
    assert [s.id for s in saved] == [r.id]
    assert any("Run 2/2" in e.message for e in events)
    assert service.review.requested == [["llm"], ["llm"]]  # type: ignore[attr-defined]


def test_AC_EVAL_09_evaluate_with_rules_requests_all_checks(service: EvalService) -> None:
    service.evaluate(FakeProvider(), "mini", include_rules=True)
    assert service.review.requested == [None]  # type: ignore[attr-defined]


def test_AC_EVAL_09_evaluate_can_be_cancelled(service: EvalService, tmp_path: Path) -> None:
    cancel = threading.Event()

    def respond(system: str, prefix: str, prompt: str) -> object:
        cancel.set()
        return {"findings": []}

    with pytest.raises(ReviewCancelled):
        service.evaluate(FakeProvider(respond), "mini", cancel=cancel)
    assert EvalStore(tmp_path / "evals").load_all() == []


def _result(model: str, score: float, minutes: int, key_version: str = "1", benchmark: str = "shopflow"):
    m = EvalMetrics(recall=0, precision=0, f1=0, category_accuracy=0, severity_accuracy=0,
                    verified_quote_rate=0, valid_output_rate=0, stability=None)
    return EvalResult(id=f"{model}{minutes}", model=model, benchmark=benchmark, key_version=key_version,
                      started_at=datetime(2026, 10, 10, tzinfo=UTC) + timedelta(minutes=minutes), repeat=1,
                      include_rules=False, metrics=m, eval_score=score, per_category=[], missed=[], unexpected=[],
                      matched=[("C2", "F001")], usage=Usage(), duration_s=1.0, run_ids=["x"])


def test_AC_EVAL_10_leaderboard_latest_per_model_sorted_by_score() -> None:
    rows = leaderboard([_result("a", 80, 1), _result("a", 60, 2), _result("b", 70, 1),
                        _result("b", 90, 3, key_version="2"), _result("c", 75, 1, benchmark="other")])
    assert [(r.model, r.eval_score, r.key_version) for r in rows] == [
        ("b", 90, "2"), ("c", 75, "1"), ("b", 70, "1"), ("a", 60, "1")]


def test_AC_EVAL_11_eval_store_round_trip_and_default_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMR_EVALS_DIR", str(tmp_path / "env-evals"))
    store = EvalStore()
    assert store.root == tmp_path / "env-evals"
    first, second = _result("a", 50, 2), _result("b", 60, 1)
    path = store.save(first)
    store.save(second)
    assert path.parent == tmp_path / "env-evals" and path.suffix == ".json"
    (store.root / "broken.json").write_text("{not json", encoding="utf-8")
    loaded = store.load_all()
    assert [r.id for r in loaded] == [second.id, first.id]  # oldest first, broken file skipped
    assert loaded[1] == first


def test_AC_EVAL_12_expected_quotes_are_located_to_lines(service: EvalService) -> None:
    # reported finding gives only line numbers (no quotes); it must still match X28 via located key quotes
    x28 = finding("value-conflict", loc("order-capturing/01-getting-started.md", 31),
                  loc("order-capturing/04-troubleshooting.md", 17), severity=Severity.MINOR)
    r = service.score_runs([run(x28)], "mini")
    assert [e for e, _ in r.matched] == ["X28"]
    wrong_lines = finding("value-conflict", loc("order-capturing/01-getting-started.md", 5),
                          loc("order-capturing/04-troubleshooting.md", 9))
    assert service.score_runs([run(wrong_lines)], "mini").matched == []


def test_AC_EVAL_13_benchmarks_from_config(service: EvalService) -> None:
    assert service.benchmarks() == ["mini"]
    with pytest.raises(KeyError):
        service.score_runs([run()], "nope")
    default = EvalService(REPO / "config" / "eval.yaml", store=EvalStore(Path("unused")))
    assert default.benchmarks() == ["shopflow"]
    assert len(default.answer_key("shopflow").findings) == 68


def test_AC_EVAL_02_exact_category_wins_ties(tmp_path: Path) -> None:
    key = {"version": "1", "benchmark": "tie", "findings": [
        {"id": "I", "category": "inconsistency", "severity": "minor", "title": "a", "accept_categories": ["ui-label"],
         "locations": [{"page": P1, "quote": "Click Submit Order."}]},
        {"id": "U", "category": "ui-label", "severity": "minor", "title": "b",
         "locations": [{"page": P1, "quote": "Click Submit Order."}]}]}
    (tmp_path / "k.yaml").write_text(yaml.safe_dump(key), encoding="utf-8")
    cfg = {"benchmarks": {"tie": {"journey": str(JOURNEY), "answer_key": str(tmp_path / "k.yaml")}}}
    (tmp_path / "e.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    svc = EvalService(tmp_path / "e.yaml", store=EvalStore(tmp_path / "evals"))
    r = svc.score_runs([run(finding("ui-label", loc(P1, 47)))], "tie")
    assert [e for e, _ in r.matched] == ["U"]
