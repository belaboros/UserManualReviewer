"""Tests for spec VERSION: stale version mentions (TEST_SPECS/VERSION-stale-versions.md)."""

from __future__ import annotations

from umr.checks import CheckRegistry
from umr.domain import Category, Scope, Severity, Tier

from .helpers import MakeJourney, run_check


def _md(make_journey: MakeJourney, text: str, version: str | None = "3.4"):
    versions = {"m": version} if version else None
    j = make_journey({"m": {"index.md": text}}, versions=versions, titles={"m": "Acme Ordering"})
    return run_check("versions", j)


def test_AC_VERSION_01_registered_and_applies_only_with_versions(make_journey: MakeJourney) -> None:
    cls = CheckRegistry.get("versions")
    assert cls.tier == Tier.RULE and cls.scope == Scope.MANUAL and cls.categories == (Category.STALE_VERSION,)
    j = make_journey({"m": {"index.md": "# A\n\nAcme 3.2.\n"}})
    assert not cls().applies_to(j)


def test_AC_VERSION_02_product_version_claim_differs(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# A\n\nThis chapter describes the order flow in Acme 3.2.\n")
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == Severity.MINOR and "'Acme 3.2'" in f.title and "3.4" in f.title
    assert "older version" in f.explanation
    assert f.locations[0].line_start == 3 and f.locations[0].quote == "Acme 3.2"


def test_AC_VERSION_03_version_and_v_patterns(make_journey: MakeJourney) -> None:
    text = "# A\n\nThis guide covers version 3.1 of the tool.\n\nThe screenshots show v4.0.\n\nSee v3.4 too.\n"
    findings = _md(make_journey, text)
    assert [f.locations[0].line_start for f in findings] == [3, 5]
    assert "different version" in findings[1].explanation


def test_AC_VERSION_04_matching_versions_not_reported(make_journey: MakeJourney) -> None:
    text = "# A\n\nVersion: Acme 3.4 · Audience: agents\n\nAcme 3.4.2 fixes a bug.\n\nThis is version 3.4.\n"
    assert _md(make_journey, text) == []


def test_AC_VERSION_05_historical_future_and_range_context_ignored(make_journey: MakeJourney) -> None:
    text = ("# A\n\nClassic screens were removed in Acme 3.0.\n\nSMS is planned for Acme 4.0.\n\n"
            "Acme 2.x sent SMS through a gateway.\n\nRequires Acme 3.2+.\n\nSince version 3.1 this works.\n\n"
            "Upgrade from Acme 3.3 first.\n")
    assert _md(make_journey, text) == []


def test_AC_VERSION_06_other_products_and_code_ignored(make_journey: MakeJourney) -> None:
    text = ("# A\n\nUse Chrome 120 or Python version 3.12 to run it.\n\n```\nacme 3.2 --help\nversion 3.2\n```\n"
            "\nThe API path is /api/v1.2/orders.\n")
    assert _md(make_journey, text) == []


def test_AC_VERSION_07_manual_without_version_not_checked(make_journey: MakeJourney) -> None:
    j = make_journey({"a": {"index.md": "# A\n\nAcme 3.2 is described here.\n"},
                      "b": {"index.md": "# B\n\nAcme 3.2 is described here.\n"}},
                     versions={"b": "3.4"}, titles={"a": "Acme A", "b": "Acme B"})
    findings = run_check("versions", j)
    assert [f.locations[0].manual_id for f in findings] == ["b"]


def test_AC_VERSION_08_several_mentions_on_one_line_give_one_finding(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# A\n\nThis page shows Acme 3.1 and Acme 3.2 screens.\n")
    assert len(findings) == 1 and "'Acme 3.1'" in findings[0].title and "'Acme 3.2'" in findings[0].title
