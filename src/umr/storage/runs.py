"""Review runs as JSON files (ADR-0009)."""

import os
import re
from pathlib import Path

from umr.domain import ReviewRun


def default_runs_dir() -> Path:
    return Path(os.environ.get("UMR_RUNS_DIR", Path.home() / ".user-manual-reviewer" / "runs"))


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-").lower() or "x"


class RunStore:
    def __init__(self, root: Path | None = None):
        self.root = root or default_runs_dir()

    def save(self, run: ReviewRun) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        stamp = run.started_at.strftime("%Y%m%d-%H%M%S")
        path = self.root / f"{stamp}-{_safe(run.journey_name)}-{_safe(run.model or 'rules')}-{run.id[:6]}.json"
        path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, path: Path) -> ReviewRun:
        return ReviewRun.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*.json"), reverse=True)
