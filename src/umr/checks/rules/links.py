"""Broken relative links and anchors (spec LINK, AC-LINK-01..07)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz import fuzz, process, utils

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import (
    LinkResolver,
    Quoter,
    Target,
    clip,
    location,
    slug,
    strip_number_prefix,
)
from umr.domain import Category, Finding, Link, Page, Scope, Severity, Tier


def link_markup(page: Page, link: Link) -> str:
    """The link's own markup on its source line, e.g. ``[Text](x.md)`` or ``<a href="x.html">``."""
    if not 0 < link.line <= len(page.lines):
        return ""
    raw = page.lines[link.line - 1]
    target = re.escape(link.target)
    if page.format == "md":
        m = re.search(r"!?\[[^\]]*\]\(\s*<?" + target + r">?(?:\s+[\"'][^)]*)?\)", raw)
    else:
        m = re.search(r"<(?:a|img)\b[^>]*?(?:href|src)\s*=\s*[\"']?" + target + r"[\"']?[^>]*>", raw, re.I)
    return m.group(0) if m else ""


@dataclass
class _Issue:
    category: Category
    severity: Severity
    title: str
    explanation: str
    fix: str


@register
class LinksCheck(Check):
    id = "links"
    title = "Broken links and anchors"
    description = ("Relative links to files that do not exist, and #anchors that do not exist on the "
                   "target page. Links into other manuals of the journey are followed; http(s), mailto and "
                   "other external links are ignored.")
    tier = Tier.RULE
    scope = Scope.MANUAL
    categories = (Category.BROKEN_LINK, Category.BROKEN_ANCHOR)

    def run(self, ctx: CheckContext) -> list[Finding]:
        resolver = LinkResolver(ctx.journey)
        findings: list[Finding] = []
        for page in ctx.journey.pages:
            quoter = Quoter(page)
            grouped: dict[tuple[int, Category], list[tuple[Link, _Issue]]] = defaultdict(list)
            for link in page.links:
                if link.is_image:
                    continue
                issue = self._check_link(resolver, page, link)
                if issue:
                    grouped[(link.line, issue.category)].append((link, issue))
            for (line, _cat), items in sorted(grouped.items(), key=lambda kv: kv[0][0]):
                findings.append(self._finding(page, quoter, line, items))
        return findings

    def _check_link(self, resolver: LinkResolver, page: Page, link: Link) -> _Issue | None:
        href = link.target.strip()
        label = f"'{clip(link.text, 50)}' " if link.text.strip() else ""
        if not href:
            return _Issue(Category.BROKEN_LINK, Severity.MAJOR, "Link has an empty target",
                          f"The link {label}has no target, so it leads nowhere.",
                          "Add the page or URL the link should point to, or remove the link.")
        if href == "#":
            return None  # placeholder / script link
        target = resolver.resolve(page, href)
        if target is None:
            return None
        if not target.exists:
            return self._missing_file(resolver, page, link, target, label)
        if target.fragment:
            return self._check_anchor(resolver, page, link, target, label)
        return None

    def _missing_file(self, resolver: LinkResolver, page: Page, link: Link, target: Target,
                      label: str) -> _Issue:
        assert target.path is not None
        fix = "Create the missing page, or correct or remove the link."
        folder = target.path.parent
        if folder.is_dir():
            names = [p.name for p in folder.iterdir() if p.is_file()]
            best = process.extractOne(target.path.name, names, scorer=fuzz.ratio,
                                      processor=utils.default_process, score_cutoff=75)
            if best:
                suggestion = resolver.href_to(page, folder / best[0])
                if target.fragment:
                    suggestion += "#" + target.fragment
                fix = f"Did you mean '{suggestion}'? Change the link target to the existing file."
        return _Issue(Category.BROKEN_LINK, Severity.MAJOR, f"Broken link to '{link.target}'",
                      f"The link {label}points to '{link.target}', but no such file exists "
                      f"(resolved relative to {page.path}).", fix)

    def _check_anchor(self, resolver: LinkResolver, page: Page, link: Link, target: Target,
                      label: str) -> _Issue | None:
        tpage = target.page
        if tpage is None:
            return None  # an existing non-manual file (PDF, image, ...): anchors cannot be checked
        anchors = resolver.anchors(tpage)
        frag = target.fragment
        if frag in anchors:
            return None
        where = "this page" if tpage is page else f"'{tpage.manual_id}/{tpage.path}'"
        return _Issue(Category.BROKEN_ANCHOR, Severity.MINOR, f"Broken anchor '#{frag}'",
                      f"The link {label}points to '#{frag}' on {where}, but that page has no heading or "
                      f"element with this anchor. The reader lands at the top of the page instead of "
                      f"the intended section.", self._anchor_fix(tpage, frag, anchors))

    @staticmethod
    def _anchor_fix(tpage: Page, frag: str, anchors: set[str]) -> str:
        lowered = {a.lower(): a for a in anchors}
        if frag.lower() in lowered:
            return f"Anchors are case-sensitive: use '#{lowered[frag.lower()]}'."
        choices = {a: strip_number_prefix(a) for a in anchors if a != "top"}
        best = process.extractOne(strip_number_prefix(frag), choices, scorer=fuzz.WRatio, score_cutoff=80)
        if best:
            return f"Did you mean '#{best[2]}'? Change the link to an existing anchor."
        if tpage.format != "md":
            unnamed = {s.heading: strip_number_prefix(slug(s.heading)) for s in tpage.sections if not s.anchor}
            hit = process.extractOne(frag, unnamed, scorer=fuzz.WRatio, score_cutoff=80)
            if hit:
                return (f"The heading '{hit[2]}' has no id. Add id=\"{frag}\" to that heading, or link to "
                        f"the page without the anchor.")
        return "Point the link to an existing heading anchor, or add the missing section."

    @staticmethod
    def _finding(page: Page, quoter: Quoter, line: int, items: list[tuple[Link, _Issue]]) -> Finding:
        first_link, first = items[0]
        markups = [link_markup(page, lk) for lk, _ in items]
        quote = quoter.quote(line, [markups[0], first_link.target])
        if len(items) == 1:
            title, explanation, fix = first.title, first.explanation, first.fix
        else:
            targets = ", ".join(f"'{lk.target}'" for lk, _ in items)
            title = f"{len(items)} broken {'anchors' if first.category == Category.BROKEN_ANCHOR else 'links'}" \
                    f" on one line: {clip(targets, 70)}"
            explanation = " ".join(i.explanation for _, i in items)
            fix = " ".join(i.fix for _, i in items)
        severity = Severity.MAJOR if any(i.severity == Severity.MAJOR for _, i in items) else first.severity
        return Finding(check_id=LinksCheck.id, category=first.category, severity=severity, title=title,
                       explanation=explanation, suggested_fix=fix, source="rule", confidence=1.0,
                       locations=[location(page, line, quote)])
