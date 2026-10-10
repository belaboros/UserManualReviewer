"""Helpers for the rule-check tests: build tiny journeys, run one check, verify its findings."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import yaml

from umr.app.verify import verify_finding
from umr.checks import CheckContext, CheckRegistry
from umr.domain import Finding, Journey, Page
from umr.ingest import load_journey

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "rules"
MakeJourney = Callable[..., Journey]


def run_check(check_id: str, journey: Journey) -> list[Finding]:
    """Run one check like ReviewService does, including quote verification."""
    check = CheckRegistry.get(check_id)()
    findings = check.run(CheckContext(journey=journey))
    expected_lines = [[loc.line_start for loc in f.locations] for f in findings]
    for f, lines in zip(findings, expected_lines, strict=True):
        verify_finding(journey, f)
        assert f.verified, f"unverified finding: {f.title} {f.locations}"
        # the chosen quote must resolve back to the line the check meant
        assert [loc.line_start for loc in f.locations] == lines, f.title
        assert f.source == "rule" and f.confidence == 1.0
        assert f.check_id == check_id and f.category in check.categories
        assert f.title and f.explanation and f.suggested_fix
    return findings


def line_of(page: Page, text: str, nth: int = 1) -> int:
    hits = [n for n, line in enumerate(page.lines, 1) if text in line]
    assert len(hits) >= nth, f"{text!r} not in {page.path}"
    return hits[nth - 1]


def build_journey(tmp_path: Path) -> MakeJourney:
    def make(manuals: dict[str, dict[str, str]], *, versions: dict[str, str] | None = None,
             titles: dict[str, str] | None = None, entries: dict[str, str] | None = None,
             ui_strings: object | None = None, name: str = "Test journey") -> Journey:
        for mid, files in manuals.items():
            folder = tmp_path / mid
            folder.mkdir(parents=True, exist_ok=True)
            meta: dict[str, str] = {"id": mid, "title": (titles or {}).get(mid, f"Acme {mid}")}
            if versions and mid in versions:
                meta["version"] = versions[mid]
            if entries and mid in entries:
                meta["entry"] = entries[mid]
            (folder / "manual.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
            for rel, content in files.items():
                path = folder / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
        journey: dict[str, object] = {"name": name, "manuals": list(manuals)}
        if ui_strings is not None:
            (tmp_path / "ui-strings.json").write_text(json.dumps(ui_strings), encoding="utf-8")
            journey["reference"] = {"ui_strings": "ui-strings.json"}
        (tmp_path / "journey.yaml").write_text(yaml.safe_dump(journey), encoding="utf-8")
        return load_journey(tmp_path / "journey.yaml")

    return make
