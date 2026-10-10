"""Background work in a QThreadPool; results come back to the GUI thread through Qt signals."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from umr.app import ReviewCancelled

# fn(progress, cancel) -> result; progress(*args) may be called from any thread
TaskFn = Callable[[Callable[..., None], threading.Event], Any]


class TaskSignals(QObject):
    progress = Signal(object)  # tuple of the progress callback's arguments
    finished = Signal(object)
    failed = Signal(object)  # the exception
    cancelled = Signal()


class Task(QRunnable):
    def __init__(self, fn: TaskFn):
        super().__init__()
        self.fn = fn
        self.cancel_event = threading.Event()
        self.signals = TaskSignals()
        self.setAutoDelete(False)

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            result = self.fn(lambda *args: self.signals.progress.emit(args), self.cancel_event)
        except ReviewCancelled:
            self.signals.cancelled.emit()
        except BaseException as e:  # reported to the GUI, never lost in the worker
            if self.cancel_event.is_set() and type(e).__name__.endswith("Cancelled"):
                self.signals.cancelled.emit()
            else:
                self.signals.failed.emit(e)
        else:
            if self.cancel_event.is_set():
                self.signals.cancelled.emit()
            else:
                self.signals.finished.emit(result)


def start_task(task: Task, pool: QThreadPool | None = None) -> Task:
    (pool or QThreadPool.globalInstance()).start(task)
    return task


def split_progress_args(args: tuple[Any, ...]) -> tuple[str | None, Any]:
    """Accept progress(event) and progress(label, event) callback shapes."""
    label = next((a for a in args if isinstance(a, str)), None)
    event = next((a for a in args if not isinstance(a, str)), None)
    return label, event
