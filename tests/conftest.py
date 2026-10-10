import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "samples" / "shopflow"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never write runs or evals into the real home folder during tests."""
    base = tmp_path_factory.mktemp("umr-home")
    monkeypatch.setenv("UMR_RUNS_DIR", str(base / "runs"))
    monkeypatch.setenv("UMR_EVALS_DIR", str(base / "evals"))


@pytest.fixture
def make_manual(tmp_path: Path):
    """Create a manual folder from {relative path: content}; returns the folder."""

    def _make(files: dict[str, str], name: str = "man", meta: str | None = None, root: Path | None = None) -> Path:
        folder = (root or tmp_path) / name
        for rel, content in files.items():
            p = folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        if meta is not None:
            (folder / "manual.yaml").write_text(meta, encoding="utf-8")
        return folder

    return _make


@pytest.fixture
def samples_journey_path() -> Path:
    return SAMPLES / "journey.yaml"
