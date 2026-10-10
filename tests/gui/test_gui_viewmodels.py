"""Widget-free tests of the GUI view-model helpers (spec GUI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from gui_helpers import QUOTE, SAMPLE

from umr.app import ProgressEvent
from umr.app.verify import verify_finding
from umr.domain import Category, CheckResult, Finding, Location, Severity, Tier
from umr.gui.viewmodels import (
    BAND_AMBER,
    BAND_GREEN,
    BAND_RED,
    FindingFilter,
    friendly_error,
    passage_html,
    progress_line,
    score_band,
    selection_summary,
)
from umr.gui.viewmodels import CheckInfo as CI
from umr.ingest import IngestError, load_journey
from umr.llm.base import LlmError

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def journey():
    return load_journey(SAMPLE)


def test_AC_GUI_07_score_band_colours():
    assert score_band(100) == score_band(90) == BAND_GREEN
    assert score_band(89.9) == score_band(70) == BAND_AMBER
    assert score_band(69.9) == score_band(0) == BAND_RED


def test_AC_GUI_12_passage_html_numbers_context_and_marks_quote(journey):
    f = Finding(check_id="x", category=Category.VALUE_CONFLICT, severity=Severity.MAJOR, title="t",
                locations=[Location(manual_id="order-capturing", page_path="02-creating-an-order.md", quote=QUOTE)])
    verify_finding(journey, f)
    loc = f.locations[0]
    html = passage_html(journey, loc)
    n = loc.line_start
    assert n is not None
    for k in range(n - 5, n + 6):
        assert f">{k}</td>" in html
    assert f">{n - 6}</td>" not in html and f">{n + 6}</td>" not in html
    assert f'font-weight:bold">{QUOTE}</span>' in html
    assert html.count("<tr bgcolor=") == 1  # only the located line is highlighted


def test_AC_GUI_12_passage_html_html_page_uses_readable_text(journey):
    loc = Location(manual_id="delivery", page_path="dispatch.html", line_start=12, line_end=12, verified=True)
    html = passage_html(journey, loc)
    assert "&lt;" not in html.split("</p>", 1)[1]  # markup stripped: readable text per line


def test_AC_GUI_12_passage_html_missing_source():
    loc = Location(manual_id="m", page_path="p.md", quote="some words")
    html = passage_html(None, loc)
    assert "source not available" in html and "some words" in html


def test_AC_GUI_10_finding_filter_combines_with_and():
    f = Finding(check_id="c", category=Category.TERMINOLOGY, severity=Severity.MINOR, title="Drift of term",
                verified=False, locations=[Location(manual_id="delivery", page_path="a.md", quote="pick list")])
    assert FindingFilter().accepts(f)
    assert FindingFilter(severity=Severity.MINOR, category=Category.TERMINOLOGY, manual="delivery").accepts(f)
    assert not FindingFilter(severity=Severity.MAJOR).accepts(f)
    assert not FindingFilter(manual="notification").accepts(f)
    assert not FindingFilter(verified_only=True).accepts(f)
    assert FindingFilter(text="PICK drift").accepts(f)
    assert not FindingFilter(text="pick missing").accepts(f)


def test_AC_GUI_03_selection_summary_counts_llm_checks():
    checks = [CI("a", "A", "", Tier.RULE), CI("b", "B", "", Tier.LLM), CI("c", "C", "", Tier.LLM)]
    assert selection_summary(checks, {"a", "b"}, has_model=True) == "2 of 3 checks selected · 1 need an LLM"
    assert "skipped" in selection_summary(checks, {"b"}, has_model=False)


def test_AC_GUI_05_progress_lines():
    res = CheckResult(check_id="links", tier=Tier.RULE, findings=[], duration_s=0.5)
    assert progress_line(ProgressEvent("check_finished", "links", 1, 4, res)) == \
        "✓ links finished: 0 findings, 0.50 s  (1/4)"
    bad = CheckResult(check_id="x", tier=Tier.LLM, error="LlmError: timeout")
    assert progress_line(ProgressEvent("check_finished", "x", 2, 4, bad), "B").startswith("[B] ✗ x failed")


def test_AC_GUI_17_friendly_error_messages():
    title, text = friendly_error(LlmError("environment variable OPENAI_API_KEY is not set"))
    assert title == "Model error" and "OPENAI_API_KEY" in text and ".env" in text
    assert friendly_error(IngestError("bad"))[0] == "Could not open the journey"
    assert friendly_error(FileNotFoundError(str(Path("x"))))[0] == "File not found"
