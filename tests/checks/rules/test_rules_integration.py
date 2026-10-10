"""Integration: all rule checks on the ShopFlow sample journey through ReviewService."""

from __future__ import annotations

from pathlib import Path

import pytest

from umr.app.review import ReviewService
from umr.checks import CheckRegistry
from umr.domain import ReviewRun, Tier
from umr.ingest import load_journey

SAMPLE = Path(__file__).resolve().parents[3] / "samples" / "shopflow" / "journey.yaml"
RULE_CHECKS = ["links", "images", "orphans", "duplicates", "numbering", "code", "ui-labels", "versions"]


@pytest.fixture(scope="module")
def run() -> ReviewRun:
    return ReviewService().review(load_journey(SAMPLE), ["rules"])


def _assert_check_ok(run: ReviewRun, check_ids: list[str]) -> None:
    assert run.errors == []
    for check_id in check_ids:
        assert check_id in run.checks
        findings = [f for f in run.findings if f.check_id == check_id]
        assert findings, f"{check_id} found nothing on the sample"
        for f in findings:
            assert f.source == "rule" and f.verified, f.title
            assert all(loc.verified and loc.quote and loc.line_start for loc in f.locations), f.title


def test_AC_LINK_19_sample_review_link_findings_verified(run: ReviewRun) -> None:
    assert set(RULE_CHECKS) <= set(CheckRegistry.ids(Tier.RULE))
    assert run.findings
    assert all(f.verified for f in run.findings if f.source == "rule")
    _assert_check_ok(run, ["links", "images", "orphans"])


def test_AC_DUP_08_sample_review_duplicate_findings_verified(run: ReviewRun) -> None:
    _assert_check_ok(run, ["duplicates"])


def test_AC_STRUCT_09_sample_review_numbering_findings_verified(run: ReviewRun) -> None:
    _assert_check_ok(run, ["numbering"])


def test_AC_CODE_08_sample_review_code_findings_verified(run: ReviewRun) -> None:
    _assert_check_ok(run, ["code"])


def test_AC_UILABEL_10_sample_review_ui_label_findings_verified(run: ReviewRun) -> None:
    _assert_check_ok(run, ["ui-labels"])


def test_AC_VERSION_09_sample_review_version_findings_verified(run: ReviewRun) -> None:
    _assert_check_ok(run, ["versions"])
