"""Ordered-list numbering that skips, repeats or goes backwards (spec STRUCT)."""

from __future__ import annotations

import re

from markdown_it import MarkdownIt

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import Quoter, code_lines, location
from umr.domain import Category, Finding, Page, Scope, Severity, Tier

_md = MarkdownIt("commonmark")
_NUMBERED = re.compile(r"^\s*(\d{1,4})[.)]\s+\S")
_HEADING_TAG = re.compile(r"<h[1-6]\b", re.I)

Item = tuple[int, int]  # (number, source line)


def markdown_lists(page: Page) -> list[list[Item]]:
    """Ordered lists of a Markdown page, as written in the source (nested lists separately)."""
    lists: list[list[Item]] = []
    stack: list[list[Item] | None] = []
    for tok in _md.parse(page.source):
        if tok.type == "ordered_list_open":
            stack.append([])
        elif tok.type == "bullet_list_open":
            stack.append(None)
        elif tok.type in ("ordered_list_close", "bullet_list_close"):
            done = stack.pop() if stack else None
            if done is not None:
                lists.append(done)
        elif tok.type == "list_item_open" and stack and stack[-1] is not None and tok.map and tok.info.isdigit():
            stack[-1].append((int(tok.info), tok.map[0] + 1))
    return lists


def text_lists(page: Page) -> list[list[Item]]:
    """Runs of '1. ...' lines in a page's readable text (used for HTML, where numbers are typed as text)."""
    skip = code_lines(page)
    lists: list[list[Item]] = []
    current: list[Item] = []
    for n, (raw, text) in enumerate(zip(page.lines, page.plain_lines, strict=False), 1):
        m = _NUMBERED.match(text)
        if m and n not in skip and not _HEADING_TAG.search(raw):
            current.append((int(m.group(1)), n))
        elif text.strip():
            if current:
                lists.append(current)
            current = []
    if current:
        lists.append(current)
    return lists


@register
class NumberingCheck(Check):
    id = "numbering"
    title = "Step numbering"
    description = ("Numbered steps that skip a number (1, 2, 3, 5), repeat one (1, 2, 3, 3) or go "
                   "backwards. Lists numbered 1, 1, 1 on purpose are accepted.")
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.STEP_ORDER,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        findings: list[Finding] = []
        for page in ctx.journey.pages:
            lists = markdown_lists(page) if page.format == "md" else text_lists(page)
            quoter = Quoter(page)
            for items in lists:
                findings.extend(self._check(page, quoter, items))
        return findings

    @staticmethod
    def _check(page: Page, quoter: Quoter, items: list[Item]) -> list[Finding]:
        numbers = [n for n, _ in items]
        if len(items) < 2 or len(set(numbers)) == 1:
            return []
        out = []
        sequence = ", ".join(str(n) for n in numbers)
        for (prev, _), (cur, line) in zip(items, items[1:], strict=False):
            if cur == prev + 1:
                continue
            if cur == prev:
                title = f"Step number {cur} is used twice"
                explanation = (f"The numbered list ({sequence}) repeats step {cur}. Readers cannot tell "
                               f"whether a step is missing or the steps are out of order.")
                fix = "Renumber the steps consecutively, and check that no step is missing."
                severity = Severity.MINOR
            elif cur > prev + 1:
                missing = ", ".join(str(n) for n in range(prev + 1, cur))
                title = f"Step numbering skips from {prev} to {cur}"
                explanation = (f"The numbered list ({sequence}) jumps from step {prev} to step {cur}; step "
                               f"{missing} is missing. Either a step was deleted without renumbering, or "
                               f"the instructions are incomplete.")
                fix = f"Add the missing step {missing}, or renumber the steps consecutively."
                severity = Severity.MAJOR
            else:
                title = f"Step numbering goes back from {prev} to {cur}"
                explanation = f"The numbered list ({sequence}) goes backwards from step {prev} to step {cur}."
                fix = "Put the steps in order and number them consecutively."
                severity = Severity.MINOR
            quote = quoter.quote(line, [page.plain_lines[line - 1]])
            out.append(Finding(check_id=NumberingCheck.id, category=Category.STEP_ORDER, severity=severity,
                               title=title, explanation=explanation, suggested_fix=fix, source="rule",
                               confidence=1.0, locations=[location(page, line, quote)]))
        return out
