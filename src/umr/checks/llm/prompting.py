"""Prompt building shared by all LLM checks (architecture section 9, spec PROMPT).

The corpus block is rendered identically for every check of a run and always comes first, so providers
can cache it; the check instruction comes after it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from umr.domain import Category, Finding, Journey, Location, Manual, Page, Severity

PROMPT_VERSION = "1"
REFERENCE_EXTENSIONS = {".json", ".yaml", ".yml", ".txt", ".md", ".csv"}
MAX_REFERENCE_CHARS = 100_000

SYSTEM_PROMPT = """\
You are an expert reviewer of technical documentation and user manuals. You review a set of related \
manuals that together describe one end-to-end user journey, and you report problems a real reader would \
hit: statements that cannot both be true, values that disagree, steps or hand-offs nobody documents, \
names that change, terms that are never explained.

Rules for every answer:
- Report only real problems that are supported by the text. Do not report style preferences, grammar, \
missing marketing detail, or things that are merely phrased differently but mean the same.
- Every finding needs at least one location. Each location has:
  - "page": the exact page id as written in the page header, e.g. "manual-id/path/to/page.md" \
(the part after "=== PAGE " up to the first space).
  - "quote": 5 to 25 consecutive words copied EXACTLY, character for character, from that page's text. \
Never paraphrase, translate, shorten with "...", merge sentences, or invent a quote. A quote that cannot \
be found in the page is discarded.
- Use only the categories listed in the task. Severity: "critical" = a reader following the manual will \
fail or cause damage; "major" = a reader is likely to do the wrong thing or get stuck; "minor" = confusing \
but recoverable; "info" = worth tidying.
- "confidence" is your probability (0 to 1) that the problem is real.
- Write title, explanation and suggested_fix in the language of the manuals; keep the title under 15 words.
- One finding per distinct problem; do not repeat the same problem with different wording.
- If you find nothing, return {"findings": []}.
"""

# ---------- response schema (shared by all checks, so the schema never breaks the prompt cache) ----------

_SEVERITY_SYNONYMS = {
    "blocker": "critical", "fatal": "critical", "severe": "critical",
    "high": "major", "error": "major", "important": "major",
    "medium": "minor", "moderate": "minor", "low": "minor", "warning": "minor", "warn": "minor",
    "trivial": "info", "note": "info", "suggestion": "info", "information": "info", "informational": "info",
}


class LlmLocation(BaseModel):
    page: str = Field(description="Page id exactly as in the page header: <manual_id>/<page_path>")
    quote: str = Field(default="", description="5-25 words copied verbatim from the page text")


class LlmFinding(BaseModel):
    category: str = Field(description="One of the categories listed in the task")
    severity: Literal["critical", "major", "minor", "info"]
    title: str
    explanation: str = ""
    suggested_fix: str = ""
    confidence: float = Field(default=0.7, ge=0, le=1)
    locations: list[LlmLocation] = Field(default_factory=list)

    @field_validator("severity", mode="before")
    @classmethod
    def _severity(cls, v: Any) -> Any:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"critical", "major", "minor", "info"}:
                return s
            return _SEVERITY_SYNONYMS.get(s, "minor")
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v: Any) -> Any:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.7
        if f > 1 and f <= 100:  # a percentage
            f /= 100
        return min(max(f, 0.0), 1.0)

    @field_validator("explanation", "suggested_fix", "title", mode="before")
    @classmethod
    def _text(cls, v: Any) -> Any:
        return "" if v is None else v


class FindingsResponse(BaseModel):
    findings: list[LlmFinding] = Field(default_factory=list)


# ---------- corpus ----------


_MD_STRUCTURE = re.compile(r"^\s{0,3}(#{1,6}|[-*+]|\d+[.)])\s+")


def _page_text(page: Page) -> str:
    """Readable text of a page, with runs of empty lines collapsed.

    Markdown heading markers and list markers (including step numbers) are kept, so the model sees
    the structure and the order of steps.
    """
    out: list[str] = []
    blank = False
    for raw, line in zip(page.lines, page.plain_lines, strict=False):
        if line.strip():
            m = _MD_STRUCTURE.match(raw) if page.format == "md" else None
            out.append(f"{m.group(1)} {line.strip()}" if m else line.rstrip())
            blank = False
        elif out and not blank:
            out.append("")
            blank = True
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def page_header(page: Page, manual: Manual | None) -> str:
    title = manual.title if manual else page.manual_id
    version = (manual.version if manual else None) or "unspecified"
    return f"=== PAGE {page.page_id} (manual: {title}, version {version}) ==="


def _reference_block(journey: Journey) -> list[str]:
    parts: list[str] = []
    for key in sorted(journey.reference):
        path = journey.reference[key]
        if path.suffix.lower() not in REFERENCE_EXTENSIONS or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if len(text) > MAX_REFERENCE_CHARS:
            continue
        parts.append(f"=== REFERENCE {key}: {path.name} (ground truth, not part of the manuals) ===")
        parts.append(text.strip())
        parts.append("")
    return parts


def render_corpus(journey: Journey, manuals: Sequence[Manual] | None = None,
                  pages: Sequence[Page] | None = None, include_reference: bool = True) -> str:
    """Deterministic text block with the journey header, reference files and the pages.

    `manuals` limits the block to those manuals; `pages` limits it further to those pages (used by the
    context-budget fallback). The same arguments always give byte-identical output.
    """
    selected = list(manuals) if manuals is not None else list(journey.manuals)
    wanted: set[str] | None = None
    if pages is not None:
        wanted = {p.page_id for p in pages}
        ids = {p.manual_id for p in pages}
        selected = [m for m in selected if m.id in ids]
    lines = [f"JOURNEY: {journey.name}"]
    if journey.description.strip():
        lines.append(f"DESCRIPTION: {' '.join(journey.description.split())}")
    lines.append("MANUALS:")
    for m in selected:
        lines.append(f"- {m.id}: {m.title} (version {m.version or 'unspecified'}, {len(m.pages)} pages)")
    lines.append("")
    if include_reference:
        lines.extend(_reference_block(journey))
    for m in selected:
        for page in m.pages:
            if wanted is not None and page.page_id not in wanted:
                continue
            lines.append(page_header(page, m))
            lines.append(_page_text(page))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_instruction(task: str, categories: Sequence[Category], *, scope_note: str = "") -> str:
    cats = "\n".join(f"- {c.value}" for c in categories)
    parts = ["TASK", task.strip(), "", "Allowed categories (use the value exactly):", cats]
    if scope_note:
        parts += ["", scope_note]
    parts += ["", 'Return JSON: {"findings": [{"category", "severity", "title", "explanation", '
              '"suggested_fix", "confidence", "locations": [{"page", "quote"}]}]}.']
    return "\n".join(parts)


# ---------- response -> domain findings ----------

_CAT_NORM = re.compile(r"[\s_]+")


def map_category(value: str, allowed: Sequence[Category]) -> Category:
    """Category for a model-supplied value; anything unknown or not allowed maps to the first allowed one."""
    key = _CAT_NORM.sub("-", value.strip().lower())
    for c in allowed:
        if key in (c.value, c.name.lower().replace("_", "-")):
            return c
    return allowed[0]


def split_page_id(journey: Journey, page: str) -> tuple[str, str]:
    """(manual_id, page_path) for a model-supplied page id."""
    p = page.strip().strip("`'\"")
    p = re.sub(r"^(=+\s*)?PAGE\s+", "", p, flags=re.IGNORECASE)
    p = p.split(" (manual:")[0].strip().strip("/")
    if journey.page(p):
        return p.split("/", 1)[0], p.split("/", 1)[1]
    # longest manual id that prefixes the value (manual ids may contain '/': unlikely, but be exact)
    for m in sorted(journey.manuals, key=lambda m: -len(m.id)):
        if p.startswith(m.id + "/"):
            return m.id, p[len(m.id) + 1:]
    if "/" in p:
        a, b = p.split("/", 1)
        return a, b
    return "", p


def to_findings(response: FindingsResponse, *, check_id: str, categories: Sequence[Category],
                source: str, journey: Journey) -> list[Finding]:
    out: list[Finding] = []
    for f in response.findings:
        locations = []
        for loc in f.locations:
            if not loc.page.strip():
                continue
            manual_id, page_path = split_page_id(journey, loc.page)
            locations.append(Location(manual_id=manual_id, page_path=page_path, quote=loc.quote.strip()))
        out.append(Finding(check_id=check_id, category=map_category(f.category, categories),
                           severity=Severity(f.severity), title=f.title.strip() or "Untitled finding",
                           explanation=f.explanation.strip(), suggested_fix=f.suggested_fix.strip(),
                           locations=locations, source=source, confidence=f.confidence, verified=False))
    return out
