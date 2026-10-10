import math
from pathlib import Path

from umr.domain import Category, Finding, Journey, Location, Manual, Page, Severity
from umr.scoring import ScoringConfig, score_run, score_value


def _page(manual: str, path: str, words: int) -> Page:
    return Page(manual_id=manual, path=path, abs_path=Path(path), format="md", title=path, source="",
                lines=[], plain_lines=[], word_count=words)


def _journey() -> Journey:
    return Journey(name="J", root_path=Path("."), manuals=[
        Manual(id="a", title="A", root_path=Path("a"), pages=[_page("a", "p.md", 1000), _page("a", "q.md", 100)]),
        Manual(id="b", title="B", root_path=Path("b"), pages=[_page("b", "r.md", 1000)]),
    ])


def _f(sev: Severity, *pages: str, verified: bool = True) -> Finding:
    locs = [Location(manual_id=p.split("/")[0], page_path=p.split("/")[1], line_start=1) for p in pages]
    return Finding(check_id="t", category=Category.CONTRADICTION, severity=sev, title="t", locations=locs,
                   verified=verified)


def test_AC_SCORE_01_no_findings_is_100() -> None:
    assert all(s.value == 100.0 for s in score_run(_journey(), [], ScoringConfig()))


def test_AC_SCORE_02_one_major_on_1000_words() -> None:
    scores = {s.target: s.value for s in score_run(_journey(), [_f(Severity.MAJOR, "a/p.md")], ScoringConfig())}
    assert scores["a/p.md"] == 77.9


def test_AC_SCORE_03_monotonic_and_positive() -> None:
    cfg = ScoringConfig()
    values = [score_value(p, 1000, cfg) for p in (0, 2, 5, 10, 50, 500, 5000)]
    assert all(a > b for a, b in zip(values, values[1:], strict=False))
    assert values[-1] >= 0
    assert math.isclose(score_value(20, 1000, cfg), 100 * math.exp(-1))


def test_AC_SCORE_04_min_words_floor() -> None:
    cfg = ScoringConfig()
    assert score_value(5, 100, cfg) == score_value(5, 300, cfg)


def test_AC_SCORE_05_cross_manual_finding_counts_in_both() -> None:
    scores = {s.target: s for s in score_run(_journey(), [_f(Severity.MAJOR, "a/p.md", "b/r.md")], ScoringConfig())}
    assert scores["a"].value < 100 and scores["b"].value < 100 and scores["set"].value < 100
    assert scores["a/q.md"].value == 100
    assert scores["set"].finding_count == 1


def test_AC_SCORE_06_unverified_ignored() -> None:
    scores = score_run(_journey(), [_f(Severity.CRITICAL, "a/p.md", verified=False)], ScoringConfig())
    assert all(s.value == 100.0 for s in scores)


def test_AC_SCORE_07_config_file(tmp_path: Path) -> None:
    p = tmp_path / "s.yaml"
    p.write_text("severity_weights: {critical: 1, major: 1, minor: 1, info: 1}\nk: 1\nmin_words: 10\n")
    cfg = ScoringConfig.load(p)
    assert cfg.k == 1 and cfg.min_words == 10
    assert math.isclose(score_value(1, 1000, cfg), 100 * math.exp(-1))
    assert ScoringConfig.load(Path("config/scoring.yaml")).k == 20
