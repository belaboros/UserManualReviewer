"""Orphan pages: pages nothing links to (spec LINK, AC-LINK-12..15)."""

from __future__ import annotations

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import LinkResolver, Quoter, location
from umr.domain import Category, Finding, Manual, Page, Scope, Severity, Tier

INDEX_NAMES = ("index.md", "index.markdown", "index.html", "index.htm", "readme.md")


def entry_page(manual: Manual) -> Page | None:
    """The manual's start page: ``entry`` from manual.yaml, else index.* at the root, else the first page."""
    if manual.entry:
        page = manual.page(manual.entry.strip().lstrip("./"))
        if page:
            return page
    for name in INDEX_NAMES:
        page = next((p for p in manual.pages if p.path.lower() == name), None)
        if page:
            return page
    return min(manual.pages, key=lambda p: ("/" in p.path, p.path), default=None)


@register
class OrphansCheck(Check):
    id = "orphans"
    title = "Orphan pages"
    description = ("Pages that no other page in the journey links to and that are not the manual's entry "
                   "page, so readers cannot reach them by navigation.")
    tier = Tier.RULE
    scope = Scope.MANUAL
    categories = (Category.ORPHAN_PAGE,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        resolver = LinkResolver(ctx.journey)
        linked: set[str] = set()
        for page in ctx.journey.pages:
            for link in page.links:
                if link.is_image or not link.target.strip():
                    continue
                target = resolver.resolve(page, link.target)
                if target and target.page is not None and target.page is not page:
                    linked.add(target.page.page_id)
        findings: list[Finding] = []
        for manual in ctx.journey.manuals:
            if len(manual.pages) < 2:
                continue
            entry = entry_page(manual)
            for page in manual.pages:
                if page is entry or page.page_id in linked:
                    continue
                findings.append(self._finding(manual, page, entry))
        return findings

    @staticmethod
    def _finding(manual: Manual, page: Page, entry: Page | None) -> Finding:
        line = next((n for n, t in enumerate(page.plain_lines, 1) if t.strip()), 1)
        quote = Quoter(page).quote(line, [page.title])
        start = f" such as the entry page '{entry.path}'" if entry else ""
        return Finding(
            check_id=OrphansCheck.id, category=Category.ORPHAN_PAGE, severity=Severity.MINOR,
            title=f"Orphan page '{page.path}'",
            explanation=(f"No other page in the journey links to '{page.path}' ({page.title}), and it is not "
                         f"the start page of the manual '{manual.title}'. Readers navigating the manual "
                         f"will not find it; it may also be obsolete."),
            suggested_fix=(f"Link to this page from a related page{start}, or remove the page if it is "
                           f"no longer needed."),
            source="rule", confidence=1.0, locations=[location(page, line, quote)],
        )
