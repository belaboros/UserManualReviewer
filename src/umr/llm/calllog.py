"""Log every LLM request and response (spec LLM, AC-LLM-22..26).

Two outputs:
- a one-line summary per request and per response on the `umr.llm` Python logger (INFO), which the CLI
  prints with `--verbose` and the GUI shows in its run log;
- the full request body and the full response (or error, including the HTTP response body) as one JSON
  object per line in `~/.user-manual-reviewer/logs/llm-calls-YYYY-MM-DD.jsonl` (or `$UMR_LOG_DIR`).

API keys are never logged: requests are logged as bodies, without headers.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("umr.llm")

_lock = threading.Lock()
_REDACT_KEYS = {"api_key", "authorization", "x-api-key"}


def log_dir() -> Path:
    return Path(os.environ.get("UMR_LOG_DIR", Path.home() / ".user-manual-reviewer" / "logs"))


def log_file() -> Path:
    return log_dir() / f"llm-calls-{datetime.now(UTC):%Y-%m-%d}.jsonl"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("<redacted>" if str(k).lower() in _REDACT_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def to_jsonable(obj: Any) -> Any:
    """Best-effort conversion of SDK objects (pydantic models) to plain JSON data."""
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except Exception:  # pragma: no cover - SDK oddities
            pass
    return repr(obj)


def _write(entry: dict[str, Any]) -> None:
    if os.environ.get("UMR_LLM_LOG", "1") == "0":
        return
    try:
        path = log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(_redact(entry), ensure_ascii=False, default=repr)
        with _lock, path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:  # logging must never break a review
        logger.warning("Could not write LLM call log: %s", e)


def _size(request: dict[str, Any]) -> int:
    return sum(len(str(m.get("content", ""))) for m in request.get("messages", []) if isinstance(m, dict)) + \
        len(str(request.get("system", "")))


class CallRecord:
    """One LLM call: `start()` logs the request, then exactly one of `ok()` or `failed()`."""

    def __init__(self, provider: str, adapter: str, url: str, model: str, request: dict[str, Any]):
        self.id = uuid.uuid4().hex[:8]
        self.provider, self.adapter, self.url, self.model = provider, adapter, url, model
        self.request = request

    def start(self) -> CallRecord:
        logger.info("→ [%s] %s POST %s model=%s (%s chars of prompt)", self.id, self.provider, self.url,
                    self.model, f"{_size(self.request):,}")
        _write({"time": datetime.now(UTC).isoformat(), "call_id": self.id, "event": "request",
                "provider": self.provider, "adapter": self.adapter, "url": self.url, "model": self.model,
                "request": to_jsonable(self.request)})
        return self

    def ok(self, *, raw_text: str, response: Any, duration_s: float, input_tokens: int = 0,
           output_tokens: int = 0, finish_reason: str | None = None) -> None:
        logger.info("← [%s] %s OK in %.1f s, %s in / %s out tokens, finish=%s, %s chars: %s", self.id,
                    self.provider, duration_s, f"{input_tokens:,}", f"{output_tokens:,}", finish_reason,
                    f"{len(raw_text):,}", _preview(raw_text))
        _write({"time": datetime.now(UTC).isoformat(), "call_id": self.id, "event": "response",
                "provider": self.provider, "url": self.url, "model": self.model, "duration_s": round(duration_s, 3),
                "finish_reason": finish_reason, "raw_text": raw_text, "response": to_jsonable(response)})

    def failed(self, *, error: BaseException, duration_s: float, status_code: int | None = None,
               body: Any = None) -> None:
        logger.warning("✗ [%s] %s failed after %.1f s: %s%s", self.id, self.provider, duration_s,
                       f"HTTP {status_code} " if status_code else "", _preview(str(error), 300))
        _write({"time": datetime.now(UTC).isoformat(), "call_id": self.id, "event": "error",
                "provider": self.provider, "url": self.url, "model": self.model, "duration_s": round(duration_s, 3),
                "error_type": type(error).__name__, "error": str(error), "status_code": status_code,
                "response_body": to_jsonable(body)})


def _preview(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "…"
