"""CONSIST: inconsistencies within one manual."""

from __future__ import annotations

from typing import ClassVar

from umr.checks.base import register
from umr.checks.llm.llm_check import LlmCheck
from umr.domain import Category, Scope


@register
class ConsistencyCheck(LlmCheck):
    id: ClassVar[str] = "consistency"
    title: ClassVar[str] = "Inconsistencies within a manual"
    description: ClassVar[str] = ("Values, names, formats, commands and versions that disagree within one "
                                  "manual, and references to features the manual says no longer exist.")
    scope: ClassVar[Scope] = Scope.MANUAL
    categories: ClassVar[tuple[Category, ...]] = (Category.INCONSISTENCY, Category.VALUE_CONFLICT,
                                                  Category.STALE_VERSION, Category.UI_LABEL,
                                                  Category.MALFORMED_CODE)
    task: ClassVar[str] = """\
Find INCONSISTENCIES WITHIN THIS ONE MANUAL: places where the manual disagrees with itself, so a reader \
who reads one page and then another gets two different answers.

Look especially at:
- values given more than once: limits, sizes, timeouts, ports, URLs, file paths, default settings, \
counts, durations, prices ("value-conflict");
- the same UI element, menu path, button or screen named differently on different pages, or a label \
that differs from the reference UI strings if a REFERENCE block is given ("ui-label");
- the same role, object, status or setting named differently ("inconsistency");
- identifiers, codes and formats that change (order number formats, date formats, field names, \
event names) ("inconsistency");
- commands, code samples or configuration snippets that conflict with each other or with the text that \
describes them, template variables used in examples but not in the documented list (or the reverse), \
and code blocks that are syntactically broken ("malformed-code");
- references to features, channels, screens or settings that the same manual elsewhere says were \
removed, replaced or are legacy; product versions, release dates or "new in" notes that disagree or are \
clearly outdated relative to the manual's own version ("stale-version").

Rules:
- Each finding needs a location for every conflicting statement (usually two or more quotes, on the same \
or different pages of this manual). A malformed code block or a stale reference may have one location.
- Do not report differences between this manual and other manuals; only within this manual \
(the REFERENCE block, if present, counts as ground truth for UI labels).
- In suggested_fix, say what to align and where."""
