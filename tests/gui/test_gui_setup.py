"""GUI tests: main window, Setup view, running and cancelling reviews (spec GUI, AC-GUI-01…06, 17, 18, 20)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from gui_helpers import (
    QUOTE,
    SAMPLE,
    WORKER_THREADS,
    SlowCheck,
    StubLinkCheck,
    StubLlmCheck,
    StubValueCheck,
    run_review,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from umr.gui.integrations import ProviderCatalog
from umr.gui.viewmodels import NONE_A, NONE_B, OPEN_JOURNEY
from umr.llm.base import LlmError, LlmProvider
from umr.llm.fake import FakeProvider

pytestmark = pytest.mark.gui


def test_AC_GUI_01_window_opens_with_sidebar_and_empty_state(window):
    window.show()
    assert [window.nav.item(i).text() for i in range(window.nav.count())] == [
        "Setup", "Dashboard", "Findings", "Compare", "Evaluate", "Leaderboard"]
    assert window.current_view() == "Setup"
    assert window.setup.manuals_stack.currentWidget() is window.setup.manuals_empty
    assert window.setup.manuals_empty.text() == OPEN_JOURNEY
    assert window.findings.empty.text() == OPEN_JOURNEY
    assert window.windowTitle() == "User Manual Reviewer"
    window.nav.setCurrentRow(5)
    assert window.current_view() == "Leaderboard"


def test_AC_GUI_02_open_sample_journey_lists_three_manuals(window):
    assert window.open_journey(SAMPLE)
    tree = window.setup.manuals
    assert window.setup.manual_count() == 3
    ids = [tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) for i in range(3)]
    assert ids == ["order-capturing", "delivery", "notification"]
    first = tree.topLevelItem(0)
    assert first.childCount() == len(window.journey.manuals[0].pages)
    assert first.child(0).text(2) == f"{window.journey.manuals[0].pages[0].word_count:,}"
    assert "ShopFlow order to delivery" in window.windowTitle()
    assert window.settings.value("last_journey") == str(SAMPLE.resolve())


def test_AC_GUI_02_initial_journey_is_remembered_path(make_window, tmp_path):
    w1 = make_window()
    w1.open_journey(SAMPLE)
    w2 = make_window()  # same settings file
    w2.open_initial_journey()
    assert w2.journey is not None and w2.journey.name == "ShopFlow order to delivery"


def test_AC_GUI_02_bad_journey_shows_readable_error(window, tmp_path):
    assert not window.open_journey(tmp_path / "nope.yaml")
    assert window.last_error is not None
    assert window.last_error[0] == "Could not open the journey"


def test_AC_GUI_03_check_buttons_group_and_badge(make_window):
    w = make_window(stubs=[StubValueCheck, StubLinkCheck, StubLlmCheck])
    tree = w.setup.checks_tree
    assert tree.topLevelItemCount() == 2
    assert tree.topLevelItem(0).text(0).startswith("Rule checks")
    assert tree.topLevelItem(1).text(0).startswith("LLM checks")
    llm_item = tree.topLevelItem(1).child(0)
    assert llm_item.text(1) == "needs LLM"
    assert tree.topLevelItem(0).child(0).text(1) == ""
    assert set(w.setup.selected_check_ids()) == {"stub-value", "stub-link", "stub-llm"}
    assert "1 need an LLM" in w.setup.summary.text()
    assert "LLM checks will be skipped" in w.setup.summary.text()
    w.setup.rules_btn.click()
    assert w.setup.selected_check_ids() == ["stub-value", "stub-link"]
    assert "0 need an LLM" in w.setup.summary.text()
    w.setup.none_btn.click()
    assert w.setup.selected_check_ids() == []
    w.setup.all_btn.click()
    assert len(w.setup.selected_check_ids()) == 3
    w.setup.model_a.setCurrentIndex(1)
    assert "skipped" not in w.setup.summary.text()


def test_AC_GUI_04_model_pickers_list_providers(window):
    a = [window.setup.model_a.itemText(i) for i in range(window.setup.model_a.count())]
    b = [window.setup.model_b.itemText(i) for i in range(window.setup.model_b.count())]
    assert a == [NONE_A, "fake-a", "fake-b"]
    assert b == [NONE_B, "fake-a", "fake-b"]
    window.setup.model_b.setCurrentIndex(2)
    assert window.setup.start_btn.text() == "Start comparison"


def test_AC_GUI_04_example_config_notice(tmp_path, make_window):
    example = Path(__file__).resolve().parents[2] / "config" / "llm-providers.example.yaml"
    catalog = ProviderCatalog.load(config_file=tmp_path / "llm-providers.yaml", example_file=example)
    assert "example" in catalog.notice and "environment variable" in catalog.notice
    assert "claude-sonnet" in catalog.names()
    w = make_window(providers=catalog)
    assert w.setup.provider_notice.text() == catalog.notice
    assert w.setup.model_a.findText("claude-sonnet") > 0


def test_AC_GUI_05_start_runs_in_worker_logs_and_saves(window, qtbot):
    window.open_journey(SAMPLE)
    WORKER_THREADS.clear()
    run = run_review(qtbot, window)
    assert WORKER_THREADS and WORKER_THREADS[0] != threading.main_thread().name
    log = window.setup.log.toPlainText()
    assert "▶ stub-value started" in log
    assert "✓ stub-value finished: 1 finding" in log
    assert "✓ stub-link finished: 1 finding" in log
    assert "Review finished" in log
    assert window.setup.progress.value() == 100
    assert window.setup.start_btn.isEnabled() and not window.setup.cancel_btn.isEnabled()
    saved = window.run_store.list()
    assert len(saved) == 1 and window.run_store.load(saved[0]).id == run.id
    assert window.current_view() == "Dashboard"
    assert run.findings[0].locations[0].quote == QUOTE


def test_AC_GUI_06_cancel_stops_review(make_window, qtbot):
    w = make_window(stubs=[SlowCheck, StubValueCheck])
    w.open_journey(SAMPLE)
    SlowCheck.started.clear()
    SlowCheck.release.clear()
    w.start_review()
    assert w.is_running()
    assert not w.setup.start_btn.isEnabled()
    qtbot.waitUntil(SlowCheck.started.is_set, timeout=5000)
    with qtbot.waitSignal(w.task_ended, timeout=10000) as blocker:
        w.setup.cancel_btn.click()
        SlowCheck.release.set()
    assert blocker.args == ["cancelled"]
    assert "Review cancelled." in w.setup.log.toPlainText()
    assert w.setup.start_btn.isEnabled()
    assert not w.is_running()
    assert w.run_store.list() == []


class _MissingKey:
    def __call__(self) -> LlmProvider:
        raise LlmError("Provider 'cloud': environment variable CLOUD_API_KEY is not set. "
                       "Set it in your environment or in a .env file.")


def test_AC_GUI_17_missing_api_key_shows_error_dialog(make_window):
    catalog = ProviderCatalog({"cloud": _MissingKey()})
    w = make_window(providers=catalog)
    w.open_journey(SAMPLE)
    w.setup.model_a.setCurrentIndex(1)
    w.start_review()
    assert w.last_error is not None
    title, text = w.last_error
    assert title == "Model error"
    assert "CLOUD_API_KEY" in text and "api_key_env" in text
    assert not w.is_running()


def test_AC_GUI_17_no_journey_and_no_checks_errors(window):
    window.start_review()
    assert window.last_error is not None and window.last_error[0] == "No journey open"
    window.open_journey(SAMPLE)
    window.setup.none_btn.click()
    window.start_review()
    assert window.last_error[0] == "No checks selected"


def test_AC_GUI_18_keyboard_shortcuts(make_window, qtbot, monkeypatch):
    w = make_window(stubs=[SlowCheck, StubValueCheck])
    w.show()
    qtbot.waitExposed(w)
    w.activateWindow()
    qtbot.waitUntil(w.isActiveWindow, timeout=3000)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(SAMPLE), ""))
    qtbot.keyClick(w, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    assert w.journey is not None and w.setup.manual_count() == 3
    SlowCheck.started.clear()
    SlowCheck.release.clear()
    qtbot.keyClick(w, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
    assert w.is_running()
    qtbot.waitUntil(SlowCheck.started.is_set, timeout=5000)
    with qtbot.waitSignal(w.task_ended, timeout=10000) as blocker:
        qtbot.keyClick(w, Qt.Key.Key_Escape)
        SlowCheck.release.set()
    assert blocker.args == ["cancelled"]
    assert w.act_open.shortcut().toString() == "Ctrl+O"
    assert w.act_start.shortcut().toString() == "Ctrl+R"
    assert w.act_cancel.shortcut().toString() == "Esc"


def test_AC_GUI_20_model_b_runs_comparison(make_window, qtbot):
    w = make_window(stubs=[StubValueCheck, StubLlmCheck],
                    providers=ProviderCatalog.from_providers({"fake-a": FakeProvider(name="fake-a"),
                                                              "fake-b": FakeProvider(name="fake-b")}))
    w.open_journey(SAMPLE)
    w.setup.model_a.setCurrentIndex(1)
    w.setup.model_b.setCurrentIndex(2)
    with qtbot.waitSignal(w.comparison_finished, timeout=15000) as blocker:
        w.start_review()
    comparison = blocker.args[0]
    assert comparison.run_a.model == "fake-a" and comparison.run_b.model == "fake-b"
    assert len(w.run_store.list()) == 2
    assert w.current_view() == "Compare"
    assert w.compare.both_box.title() == f"Found by both ({len(comparison.both)})"
    assert len(comparison.both) == 2
    log = w.setup.log.toPlainText()
    assert "[fake-a]" not in log and "[A] ✓ stub-value finished" in log and "[B]" in log
    assert w.setup.progress.value() == 100
    assert w.run is comparison.run_a
