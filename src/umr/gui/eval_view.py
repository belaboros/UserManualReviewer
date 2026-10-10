"""Evaluate view (run a model on a benchmark) and Leaderboard view."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from umr.gui.viewmodels import (
    LEADERBOARD_COLUMNS,
    NO_EVALS,
    expected_label,
    finding_label,
    fmt_cost,
    fmt_duration,
    fmt_int,
    fmt_pct,
    fmt_score,
    leaderboard_row,
    metric_rows,
    score_band,
)
from umr.gui.widgets import RateBarDelegate, ScoreRing, clear_layout, empty_label, heading_label

SORT_ROLE = Qt.ItemDataRole.UserRole + 1
CATEGORY_COLUMNS = ["Category", "Expected", "Found", "Reported", "Recall", "Precision", "F1"]


class EvaluateView(QWidget):
    run_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.result: Any = None
        self.provider = QComboBox()
        self.benchmark = QComboBox()
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 10)
        self.include_rules = QCheckBox("Include rule checks")
        self.include_rules.setToolTip("Score the whole system, not only LLM-tier categories")
        self.run_btn = QPushButton("Run evaluation")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setEnabled(False)

        form = QFormLayout()
        form.addRow("Model", self.provider)
        form.addRow("Benchmark", self.benchmark)
        form.addRow("Repeat", self.repeat)
        form.addRow("", self.include_rules)
        row = QHBoxLayout()
        row.addWidget(self.run_btn)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.progress, 1)
        setup_box = QGroupBox("Evaluate a model against an answer-keyed benchmark")
        sl = QVBoxLayout(setup_box)
        sl.addLayout(form)
        sl.addLayout(row)
        sl.addWidget(self.status)

        # results
        self.empty = empty_label("Pick a model and a benchmark, then click Run evaluation.")
        self.ring = ScoreRing(150, "eval score")
        self.score_label = heading_label("", 1.6)
        self.facts = QLabel()
        self.facts.setWordWrap(True)
        self.metrics = QGridLayout()
        metrics_w = QWidget()
        metrics_w.setLayout(self.metrics)
        hero = QHBoxLayout()
        hero.addWidget(self.ring)
        col = QVBoxLayout()
        col.addWidget(self.score_label)
        col.addWidget(self.facts)
        col.addWidget(metrics_w)
        col.addStretch(1)
        hero.addLayout(col, 1)

        self.categories = QTableWidget(0, len(CATEGORY_COLUMNS))
        self.categories.setHorizontalHeaderLabels(CATEGORY_COLUMNS)
        self.categories.verticalHeader().setVisible(False)
        self.categories.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.categories.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.categories.setMinimumHeight(260)
        self._delegate = RateBarDelegate(self.categories)
        for c in (4, 5, 6):
            self.categories.setItemDelegateForColumn(c, self._delegate)
        cat_box = QGroupBox("Per category")
        QVBoxLayout(cat_box).addWidget(self.categories)

        self.missed = QListWidget()
        self.unexpected = QListWidget()
        self.missed_box = QGroupBox("Missed (in the key, not found)")
        self.unexpected_box = QGroupBox("Unexpected (found, not in the key)")
        QVBoxLayout(self.missed_box).addWidget(self.missed)
        QVBoxLayout(self.unexpected_box).addWidget(self.unexpected)
        lists = QHBoxLayout()
        lists.addWidget(self.missed_box)
        lists.addWidget(self.unexpected_box)

        result_w = QWidget()
        rl = QVBoxLayout(result_w)
        rl.addLayout(hero)
        rl.addWidget(cat_box)
        rl.addLayout(lists)
        scroll = QScrollArea()
        scroll.setWidget(result_w)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(scroll)

        layout = QVBoxLayout(self)
        layout.addWidget(setup_box)
        layout.addWidget(self.stack, 1)
        self.run_btn.clicked.connect(self.run_requested)
        self.cancel_btn.clicked.connect(self.cancel_requested)

    def set_options(self, providers: list[str], benchmarks: list[str], notice: str = "") -> None:
        self.provider.clear()
        for p in providers:
            self.provider.addItem(p, p)
        self.benchmark.clear()
        for b in benchmarks:
            self.benchmark.addItem(b, b)
        if not providers:
            notice = (notice + " " if notice else "") + "No model is configured, so no evaluation can run."
        if not benchmarks:
            notice = (notice + " " if notice else "") + "No benchmark is available."
        self.status.setText(notice.strip())
        self.run_btn.setEnabled(bool(providers and benchmarks))

    def set_running(self, running: bool) -> None:
        self.run_btn.setEnabled(not running and self.provider.count() > 0 and self.benchmark.count() > 0)
        self.cancel_btn.setEnabled(running)
        for w in (self.provider, self.benchmark, self.repeat, self.include_rules):
            w.setEnabled(not running)
        if running:
            self.progress.setValue(0)

    def set_result(self, r: Any) -> None:
        self.result = r
        if r is None:
            self.stack.setCurrentWidget(self.empty)
            return
        self.stack.setCurrentIndex(1)
        score = float(r.eval_score)
        self.ring.set_value(score)
        self.score_label.setText(f"{r.model} · eval score {fmt_score(score)}")
        self.score_label.setStyleSheet(f"color: {score_band(score)}")
        usage = getattr(r, "usage", None)
        tokens = (f"{fmt_int(usage.input_tokens)} in / {fmt_int(usage.output_tokens)} out"
                  if usage is not None else "–")
        self.facts.setText(
            f"Benchmark <b>{r.benchmark}</b> (key version {getattr(r, 'key_version', '–')}) · "
            f"repeat {getattr(r, 'repeat', 1)} · cost {fmt_cost(getattr(usage, 'cost_usd', None))} · "
            f"tokens {tokens} · duration {fmt_duration(getattr(r, 'duration_s', None))}")
        clear_layout(self.metrics)
        for i, (label, value) in enumerate(metric_rows(r.metrics)):
            k = QLabel(label)
            k.setEnabled(False)
            v = QLabel(f"<b>{fmt_pct(value)}</b>")
            self.metrics.addWidget(k, i // 4, (i % 4) * 2)
            self.metrics.addWidget(v, i // 4, (i % 4) * 2 + 1)

        cats = list(getattr(r, "per_category", []) or [])
        self.categories.setRowCount(len(cats))
        for row, c in enumerate(cats):
            cat = getattr(c.category, "value", c.category)
            values: list[Any] = [str(cat), int(c.expected), int(c.found), int(c.reported),
                                 float(c.recall), float(c.precision), float(c.f1)]
            for col, v in enumerate(values):
                cell = QTableWidgetItem(fmt_pct(v) if isinstance(v, float) else str(v))
                if isinstance(v, float):
                    cell.setData(Qt.ItemDataRole.UserRole, v)
                if col:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.categories.setItem(row, col, cell)

        missed = list(getattr(r, "missed", []) or [])
        unexpected = list(getattr(r, "unexpected", []) or [])
        self.missed_box.setTitle(f"Missed — in the key, not found ({len(missed)})")
        self.unexpected_box.setTitle(f"Unexpected — found, not in the key ({len(unexpected)})")
        self.missed.clear()
        self.missed.addItems([expected_label(e) for e in missed] or ["(none)"])
        self.unexpected.clear()
        self.unexpected.addItems([finding_label(f) for f in unexpected] or ["(none)"])


class NumericSortProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)


class LeaderboardView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.results: list[Any] = []
        self.model = QStandardItemModel(0, len(LEADERBOARD_COLUMNS), self)
        self.model.setHorizontalHeaderLabels(LEADERBOARD_COLUMNS)
        self.proxy = NumericSortProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.refresh_btn = QPushButton("Refresh")
        self.empty = empty_label(NO_EVALS)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.table)
        top = QHBoxLayout()
        top.addWidget(heading_label("Leaderboard", 1.3))
        top.addStretch(1)
        top.addWidget(self.refresh_btn)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.stack, 1)

    def set_results(self, ranked: list[Any]) -> None:
        self.results = list(ranked)
        self.model.removeRows(0, self.model.rowCount())
        for rank, r in enumerate(self.results, 1):
            items = []
            for col, (text, sort) in enumerate(leaderboard_row(rank, r)):
                item = QStandardItem(text)
                item.setData(sort, SORT_ROLE)
                if col == 4:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                if col not in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                items.append(item)
            self.model.appendRow(items)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.stack.setCurrentWidget(self.table if self.results else self.empty)

    def column_texts(self, column: int) -> list[str]:
        return [str(self.proxy.data(self.proxy.index(r, column))) for r in range(self.proxy.rowCount())]
