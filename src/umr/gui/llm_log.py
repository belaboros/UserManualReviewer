"""Show `umr.llm` request/response summaries in the run log (AC-LLM-25).

LLM calls run on worker threads, so the handler emits a Qt signal; the queued connection delivers each
line on the GUI thread.
"""

from __future__ import annotations

import contextlib
import logging

from PySide6.QtCore import QObject, Signal


class LlmLogBridge(QObject):
    line = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.handler = _Handler(self)
        self.handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logger = logging.getLogger("umr.llm")
        logger.addHandler(self.handler)
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)

    def close(self) -> None:
        logging.getLogger("umr.llm").removeHandler(self.handler)


class _Handler(logging.Handler):
    def __init__(self, bridge: LlmLogBridge):
        super().__init__(logging.INFO)
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(RuntimeError):  # the window is gone
            self.bridge.line.emit(self.format(record))
