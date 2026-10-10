"""Missing image files and images without alt text (spec LINK, AC-LINK-08..11)."""

from __future__ import annotations

import re
from collections import defaultdict

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import LinkResolver, Quoter, location, max_severity
from umr.checks.rules.links import link_markup
from umr.domain import Category, Finding, Link, Page, Scope, Severity, Tier

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
_ALT_ATTR = re.compile(r"\balt\s*=", re.I)


def _has_explicit_alt(page: Page, link: Link) -> bool:
    """HTML ``alt=""`` marks a decorative image on purpose; only a missing attribute is a problem."""
    if page.format == "md" or not 0 < link.line <= len(page.lines):
        return False
    tags = _IMG_TAG.findall(page.lines[link.line - 1])
    return any(link.target in tag and _ALT_ATTR.search(tag) for tag in tags)


@register
class ImagesCheck(Check):
    id = "images"
    title = "Missing images and alt text"
    description = ("Images whose file does not exist, and images without alternative text. External image "
                   "URLs are not downloaded; only their alt text is checked.")
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.IMAGE,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        resolver = LinkResolver(ctx.journey)
        findings: list[Finding] = []
        for page in ctx.journey.pages:
            quoter = Quoter(page)
            by_line: dict[int, list[tuple[Link, bool, bool]]] = defaultdict(list)
            for link in page.links:
                if not link.is_image:
                    continue
                src = link.target.strip()
                target = resolver.resolve(page, src) if src else None
                missing = not src or (target is not None and not target.exists)
                no_alt = not (link.alt or "").strip() and not _has_explicit_alt(page, link)
                if missing or no_alt:
                    by_line[link.line].append((link, missing, no_alt))
            for line, items in sorted(by_line.items()):
                findings.append(self._finding(page, quoter, line, items))
        return findings

    @staticmethod
    def _finding(page: Page, quoter: Quoter, line: int, items: list[tuple[Link, bool, bool]]) -> Finding:
        titles, explanations, fixes, severities = [], [], [], []
        for link, missing, no_alt in items:
            src = link.target.strip() or "(empty)"
            if missing and no_alt:
                titles.append(f"Missing image '{src}' without alt text")
                explanations.append(f"The image file '{src}' does not exist, so readers see a broken image, "
                                    f"and the image has no alt text to describe what it should show.")
                fixes.append(f"Add the image file '{src}' (or correct the path) and give it alt text that "
                             f"describes what it shows.")
                severities.append(Severity.MAJOR)
            elif missing:
                titles.append(f"Missing image '{src}'")
                explanations.append(f"The image file '{src}' does not exist (resolved relative to "
                                    f"{page.path}), so readers see a broken image.")
                fixes.append(f"Add the image file '{src}' or correct the path.")
                severities.append(Severity.MAJOR)
            else:
                titles.append(f"Image '{src}' has no alt text")
                explanations.append("Screen-reader users, and readers whose images do not load, get no "
                                    "description of this image.")
                fixes.append("Add alt text that describes what the image shows (for example the screen name)"
                             "; use alt=\"\" in HTML only for purely decorative images.")
                severities.append(Severity.MINOR)
        first = items[0][0]
        quote = quoter.quote(line, [link_markup(page, first), first.target])
        return Finding(check_id=ImagesCheck.id, category=Category.IMAGE, severity=max_severity(severities),
                       title="; ".join(titles), explanation=" ".join(explanations),
                       suggested_fix=" ".join(fixes), source="rule", confidence=1.0,
                       locations=[location(page, line, quote)])
