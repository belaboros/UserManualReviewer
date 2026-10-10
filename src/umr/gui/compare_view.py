"""Compare view: found by both / only A / only B, with both runs' figures side by side."""

from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from umr.domain import Finding, Journey
from umr.gui.findings_view import FindingDetail
from umr.gui.viewmodels import compare_rows, finding_label
from umr.gui.widgets import empty_label

NO_COMPARISON = ("Choose a model B in Setup and start a comparison, or use File → Compare two runs… "
                 "to compare saved runs.")


class CompareView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.comparison: Any = None
        self.journey: Journey | None = None
        self.empty = empty_label(NO_COMPARISON)

        self.summary = QTableWidget(0, 3)
        self.summary.verticalHeader().setVisible(False)
        self.summary.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.summary.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.summary.setMaximumHeight(250)

        self.both = QListWidget()
        self.only_a = QListWidget()
        self.only_b = QListWidget()
        self.both_box = QGroupBox("Found by both")
        self.a_box = QGroupBox("Only A")
        self.b_box = QGroupBox("Only B")
        cols = QHBoxLayout()
        for box, lst in ((self.both_box, self.both), (self.a_box, self.only_a), (self.b_box, self.only_b)):
            QVBoxLayout(box).addWidget(lst)
            lst.setWordWrap(True)
            lst.currentItemChanged.connect(self._on_item)
            cols.addWidget(box)
        lists = QWidget()
        lists.setLayout(cols)

        self.detail = FindingDetail()
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(lists)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self.summary)
        cl.addWidget(split, 1)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(content)
        QVBoxLayout(self).addWidget(self.stack)

    def set_comparison(self, comparison: Any, journey: Journey | None = None) -> None:
        self.comparison = comparison
        self.journey = journey
        if comparison is None:
            self.stack.setCurrentWidget(self.empty)
            return
        self.stack.setCurrentIndex(1)
        (la, lb), rows = compare_rows(comparison)
        self.summary.setRowCount(len(rows))
        self.summary.setHorizontalHeaderLabels(["", f"A: {la}", f"B: {lb}"])
        for r, (metric, va, vb) in enumerate(rows):
            for c, text in enumerate((metric, va, vb)):
                item = QTableWidgetItem(text)
                if c == 0:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.summary.setItem(r, c, item)
        self.summary.resizeRowsToContents()

        self.both_box.setTitle(f"Found by both ({len(comparison.both)})")
        self.a_box.setTitle(f"Only {la} ({len(comparison.only_a)})")
        self.b_box.setTitle(f"Only {lb} ({len(comparison.only_b)})")
        self._fill(self.both, [(fa, fb) for fa, fb in comparison.both])
        self._fill(self.only_a, [(f, None) for f in comparison.only_a])
        self._fill(self.only_b, [(f, None) for f in comparison.only_b])
        self.detail.clear_finding("Click a finding to see its detail.")

    def _fill(self, lst: QListWidget, items: list[tuple[Finding, Finding | None]]) -> None:
        lst.blockSignals(True)
        lst.clear()
        muted = self.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        for f, other in items:
            item = QListWidgetItem(finding_label(f))
            item.setData(Qt.ItemDataRole.UserRole, (f, other))
            item.setToolTip(f.explanation)
            if not f.verified:
                item.setForeground(muted)
                font = QFont(item.font())
                font.setItalic(True)
                item.setFont(font)
            lst.addItem(item)
        if not items:
            empty = QListWidgetItem("(none)")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            lst.addItem(empty)
        lst.blockSignals(False)

    def _on_item(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        f, other = data
        for lst in (self.both, self.only_a, self.only_b):  # one selection across the three lists
            if lst is not current.listWidget():
                lst.blockSignals(True)
                lst.setCurrentRow(-1)
                lst.blockSignals(False)
        extra = ""
        if other is not None:
            lb = self.comparison.run_b.model or "rules"
            extra = (f"<p><i>Model B ({html.escape(lb)}) reported:</i> {html.escape(other.title)} "
                     f"[{other.severity.value}, {other.id}]</p>")
        self.detail.show_finding(f, self.journey, extra)
