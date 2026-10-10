"""Fixtures for the GUI tests: an isolated main window with stub checks, fake providers and temp stores."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui_helpers import DEFAULT_STUBS, FakeEvalService, StubReviewService  # noqa: E402
from PySide6.QtCore import QSettings, QThreadPool  # noqa: E402

from umr.checks import Check  # noqa: E402
from umr.gui.integrations import ProviderCatalog  # noqa: E402
from umr.gui.main_window import MainWindow  # noqa: E402
from umr.llm.fake import FakeProvider  # noqa: E402
from umr.storage import RunStore  # noqa: E402
from umr.storage.evals import EvalStore  # noqa: E402


@pytest.fixture
def make_window(qtbot: Any, tmp_path: Path) -> Callable[..., MainWindow]:
    def factory(stubs: list[type[Check]] | None = None, providers: ProviderCatalog | None = None,
                **kwargs: Any) -> MainWindow:
        stubs = DEFAULT_STUBS if stubs is None else stubs
        eval_store = EvalStore(tmp_path / "evals")
        catalog = providers if providers is not None else ProviderCatalog.from_providers(
            {"fake-a": FakeProvider(name="fake-a"), "fake-b": FakeProvider(name="fake-b")})
        options: dict[str, Any] = {
            "settings": QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
            "run_store": RunStore(tmp_path / "runs"),
            "review_service": StubReviewService(stubs),
            "providers": catalog,
            "check_classes": lambda: list(stubs),
            "eval_service": FakeEvalService(eval_store),
            "eval_store": eval_store,
            "pool": QThreadPool(),
        }
        options.update(kwargs)
        window = MainWindow(**options)
        window.dialogs_enabled = False
        qtbot.addWidget(window)
        return window

    return factory


@pytest.fixture
def window(make_window: Callable[..., MainWindow]) -> MainWindow:
    return make_window()
