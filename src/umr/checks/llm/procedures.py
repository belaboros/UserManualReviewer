"""CONSIST (procedures): step-order logic problems within a manual's procedures."""

from __future__ import annotations

from typing import ClassVar

from umr.checks.base import register
from umr.checks.llm.llm_check import LlmCheck
from umr.domain import Category, Scope


@register
class ProceduresCheck(LlmCheck):
    id: ClassVar[str] = "procedures"
    title: ClassVar[str] = "Step order logic"
    description: ClassVar[str] = "Procedures whose steps use something before it exists or come in the wrong order."
    scope: ClassVar[Scope] = Scope.MANUAL
    categories: ClassVar[tuple[Category, ...]] = (Category.STEP_ORDER,)
    task: ClassVar[str] = """\
Find STEP ORDER PROBLEMS in the procedures (numbered or sequential instructions) of THIS ONE MANUAL: \
places where a reader who follows the steps exactly in the written order will fail or do something \
wrong.

Look especially at:
- a step that uses, selects or opens something (a record, customer, file, setting, screen, button, \
permission) that is only created, enabled or explained in a LATER step;
- a warning, check or prerequisite that appears after the action it should precede \
(for example "before you click X, make sure ..." placed after the step that clicks X);
- a step that confirms or saves before the data it needs has been entered;
- steps that refer to the wrong step number ("as in step 5" when step 5 is something else).

Do not report numbering typos, formatting, or optional steps that are clearly marked as optional.
Each finding needs at least one location: quote the step that comes too early (and, if possible, a \
second location quoting the step it depends on). In suggested_fix, give the corrected order."""
