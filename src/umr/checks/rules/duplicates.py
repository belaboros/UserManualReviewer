"""Near-duplicate sections within and across manuals (spec DUP)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import Quoter, location
from umr.domain import Category, Finding, Page, Scope, Section, Severity, Tier

MIN_WORDS = 20  # sections with a shorter body are ignored
THRESHOLD = 85.0  # rapidfuzz ratio (0-100) on the normalised body text

_PUNCT = re.compile(r"[^\w\s]")


def normalise(text: str) -> str:
    return " ".join(_PUNCT.sub(" ", text.lower()).split())


@dataclass
class _Sec:
    page: Page
    section: Section
    body: str

    def contains(self, other: _Sec) -> bool:
        return (self.page is other.page and self.section.line_start <= other.section.line_start
                and other.section.line_end <= self.section.line_end)


Pair = tuple[_Sec, _Sec, float]


def _sections(pages: list[Page]) -> list[_Sec]:
    out = []
    for page in pages:
        for s in page.sections:
            # the body excludes the heading line, so different headings over the same text still match
            body = normalise("\n".join(page.plain_lines[s.line_start:s.line_end]))
            if len(body.split()) >= MIN_WORDS:
                out.append(_Sec(page, s, body))
    return out


@register
class DuplicatesCheck(Check):
    id = "duplicates"
    title = "Duplicate sections"
    description = (f"Sections whose text is identical or nearly identical (similarity >= {THRESHOLD:.0f}%), "
                   f"on the same page, another page or in another manual. Sections under {MIN_WORDS} words "
                   f"are ignored.")
    tier = Tier.RULE
    scope = Scope.MANUAL
    categories = (Category.DUPLICATE,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        secs = _sections(ctx.journey.pages)
        pairs: list[Pair] = []
        for i, a in enumerate(secs):
            for b in secs[i + 1:]:
                if a.contains(b) or b.contains(a):
                    continue
                la, lb = len(a.body), len(b.body)
                if 200.0 * min(la, lb) / (la + lb) < THRESHOLD:  # upper bound of ratio
                    continue
                score = fuzz.ratio(a.body, b.body)
                if score >= THRESHOLD:
                    pairs.append((a, b, score))
        return [self._finding(a, b, s) for a, b, s in _one_per_group(pairs)]

    @staticmethod
    def _finding(a: _Sec, b: _Sec, score: float) -> Finding:
        identical = a.body == b.body
        kind = "Duplicate" if identical else "Near-duplicate"
        how = "identical text" if identical else f"{score:.0f}% similar text"
        where = "on the same page" if a.page is b.page else (
            "in the same manual" if a.page.manual_id == b.page.manual_id else "in two different manuals")
        locs = []
        for x in (a, b):
            quote = Quoter(x.page).quote(x.section.line_start, [x.section.heading])
            locs.append(location(x.page, x.section.line_start, quote, x.section.line_end))
        return Finding(
            check_id=DuplicatesCheck.id, category=Category.DUPLICATE, severity=Severity.MINOR,
            title=f"{kind} sections: '{a.section.heading}' and '{b.section.heading}'",
            explanation=(f"The section '{a.section.heading}' ({a.page.page_id}) and the section "
                         f"'{b.section.heading}' ({b.page.page_id}) have {how} {where}. Duplicated text "
                         f"drifts apart when only one copy is updated, and readers cannot tell which one "
                         f"is current."),
            suggested_fix=("Keep the content in one place and link to it from the other, or make the "
                           "differences explicit if both are needed."),
            source="rule", confidence=1.0, locations=locs,
        )


def _related(x: Pair, y: Pair) -> bool:
    """One pair contains the other (a parent pair and a child pair of the same duplicated text)."""
    def covers(p: Pair, q: Pair) -> bool:
        return ((p[0].contains(q[0]) and p[1].contains(q[1])) or (p[0].contains(q[1]) and p[1].contains(q[0])))
    return covers(x, y) or covers(y, x)


def _size(pair: Pair) -> int:
    a, b, _ = pair
    return (a.section.line_end - a.section.line_start) + (b.section.line_end - b.section.line_start)


def _one_per_group(pairs: list[Pair]) -> list[Pair]:
    """Parent and child sections of the same duplicated text form one group; report one pair per group:
    the most similar one, and on a tie the outer one (a whole duplicated chapter is one finding)."""
    group = list(range(len(pairs)))

    def find(i: int) -> int:
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i

    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            if _related(pairs[i], pairs[j]):
                group[find(i)] = find(j)
    best: dict[int, Pair] = {}
    for i, pair in enumerate(pairs):
        g = find(i)
        if g not in best or (round(pair[2], 1), _size(pair)) > (round(best[g][2], 1), _size(best[g])):
            best[g] = pair
    return [p for i, p in enumerate(pairs) if best.get(find(i)) is p]
