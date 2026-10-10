"""Match findings between two runs or against an answer key (ADR-0010, ADR-0013)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz

from umr.domain import Location

QUOTE_SIMILARITY = 0.8


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _page_level(loc: Location) -> bool:
    return loc.line_start is None and not loc.quote.strip()


def locations_match(a: Location, b: Location, quote_similarity: float = QUOTE_SIMILARITY) -> bool:
    if a.page_id != b.page_id:
        return False
    if _page_level(a) or _page_level(b):  # e.g. an orphan page: the location is the whole page
        return True
    if (a.line_start is not None and b.line_start is not None):
        a_end = a.line_end or a.line_start
        b_end = b.line_end or b.line_start
        if a.line_start <= b_end and b.line_start <= a_end:
            return True
    if a.quote and b.quote:
        qa, qb = _norm(a.quote), _norm(b.quote)
        if qa in qb or qb in qa:
            return True
        return fuzz.partial_ratio(qa, qb) / 100.0 >= quote_similarity
    return False


def location_overlap(a: Sequence[Location], b: Sequence[Location],
                     quote_similarity: float = QUOTE_SIMILARITY) -> int:
    """Number of locations in `b` matched by some location in `a`."""
    return sum(1 for lb in b if any(locations_match(la, lb, quote_similarity) for la in a))


def findings_match(a_locs: Sequence[Location], b_locs: Sequence[Location],
                   quote_similarity: float = QUOTE_SIMILARITY) -> bool:
    if not a_locs or not b_locs:
        return False
    needed = 2 if len(a_locs) >= 2 and len(b_locs) >= 2 else 1
    return location_overlap(a_locs, b_locs, quote_similarity) >= needed


@dataclass
class Pairing:
    pairs: list[tuple[int, int]]
    only_a: list[int]
    only_b: list[int]


def pair_items(a: Sequence[tuple[str, Sequence[Location]]], b: Sequence[tuple[str, Sequence[Location]]],
               same_category: bool = True, quote_similarity: float = QUOTE_SIMILARITY) -> Pairing:
    """Greedy one-to-one pairing. Items are (category, locations)."""
    used_b: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for i, (cat_a, locs_a) in enumerate(a):
        best_j, best_score = -1, 0
        for j, (cat_b, locs_b) in enumerate(b):
            if j in used_b or (same_category and cat_a != cat_b):
                continue
            if findings_match(locs_a, locs_b, quote_similarity):
                score = location_overlap(locs_a, locs_b, quote_similarity)
                if score > best_score:
                    best_j, best_score = j, score
        if best_j >= 0:
            used_b.add(best_j)
            pairs.append((i, best_j))
    paired_a = {i for i, _ in pairs}
    return Pairing(pairs=pairs, only_a=[i for i in range(len(a)) if i not in paired_a],
                   only_b=[j for j in range(len(b)) if j not in used_b])


def pair_best(a: Sequence[Sequence[Location]], b: Sequence[Sequence[Location]],
              allowed: Callable[[int, int], bool] | None = None,
              preferred: Callable[[int, int], int] | None = None,
              quote_similarity: float = QUOTE_SIMILARITY) -> Pairing:
    """Globally greedy one-to-one pairing of location lists.

    Every matching pair (`findings_match`) is a candidate; candidates are taken in order of
    location overlap (higher first), then higher `preferred` rank (e.g. 2 = same category, 1 = accepted
    category), then input order.
    `allowed` filters candidates (e.g. same category only).
    """
    candidates: list[tuple[int, int, int, int]] = []
    for i, locs_a in enumerate(a):
        for j, locs_b in enumerate(b):
            if allowed is not None and not allowed(i, j):
                continue
            if findings_match(locs_a, locs_b, quote_similarity):
                score = min(location_overlap(locs_a, locs_b, quote_similarity),
                            location_overlap(locs_b, locs_a, quote_similarity))
                pref = preferred(i, j) if preferred is not None else 0
                candidates.append((-score, -pref, i, j))
    candidates.sort()
    used_a: set[int] = set()
    used_b: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, _, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        pairs.append((i, j))
    pairs.sort()
    return Pairing(pairs=pairs, only_a=[i for i in range(len(a)) if i not in used_a],
                   only_b=[j for j in range(len(b)) if j not in used_b])
