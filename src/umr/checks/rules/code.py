"""Malformed JSON, YAML and CSV code blocks (spec CODE)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass

import yaml

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import Quoter, location
from umr.domain import Category, CodeBlock, Finding, Location, Page, Scope, Severity, Tier

JSON_LANGS = {"json"}
YAML_LANGS = {"yaml", "yml"}
CSV_LANGS = {"csv": None, "tsv": "\t"}
_TEMPLATE_MARKS = ("{{", "{%", "<%")
_MAX_ROW_LOCATIONS = 5


@dataclass
class _Error:
    line: int  # 1-based line within the block content
    message: str


def _first_line_offset(page: Page, block: CodeBlock) -> int:
    """Source line of the block's first content line, minus one."""
    if page.format == "md" and 0 < block.line_start <= len(page.lines):
        opener = page.lines[block.line_start - 1].lstrip()
        if opener.startswith(("```", "~~~")):
            return block.line_start
    return block.line_start - 1


def detect_kind(block: CodeBlock) -> str | None:
    lang = block.language.strip().lower()
    content = block.content
    if any(m in content for m in _TEMPLATE_MARKS):
        return None  # templating placeholders are not meant to parse
    if lang in JSON_LANGS:
        return "json"
    if lang in YAML_LANGS:
        return "yaml"
    if lang in CSV_LANGS:
        return lang
    if not lang and content.lstrip().startswith(("{", "[")) and "..." not in content and "…" not in content:
        return "json"
    return None


def json_error(content: str) -> _Error | None:
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        lines = content.splitlines()
        hint = ""
        if e.msg.startswith("Expecting property name") or e.msg.startswith("Expecting value"):
            before = "\n".join(lines[: e.lineno - 1]) + "\n" + lines[e.lineno - 1][: e.colno - 1]
            if before.rstrip().endswith(","):
                hint = " (probably a trailing comma before a closing bracket)"
        elif e.msg.startswith("Expecting ',' delimiter"):
            hint = " (probably a missing comma)"
        return _Error(e.lineno, f"{e.msg}{hint} at line {e.lineno}, column {e.colno} of the block")
    return None


def yaml_error(content: str) -> _Error | None:
    try:
        for _ in yaml.safe_load_all(content):
            pass
    except yaml.MarkedYAMLError as e:
        mark = e.problem_mark or e.context_mark
        line = mark.line + 1 if mark else 1
        problem = e.problem or e.context or "invalid YAML"
        return _Error(line, f"{problem} at line {line} of the block")
    except yaml.YAMLError as e:
        return _Error(1, str(e).splitlines()[0])
    return None


def csv_errors(content: str, delimiter: str | None) -> tuple[str, int, list[tuple[int, int]]]:
    """Return (delimiter, header column count, [(block line, column count)] of rows that differ)."""
    raw_lines = content.splitlines()
    numbered = [(n, line) for n, line in enumerate(raw_lines, 1) if line.strip()]
    if not numbered:
        return ",", 0, []
    header = numbered[0][1]
    if delimiter is None:
        delimiter = max((",", ";", "\t", "|"), key=header.count)
    rows = [(n, next(csv.reader([line], delimiter=delimiter))) for n, line in numbered]
    width = len(rows[0][1])
    if width < 2:
        return delimiter, width, []
    return delimiter, width, [(n, len(cells)) for n, cells in rows[1:] if len(cells) != width]


_DELIM_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}


@register
class CodeCheck(Check):
    id = "code"
    title = "Malformed code blocks"
    description = ("JSON code blocks that do not parse, YAML blocks that do not parse and CSV blocks whose "
                   "rows have a different number of columns than the header.")
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.MALFORMED_CODE,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        findings: list[Finding] = []
        for page in ctx.journey.pages:
            quoter = Quoter(page)
            for block in page.code_blocks:
                finding = self._check(page, quoter, block)
                if finding:
                    findings.append(finding)
        return findings

    def _check(self, page: Page, quoter: Quoter, block: CodeBlock) -> Finding | None:
        kind = detect_kind(block)
        if kind is None or not block.content.strip():
            return None
        offset = _first_line_offset(page, block)
        if kind in ("json", "yaml"):
            err = json_error(block.content) if kind == "json" else yaml_error(block.content)
            if err is None:
                return None
            line = min(max(offset + err.line, block.line_start), block.line_end)
            label = kind.upper()
            return self._finding(
                page, [location(page, line, quoter.quote(line))],
                f"Malformed {label} code block", Severity.MAJOR,
                (f"The {label} example starting at line {block.line_start} does not parse: {err.message}. "
                 f"Readers who copy it get an error."),
                f"Fix the {label} syntax so the example can be copied and used as it is.")
        delimiter, width, bad = csv_errors(block.content, CSV_LANGS[kind])
        if not bad:
            return None
        rows = ", ".join(f"line {offset + n} has {cols}" for n, cols in bad)
        locs = [location(page, offset + n, quoter.quote(offset + n)) for n, _ in bad[:_MAX_ROW_LOCATIONS]]
        return self._finding(
            page, locs, f"CSV rows do not match the header's {width} columns", Severity.MAJOR,
            (f"The CSV example's header has {width} {_DELIM_NAMES.get(delimiter, repr(delimiter))}-separated "
             f"columns, but {rows}. An import of this file would fail or shift values into the wrong "
             f"columns."),
            f"Give every row exactly {width} columns (use an empty value for optional fields).")

    @staticmethod
    def _finding(page: Page, locs: list[Location], title: str, severity: Severity, explanation: str,
                 fix: str) -> Finding:
        return Finding(check_id=CodeCheck.id, category=Category.MALFORMED_CODE, severity=severity, title=title,
                       explanation=explanation, suggested_fix=fix, source="rule", confidence=1.0,
                       locations=locs)
