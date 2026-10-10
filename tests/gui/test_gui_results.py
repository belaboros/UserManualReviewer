"""GUI tests: dashboard, findings table, filters, finding detail, opening runs (AC-GUI-07…12, 16, 19)."""

from __future__ import annotations

import pytest
from gui_helpers import QUOTE, SAMPLE, EmptyCheck, FailingCheck, StubLinkCheck, StubValueCheck, run_review
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from umr.checks import CheckRegistry
from umr.domain import Category, Severity, Tier
from umr.gui.findings_view import FINDING_ROLE
from umr.gui.viewmodels import FINDING_COLUMNS, NO_FINDINGS, NO_MATCH, score_band
from umr.ingest import load_journey

pytestmark = pytest.mark.gui


@pytest.fixture
def reviewed(window, qtbot):
    """Window after a review with a rule finding, a second rule finding and an unverified LLM finding."""
    window.open_journey(SAMPLE)
    window.setup.model_a.setCurrentIndex(1)  # fake-a, so the stub LLM check runs too
    run = run_review(qtbot, window)
    return window, run


def test_AC_GUI_07_dashboard_shows_scores_charts_and_facts(reviewed):
    w, run = reviewed
    d = w.dashboard
    set_score = run.score_for("set")
    assert set_score is not None
    assert d.ring.value == set_score.value
    assert d.ring.band_color() == QColor(score_band(set_score.value))
    assert [c.manual_id for c in d.cards] == ["order-capturing", "delivery", "notification"]
    counts = {s: (v, u) for s, v, u in d.bars.counts}
    assert counts[Severity.MAJOR] == (1, 0)
    assert counts[Severity.MINOR] == (1, 0)
    assert counts[Severity.CRITICAL] == (0, 1)  # the invented quote is unverified
    hm = d.heat.data
    assert set(hm.cols) == {"value-conflict", "broken-link"}
    row = hm.rows.index("order-capturing/02-creating-an-order.md")
    assert hm.counts[row][hm.cols.index("value-conflict")] == 1
    assert len(hm.rows) == len(w.journey.pages)
    facts = {d.facts.itemAt(i).widget().text() for i in range(d.facts.count())}
    assert {"Model", "Duration", "Tokens", "Cost"} <= facts
    assert "fake-a" in facts
    assert any("1,200 in" in f for f in facts)
    assert "$0.0123" in facts
    assert not d.errors_box.isVisibleTo(w)


def test_AC_GUI_07_dashboard_with_real_rule_checks(make_window, qtbot):
    rules = [c for c in CheckRegistry.all() if c.tier == Tier.RULE]
    if not rules:
        pytest.skip("no rule checks registered")
    w = make_window(stubs=rules)
    w.open_journey(SAMPLE)
    run = run_review(qtbot, w, timeout=60000)
    assert w.dashboard.ring.value == run.score_for("set").value
    assert w.findings.model.rowCount() == len(run.findings)
    assert len(w.dashboard.cards) == 3


def test_AC_GUI_08_failed_check_listed_on_dashboard(make_window, qtbot):
    w = make_window(stubs=[StubValueCheck, FailingCheck])
    w.open_journey(SAMPLE)
    run = run_review(qtbot, w)
    assert run.errors and run.errors[0].check_id == "stub-fail"
    assert w.dashboard.errors_box.isVisibleTo(w)
    assert "stub-fail" in w.dashboard.errors_label.text()
    assert "boom in stub" in w.dashboard.errors_label.text()
    assert "✗ stub-fail failed: RuntimeError: boom in stub" in w.setup.log.toPlainText()


def test_AC_GUI_09_findings_table_columns_and_rows(reviewed):
    w, run = reviewed
    model = w.findings.model
    headers = [model.headerData(c, Qt.Orientation.Horizontal) for c in range(model.columnCount())]
    assert headers == FINDING_COLUMNS == ["Id", "Severity", "Category", "Title", "Manual(s)", "Page(s)",
                                          "Source", "Verified"]
    assert w.findings.proxy.rowCount() == len(run.findings) == 3
    texts = {model.index(r, 3).data() for r in range(model.rowCount())}
    assert "Line item limit differs" in texts
    row = next(r for r in range(model.rowCount()) if model.index(r, 0).data() == run.findings[0].id)
    assert model.index(row, 4).data() == "order-capturing"
    assert model.index(row, 5).data().startswith("02-creating-an-order.md:")
    assert model.index(row, 6).data() == "rule"


def test_AC_GUI_09_severity_sorts_by_rank(reviewed):
    w, _ = reviewed
    w.findings.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    sev = [w.findings.proxy.index(r, 1).data() for r in range(w.findings.proxy.rowCount())]
    assert sev == ["critical", "major", "minor"]


def test_AC_GUI_10_findings_filter_by_severity_category_manual_verified_text(reviewed):
    w, _ = reviewed
    f = w.findings
    f.severity.setCurrentIndex(f.severity.findData(Severity.MAJOR))
    assert [x.title for x in f.visible_findings()] == ["Line item limit differs"]
    f.severity.setCurrentIndex(0)
    f.category.setCurrentIndex(f.category.findData(Category.BROKEN_LINK))
    assert [x.category for x in f.visible_findings()] == [Category.BROKEN_LINK]
    f.category.setCurrentIndex(0)
    f.manual.setCurrentIndex(f.manual.findData("delivery"))
    assert {x.check_id for x in f.visible_findings()} == {"stub-link", "stub-llm"}
    f.verified_only.setChecked(True)
    assert [x.check_id for x in f.visible_findings()] == ["stub-link"]
    f.manual.setCurrentIndex(0)
    f.verified_only.setChecked(False)
    f.search.setText("50 line items")  # matches the quote
    assert [x.check_id for x in f.visible_findings()] == ["stub-value"]
    f.search.setText("no such words anywhere")
    assert f.visible_findings() == []
    assert f.empty.text() == NO_MATCH
    assert f.table_stack.currentWidget() is f.empty
    assert "0 of 3" in f.count_label.text()


def test_AC_GUI_11_unverified_finding_greyed_and_marked(reviewed):
    w, run = reviewed
    model = w.findings.model
    row = next(r for r in range(model.rowCount()) if not model.findings[r].verified)
    assert model.index(row, 7).data() == "unverified"
    assert model.index(row, 3).data(Qt.ItemDataRole.ForegroundRole).color() == model.muted
    assert model.index(row, 3).data(Qt.ItemDataRole.FontRole).italic()
    ok = next(r for r in range(model.rowCount()) if model.findings[r].verified)
    assert model.index(ok, 7).data() == "✓ verified"
    assert not model.index(ok, 3).data(Qt.ItemDataRole.FontRole).italic()


def test_AC_GUI_12_finding_detail_highlights_quote(reviewed):
    w, run = reviewed
    f = w.findings
    assert f.select_finding(run.findings[0].id)
    detail = f.detail
    assert detail.finding is not None and detail.finding.id == run.findings[0].id
    text = detail.toPlainText()
    assert "Line item limit differs" in text
    assert "The limit is 50 here but 40 elsewhere." in text
    assert "Use one limit everywhere." in text
    loc = run.findings[0].locations[0]
    assert loc.line_start is not None
    page = load_journey(SAMPLE).page(loc.page_id)
    assert page is not None
    assert QUOTE in text
    lines = text.splitlines()
    for n in (loc.line_start - 5, loc.line_start, loc.line_start + 5):  # line numbers with ±5 context
        assert str(n) in lines
    assert str(loc.line_start - 6) not in lines and str(loc.line_start + 6) not in lines
    assert "Click **New Order**" in text or "click **New Order**" in text  # a context line
    html = detail.toHtml()
    assert "#ffd54f" in html  # the marked quote


def test_AC_GUI_12_detail_unverified_location_says_not_found(reviewed):
    w, run = reviewed
    bad = next(x for x in run.findings if not x.verified)
    w.findings.select_finding(bad.id)
    text = w.findings.detail.toPlainText()
    assert "passage not found in the source" in text
    assert "this sentence is not in any manual at all" in text
    assert "unverified" in text


def test_AC_GUI_16_open_saved_run(make_window, qtbot):
    w1 = make_window(stubs=[StubValueCheck, StubLinkCheck])
    w1.open_journey(SAMPLE)
    run = run_review(qtbot, w1)
    path = w1.run_store.list()[0]
    w2 = make_window(stubs=[StubValueCheck], run_store=w1.run_store)
    loaded = w2.open_run(path)
    assert loaded is not None and loaded.id == run.id
    assert w2.current_view() == "Dashboard"
    assert w2.dashboard.ring.value == run.score_for("set").value
    assert w2.findings.model.rowCount() == 2
    assert w2.run_journey is not None  # sources re-loaded from the run's journey path
    assert str(path) in w2.recent_run_paths()
    w2.populate_recent_runs()
    actions = [a.text() for a in w2.recent_menu.actions()]
    assert path.stem in actions
    assert "ShopFlow order to delivery" in w2.windowTitle()


def test_AC_GUI_16_open_broken_run_shows_error(window, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert window.open_run(bad) is None
    assert window.last_error is not None and window.last_error[0] == "Could not open the run"


def test_AC_GUI_19_zero_findings_empty_state(make_window, qtbot):
    w = make_window(stubs=[EmptyCheck])
    w.open_journey(SAMPLE)
    run = run_review(qtbot, w)
    assert run.findings == []
    assert w.dashboard.no_findings.isVisibleTo(w)
    assert w.dashboard.no_findings.text() == NO_FINDINGS == "No findings — 100%"
    assert w.dashboard.ring.value == 100.0
    assert w.findings.empty.text() == NO_FINDINGS
    assert w.findings.table_stack.currentWidget() is w.findings.empty
    assert w.findings.proxy.data(w.findings.proxy.index(0, 0), FINDING_ROLE) is None
