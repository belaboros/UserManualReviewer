"""Setup view: journey, manuals, checks, models, start/cancel, progress and log."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from umr.domain import Journey, Tier
from umr.gui.viewmodels import (
    NONE_A,
    NONE_B,
    OPEN_JOURNEY,
    CheckInfo,
    fmt_int,
    group_checks,
    selection_summary,
)
from umr.gui.widgets import empty_label, heading_label

TIER_LABELS = {Tier.RULE: "Rule checks — free, offline", Tier.LLM: "LLM checks — need a model"}


class SetupView(QWidget):
    open_file_requested = Signal()
    open_folder_requested = Signal()
    start_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.checks: list[CheckInfo] = []
        self._check_items: dict[str, QTreeWidgetItem] = {}

        # journey
        self.journey_title = heading_label("No journey open", 1.3)
        self.journey_path = QLabel("")
        self.journey_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.journey_path.setEnabled(False)
        self.open_file_btn = QPushButton("Open journey…")
        self.open_file_btn.setToolTip("Open a journey.yaml (Ctrl+O)")
        self.open_folder_btn = QPushButton("Open folder…")
        self.open_folder_btn.setToolTip("Open a folder with journey.yaml, or a single manual folder")
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(self.journey_title)
        titles.addWidget(self.journey_path)
        top.addLayout(titles, 1)
        top.addWidget(self.open_file_btn)
        top.addWidget(self.open_folder_btn)

        # manuals
        self.manuals = QTreeWidget()
        self.manuals.setHeaderLabels(["Manual / page", "Format", "Words"])
        self.manuals.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.manuals.header().setStretchLastSection(False)
        self.manuals_empty = empty_label(OPEN_JOURNEY)
        self.manuals_stack = QStackedWidget()
        self.manuals_stack.addWidget(self.manuals_empty)
        self.manuals_stack.addWidget(self.manuals)
        manuals_box = QGroupBox("Manuals")
        QVBoxLayout(manuals_box).addWidget(self.manuals_stack)

        # checks
        self.checks_tree = QTreeWidget()
        self.checks_tree.setHeaderLabels(["Check", "Needs"])
        self.checks_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.checks_tree.header().setStretchLastSection(False)
        self.all_btn = QPushButton("All")
        self.rules_btn = QPushButton("Rules only")
        self.none_btn = QPushButton("None")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        btns = QHBoxLayout()
        for b in (self.all_btn, self.rules_btn, self.none_btn):
            btns.addWidget(b)
        btns.addStretch(1)
        checks_box = QGroupBox("Checks")
        cl = QVBoxLayout(checks_box)
        cl.addLayout(btns)
        cl.addWidget(self.checks_tree, 1)
        cl.addWidget(self.summary)

        # models and run
        self.model_a = QComboBox()
        self.model_b = QComboBox()
        self.provider_notice = QLabel()
        self.provider_notice.setWordWrap(True)
        self.provider_notice.setEnabled(False)
        self.start_btn = QPushButton("Start review")
        self.start_btn.setDefault(True)
        self.start_btn.setToolTip("Start the review (Ctrl+R)")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Cancel the running review (Esc)")
        self.cancel_btn.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Progress of the review appears here.")
        self.log.setMaximumBlockCount(5000)

        models_box = QGroupBox("Models")
        form = QFormLayout(models_box)
        form.addRow("Model A", self.model_a)
        form.addRow("Model B (optional)", self.model_b)
        form.addRow(self.provider_notice)
        run_row = QHBoxLayout()
        run_row.addWidget(self.start_btn)
        run_row.addWidget(self.cancel_btn)
        run_row.addWidget(self.progress, 1)
        run_box = QGroupBox("Run")
        rl = QVBoxLayout(run_box)
        rl.addLayout(run_row)
        rl.addWidget(self.log, 1)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(checks_box, 3)
        rv.addWidget(models_box)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(manuals_box)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(split, 3)
        layout.addWidget(run_box, 2)

        self.open_file_btn.clicked.connect(self.open_file_requested)
        self.open_folder_btn.clicked.connect(self.open_folder_requested)
        self.start_btn.clicked.connect(self.start_requested)
        self.cancel_btn.clicked.connect(self.cancel_requested)
        self.all_btn.clicked.connect(lambda: self.select_checks(lambda c: True))
        self.rules_btn.clicked.connect(lambda: self.select_checks(lambda c: c.tier == Tier.RULE))
        self.none_btn.clicked.connect(lambda: self.select_checks(lambda c: False))
        self.checks_tree.itemChanged.connect(lambda *_: self.update_summary())
        self.model_a.currentIndexChanged.connect(lambda *_: self.update_summary())
        self.model_b.currentIndexChanged.connect(lambda *_: self.update_summary())
        self.set_providers([], "")

    # ---- journey ----
    def set_journey(self, journey: Journey | None, path: str = "") -> None:
        self.manuals.clear()
        if journey is None:
            self.journey_title.setText("No journey open")
            self.journey_path.setText("")
            self.manuals_stack.setCurrentWidget(self.manuals_empty)
            return
        self.journey_title.setText(journey.name)
        self.journey_path.setText(path)
        for m in journey.manuals:
            label = f"{m.title}  ({m.id}{', v' + m.version if m.version else ''})"
            top = QTreeWidgetItem([label, f"{len(m.pages)} pages", fmt_int(m.word_count)])
            top.setData(0, Qt.ItemDataRole.UserRole, m.id)
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            for p in m.pages:
                QTreeWidgetItem(top, [p.path, p.format, fmt_int(p.word_count)])
            top.setTextAlignment(2, Qt.AlignmentFlag.AlignRight)
            self.manuals.addTopLevelItem(top)
            top.setExpanded(True)
        self.manuals.resizeColumnToContents(1)
        self.manuals.resizeColumnToContents(2)
        self.manuals_stack.setCurrentWidget(self.manuals)

    def manual_count(self) -> int:
        return self.manuals.topLevelItemCount()

    # ---- checks ----
    def set_checks(self, checks: list[CheckInfo], selected: set[str] | None = None) -> None:
        self.checks = checks
        self._check_items.clear()
        self.checks_tree.blockSignals(True)
        self.checks_tree.clear()
        for tier, items in group_checks(checks):
            group = QTreeWidgetItem([f"{TIER_LABELS[tier]} ({len(items)})", ""])
            group.setFlags(group.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
            f = group.font(0)
            f.setBold(True)
            group.setFont(0, f)
            self.checks_tree.addTopLevelItem(group)
            for c in items:
                item = QTreeWidgetItem(group, [c.title, "needs LLM" if c.needs_llm else ""])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                on = selected is None or c.id in selected
                item.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
                item.setData(0, Qt.ItemDataRole.UserRole, c.id)
                cats = ", ".join(c.categories)
                item.setToolTip(0, f"{c.id}\n{c.description}" + (f"\nCategories: {cats}" if cats else ""))
                if c.needs_llm:
                    item.setToolTip(1, "This check sends manual text to the chosen model A")
                self._check_items[c.id] = item
            group.setExpanded(True)
        if not checks:
            QTreeWidgetItem(self.checks_tree, ["No checks are registered", ""]).setDisabled(True)
        self.checks_tree.blockSignals(False)
        self.update_summary()

    def select_checks(self, predicate: Callable[[CheckInfo], bool]) -> None:
        self.checks_tree.blockSignals(True)
        for c in self.checks:
            on = predicate(c)
            self._check_items[c.id].setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.checks_tree.blockSignals(False)
        self.update_summary()

    def selected_check_ids(self) -> list[str]:
        return [c.id for c in self.checks
                if self._check_items[c.id].checkState(0) == Qt.CheckState.Checked]

    def update_summary(self) -> None:
        has_model = self.model_a.currentData() is not None
        self.summary.setText(selection_summary(self.checks, set(self.selected_check_ids()), has_model))
        self.start_btn.setText("Start comparison" if self.model_b.currentData() else "Start review")

    # ---- providers ----
    def set_providers(self, names: list[str], notice: str) -> None:
        for combo, none in ((self.model_a, NONE_A), (self.model_b, NONE_B)):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(none, None)
            for n in names:
                combo.addItem(n, n)
            idx = combo.findData(current) if current else 0
            combo.setCurrentIndex(max(0, idx))
            combo.blockSignals(False)
        self.provider_notice.setText(notice)
        self.provider_notice.setVisible(bool(notice))
        self.update_summary()

    def model_a_name(self) -> str | None:
        data = self.model_a.currentData()
        return str(data) if data else None

    def model_b_name(self) -> str | None:
        data = self.model_b.currentData()
        return str(data) if data else None

    # ---- run state ----
    def set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        for w in (self.open_file_btn, self.open_folder_btn, self.model_a, self.model_b, self.checks_tree,
                  self.all_btn, self.rules_btn, self.none_btn):
            w.setEnabled(not running)

    def append_log(self, line: str) -> None:
        self.log.appendPlainText(line)
