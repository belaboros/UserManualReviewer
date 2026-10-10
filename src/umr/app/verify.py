"""Locate quotes in the source and mark findings verified (ADR-0007)."""

import re

from rapidfuzz import fuzz

from umr.domain import Finding, Journey, Location, Page

FUZZY_THRESHOLD = 90.0
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


def _strip_md(s: str) -> str:
    return re.sub(r"(\*\*|__|`|\[|\]\([^)]*\))", "", s)


def locate_quote(page: Page, quote: str) -> tuple[int, int] | None:
    """Return (line_start, line_end) of the quote in the page, or None."""
    q = _norm(_strip_md(quote))
    if not q:
        return None
    texts = [_norm(t) for t in page.plain_lines]
    raws = [_norm(t) for t in page.lines]
    # exact on single lines (readable text, then raw markup)
    for candidates in (texts, raws):
        for i, t in enumerate(candidates):
            if q in t:
                return i + 1, i + 1
    # exact across a window of lines
    for window in (2, 3, 4, 6):
        for i in range(len(texts) - window + 1):
            joined = " ".join(x for x in texts[i:i + window] if x)
            if q in joined:
                return i + 1, i + window
    # fuzzy: best partial match per line / small windows
    best: tuple[float, int, int] = (0.0, 0, 0)
    for window in (1, 2, 3):
        for i in range(len(texts) - window + 1):
            joined = " ".join(x for x in texts[i:i + window] if x)
            if len(joined) < len(q) * 0.6:
                continue
            score = fuzz.partial_ratio(q, joined)
            if score > best[0]:
                best = (score, i + 1, i + window)
    if best[0] >= FUZZY_THRESHOLD:
        return best[1], best[2]
    return None


def resolve_page(journey: Journey, loc: Location) -> Page | None:
    page = journey.page(loc.page_id)
    if page:
        return page
    # tolerate LLMs giving "manual/path" in page_path or omitting the manual
    path = loc.page_path.strip("/")
    for p in journey.pages:
        if p.page_id == path or p.path == path or p.page_id.endswith("/" + path):
            loc.manual_id, loc.page_path = p.manual_id, p.path
            return p
    return None


def verify_finding(journey: Journey, finding: Finding) -> Finding:
    """Fill in line numbers from quotes; set verified flags."""
    all_ok = True
    for loc in finding.locations:
        page = resolve_page(journey, loc)
        if page is None:
            loc.verified = False
            all_ok = False
            continue
        if loc.quote:
            span = locate_quote(page, loc.quote)
            if span:
                loc.line_start, loc.line_end = span
                loc.verified = True
            else:
                loc.verified = False
                all_ok = False
        else:
            # rule findings may give line numbers without a quote
            loc.verified = loc.line_start is not None
            all_ok = all_ok and loc.verified
    finding.verified = all_ok
    return finding
