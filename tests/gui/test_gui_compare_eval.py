"""GUI tests: Compare, Evaluate and Leaderboard views (AC-GUI-13, 14, 15, 21)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from gui_helpers import SAMPLE, make_eval_result, make_run
from PySide6.QtCore import Qt

from umr.app.compare import Comparison
from umr.domain import Category, Finding, Location, Severity
from umr.gui.viewmodels import LEADERBOARD_COLUMNS, NO_EVALS
from umr.ingest import load_journey

pytestmark = pytest.mark.gui


def _finding(title: str, sev: Severity = Severity.MAJOR, verified: bool = True, fid: str = "") -> Finding:
    return Finding(id=fid, check_id="contradictions", category=Category.CONTRADICTION, severity=sev, title=title,
                   explanation=f"why {title}", verified=verified, source="m",
                   locations=[Location(manual_id="delivery", page_path="dispatch.html", line_start=10,
                                       line_end=10, quote="", verified=verified)])


@pytest.fixture
def comparison() -> Comparison:
    shared_a = _finding("Cancel rule differs", fid="F001")
    shared_b = _finding("Cancellation contradiction", fid="F004")
    only_a = [_finding("Only A sees this", Severity.MINOR, fid="F002")]
    only_b = [_finding("Only B sees this", fid="F005"), _finding("B invented", verified=False, fid="F006")]
    run_a = make_run("model-a", [shared_a, *only_a], value=91.0, minutes=2, cost=0.10)
    run_b = make_run("model-b", [shared_b, *only_b], value=64.0, minutes=0.5, cost=0.02)
    return Comparison(run_a=run_a, run_b=run_b, both=[(shared_a, shared_b)], only_a=only_a, only_b=only_b)


def test_AC_GUI_13_compare_view_groups_findings(window, comparison):
    window.show_comparison(comparison, load_journey(SAMPLE))
    c = window.compare
    assert c.stack.currentIndex() == 1
    assert c.both_box.title() == "Found by both (1)"
    assert c.a_box.title() == "Only model-a (1)"
    assert c.b_box.title() == "Only model-b (2)"
    assert c.both.item(0).text().endswith("Cancel rule differs")
    assert "(unverified)" in c.only_b.item(1).text()
    rows = {c.summary.item(r, 0).text(): (c.summary.item(r, 1).text(), c.summary.item(r, 2).text())
            for r in range(c.summary.rowCount())}
    assert rows["Set score"] == ("91.0", "64.0")
    assert rows["Cost"] == ("$0.1", "$0.02")
    assert rows["Duration"] == ("2 min 00 s", "30.0 s")
    assert rows["Tokens (in / out)"] == ("1,000 / 200", "1,000 / 200")
    assert c.summary.horizontalHeaderItem(1).text() == "A: model-a"


def test_AC_GUI_13_clicking_a_finding_shows_detail(window, comparison):
    window.show_comparison(comparison, load_journey(SAMPLE))
    c = window.compare
    c.both.setCurrentRow(0)
    text = c.detail.toPlainText()
    assert "Cancel rule differs" in text and "Cancellation contradiction" in text  # B's version too
    assert "delivery/dispatch.html" in text
    c.only_b.setCurrentRow(0)
    assert "Only B sees this" in c.detail.toPlainText()
    assert c.both.currentRow() == -1  # one selection across the lists


def test_AC_GUI_13_compare_two_saved_runs(window, comparison):
    a = window.run_store.save(comparison.run_a)
    b = window.run_store.save(comparison.run_b)
    result = window.compare_run_files([a, b])
    assert result is not None
    assert window.current_view() == "Compare"
    assert len(result.both) + len(result.only_a) + len(result.only_b) >= 3
    assert window.compare_run_files([a]) is None
    assert window.last_error[0] == "Choose two runs"


def test_AC_GUI_14_eval_view_renders_result(window):
    r = make_eval_result(score=72.5)
    window.evaluate.set_result(r)
    e = window.evaluate
    assert e.stack.currentIndex() == 1
    assert e.ring.value == 72.5
    assert "72.5" in e.score_label.text() and "fake-a" in e.score_label.text()
    metrics = [e.metrics.itemAt(i).widget().text() for i in range(e.metrics.count())]
    assert "Recall" in metrics and "<b>60%</b>" in metrics and "Verified quotes" in metrics
    assert "Stability" in metrics and "<b>–</b>" in metrics  # no repeat → no stability
    assert e.categories.rowCount() == 2
    assert e.categories.item(0, 0).text() == "contradiction"
    assert e.categories.item(1, 4).data(Qt.ItemDataRole.UserRole) == 0.25  # bar value for the delegate
    assert e.categories.item(1, 4).text() == "25%"
    assert e.missed.count() == 1 and "J3" in e.missed.item(0).text()
    assert "Returns are never documented" in e.missed.item(0).text()
    assert e.unexpected.count() == 1 and "Possibly real extra problem" in e.unexpected.item(0).text()
    assert "$0.42" in e.facts.text() and "1 min 33 s" in e.facts.text()


def test_AC_GUI_15_leaderboard_lists_and_sorts(window):
    results = [
        make_eval_result("alpha", score=9.5, recall=0.1, cost=3.0, started=datetime(2026, 10, 1, tzinfo=UTC)),
        make_eval_result("beta", score=81.0, recall=0.8, cost=0.5, started=datetime(2026, 10, 2, tzinfo=UTC)),
        make_eval_result("gamma", score=10.0, recall=0.2, cost=12.0, started=datetime(2026, 10, 3, tzinfo=UTC)),
    ]
    for r in results:
        window.eval_store.save(r)
    window.refresh_leaderboard()
    lb = window.leaderboard
    assert lb.stack.currentWidget() is lb.table
    header = [lb.model.headerData(c, Qt.Orientation.Horizontal) for c in range(lb.model.columnCount())]
    assert header == LEADERBOARD_COLUMNS
    assert lb.column_texts(1) == ["beta", "gamma", "alpha"]  # ranked by eval score
    lb.table.sortByColumn(4, Qt.SortOrder.AscendingOrder)
    assert lb.column_texts(4) == ["9.5", "10.0", "81.0"]  # numeric, not "10.0" < "81.0" < "9.5"
    lb.table.sortByColumn(10, Qt.SortOrder.DescendingOrder)
    assert lb.column_texts(1) == ["gamma", "alpha", "beta"]  # by cost
    lb.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
    assert lb.column_texts(1) == ["alpha", "beta", "gamma"]
    row = lb.column_texts(1).index("beta")
    cells = [lb.proxy.index(row, c).data() for c in range(len(LEADERBOARD_COLUMNS))]
    assert cells[2:10] == ["shopflow", "1", "81.0", "80%", "80%", "69%", "95%", "100%"]
    assert cells[11] == "1 min 33 s"


def test_AC_GUI_15_leaderboard_empty_state(window):
    assert window.leaderboard.stack.currentWidget() is window.leaderboard.empty
    assert window.leaderboard.empty.text() == NO_EVALS


def test_AC_GUI_21_evaluate_runs_in_worker_and_saves(window, qtbot):
    e = window.evaluate
    assert [e.provider.itemText(i) for i in range(e.provider.count())] == ["fake-a", "fake-b"]
    assert e.benchmark.currentText() == "shopflow"
    e.provider.setCurrentIndex(1)
    e.repeat.setValue(2)
    e.include_rules.setChecked(True)
    with qtbot.waitSignal(window.eval_finished, timeout=10000) as blocker:
        e.run_btn.click()
    result = blocker.args[0]
    call = window.eval_service.calls[0]
    assert call["provider"] == "fake-b" and call["repeat"] == 2 and call["include_rules"] is True
    assert call["thread"] != "MainThread"
    assert e.result is result and e.ring.value == 81.0
    assert "Evaluation finished" in e.status.text()
    assert len(window.eval_store.load_all()) == 1
    assert window.leaderboard.column_texts(1) == ["fake-b"]
    assert e.run_btn.isEnabled() and not e.cancel_btn.isEnabled()
