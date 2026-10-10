"""Helpers shared by the rule checks: quotes that verify, link resolution, anchors."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from umr.domain import Journey, Location, Page, Severity

# ---------- quotes ----------
# Quote verification (app/verify.py) locates a quote by its *first* exact occurrence in the page. The checks
# layer must not import the app layer, so the exact-match part of that logic is mirrored here; it lets a
# check pick a quote that resolves back to the line it means, not to an earlier line with the same text.

_WS = re.compile(r"\s+")
_MD_STRIP = re.compile(r"(\*\*|__|`|\[|\]\([^)]*\))")


def _norm(s: str) -> str:
    return _WS.sub(" ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


class Quoter:
    """Chooses short verbatim quotes that verification maps back to the intended line."""

    def __init__(self, page: Page):
        self.page = page
        self._texts = [_norm(t) for t in page.plain_lines]
        self._raws = [_norm(t) for t in page.lines]

    def span(self, quote: str) -> tuple[int, int] | None:
        q = _norm(_MD_STRIP.sub("", quote))
        if not q:
            return None
        for candidates in (self._texts, self._raws):
            for i, t in enumerate(candidates):
                if q in t:
                    return i + 1, i + 1
        for window in (2, 3, 4, 6):
            for i in range(len(self._texts) - window + 1):
                if q in " ".join(x for x in self._texts[i:i + window] if x):
                    return i + 1, i + window
        return None

    def quote(self, line: int, candidates: Iterable[str] = ()) -> str:
        """Return the first candidate (then the line's own text) whose quote resolves to ``line``.

        Returns "" when no text on the line is unique enough; verification then keeps the check's own
        line numbers instead of moving the finding to an earlier line with the same text.
        """
        page = self.page
        plain = page.plain_lines[line - 1].strip() if 0 < line <= len(page.plain_lines) else ""
        raw = page.lines[line - 1].strip() if 0 < line <= len(page.lines) else ""
        tries = [c.strip() for c in candidates if c and c.strip()] + [plain, raw]
        # widen with neighbouring lines when the line's text is not unique on the page
        for before, after in ((0, 1), (0, 2), (0, 3)):
            lo, hi = max(1, line - before), min(len(page.plain_lines), line + after)
            joined = "\n".join(t.strip() for t in page.plain_lines[lo - 1:hi] if t.strip())
            tries.append(joined)
        for cand in tries:
            if len(_norm(_MD_STRIP.sub("", cand))) < 3:  # e.g. "![](x.png)" strips down to "!"
                continue
            span = self.span(cand)
            if span and span[0] == line:
                return cand
        return ""


def location(page: Page, line: int, quote: str, line_end: int | None = None) -> Location:
    return Location(manual_id=page.manual_id, page_path=page.path, line_start=line,
                    line_end=line_end or line, quote=quote)


def clip(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def max_severity(severities: Iterable[Severity]) -> Severity:
    order = [Severity.INFO, Severity.MINOR, Severity.MAJOR, Severity.CRITICAL]
    return max(severities, key=order.index)


def code_lines(page: Page) -> set[int]:
    """Source line numbers inside code blocks (fences included)."""
    out: set[int] = set()
    for cb in page.code_blocks:
        out.update(range(cb.line_start, cb.line_end + 1))
    return out


# ---------- links ----------

_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_ID_ATTR = re.compile(r"""\b(?:id|name)\s*=\s*["']([^"']+)["']""")


def is_external(href: str) -> bool:
    href = href.strip()
    return bool(_SCHEME.match(href)) or href.startswith("//")


@dataclass
class Target:
    href: str
    path: Path | None  # resolved file path; None for an in-page link
    fragment: str
    page: Page | None  # the journey page the link points to, if any

    @property
    def exists(self) -> bool:
        return self.path is None or self.path.exists()


class LinkResolver:
    """Resolves relative hrefs against a page, across all manuals of the journey."""

    def __init__(self, journey: Journey):
        self.journey = journey
        self._by_path = {os.path.normpath(str(p.abs_path)): p for p in journey.pages}
        self._manual_roots = {m.id: m.root_path for m in journey.manuals}
        self._anchors: dict[str, set[str]] = {}

    def resolve(self, page: Page, href: str) -> Target | None:
        """None for external links (http, mailto, ...)."""
        href = href.strip()
        if is_external(href):
            return None
        path_part, _, fragment = href.partition("#")
        path_part = unquote(path_part.split("?", 1)[0])
        fragment = unquote(fragment)
        if not path_part:
            return Target(href=href, path=None, fragment=fragment, page=page)
        if path_part.startswith("/"):  # root-relative: relative to the manual root
            base = self._manual_roots.get(page.manual_id, page.abs_path.parent)
            path_part = path_part.lstrip("/")
        else:
            base = page.abs_path.parent
        resolved = Path(os.path.normpath(str(base / path_part)))
        return Target(href=href, path=resolved, fragment=fragment, page=self._by_path.get(str(resolved)))

    def anchors(self, page: Page) -> set[str]:
        if page.page_id not in self._anchors:
            found = set(page.anchors) | {"top"}
            for line in page.lines:
                found.update(_ID_ATTR.findall(line))
            self._anchors[page.page_id] = found
        return self._anchors[page.page_id]

    def href_to(self, page: Page, path: Path) -> str:
        return Path(os.path.relpath(path, page.abs_path.parent)).as_posix()


def slug(text: str) -> str:
    s = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return s.replace(" ", "-")


def strip_number_prefix(anchor: str) -> str:
    """'12-logging-in' -> 'logging-in' (GitHub slugs of numbered headings)."""
    return re.sub(r"^\d+(?:-\d+)*-", "", anchor)
