"""Evaluation results as JSON files, like review runs (ADR-0009, ADR-0013, spec EVAL)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from umr.storage.runs import _safe

if TYPE_CHECKING:
    from umr.app.evaluation import EvalResult


def default_evals_dir() -> Path:
    return Path(os.environ.get("UMR_EVALS_DIR", Path.home() / ".user-manual-reviewer" / "evals"))


class EvalStore:
    def __init__(self, root: Path | None = None):
        self.root = root or default_evals_dir()

    def save(self, result: EvalResult) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        stamp = result.started_at.strftime("%Y%m%d-%H%M%S")
        path = self.root / f"{stamp}-{_safe(result.benchmark)}-{_safe(result.model)}-{result.id[:6]}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, path: Path) -> EvalResult:
        # EvalResult is defined with the EvalService; imported here lazily so storage stays below app.
        from umr.app.evaluation import EvalResult

        return EvalResult.model_validate_json(path.read_text(encoding="utf-8"))

    def paths(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*.json"), reverse=True)

    def load_all(self) -> list[EvalResult]:
        """All readable results, oldest first; unreadable files are skipped."""
        results = []
        for path in self.paths():
            try:
                results.append(self.load(path))
            except (OSError, ValueError, ValidationError):
                continue
        return sorted(results, key=lambda r: r.started_at)
