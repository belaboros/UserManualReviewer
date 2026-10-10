"""The ShopFlow answer key stays in sync with the sample manuals (AC-EVAL-14, ADR-0011)."""

from __future__ import annotations

from pathlib import Path

import pytest

from umr.app.evaluation import AnswerKey
from umr.app.verify import locate_quote
from umr.domain import Journey, Tier
from umr.ingest import load_journey

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "shopflow"


@pytest.fixture(scope="module")
def key() -> AnswerKey:
    return AnswerKey.load(SAMPLES / "expected-findings.yaml")


@pytest.fixture(scope="module")
def journey() -> Journey:
    return load_journey(SAMPLES / "journey.yaml")


def test_AC_EVAL_14_key_loads_with_unique_ids(key: AnswerKey) -> None:
    assert key.version == "1" and key.benchmark == "shopflow"
    ids = [f.id for f in key.findings]
    assert len(ids) == len(set(ids)) == 68  # the distinct mistakes listed in ANSWER_KEY.md
    assert {f.tier for f in key.findings} == {Tier.LLM, Tier.RULE}


def test_AC_EVAL_14_every_entry_has_a_location(key: AnswerKey) -> None:
    assert all(f.locations for f in key.findings)
    assert all(f.category not in f.accept_categories for f in key.findings)


def test_AC_EVAL_14_every_quote_found_in_sample_manuals(key: AnswerKey, journey: Journey) -> None:
    missing = []
    for f in key.findings:
        for loc in f.locations:
            page = journey.page(loc.page)
            if page is None or locate_quote(page, loc.quote) is None:
                missing.append(f"{f.id}: {loc.page}: {loc.quote!r}")
    assert not missing, "quotes not found:\n" + "\n".join(missing)
