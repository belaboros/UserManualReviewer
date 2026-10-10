"""Tests for spec LINK: links, images and orphans (TEST_SPECS/LINK-links-images-orphans.md)."""

from __future__ import annotations

import pytest

from umr.checks import CheckRegistry
from umr.domain import Category, Finding, Journey, Scope, Severity, Tier
from umr.ingest import load_journey

from .helpers import FIXTURES, MakeJourney, line_of, run_check

LINKS = FIXTURES / "links-journey"


@pytest.fixture(scope="module")
def journey() -> Journey:
    return load_journey(LINKS / "journey.yaml")


def _page(journey: Journey, page_id: str):
    page = journey.page(page_id)
    assert page is not None
    return page


def _at(findings: list[Finding], page_id: str, line: int) -> list[Finding]:
    return [f for f in findings if any(loc.page_id == page_id and loc.line_start == line for loc in f.locations)]


# ---------- registration ----------

@pytest.mark.parametrize(("check_id", "scope", "cats"), [
    ("links", Scope.MANUAL, {Category.BROKEN_LINK, Category.BROKEN_ANCHOR}),
    ("images", Scope.PAGE, {Category.IMAGE}),
    ("orphans", Scope.MANUAL, {Category.ORPHAN_PAGE}),
])
def test_AC_LINK_01_checks_registered_as_rule_checks(check_id: str, scope: Scope, cats: set[Category]) -> None:
    cls = CheckRegistry.get(check_id)
    assert cls.tier == Tier.RULE and cls.scope == scope and set(cls.categories) == cats
    assert check_id in CheckRegistry.ids(Tier.RULE)


# ---------- links ----------

def test_AC_LINK_02_missing_file_reported_as_major_broken_link(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "old-page.md"))
    assert len(hits) == 1
    f = hits[0]
    assert f.category == Category.BROKEN_LINK and f.severity == Severity.MAJOR
    assert "old-page.md" in f.title
    assert f.locations[0].quote == "[old page](old-page.md)"


def test_AC_LINK_02_missing_file_in_html_page(journey: Journey) -> None:
    findings = run_check("links", journey)
    index = _page(journey, "ops/index.html")
    hits = _at(findings, "ops/index.html", line_of(index, 'href="run.htm"'))
    assert [f.category for f in hits] == [Category.BROKEN_LINK]


def test_AC_LINK_02_empty_link_target_is_broken(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "[empty one]()"))
    assert len(hits) == 1 and "empty" in hits[0].title.lower()


def test_AC_LINK_03_existing_targets_not_reported(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    setup = _page(journey, "guide/setup.md")
    assert not _at(findings, "guide/start.md", line_of(start, "[Setup](setup.md)"))
    assert not _at(findings, "guide/setup.md", line_of(setup, "(start.md)"))
    # "#" alone is a placeholder, not a broken anchor
    assert all("'#'" not in f.title for f in findings)


def test_AC_LINK_04_broken_in_page_anchor_reported(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "#nowhere"))
    assert len(hits) == 1
    assert hits[0].category == Category.BROKEN_ANCHOR and hits[0].severity == Severity.MINOR
    assert "#nowhere" in hits[0].title and "details" not in hits[0].title


def test_AC_LINK_04_existing_in_page_anchor_html(journey: Journey) -> None:
    findings = run_check("links", journey)
    index = _page(journey, "ops/index.html")
    hits = _at(findings, "ops/index.html", line_of(index, "#missing-id"))
    assert len(hits) == 1 and "#missing-id" in hits[0].title and "#ops" not in hits[0].title


def test_AC_LINK_05_cross_page_anchor_checked_against_target_page(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "setup.md#tuning"))
    assert len(hits) == 1
    assert hits[0].category == Category.BROKEN_ANCHOR and "#tuning" in hits[0].title
    assert "installing" not in hits[0].title and "configuring" not in hits[0].title


def test_AC_LINK_06_links_into_other_manual_resolve(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    index = _page(journey, "ops/index.html")
    assert not _at(findings, "guide/start.md", line_of(start, "../ops/index.html)"))
    assert not _at(findings, "ops/index.html", line_of(index, "../guide/start.md#details"))
    gone = _at(findings, "guide/start.md", line_of(start, "../ops/gone.html"))
    assert [f.category for f in gone] == [Category.BROKEN_LINK]
    run = _at(findings, "guide/start.md", line_of(start, "run.html#failures"))
    assert {f.category for f in run} == {Category.BROKEN_ANCHOR}


def test_AC_LINK_06_single_manual_journey_still_checks_cross_manual_links() -> None:
    single = load_journey(LINKS / "guide")
    assert len(single.manuals) == 1
    check = CheckRegistry.get("links")()
    assert check.applies_to(single)
    findings = run_check("links", single)
    start = _page(single, "guide/start.md")
    assert not _at(findings, "guide/start.md", line_of(start, "../ops/index.html)"))
    assert _at(findings, "guide/start.md", line_of(start, "../ops/gone.html"))


def test_AC_LINK_07_external_links_ignored(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    assert not _at(findings, "guide/start.md", line_of(start, "External:"))


def test_AC_LINK_08_fix_suggests_similar_file_and_anchor(journey: Journey) -> None:
    findings = run_check("links", journey)
    by_title = {f.title: f for f in findings}
    assert "Did you mean 'run.html'" in by_title["Broken link to 'run.htm'"].suggested_fix
    case = next(f for f in findings if "#Running" in f.title)
    assert "case-sensitive" in case.suggested_fix and "#running" in case.suggested_fix
    no_id = next(f for f in findings if "#failures" in f.title)
    assert "has no id" in no_id.suggested_fix and 'id="failures"' in no_id.suggested_fix


def test_AC_LINK_09_several_broken_links_on_one_line_give_one_finding(journey: Journey) -> None:
    findings = run_check("links", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "Two broken here"))
    assert len(hits) == 1
    assert "first-missing.md" in hits[0].title and "second-missing.md" in hits[0].title


# ---------- images ----------

def test_AC_LINK_10_missing_image_file_reported(journey: Journey) -> None:
    findings = run_check("images", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "img/diagram.png"))
    assert len(hits) == 1
    f = hits[0]
    assert f.category == Category.IMAGE and f.severity == Severity.MAJOR
    assert f.title == "Missing image 'img/diagram.png'"
    assert not _at(findings, "guide/start.md", line_of(start, "![Logo](img/ok.png)"))


def test_AC_LINK_11_image_without_alt_text_is_minor(journey: Journey) -> None:
    findings = run_check("images", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "![](img/ok.png)"))
    assert len(hits) == 1 and hits[0].severity == Severity.MINOR and "alt text" in hits[0].title


def test_AC_LINK_11_html_explicit_empty_alt_is_decorative(journey: Journey) -> None:
    findings = run_check("images", journey)
    index = _page(journey, "ops/index.html")
    hits = _at(findings, "ops/index.html", line_of(index, "decorative.png"))
    assert len(hits) == 1 and hits[0].title == "Missing image 'pics/decorative.png'"


def test_AC_LINK_12_missing_image_without_alt_gives_one_major_finding(journey: Journey) -> None:
    findings = run_check("images", journey)
    start = _page(journey, "guide/start.md")
    hits = _at(findings, "guide/start.md", line_of(start, "img/missing.png"))
    assert len(hits) == 1
    assert hits[0].severity == Severity.MAJOR and "without alt text" in hits[0].title
    assert hits[0].locations[0].quote == "img/missing.png"


def test_AC_LINK_13_external_image_only_checked_for_alt(journey: Journey) -> None:
    findings = run_check("images", journey)
    index = _page(journey, "ops/index.html")
    hits = _at(findings, "ops/index.html", line_of(index, "remote.png"))
    assert len(hits) == 1 and hits[0].severity == Severity.MINOR and "Missing image" not in hits[0].title


# ---------- orphans ----------

def test_AC_LINK_14_unlinked_page_reported_as_orphan(journey: Journey) -> None:
    findings = run_check("orphans", journey)
    ids = {f.locations[0].page_id for f in findings}
    assert {"guide/unused.md", "ops/extra.html"} <= ids
    f = next(f for f in findings if f.locations[0].page_id == "guide/unused.md")
    assert f.category == Category.ORPHAN_PAGE and f.severity == Severity.MINOR
    assert f.locations[0].line_start == 1 and f.locations[0].quote == "Unused page"


def test_AC_LINK_15_entry_pages_are_not_orphans(journey: Journey) -> None:
    ids = {f.locations[0].page_id for f in run_check("orphans", journey)}
    assert "guide/start.md" not in ids  # entry from manual.yaml (nothing links to it except setup.md)
    assert "ops/index.html" not in ids  # index.* when no entry is set


def test_AC_LINK_15_entry_from_manual_yaml_wins_over_index(make_journey: MakeJourney) -> None:
    j = make_journey({"m": {"index.md": "# Index\n\nNo links.\n", "home.md": "# Home\n\nNo links.\n"}},
                     entries={"m": "home.md"})
    ids = {f.locations[0].page_id for f in run_check("orphans", j)}
    assert ids == {"m/index.md"}


def test_AC_LINK_16_links_from_other_manuals_count_but_self_links_do_not(journey: Journey) -> None:
    ids = {f.locations[0].page_id for f in run_check("orphans", journey)}
    assert "ops/run.html" not in ids  # linked only from the guide manual
    assert "guide/setup.md" not in ids
    assert "guide/selfref.md" in ids  # links only to itself


def test_AC_LINK_17_single_page_manual_has_no_orphans(make_journey: MakeJourney) -> None:
    j = make_journey({"solo": {"only.md": "# Only page\n\nText.\n"}})
    assert run_check("orphans", j) == []


def test_AC_LINK_18_all_link_findings_verified_with_original_lines(journey: Journey) -> None:
    for check_id in ("links", "images", "orphans"):
        findings = run_check(check_id, journey)  # run_check asserts verified + unchanged lines
        assert findings
