from pathlib import Path

import pytest

from umr.ingest import IngestError, load_journey, load_manual


def test_AC_INGEST_01_journey_loads_manuals_in_order(samples_journey_path: Path) -> None:
    j = load_journey(samples_journey_path)
    assert [m.id for m in j.manuals] == ["order-capturing", "delivery", "notification"]
    assert all(m.pages for m in j.manuals)
    assert j.manual("delivery").version == "3.4"  # type: ignore[union-attr]


def test_AC_INGEST_02_manual_without_yaml_uses_folder_name(make_manual) -> None:
    m = load_manual(make_manual({"a.md": "# A\n"}, name="my-guide"))
    assert (m.id, m.title) == ("my-guide", "my-guide")


def test_AC_INGEST_03_markdown_sections_and_anchors(make_manual) -> None:
    src = "# Title\n\nintro\n\n## 1.2 Logging in\n\ntext\n\n## Logging in\n\nmore\n"
    page = load_manual(make_manual({"p.md": src})).pages[0]
    assert [(s.heading, s.anchor, s.level, s.line_start) for s in page.sections] == [
        ("Title", "title", 1, 1), ("1.2 Logging in", "12-logging-in", 2, 5), ("Logging in", "logging-in", 2, 9)]
    assert page.sections[1].line_end == 8
    assert page.anchors == ["title", "12-logging-in", "logging-in"]


def test_AC_INGEST_03_duplicate_headings_get_suffix(make_manual) -> None:
    page = load_manual(make_manual({"p.md": "## Notes\n\n## Notes\n"})).pages[0]
    assert page.anchors == ["notes", "notes-1"]


def test_AC_INGEST_04_markdown_links_and_images(make_manual) -> None:
    src = "# T\n\nSee [the guide](other.md#x) and\n[more](https://e.com).\n\n![](img/a.png)\n![Alt text](b.png)\n"
    page = load_manual(make_manual({"p.md": src})).pages[0]
    links = [(lk.target, lk.line, lk.is_image, lk.alt) for lk in page.links]
    assert links == [("other.md#x", 3, False, None), ("https://e.com", 4, False, None),
                     ("img/a.png", 6, True, None), ("b.png", 7, True, "Alt text")]


def test_AC_INGEST_05_html_parsing(make_manual) -> None:
    src = ("<!DOCTYPE html>\n<html><head><title>T</title></head>\n<body>\n<h1 id=\"top\">Top</h1>\n"
           "<p>Go <a href=\"b.html#y\">there</a>.</p>\n<img src=\"x.png\">\n<h2>Sub</h2>\n<p>end</p>\n</body></html>\n")
    page = load_manual(make_manual({"a.html": src})).pages[0]
    assert page.title == "Top"
    assert "top" in page.anchors
    assert [(lk.target, lk.line) for lk in page.links if not lk.is_image] == [("b.html#y", 5)]
    assert [(lk.target, lk.line, lk.alt) for lk in page.links if lk.is_image] == [("x.png", 6, None)]
    assert [(s.heading, s.line_start, s.line_end) for s in page.sections] == [("Top", 4, 9), ("Sub", 7, 9)]
    assert page.plain_lines[1] == ""  # <head> is not readable text
    assert page.plain_lines[4] == "Go there ."


def test_AC_INGEST_06_code_blocks_not_counted(make_manual) -> None:
    src = "# T\n\none two\n\n```json\n{\"a\": 1, \"b\": 2, \"c\": 3}\n```\n"
    page = load_manual(make_manual({"p.md": src})).pages[0]
    assert len(page.code_blocks) == 1
    cb = page.code_blocks[0]
    assert (cb.language, cb.line_start, cb.line_end) == ("json", 5, 7)
    assert '"a": 1' in cb.content
    assert page.word_count == 3  # T, one, two


def test_AC_INGEST_07_plain_lines_match_source_lines(samples_journey_path: Path) -> None:
    for page in load_journey(samples_journey_path).pages:
        assert len(page.plain_lines) == len(page.lines)


@pytest.mark.parametrize("problem", ["missing-manual", "missing-ref", "bad-yaml", "dup-id"])
def test_AC_INGEST_08_journey_errors(tmp_path: Path, make_manual, problem: str) -> None:
    make_manual({"a.md": "# A\n"}, name="m1", meta="id: same\ntitle: One\n")
    make_manual({"b.md": "# B\n"}, name="m2", meta="id: same\ntitle: Two\n" if problem == "dup-id" else "title: Two\n")
    body = {
        "missing-manual": "name: J\nmanuals: [m1, nope]\n",
        "missing-ref": "name: J\nmanuals: [m1]\nreference: {ui_strings: ui.json}\n",
        "bad-yaml": "name: J\nmanuals: [m1\n",
        "dup-id": "name: J\nmanuals: [m1, m2]\n",
    }[problem]
    (tmp_path / "journey.yaml").write_text(body)
    with pytest.raises(IngestError) as exc:
        load_journey(tmp_path / "journey.yaml")
    assert str(tmp_path) in str(exc.value)


def test_AC_INGEST_09_single_manual_folder_is_a_journey(make_manual) -> None:
    j = load_journey(make_manual({"a.md": "# A\n"}, name="solo", meta="title: Solo guide\n"))
    assert j.name == "Solo guide" and [m.id for m in j.manuals] == ["solo"]
