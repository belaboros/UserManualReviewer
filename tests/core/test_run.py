import threading
from pathlib import Path

import pytest

import umr.checks.base as base
from umr.app import ProgressEvent, ReviewCancelled, ReviewService
from umr.checks import Check, CheckContext, CheckRegistry
from umr.cli import main
from umr.domain import Category, Finding, Location, Scope, Severity, Tier, Usage
from umr.ingest import load_journey
from umr.llm.fake import FakeProvider
from umr.storage import RunStore

SRC = "# Guide\n\nThe session ends after 15 minutes.\n"


def _finding(check_id: str) -> Finding:
    return Finding(check_id=check_id, category=Category.INCONSISTENCY, severity=Severity.MINOR, title=check_id,
                   locations=[Location(manual_id="g", page_path="a.md", quote="The session ends")])


class RuleOk(Check):
    id, title, description = "rule-ok", "Rule", "d"
    tier, scope, categories = Tier.RULE, Scope.PAGE, (Category.INCONSISTENCY,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        return [_finding(self.id)]


class RuleBoom(RuleOk):
    id = "rule-boom"

    def run(self, ctx: CheckContext) -> list[Finding]:
        raise RuntimeError("boom")


class LlmOk(RuleOk):
    id, tier = "llm-ok", Tier.LLM

    def run(self, ctx: CheckContext) -> list[Finding]:
        assert ctx.provider is not None
        res = ctx.provider.complete(system="s", cache_prefix="corpus", prompt="p", schema={})
        ctx.usage.add(res.usage)
        ctx.llm_stats.calls += 1
        ctx.llm_stats.valid_first_try += 1
        f = _finding(self.id)
        f.category = Category.CONTRADICTION
        f.source = ctx.provider.name
        return [f]


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base, "_load_builtin_checks", lambda: None)
    monkeypatch.setattr(CheckRegistry, "_checks", {c.id: c for c in (RuleOk, RuleBoom, LlmOk)})


@pytest.fixture
def journey(make_manual):
    return load_journey(make_manual({"a.md": SRC}, name="g"))


def test_AC_RUN_01_rules_only(registry, journey) -> None:
    run = ReviewService().review(journey, ["rules"], FakeProvider())
    assert set(run.checks) == {"rule-ok", "rule-boom"}


def test_AC_RUN_02_llm_checks_skipped_without_model(registry, journey) -> None:
    run = ReviewService().review(journey, ["all"], None)
    assert "llm-ok" not in run.checks and run.model is None
    assert not any(e.check_id == "llm-ok" for e in run.errors)


def test_AC_RUN_03_failing_check_recorded(registry, journey) -> None:
    run = ReviewService().review(journey, ["rule-ok", "rule-boom"])
    assert [e.check_id for e in run.errors] == ["rule-boom"] and "boom" in run.errors[0].message
    assert [f.check_id for f in run.findings] == ["rule-ok"]


def test_AC_RUN_04_progress_events(registry, journey) -> None:
    events: list[ProgressEvent] = []
    ReviewService().review(journey, ["all"], FakeProvider(), progress=events.append)
    kinds = [e.kind for e in events]
    assert kinds[0] == "started" and kinds[-1] == "finished"
    finished = [e for e in events if e.kind == "check_finished"]
    assert len(finished) == 3 and finished[-1].done == finished[-1].total == 3


def test_AC_RUN_05_cancel(registry, journey) -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ReviewCancelled):
        ReviewService().review(journey, ["all"], FakeProvider(), cancel=cancel)


def test_AC_RUN_06_save_and_load(registry, journey, tmp_path: Path) -> None:
    run = ReviewService().review(journey, ["all"], FakeProvider())
    store = RunStore(tmp_path)
    loaded = store.load(store.save(run))
    assert loaded == run and store.list()


def test_AC_RUN_07_model_usage_and_llm_stats(registry, journey) -> None:
    run = ReviewService().review(journey, ["llm-ok"], FakeProvider(name="fake-a"))
    assert run.model == "fake-a"
    assert run.usage.calls == 1 and run.usage.input_tokens > 0
    assert run.llm_stats.calls == 1 and run.llm_stats.valid_output_rate == 1.0
    assert run.findings[0].source == "fake-a" and run.findings[0].verified


def test_AC_RUN_08_cli_review(registry, journey, capsys, make_manual) -> None:
    folder = make_manual({"a.md": SRC}, name="g")
    assert main(["review", str(folder), "--checks", "rule-ok"]) == 0
    out = capsys.readouterr().out
    assert "Quality score (set)" in out and "Saved:" in out
    assert RunStore().list()


def test_AC_RUN_09_cli_missing_journey(capsys, tmp_path: Path) -> None:
    assert main(["review", str(tmp_path / "nope.yaml")]) == 2
    assert "Error:" in capsys.readouterr().err


def test_usage_add() -> None:
    u = Usage(input_tokens=1, cost_usd=0.5, calls=1)
    u.add(Usage(input_tokens=2, cost_usd=0.25, calls=1))
    assert (u.input_tokens, u.cost_usd, u.calls) == (3, 0.75, 2)
