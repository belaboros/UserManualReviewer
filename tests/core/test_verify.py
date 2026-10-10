from umr.app.review import ReviewService
from umr.app.verify import verify_finding
from umr.checks import Check, CheckContext
from umr.domain import Category, Finding, Location, Scope, Severity, Tier
from umr.ingest import load_journey

SRC = ("# Guide\n\n## Cancelling\n\nAn order can be cancelled only while it has the status\n"
       "**Submitted**. After that, contact the warehouse.\n\nThe session ends after 15 minutes.\n")


def _journey(make_manual):
    return load_journey(make_manual({"orders.md": SRC}, name="oc"))


def _finding(*locs: Location) -> Finding:
    return Finding(check_id="t", category=Category.INCONSISTENCY, severity=Severity.MINOR, title="t",
                   locations=list(locs))


def test_AC_FIND_01_exact_quote_gets_line(make_manual) -> None:
    f = verify_finding(_journey(make_manual), _finding(Location(manual_id="oc", page_path="orders.md",
                                                               quote="The session ends after 15 minutes")))
    assert f.verified and f.locations[0].line_start == 8 and f.locations[0].verified


def test_AC_FIND_02_quote_across_lines(make_manual) -> None:
    f = verify_finding(_journey(make_manual), _finding(Location(
        manual_id="oc", page_path="orders.md", quote="only while it has the status Submitted. After that")))
    assert f.verified and (f.locations[0].line_start, f.locations[0].line_end) == (5, 6)


def test_AC_FIND_03_normalised_matching(make_manual) -> None:
    f = verify_finding(_journey(make_manual), _finding(Location(
        manual_id="oc", page_path="orders.md", quote="the   status\n**Submitted**")))
    assert f.verified


def test_AC_FIND_04_fuzzy_match(make_manual) -> None:
    f = verify_finding(_journey(make_manual), _finding(Location(
        manual_id="oc", page_path="orders.md", quote="An order can be canceled only while it has the status")))
    assert f.verified and f.locations[0].line_start == 5


def test_AC_FIND_05_invented_quote_unverified(make_manual) -> None:
    f = verify_finding(_journey(make_manual), _finding(Location(
        manual_id="oc", page_path="orders.md", quote="Orders are shipped by drone within one hour")))
    assert not f.verified and not f.locations[0].verified


def test_AC_FIND_06_unknown_page_unverified(make_manual) -> None:
    f = verify_finding(_journey(make_manual), _finding(Location(
        manual_id="oc", page_path="missing.md", quote="The session ends")))
    assert not f.verified


def test_AC_FIND_07_page_without_manual_id_resolved(make_manual) -> None:
    f = verify_finding(_journey(make_manual), _finding(Location(
        manual_id="", page_path="/orders.md", quote="The session ends after 15 minutes")))
    assert f.verified and f.locations[0].manual_id == "oc" and f.locations[0].page_path == "orders.md"


class _Dup(Check):
    id = "dup-test"
    title = description = "dup"
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.INCONSISTENCY,)

    def run(self, ctx: CheckContext) -> list[Finding]:
        loc = Location(manual_id="oc", page_path="orders.md", quote="The session ends after 15 minutes")
        return [_finding(loc.model_copy()), _finding(loc.model_copy())]


def test_AC_FIND_08_duplicates_reported_once(make_manual, monkeypatch) -> None:
    monkeypatch.setattr(ReviewService, "resolve_checks", lambda self, ids, provider: [_Dup])
    run = ReviewService().review(_journey(make_manual))
    assert len(run.findings) == 1 and run.findings[0].id == "F001"
