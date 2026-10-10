"""Findings table with filters, and the finding detail panel."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSplitter,
    QStackedWidget,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from umr.domain import Category, Finding, Journey, Severity
from umr.gui.viewmodels import (
    FINDING_COLUMNS,
    NO_FINDINGS,
    NO_MATCH,
    OPEN_JOURNEY,
    SEVERITIES_DESC,
    SEVERITY_COLORS,
    FindingFilter,
    PassageColors,
    finding_html,
    finding_row,
    finding_sort_key,
)
from umr.gui.widgets import empty_label

SORT_ROLE = Qt.ItemDataRole.UserRole + 1
FINDING_ROLE = Qt.ItemDataRole.UserRole + 2

_Index = QModelIndex | QPersistentModelIndex


class FindingsModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.findings: list[Finding] = []
        self._rows: list[list[str]] = []
        self.muted = QColor("#888888")

    def set_findings(self, findings: list[Finding]) -> None:
        self.beginResetModel()
        self.findings = list(findings)
        self._rows = [finding_row(f) for f in self.findings]
        self.endResetModel()

    def rowCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.findings)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(FINDING_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation,  # noqa: N802
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return FINDING_COLUMNS[section]
        return None

    def data(self, index: _Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        f = self.findings[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._rows[index.row()][col]
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{f.title}\n\n{f.explanation}" if col == 3 else self._rows[index.row()][col]
        if role == SORT_ROLE:
            return finding_sort_key(f, col)
        if role == FINDING_ROLE:
            return f
        if role == Qt.ItemDataRole.ForegroundRole:
            if not f.verified:
                return QBrush(self.muted)
            if col == 1:
                return QBrush(QColor(SEVERITY_COLORS[f.severity]))
        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            if not f.verified:
                font.setItalic(True)
            elif col == 1:
                font.setBold(True)
            return font
        return None


class FindingsProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.filter = FindingFilter()
        self.setSortRole(SORT_ROLE)

    def set_filter(self, flt: FindingFilter) -> None:
        self.filter = flt
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: _Index) -> bool:  # noqa: N802
        model = self.sourceModel()
        if not isinstance(model, FindingsModel):
            return True
        return self.filter.accepts(model.findings[source_row])


def passage_colors(widget: QWidget) -> PassageColors:
    """Passage colours derived from the widget's palette, legible on light and dark themes."""
    pal = widget.palette()
    text = pal.color(QPalette.ColorRole.Text)
    base = pal.color(QPalette.ColorRole.Base)
    dark = base.lightness() < 128
    muted = QColor.fromRgbF((text.redF() + base.redF()) / 2, (text.greenF() + base.greenF()) / 2,
                            (text.blueF() + base.blueF()) / 2)
    return PassageColors(text=text.name(), muted=muted.name(), highlight_bg="#4a4000" if dark else "#fff3b0",
                         mark_bg="#ffd54f", mark_fg="#000000", border=muted.name(), code_bg=base.name())


class FindingDetail(QTextBrowser):
    """HTML rendering of one finding with its source passages (QTextBrowser, see spec deviation)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.finding: Finding | None = None
        self.clear_finding()

    def clear_finding(self, text: str = "Select a finding to see its details.") -> None:
        self.finding = None
        self.setHtml(f'<p style="color:gray; margin:20px">{text}</p>')

    def show_finding(self, f: Finding, journey: Journey | None, extra: str = "") -> None:
        self.finding = f
        self.setHtml(finding_html(f, journey, passage_colors(self), extra))


class FindingsView(QWidget):
    finding_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.journey: Journey | None = None
        self.has_run = False
        self.model = FindingsModel(self)
        self.model.muted = self.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        self.proxy = FindingsProxy(self)
        self.proxy.setSourceModel(self.model)

        self.severity = QComboBox()
        self.severity.addItem("All severities", None)
        for s in SEVERITIES_DESC:
            self.severity.addItem(s.value, s.value)
        self.category = QComboBox()
        self.manual = QComboBox()
        self.verified_only = QCheckBox("Verified only")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title, text, quotes, pages…")
        self.search.setClearButtonEnabled(True)
        self.count_label = QLabel()
        self._fill_combos([])

        bar = QHBoxLayout()
        for w in (QLabel("Severity"), self.severity, QLabel("Category"), self.category, QLabel("Manual"),
                  self.manual, self.verified_only):
            bar.addWidget(w)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.count_label)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(False)
        for col, width in enumerate([56, 72, 130, 320, 120, 220, 80, 90]):
            self.table.setColumnWidth(col, width)
        self.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        self.empty = empty_label(OPEN_JOURNEY)
        self.table_stack = QStackedWidget()
        self.table_stack.addWidget(self.empty)
        self.table_stack.addWidget(self.table)

        self.detail = FindingDetail()
        split = QSplitter(Qt.Orientation.Vertical)  # detail below: full width for side-by-side passages
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addLayout(bar)
        lv.addWidget(self.table_stack, 1)
        split.addWidget(left)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([380, 420])
        layout = QVBoxLayout(self)
        layout.addWidget(split)
        self.splitter = split

        for combo in (self.severity, self.category, self.manual):
            combo.currentIndexChanged.connect(self.apply_filter)
        self.verified_only.toggled.connect(self.apply_filter)
        self.search.textChanged.connect(self.apply_filter)
        self.table.selectionModel().currentRowChanged.connect(self._on_current)
        self._update_empty()

    def _fill_combos(self, findings: list[Finding]) -> None:
        for combo in (self.category, self.manual):
            combo.blockSignals(True)
            combo.clear()
        self.category.addItem("All categories", None)
        for c in Category:
            if any(f.category == c for f in findings):
                self.category.addItem(c.value, c.value)
        self.manual.addItem("All manuals", None)
        ids = list(dict.fromkeys(loc.manual_id for f in findings for loc in f.locations))
        if self.journey is not None:
            ids = [m.id for m in self.journey.manuals] + [i for i in ids if not self.journey.manual(i)]
        for mid in ids:
            self.manual.addItem(mid, mid)
        for combo in (self.category, self.manual):
            combo.blockSignals(False)

    def set_findings(self, findings: list[Finding], journey: Journey | None) -> None:
        self.journey = journey
        self.has_run = True
        self.model.set_findings(findings)
        self._fill_combos(findings)
        self.detail.clear_finding()
        self.apply_filter()
        if self.proxy.rowCount():
            self.table.selectRow(0)

    def current_filter(self) -> FindingFilter:
        sev = self.severity.currentData()
        cat = self.category.currentData()
        return FindingFilter(severity=Severity(sev) if sev else None, category=Category(cat) if cat else None,
                             manual=self.manual.currentData() or None,
                             verified_only=self.verified_only.isChecked(), text=self.search.text())

    def apply_filter(self) -> None:
        self.proxy.set_filter(self.current_filter())
        total, shown = self.model.rowCount(), self.proxy.rowCount()
        self.count_label.setText(f"{shown} of {total}" if shown != total else f"{total} findings")
        self._update_empty()

    def _update_empty(self) -> None:
        if not self.has_run:
            text = OPEN_JOURNEY
        elif self.model.rowCount() == 0:
            text = NO_FINDINGS
        elif self.proxy.rowCount() == 0:
            text = NO_MATCH
        else:
            text = ""
        self.empty.setText(text)
        self.table_stack.setCurrentWidget(self.empty if text else self.table)

    def visible_findings(self) -> list[Finding]:
        return [self.proxy.data(self.proxy.index(r, 0), FINDING_ROLE) for r in range(self.proxy.rowCount())]

    def select_finding(self, finding_id: str) -> bool:
        for r in range(self.proxy.rowCount()):
            f = self.proxy.data(self.proxy.index(r, 0), FINDING_ROLE)
            if f.id == finding_id:
                self.table.selectRow(r)
                return True
        return False

    def _on_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        f = self.proxy.data(current, FINDING_ROLE)
        if isinstance(f, Finding):
            self.detail.show_finding(f, self.journey)
            self.finding_selected.emit(f)
