"""Product version claims that differ from the manual's version (spec VERSION)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import Quoter, code_lines, location
from umr.domain import Category, Finding, Journey, Manual, Page, Scope, Severity, Tier

_VER = r"(?P<ver>\d+(?:\.(?:\d+|x|X|\*))+)"
_GENERIC = [
    re.compile(r"(?<![\w.])(?:(?P<before>\w+)\s+)?version\s+" + _VER + r"(?P<after>\+?)", re.I),
    re.compile(r"(?<![\w./-])v" + _VER + r"(?P<after>\+?)"),
]
# Words that put a version into a historical, future or range context: not a claim about the current version.
_CONTEXT = re.compile(
    r"\b(?:removed|deprecated|introduced|added|new|changed|since|before|prior|earlier|older|previous|"
    r"previously|legacy|planned|upcoming|future|will|until|after|later|newer|upgrad\w*|migrat\w*|"
    r"replaced|no\s+longer|starting|onwards|from|as\s+of|up\s+to|above|below|minimum|at\s+least|"
    r"requires?|required|compatible|supported|unsupported|released|release\s+notes|was|were|used\s+to)\b",
    re.I,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {"the", "a", "an", "user", "users", "manual", "guide", "for", "and", "of", "to", "in"}


def product_names(journey: Journey) -> set[str]:
    """Product names guessed from the first word of each manual title and of the journey name."""
    names = set()
    for title in [m.title for m in journey.manuals] + [journey.name]:
        words = title.split()
        if words and words[0][:1].isupper() and words[0].lower() not in _STOPWORDS and len(words[0]) > 2:
            names.add(words[0].strip(",.:;"))
    return names


def _parts(version: str) -> list[str]:
    return version.lower().strip().lstrip("v").split(".")


def same_version(mentioned: str, manual_version: str) -> bool:
    """'3.4' matches '3.4' and '3.4.1' (a patch release of the same version)."""
    a, b = _parts(mentioned), _parts(manual_version)
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in _parts(version) if p.isdigit())


@dataclass
class Mention:
    version: str
    line: int
    text: str  # the matched phrase, e.g. "ShopFlow 3.2"


def find_claims(page: Page, products: set[str]) -> list[Mention]:
    """Bare version claims: '<Product> X.Y', 'version X.Y', 'vX.Y' outside code and outside context words."""
    patterns = list(_GENERIC)
    if products:
        names = "|".join(re.escape(p) for p in sorted(products, key=len, reverse=True))
        patterns.insert(0, re.compile(r"\b(?:" + names + r")\s+" + _VER + r"(?P<after>\+?)"))
    skip = code_lines(page)
    found: list[Mention] = []
    for n, text in enumerate(page.plain_lines, 1):
        if n in skip or not text.strip():
            continue
        for sentence in _SENTENCE.split(text):
            if _CONTEXT.search(sentence):
                continue
            seen: set[tuple[int, int]] = set()
            for pat in patterns:
                for m in pat.finditer(sentence):
                    version = m.group("ver")
                    if m.group("after") or "x" in version.lower() or "*" in version:
                        continue  # "3.2+" is a minimum, "2.x" a version range
                    before = m.groupdict().get("before")
                    if before and before[:1].isupper() and before not in products:
                        continue  # "Python version 3.12": another product's version
                    span = m.span("ver")
                    if any(s[0] <= span[0] < s[1] for s in seen):
                        continue
                    seen.add(span)
                    found.append(Mention(version=version, line=n, text=m.group(0).strip()))
    return found


@register
class VersionsCheck(Check):
    id = "versions"
    title = "Stale version mentions"
    description = ("Statements such as 'this chapter describes ShopFlow 3.2' that name a different product "
                   "version than the manual's version in manual.yaml. Mentions in a historical, future or "
                   "range context ('removed in 3.0', 'planned for 4.0', '2.x', '3.2+') are ignored.")
    tier = Tier.RULE
    scope = Scope.MANUAL
    categories = (Category.STALE_VERSION,)

    def applies_to(self, journey: Journey) -> bool:
        return any(m.version for m in journey.manuals)

    def run(self, ctx: CheckContext) -> list[Finding]:
        products = product_names(ctx.journey)
        findings: list[Finding] = []
        for manual in ctx.journey.manuals:
            if not manual.version:
                continue
            for page in manual.pages:
                quoter = Quoter(page)
                by_line: dict[int, list[Mention]] = defaultdict(list)
                for mention in find_claims(page, products):
                    if not same_version(mention.version, manual.version):
                        by_line[mention.line].append(mention)
                for line, mentions in sorted(by_line.items()):
                    findings.append(self._finding(manual, page, quoter, line, mentions))
        return findings

    @staticmethod
    def _finding(manual: Manual, page: Page, quoter: Quoter, line: int, mentions: list[Mention]) -> Finding:
        assert manual.version is not None
        current = _key(manual.version)
        older = all(_key(m.version) < current for m in mentions)
        phrases = ", ".join(f"'{m.text}'" for m in mentions)
        what = "an older" if older else "a different"
        return Finding(
            check_id=VersionsCheck.id, category=Category.STALE_VERSION, severity=Severity.MINOR,
            title=f"Version mention {phrases} differs from the manual version {manual.version}",
            explanation=(f"The manual '{manual.title}' is for version {manual.version}, but this text claims "
                         f"{what} version ({phrases}). The passage may be out of date, or the version "
                         f"reference was not updated."),
            suggested_fix=(f"Check the passage against version {manual.version} and update it, or change the "
                           f"version to {manual.version} if the content is still correct."),
            source="rule", confidence=1.0, locations=[location(page, line, quoter.quote(line, [mentions[0].text]))],
        )
