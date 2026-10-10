"""Pure data model shared by all layers (architecture section 5)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class Severity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


SEVERITY_ORDER = [Severity.INFO, Severity.MINOR, Severity.MAJOR, Severity.CRITICAL]


class Category(StrEnum):
    DUPLICATE = "duplicate"
    BROKEN_LINK = "broken-link"
    BROKEN_ANCHOR = "broken-anchor"
    ORPHAN_PAGE = "orphan-page"
    IMAGE = "image"
    INCONSISTENCY = "inconsistency"
    CONTRADICTION = "contradiction"
    JOURNEY_GAP = "journey-gap"
    TERMINOLOGY = "terminology"
    UI_LABEL = "ui-label"
    PREREQUISITE = "prerequisite"
    STEP_ORDER = "step-order"
    UNDEFINED_TERM = "undefined-term"
    STALE_VERSION = "stale-version"
    VALUE_CONFLICT = "value-conflict"
    MISSING_ERROR_PATH = "missing-error-path"
    MALFORMED_CODE = "malformed-code"


class Tier(StrEnum):
    RULE = "rule"
    LLM = "llm"


class Scope(StrEnum):
    PAGE = "page"
    MANUAL = "manual"
    JOURNEY = "journey"


# ---------- corpus ----------


class Link(BaseModel):
    target: str  # raw href
    text: str = ""
    line: int
    is_image: bool = False
    alt: str | None = None


class CodeBlock(BaseModel):
    language: str = ""
    content: str
    line_start: int
    line_end: int


class Section(BaseModel):
    heading: str
    anchor: str
    level: int
    line_start: int
    line_end: int
    text: str


class Page(BaseModel):
    manual_id: str
    path: str  # relative to the manual root, posix
    abs_path: Path
    format: str  # "md" | "html"
    title: str
    source: str  # original file text
    lines: list[str]  # original file lines (source line numbers are 1-based)
    plain_lines: list[str]  # readable text per source line (markup removed); same length as lines
    sections: list[Section] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)
    code_blocks: list[CodeBlock] = Field(default_factory=list)
    word_count: int = 0

    @property
    def page_id(self) -> str:
        return f"{self.manual_id}/{self.path}"

    @property
    def plain_text(self) -> str:
        return "\n".join(self.plain_lines)


class Manual(BaseModel):
    id: str
    title: str
    version: str | None = None
    entry: str | None = None
    root_path: Path
    pages: list[Page] = Field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(p.word_count for p in self.pages)

    def page(self, path: str) -> Page | None:
        return next((p for p in self.pages if p.path == path), None)


class Journey(BaseModel):
    name: str
    description: str = ""
    root_path: Path
    manuals: list[Manual] = Field(default_factory=list)
    reference: dict[str, Path] = Field(default_factory=dict)

    @property
    def pages(self) -> list[Page]:
        return [p for m in self.manuals for p in m.pages]

    @property
    def word_count(self) -> int:
        return sum(m.word_count for m in self.manuals)

    def manual(self, manual_id: str) -> Manual | None:
        return next((m for m in self.manuals if m.id == manual_id), None)

    def page(self, page_id: str) -> Page | None:
        return next((p for p in self.pages if p.page_id == page_id), None)


# ---------- findings ----------


class Location(BaseModel):
    manual_id: str
    page_path: str
    line_start: int | None = None
    line_end: int | None = None
    quote: str = ""
    verified: bool = False

    @property
    def page_id(self) -> str:
        return f"{self.manual_id}/{self.page_path}"


class Finding(BaseModel):
    id: str = ""
    check_id: str
    category: Category
    severity: Severity
    title: str
    explanation: str = ""
    suggested_fix: str = ""
    locations: list[Location] = Field(default_factory=list)
    source: str = "rule"  # "rule" or provider name
    confidence: float = 1.0
    verified: bool = True

    @property
    def fingerprint(self) -> str:
        locs = sorted(f"{loc.page_id}:{loc.line_start}" for loc in self.locations)
        raw = f"{self.category}|{'|'.join(locs)}|{self.title if not locs else ''}"
        return hashlib.sha1(raw.encode()).hexdigest()[:12]


# ---------- runs ----------


class Score(BaseModel):
    level: Scope
    target: str  # "set", manual id, or page id
    value: float
    penalty: float
    word_count: int
    finding_count: int


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    duration_s: float = 0.0
    calls: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_tokens += other.cached_tokens
        self.cost_usd += other.cost_usd
        self.duration_s += other.duration_s
        self.calls += other.calls


class LlmCallStats(BaseModel):
    """Structured-output reliability of LLM calls (used by the LLM evaluation, ADR-0013)."""

    calls: int = 0
    valid_first_try: int = 0
    retried: int = 0
    failed: int = 0

    def add(self, other: LlmCallStats) -> None:
        self.calls += other.calls
        self.valid_first_try += other.valid_first_try
        self.retried += other.retried
        self.failed += other.failed

    @property
    def valid_output_rate(self) -> float:
        return self.valid_first_try / self.calls if self.calls else 1.0


class CheckError(BaseModel):
    check_id: str
    message: str


class CheckResult(BaseModel):
    check_id: str
    tier: Tier
    findings: list[Finding] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    llm_stats: LlmCallStats = Field(default_factory=LlmCallStats)
    error: str | None = None
    duration_s: float = 0.0


class ReviewRun(BaseModel):
    schema_version: int = SCHEMA_VERSION
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    journey_name: str
    journey_path: str
    checks: list[str]
    model: str | None = None
    scoring: dict[str, object] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    scores: list[Score] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    llm_stats: LlmCallStats = Field(default_factory=LlmCallStats)
    errors: list[CheckError] = Field(default_factory=list)
    check_durations: dict[str, float] = Field(default_factory=dict)

    def score_for(self, target: str) -> Score | None:
        return next((s for s in self.scores if s.target == target), None)
