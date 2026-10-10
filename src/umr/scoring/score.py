"""Quality score (ADR-0008): 100 × e^(−density / k)."""

import math
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from umr.domain import Finding, Journey, Scope, Score, Severity


class ScoringConfig(BaseModel):
    severity_weights: dict[Severity, float] = Field(default_factory=lambda: {
        Severity.CRITICAL: 10.0, Severity.MAJOR: 5.0, Severity.MINOR: 2.0, Severity.INFO: 0.5})
    k: float = 20.0
    min_words: int = 300

    @classmethod
    def load(cls, path: Path | None) -> "ScoringConfig":
        if path and path.exists():
            return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        return cls()


def score_value(penalty: float, words: int, cfg: ScoringConfig) -> float:
    density = penalty / max(words, cfg.min_words) * 1000
    return 100.0 * math.exp(-density / cfg.k)


def score_run(journey: Journey, findings: list[Finding], cfg: ScoringConfig) -> list[Score]:
    counted = [f for f in findings if f.verified]
    w = cfg.severity_weights

    def make(level: Scope, target: str, words: int, fs: list[Finding]) -> Score:
        penalty = sum(w[f.severity] for f in fs)
        return Score(level=level, target=target, value=round(score_value(penalty, words, cfg), 1),
                     penalty=penalty, word_count=words, finding_count=len(fs))

    scores = [make(Scope.JOURNEY, "set", journey.word_count, counted)]
    for m in journey.manuals:
        fs = [f for f in counted if any(loc.manual_id == m.id for loc in f.locations)]
        scores.append(make(Scope.MANUAL, m.id, m.word_count, fs))
        for p in m.pages:
            pfs = [f for f in counted if any(loc.page_id == p.page_id for loc in f.locations)]
            scores.append(make(Scope.PAGE, p.page_id, p.word_count, pfs))
    return scores
