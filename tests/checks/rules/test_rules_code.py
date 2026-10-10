"""Tests for spec CODE: malformed code blocks (TEST_SPECS/CODE-malformed-code.md)."""

from __future__ import annotations

from umr.checks import CheckRegistry
from umr.domain import Category, Scope, Severity, Tier

from .helpers import MakeJourney, run_check


def _md(make_journey: MakeJourney, text: str):
    return run_check("code", make_journey({"m": {"index.md": text}}))


def test_AC_CODE_01_registered_as_page_scope_rule_check() -> None:
    cls = CheckRegistry.get("code")
    assert cls.tier == Tier.RULE and cls.scope == Scope.PAGE and cls.categories == (Category.MALFORMED_CODE,)


def test_AC_CODE_02_invalid_json_reported_at_error_line(make_journey: MakeJourney) -> None:
    text = '# Config\n\n```json\n{\n  "smtp": {\n    "port": 587,\n  }\n}\n```\n'
    findings = _md(make_journey, text)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == Severity.MAJOR and f.title == "Malformed JSON code block"
    assert "trailing comma" in f.explanation
    assert f.locations[0].line_start == 7  # the closing brace after the trailing comma


def test_AC_CODE_02_valid_json_not_reported(make_journey: MakeJourney) -> None:
    assert _md(make_journey, '# C\n\n```json\n{"a": [1, 2], "b": {"c": null}}\n```\n') == []


def test_AC_CODE_03_unlabelled_block_starting_with_brace_is_json(make_journey: MakeJourney) -> None:
    findings = _md(make_journey, '# C\n\n```\n[1, 2\n```\n\n```\n{ "elided": ... }\n```\n\n```\nplain text\n```\n')
    assert len(findings) == 1 and findings[0].locations[0].line_start in (4, 5)


def test_AC_CODE_04_invalid_yaml_reported(make_journey: MakeJourney) -> None:
    text = "# C\n\n```yaml\nserver:\n  host: example.com\n port: 25\n```\n\n```yml\nok: [1, 2]\n```\n"
    findings = _md(make_journey, text)
    assert len(findings) == 1
    f = findings[0]
    assert f.title == "Malformed YAML code block"
    assert 4 <= f.locations[0].line_start <= 6


def test_AC_CODE_05_csv_rows_with_wrong_column_count(make_journey: MakeJourney) -> None:
    text = ("# Import\n\n```csv\ncustomer_id;sku;quantity;postal_code\nC-1;S-1;2;1051\nC-2;S-2;1\n"
            "C-3;S-3;5;1132;express\n```\n")
    findings = _md(make_journey, text)
    assert len(findings) == 1
    f = findings[0]
    assert f.title == "CSV rows do not match the header's 4 columns"
    assert "semicolon" in f.explanation
    assert [loc.line_start for loc in f.locations] == [6, 7]


def test_AC_CODE_05_csv_delimiters_and_quotes(make_journey: MakeJourney) -> None:
    text = ('# C\n\n```csv\nname,city\n"Smith, J.",Paris\nDoe,Rome\n```\n\n'
            '```tsv\na\tb\n1\t2\n```\n\n```csv\na\tb\tc\n1\t2\n```\n')
    findings = _md(make_journey, text)
    assert len(findings) == 1 and "tab" in findings[0].explanation
    assert findings[0].locations[0].line_start == 16


def test_AC_CODE_06_templates_and_other_languages_skipped(make_journey: MakeJourney) -> None:
    text = ('# C\n\n```json\n{"name": {{ name }}}\n```\n\n```python\n{"a": 1,}\n```\n\n'
            '```\nHello {{customer}},\n```\n')
    assert _md(make_journey, text) == []


def test_AC_CODE_07_html_code_block_checked(make_journey: MakeJourney) -> None:
    html = ('<html><body>\n<h1>Config</h1>\n<pre><code class="language-json">{\n  "a": 1\n  "b": 2\n}'
            '</code></pre>\n</body></html>\n')
    findings = run_check("code", make_journey({"m": {"index.html": html}}))
    assert len(findings) == 1
    assert "missing comma" in findings[0].explanation
    assert findings[0].locations[0].line_start == 5
