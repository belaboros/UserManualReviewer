"""Fixture journeys for LLM check tests (small, written to tmp_path)."""

from collections.abc import Callable
from pathlib import Path

import pytest

from umr.domain import Journey
from umr.ingest import load_journey

ORDERS = {
    "index.md": "# Orders\n\nThis manual explains how to capture orders.\n\n\n\nSee [Creating](create.md).\n",
    "create.md": ("# Creating an order\n\n1. Open the Orders dashboard.\n2. Click **New Order**.\n"
                  "3. Select the customer.\n\nAn order can be cancelled while it has the status Paid.\n"),
}
DELIVERY = {
    "index.md": "# Delivery\n\nWarehouse operators pick and pack orders.\n",
    "statuses.md": ("# Statuses\n\nOnce an order is Paid it can no longer be cancelled by the sales agent.\n"
                    "The maximum parcel weight is 30 kg.\n"),
}
NOTIFY = {
    "index.md": "# Notifications\n\nCustomers receive an e-mail when the order ships.\n",
}


def build(tmp_path: Path, manuals: dict[str, dict[str, str]], reference: bool = True) -> Journey:
    n = 1
    while (tmp_path / f"j{n}").exists():
        n += 1
    tmp_path = tmp_path / f"j{n}"
    tmp_path.mkdir()
    lines = ["name: Test journey", "description: Order from capture to delivery.", "manuals:"]
    for mid, pages in manuals.items():
        folder = tmp_path / mid
        folder.mkdir()
        (folder / "manual.yaml").write_text(f"id: {mid}\ntitle: {mid.title()} Manual\nversion: '1.0'\n")
        for name, text in pages.items():
            (folder / name).write_text(text, encoding="utf-8")
        lines.append(f"  - {mid}")
    if reference:
        (tmp_path / "ui.json").write_text('{"oms": {"order.new": "New Order"}}\n', encoding="utf-8")
        lines += ["reference:", "  ui_strings: ui.json"]
    (tmp_path / "journey.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_journey(tmp_path / "journey.yaml")


@pytest.fixture
def make_journey(tmp_path: Path) -> Callable[..., Journey]:
    def make(manuals: dict[str, dict[str, str]] | None = None, reference: bool = True) -> Journey:
        return build(tmp_path, manuals or {"orders": ORDERS, "delivery": DELIVERY}, reference)
    return make


@pytest.fixture
def journey(make_journey: Callable[..., Journey]) -> Journey:
    return make_journey()


@pytest.fixture
def three_manuals(make_journey: Callable[..., Journey]) -> Journey:
    return make_journey({"orders": ORDERS, "delivery": DELIVERY, "notify": NOTIFY})


@pytest.fixture
def single_manual(make_journey: Callable[..., Journey]) -> Journey:
    return make_journey({"orders": ORDERS}, reference=False)
