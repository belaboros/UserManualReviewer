"""Tests for spec UILABEL: UI labels against ui-strings.json (TEST_SPECS/UILABEL-ui-labels.md)."""

from __future__ import annotations

from pathlib import Path

from umr.checks import CheckRegistry
from umr.checks.rules.ui_labels import load_labels
from umr.domain import Category, Scope, Severity, Tier

from .helpers import MakeJourney, run_check

UI = {
    "_comment": "Not a label",
    "app": {"save": "Save", "submit": "Place Order", "signin": "Sign in", "_hidden": "Secret"},
    "menus": {"templates": "Admin › Notifications › Templates", "prefs": "Preferences"},
    "list": ["Mark as delivered", {"nested": "Load parcel"}],
}


def _md(make_journey: MakeJourney, text: str):
    return run_check("ui-labels", make_journey({"m": {"index.md": text}}, ui_strings=UI))


def test_AC_UILABEL_01_registered_and_only_applies_with_reference(make_journey: MakeJourney) -> None:
    cls = CheckRegistry.get("ui-labels")
    assert cls.tier == Tier.RULE and cls.scope == Scope.PAGE and cls.categories == (Category.UI_LABEL,)
    without = make_journey({"m": {"index.md": "# A\n\nClick **Nope**.\n"}})
    assert not cls().applies_to(without)
    assert run_check("ui-labels", without) == []


def test_AC_UILABEL_02_reference_labels_are_all_string_leaves(tmp_path: Path) -> None:
    import json
    path = tmp_path / "ui.json"
    path.write_text(json.dumps(UI), encoding="utf-8")
    labels = load_labels(path)
    assert set(labels) == {"Save", "Place Order", "Sign in", "Admin › Notifications › Templates", "Preferences",
                           "Mark as delivered", "Load parcel"}


def test_AC_UILABEL_03_unknown_label_after_action_verb_reported(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# A\n\n1. Check the total.\n2. Click **Submit Order**.\n3. Click **Save**.\n")
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == Severity.MAJOR and "'Submit Order'" in f.title
    assert f.locations[0].line_start == 4 and f.locations[0].quote == "**Submit Order**"
    assert "Place Order" in f.suggested_fix


def test_AC_UILABEL_03_verbs_recognised(make_journey: MakeJourney) -> None:
    text = ("# A\n\nSelect **One**.\nPress **Two**.\nTap the **Three** button.\nChoose **Four**.\n"
            "Open **Five**.\nGo to **Six**.\nThen double-click **Seven**.\n")
    findings = _md(make_journey, text)
    assert [f.locations[0].line_start for f in findings] == [3, 4, 5, 6, 7, 8, 9]


def test_AC_UILABEL_04_html_strong_and_b(make_journey: MakeJourney) -> None:
    html = ("<html><body>\n<h1>A</h1>\n<p>Click <strong>Load</strong>. The status becomes <strong>Shipped"
            "</strong>.</p>\n<p>Then click <b>Mark as delivered</b>.</p>\n</body></html>\n")
    findings = run_check("ui-labels", make_journey({"m": {"index.html": html}}, ui_strings=UI))
    assert len(findings) == 1
    assert "'Load'" in findings[0].title and "Did you mean 'Load parcel'?" in findings[0].suggested_fix
    assert findings[0].locations[0].quote == "<strong>Load</strong>"


def test_AC_UILABEL_05_bold_without_action_verb_ignored(make_journey: MakeJourney) -> None:
    text = ("# A\n\nThe **Orders** dashboard opens.\nYou need the **Sales Agent** role.\n"
            "Select the saved delivery address from the **Address book**.\nIf **Unknown** fails, retry.\n")
    assert _md(make_journey, text) == []


def test_AC_UILABEL_06_menu_paths_compared_as_whole_and_by_segment(make_journey: MakeJourney) -> None:
    text = ("# A\n\nGo to **Admin › Notifications › Templates**.\n"
            "Your admin uses **Settings › Notifications › Templates**.\n"
            "Open **Admin** › **Notifications** › **Templates**.\n"
            "Select **Admin > Notifications > Templates**.\n"
            "Select **Preferences › Language**.\n")
    findings = _md(make_journey, text)
    assert [f.locations[0].line_start for f in findings] == [4, 7]
    settings, prefs = findings
    assert "'Settings › Notifications › Templates'" in settings.title
    assert "Unknown menu entries: 'Settings'" in settings.explanation
    assert "'Admin › Notifications › Templates'" in settings.suggested_fix
    assert "'Language'" in prefs.explanation


def test_AC_UILABEL_07_case_only_mismatch_is_minor_with_suggestion(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# A\n\nClick **Sign In**.\n")
    assert len(findings) == 1
    assert findings[0].severity == Severity.MINOR
    assert "Did you mean 'Sign in'?" in findings[0].suggested_fix


def test_AC_UILABEL_08_several_labels_on_one_line_give_one_finding(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, "# A\n\nClick **Foo** or **Bar**, then click **Save**.\n")
    assert len(findings) == 1
    assert "'Foo'" in findings[0].title and "'Bar'" in findings[0].title


def test_AC_UILABEL_09_code_blocks_ignored(make_journey: MakeJourney) -> None:
    assert _md(make_journey, "# A\n\n```\nclick **Nope**\n```\n") == []
