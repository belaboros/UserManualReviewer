"""Tests for spec DUP: duplicate sections (TEST_SPECS/DUP-duplicate-sections.md)."""

from __future__ import annotations

from umr.checks import CheckRegistry
from umr.domain import Category, Scope, Severity, Tier

from .helpers import MakeJourney, run_check

BODY = ("Open the order list and pick the order you want to change. Check the customer data, the delivery "
        "address and every line item carefully before you continue with the next step of the process.")
OTHER = ("Warehouse staff scan each parcel at the loading dock, weigh it on the calibrated scale and print "
         "a shipping label that matches the carrier chosen for the route of the day.")


def test_AC_DUP_01_registered_as_manual_scope_rule_check() -> None:
    cls = CheckRegistry.get("duplicates")
    assert cls.tier == Tier.RULE and cls.scope == Scope.MANUAL and cls.categories == (Category.DUPLICATE,)


def test_AC_DUP_02_identical_sections_on_different_pages(make_journey: MakeJourney) -> None:
    j = make_journey({"m": {
        "index.md": f"# Index\n\n## Editing orders\n\n{BODY}\n",
        "other.md": f"# Other\n\n## Changing an order\n\n{BODY}\n\n## Loading\n\n{OTHER}\n",
    }})
    findings = run_check("duplicates", j)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == Severity.MINOR and f.title.startswith("Duplicate sections")
    assert [(loc.page_id, loc.line_start) for loc in f.locations] == [("m/index.md", 3), ("m/other.md", 3)]
    assert [loc.quote for loc in f.locations] == ["Editing orders", "Changing an order"]


def test_AC_DUP_03_near_duplicate_across_manuals_and_formats(make_journey: MakeJourney) -> None:
    changed = BODY.replace("carefully", "").replace("next step", "following step") + " See the FAQ."
    j = make_journey({
        "a": {"index.md": f"# A\n\n## Editing orders\n\n{BODY}\n"},
        "b": {"index.html": f"<html><body>\n<h1>B</h1>\n<h2>Edit an order</h2>\n<p>{changed}</p>\n</body></html>\n"},
    })
    findings = run_check("duplicates", j)
    assert len(findings) == 1
    f = findings[0]
    assert f.title.startswith("Near-duplicate sections")
    assert "% similar" in f.explanation and "two different manuals" in f.explanation
    assert {loc.manual_id for loc in f.locations} == {"a", "b"}


def test_AC_DUP_04_different_sections_not_reported(make_journey: MakeJourney) -> None:
    j = make_journey({"m": {"index.md": f"# Index\n\n## One\n\n{BODY}\n\n## Two\n\n{OTHER}\n"}})
    assert run_check("duplicates", j) == []


def test_AC_DUP_05_short_sections_ignored(make_journey: MakeJourney) -> None:
    short = "Click Save to keep your changes."
    j = make_journey({"m": {"index.md": f"# Index\n\n## One\n\n{short}\n\n## Two\n\n{short}\n"}})
    assert run_check("duplicates", j) == []


def test_AC_DUP_06_parent_and_child_not_reported_as_duplicates(make_journey: MakeJourney) -> None:
    # the parent's body is mostly its only child: they must not be reported against each other
    j = make_journey({"m": {"index.md": f"# Index\n\n## Parent\n\n### Child\n\n{BODY}\n\n## Last\n\n{OTHER}\n"}})
    assert run_check("duplicates", j) == []


def test_AC_DUP_06_duplicated_parent_reported_once_not_per_child(make_journey: MakeJourney) -> None:
    page = f"# Topic\n\n## Part one\n\n{BODY}\n\n## Part two\n\n{OTHER}\n"
    j = make_journey({"a": {"index.md": page}, "b": {"index.md": page}})
    findings = run_check("duplicates", j)
    assert len(findings) == 1
    assert [loc.quote for loc in findings[0].locations] == ["Topic", "Topic"]


def test_AC_DUP_07_same_page_duplicates_point_to_both_headings(make_journey: MakeJourney) -> None:
    j = make_journey({"m": {"index.md": f"# Index\n\n## Same\n\n{BODY}\n\n## Same\n\n{BODY}\n"}})
    findings = run_check("duplicates", j)
    assert len(findings) == 1
    assert [loc.line_start for loc in findings[0].locations] == [3, 7]
    assert "on the same page" in findings[0].explanation
