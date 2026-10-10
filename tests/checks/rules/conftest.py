"""Fixtures for the rule-check tests."""

from pathlib import Path

import pytest

from .helpers import MakeJourney, build_journey


@pytest.fixture
def make_journey(tmp_path: Path) -> MakeJourney:
    """make_journey({"man-a": {"index.md": "..."}}, versions={"man-a": "3.4"}, ui_strings={...})"""
    return build_journey(tmp_path)
