"""CONTRA: statements in different manuals that cannot both be true."""

from __future__ import annotations

from typing import ClassVar

from umr.checks.base import register
from umr.checks.llm.llm_check import LlmCheck
from umr.domain import Category, Finding, Scope


@register
class ContradictionsCheck(LlmCheck):
    id: ClassVar[str] = "contradictions"
    title: ClassVar[str] = "Contradictions between manuals"
    description: ClassVar[str] = "Statements in different manuals that cannot both be true."
    scope: ClassVar[Scope] = Scope.JOURNEY
    categories: ClassVar[tuple[Category, ...]] = (Category.CONTRADICTION, Category.VALUE_CONFLICT)
    task: ClassVar[str] = """\
Find CONTRADICTIONS BETWEEN DIFFERENT MANUALS: pairs (or groups) of statements in two or more manuals \
that cannot both be true for the same product, so a reader who reads both does not know which to believe.

Compare the manuals systematically, topic by topic. Look especially at:
- statuses and state transitions: names, order, which states exist, what triggers a transition, \
which states are final, in which states an action (cancel, edit, return) is still allowed;
- who may do what: roles, permissions, approvals;
- timings and deadlines: when something happens, how long it takes, cut-off times, retries, expiry;
- limits and values: quantities, sizes, amounts, ports, counts, defaults;
- flows and hand-offs: which system or team does a step, what event is sent, in which order;
- channels and notifications: which channels exist, when a message is sent, opt-in/opt-out rules;
- features one manual describes as available and another as removed, replaced or not supported.

Rules:
- Each finding MUST have at least two locations in DIFFERENT manuals, one quote per conflicting statement.
- Use "value-conflict" when the only difference is a value (number, duration, limit, name of a setting); \
use "contradiction" when the statements conflict in meaning (flow, rule, permission, availability).
- Do not report a difference when one manual is simply more detailed, or when the statements apply to \
clearly different situations, roles or versions.
- In the explanation, state both claims and why they cannot both hold; in suggested_fix, say which \
manual(s) to align (without inventing which one is correct if the text does not tell)."""

    def accept(self, finding: Finding) -> bool:
        return len({loc.manual_id for loc in finding.locations}) >= 2
