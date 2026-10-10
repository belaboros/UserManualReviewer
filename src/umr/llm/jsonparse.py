"""Tolerant JSON extraction from model text (spec LLM, prompt-only structured output)."""

from __future__ import annotations

import json
import re
from typing import Any

_THINK = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK = re.compile(r"^.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.DOTALL)


def strip_reasoning(text: str) -> str:
    """Remove `<think>...</think>` blocks that reasoning models put before the answer."""
    text = _THINK.sub("", text)
    # a closing tag without an opening one (some servers drop the opening tag)
    if re.search(r"</think(?:ing)?>", text, re.IGNORECASE):
        text = _OPEN_THINK.sub("", text, count=1)
    return text.strip()


def extract_json(text: str) -> Any | None:
    """Return the first JSON object or array in `text`, or None if there is none.

    Handles plain JSON, ```json fences, `<think>` blocks and prose around the JSON.
    """
    if not text:
        return None
    text = strip_reasoning(text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    decoder = json.JSONDecoder()
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except ValueError:
            pass
        for i, ch in enumerate(candidate):
            if ch not in "{[":
                continue
            try:
                value, _ = decoder.raw_decode(candidate, i)
            except ValueError:
                continue
            if isinstance(value, dict | list):
                return value
    return None
