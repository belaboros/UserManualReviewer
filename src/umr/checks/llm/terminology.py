"""TERM: terminology drift and undefined terms."""

from __future__ import annotations

from typing import ClassVar

from umr.checks.base import register
from umr.checks.llm.llm_check import LlmCheck
from umr.domain import Category, Journey, Scope


@register
class TerminologyCheck(LlmCheck):
    id: ClassVar[str] = "terminology"
    title: ClassVar[str] = "Terminology drift and undefined terms"
    description: ClassVar[str] = ("The same concept under different names, and terms or acronyms used "
                                  "without explanation.")
    scope: ClassVar[Scope] = Scope.JOURNEY
    categories: ClassVar[tuple[Category, ...]] = (Category.TERMINOLOGY, Category.UNDEFINED_TERM)
    task: ClassVar[str] = """\
Find TERMINOLOGY PROBLEMS across the manuals shown (and within each of them).

1. "terminology": the same concept (an object, role, status, screen, system, document or action) is \
called by different names, so a reader may think they are different things. Examples of the pattern: \
"client" vs "customer" vs "buyer" for the same party, "dispatch" vs "shipping" for the same step, two \
spellings or abbreviations of the same product or module. Quote one use of EACH variant (one location \
per variant). Do not report true synonyms in ordinary prose that cannot confuse anyone.
2. "undefined-term": a product-specific term, abbreviation or acronym that a reader of the journey must \
understand, but that is never defined or explained anywhere in the manuals shown. Quote its first or \
most important use. Do not report common industry words (e.g. "email", "PDF", "URL", "API") or terms \
defined anywhere in the manuals shown.

In suggested_fix, propose the term to standardise on, or the definition to add and where."""

    def applies_to(self, journey: Journey) -> bool:
        return bool(journey.manuals)
