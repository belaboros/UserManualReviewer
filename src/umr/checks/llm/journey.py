"""JOURNEY: gaps in the end-to-end journey across manuals."""

from __future__ import annotations

from typing import ClassVar

from umr.checks.base import register
from umr.checks.llm.llm_check import LlmCheck
from umr.domain import Category, Scope


@register
class JourneyCheck(LlmCheck):
    id: ClassVar[str] = "journey"
    title: ClassVar[str] = "Journey gaps"
    description: ClassVar[str] = ("Undocumented hand-offs and steps, events or states nobody covers, missing "
                                  "error and recovery paths, prerequisites never explained.")
    scope: ClassVar[Scope] = Scope.JOURNEY
    categories: ClassVar[tuple[Category, ...]] = (Category.JOURNEY_GAP, Category.PREREQUISITE,
                                                  Category.MISSING_ERROR_PATH)
    task: ClassVar[str] = """\
Walk through the END-TO-END JOURNEY described at the top (from its first step to its last), as a reader \
who must complete it using only these manuals. Find the places where that reader gets stuck because \
something is missing.

Look especially at:
- hand-offs between manuals or systems that no manual documents: one manual ends with "the order is \
passed to X" or "you will be notified", and no manual describes what X does or how the notification \
works ("journey-gap");
- events, messages, statuses or states that one manual promises or mentions, but that no manual \
defines, produces, handles or owns ("journey-gap");
- steps in the middle of the journey that no manual describes at all ("journey-gap");
- prerequisites a reader needs (a role or permission, a device, an add-on or licence, an account, \
a configuration, data that must exist) that are required somewhere but nowhere explain how to obtain \
or set up ("prerequisite");
- error and recovery paths that are missing: what to do when a step fails, is rejected, times out, or \
must be undone, where the journey obviously can fail ("missing-error-path").

Rules:
- Report only gaps that matter for completing the journey; do not ask for more detail on things that are \
adequately covered.
- Each finding needs at least one location. Quote the sentence that creates the expectation or shows \
the gap (for example the sentence that mentions the event, the hand-off or the requirement). Use the \
explanation to say what is missing and which manual should cover it.
- Do not report contradictions between manuals; another check covers those."""
