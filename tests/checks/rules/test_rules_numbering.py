"""Tests for spec STRUCT: step numbering (TEST_SPECS/STRUCT-step-numbering.md)."""

from __future__ import annotations

from umr.checks import CheckRegistry
from umr.domain import Category, Scope, Severity, Tier

from .helpers import MakeJourney, run_check


def _md(make_journey: MakeJourney, text: str):
    return run_check("numbering", make_journey({"m": {"index.md": text}}))


def test_AC_STRUCT_01_registered_as_page_scope_rule_check() -> None:
    cls = CheckRegistry.get("numbering")
    assert cls.tier == Tier.RULE and cls.scope == Scope.PAGE and cls.categories == (Category.STEP_ORDER,)


def test_AC_STRUCT_02_skipped_number_reported_as_major(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# Steps\n\n1. Open.\n2. Fill in.\n3. Accept.\n5. Click Submit.\n")
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == Severity.MAJOR and f.title == "Step numbering skips from 3 to 5"
    assert "step 4 is missing" in f.explanation
    assert f.locations[0].line_start == 6 and f.locations[0].quote == "Click Submit."


def test_AC_STRUCT_03_repeated_number_reported(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# Steps\n\n1. Go.\n2. Select.\n3. Edit and save.\n3. Preview.\n")
    assert [f.title for f in findings] == ["Step number 3 is used twice"]
    assert findings[0].severity == Severity.MINOR and findings[0].locations[0].line_start == 6


def test_AC_STRUCT_04_backwards_number_reported(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# Steps\n\n1. Go.\n2. Select.\n3. Edit.\n2. Preview.\n")
    assert [f.title for f in findings] == ["Step numbering goes back from 3 to 2"]


def test_AC_STRUCT_05_correct_lists_not_reported(make_journey: MakeJourney) -> None:
    text = ("# Steps\n\n1. One.\n2. Two.\n\n   More about two.\n\n3. Three.\n\nText.\n\n"
            "4. Continued list starting at four.\n5. Five.\n\nAgain:\n\n1. Lazy.\n1. Lazy.\n1. Lazy.\n")
    assert _md(make_journey, text) == []


def test_AC_STRUCT_06_nested_lists_and_code_checked_separately(make_journey: MakeJourney) -> None:
    text = ("# Steps\n\n1. Outer one.\n   1. Inner one.\n   2. Inner two.\n2. Outer two.\n   1. Inner again.\n"
            "   3. Inner skips.\n3. Outer three.\n\n```\n1. not a list\n3. inside code\n```\n")
    findings = _md(make_journey, text)
    assert [f.title for f in findings] == ["Step numbering skips from 1 to 3"]
    assert findings[0].locations[0].line_start == 8


def test_AC_STRUCT_07_html_text_numbers_checked(make_journey: MakeJourney) -> None:
    html = ("<html><body>\n<h1>1. Steps</h1>\n<p>1. Scan the label.</p>\n<p>2. Assign a route.</p>\n"
            "<p>4. Send the notice.</p>\n<ol>\n<li>No number here.</li>\n<li>Nor here.</li>\n</ol>\n"
            "</body></html>\n")
    findings = run_check("numbering", make_journey({"m": {"index.html": html}}))
    assert [f.title for f in findings] == ["Step numbering skips from 2 to 4"]
    assert findings[0].locations[0].line_start == 5


def test_AC_STRUCT_07_html_headings_not_treated_as_steps(make_journey: MakeJourney) -> None:
    html = "<html><body>\n<h1>1. Intro</h1>\n<h2>3. Later</h2>\n</body></html>\n"
    assert run_check("numbering", make_journey({"m": {"index.html": html}})) == []


def test_AC_STRUCT_08_one_finding_per_break(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# S\n\n1. A.\n2. B.\n2. C.\n5. D.\n6. E.\n")
    assert [(f.title, f.locations[0].line_start) for f in findings] == [
        ("Step number 2 is used twice", 5), ("Step numbering skips from 2 to 5", 6)]
