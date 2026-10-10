"""Tests for COMPARE (SPECIFICATIONS/COMPARE-side-by-side-comparison.md)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from umr.app.compare import CompareService
from umr.app.review import ProgressEvent, ReviewCancelled, ReviewService
from umr.checks import Check
from umr.domain import Journey
from umr.ingest import load_journey
from umr.llm.base import LlmProvider
from umr.llm.fake import FakeProvider
from umr.storage import RunStore

from .helpers import FindingsCheck, finding, loc, run

P1 = "order-capturing/02-creating-an-order.md"
P2 = "delivery/dispatch.html"


class _Review(ReviewService):
    def resolve_checks(self, check_ids: list[str] | None, provider: LlmProvider | None) -> list[type[Check]]:
        return [FindingsCheck]


@pytest.fixture(scope="module")
def journey() -> Journey:
    return load_journey(Path(__file__).resolve().parents[2] / "samples" / "shopflow" / "journey.yaml")


def _response(category: str, page: str, quote: str) -> dict[str, list[dict[str, object]]]:
    return {"findings": [{"category": category, "severity": "major", "title": "x",
                          "locations": [{"page": page, "quote": quote}]}]}


def test_AC_COMPARE_01_same_category_overlapping_lines_found_by_both() -> None:
    a = run(finding("contradiction", loc(P1, 57)))
    b = run(finding("contradiction", loc(P1, 56, end=58)))
    c = CompareService().compare_runs(a, b)
    assert len(c.both) == 1 and not c.only_a and not c.only_b
    assert c.both[0] == (a.findings[0], b.findings[0])


def test_AC_COMPARE_02_quote_similarity_threshold() -> None:
    q = "An order can be cancelled only while it has the status Submitted."
    a = run(finding("inconsistency", loc(P1, None, q)))
    near = "An order can be canceled only while it has status Submitted"
    similar = run(finding("inconsistency", loc(P1, None, near)))
    different = run(finding("inconsistency", loc(P1, None, "Customers can opt out of all e-mail notifications")))
    assert len(CompareService().compare_runs(a, similar).both) == 1
    c = CompareService().compare_runs(a, different)
    assert not c.both and len(c.only_a) == 1 and len(c.only_b) == 1


def test_AC_COMPARE_03_different_page_or_lines_not_matched() -> None:
    a = run(finding("contradiction", loc(P1, 10)), finding("contradiction", loc(P1, 20)))
    b = run(finding("contradiction", loc(P2, 10)), finding("contradiction", loc(P1, 30)))
    c = CompareService().compare_runs(a, b)
    assert not c.both
    assert c.only_a == a.findings and c.only_b == b.findings


def test_AC_COMPARE_04_second_pass_matches_other_category_on_strong_locations() -> None:
    a = run(finding("inconsistency", loc(P1, 57), loc(P2, 35)))
    b = run(finding("contradiction", loc(P1, 57), loc(P2, 35)))
    c = CompareService().compare_runs(a, b)
    assert len(c.both) == 1
    # weak: only one of two locations matches -> not paired across categories
    weak_b = run(finding("contradiction", loc(P1, 57), loc(P2, 9)))
    weak = CompareService().compare_runs(run(finding("inconsistency", loc(P1, 57))), weak_b)
    assert not weak.both


def test_AC_COMPARE_04_same_category_preferred_over_other_category() -> None:
    a = run(finding("value-conflict", loc(P1, 19)))
    b = run(finding("duplicate", loc(P1, 19)), finding("value-conflict", loc(P1, 19)))
    c = CompareService().compare_runs(a, b)
    assert c.both == [(a.findings[0], b.findings[1])]
    assert c.only_b == [b.findings[0]]


def test_AC_COMPARE_05_contradiction_needs_two_matching_locations() -> None:
    a = run(finding("contradiction", loc(P1, 57), loc(P2, 35)))
    b = run(finding("contradiction", loc(P1, 57), loc(P2, 9)))
    assert not CompareService().compare_runs(a, b).both
    single = run(finding("contradiction", loc(P1, 57)))
    assert len(CompareService().compare_runs(a, single).both) == 1


def test_AC_COMPARE_06_one_to_one_pairing() -> None:
    a = run(finding("duplicate", loc(P1, 12)), finding("duplicate", loc(P1, 12)))
    b = run(finding("duplicate", loc(P1, 12)))
    c = CompareService().compare_runs(a, b)
    assert len(c.both) == 1 and len(c.only_a) == 1 and not c.only_b


def test_AC_COMPARE_07_run_and_compare_runs_both_models_concurrently(journey: Journey) -> None:
    barrier = threading.Barrier(2, timeout=5)

    def responder(quote: str):
        def respond(system: str, prefix: str, prompt: str) -> object:
            barrier.wait()  # both reviews must be in flight at the same time
            return _response("contradiction", P1, quote)
        return respond

    pa = FakeProvider(responder("An order can be cancelled only while it has the status Submitted."), name="m-a")
    pb = FakeProvider(responder("cancelled only while it has the status Submitted"), name="m-b")
    events: list[tuple[str, ProgressEvent]] = []
    lock = threading.Lock()

    def progress(side: str, e: ProgressEvent) -> None:
        with lock:
            events.append((side, e))

    c = CompareService(_Review()).run_and_compare(journey, ["test-llm"], pa, pb, progress=progress)
    assert c.run_a.model == "m-a" and c.run_b.model == "m-b"
    assert len(c.both) == 1
    assert {s for s, _ in events} == {"A", "B"}
    assert [e.kind for s, e in events if s == "A"][-1] == "finished"
    assert c.run_a.usage.calls == 1 and c.run_b.usage.calls == 1


def test_AC_COMPARE_08_groups_both_only_a_only_b(journey: Journey, tmp_path: Path) -> None:
    def two(system: str, prefix: str, prompt: str) -> object:
        d = _response("contradiction", P1, "An order can be cancelled only while it has the status Submitted.")
        d["findings"] += _response("journey-gap", P2, "The parcel is moved to the Address hold shelf.")["findings"]
        return d

    pa = FakeProvider(two, name="m-a")
    pb = FakeProvider(lambda s, p, q: _response("contradiction", P1, "cancelled only while it has the status"),
                      name="m-b")
    store = RunStore(tmp_path / "runs")
    c = CompareService(_Review(), run_store=store).run_and_compare(journey, None, pa, pb)
    assert len(c.both) == 1 and [f.category for f in c.only_a] == ["journey-gap"] and not c.only_b
    assert len(store.list()) == 2
    assert 0 < c.agreement < 1


def test_AC_COMPARE_09_cancel_stops_both_reviews(journey: Journey) -> None:
    cancel = threading.Event()

    def respond(system: str, prefix: str, prompt: str) -> object:
        cancel.set()
        return {"findings": []}

    with pytest.raises(ReviewCancelled):
        CompareService(_Review()).run_and_compare(journey, None, FakeProvider(respond, name="a"),
                                                  FakeProvider(respond, name="b"), cancel=cancel)


def test_AC_COMPARE_10_error_in_one_review_is_raised(journey: Journey) -> None:
    class Boom(ReviewService):
        def review(self, *args: object, **kwargs: object):  # type: ignore[override]
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        CompareService(Boom()).run_and_compare(journey, None, FakeProvider(), FakeProvider())
