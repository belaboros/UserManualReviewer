"""Dashboard: set score, manual cards, severity bars, heatmap, run facts and errors."""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from umr.domain import Journey, ReviewRun
from umr.gui.viewmodels import (
    NO_FINDINGS,
    NO_RUN_DASHBOARD,
    band_name,
    fmt_int,
    heatmap,
    manual_cards,
    run_facts,
    set_score,
    severity_counts,
)
from umr.gui.widgets import HeatmapWidget, ScoreRing, SeverityBars, clear_layout, empty_label, heading_label


class ManualScoreCard(QFrame):
    def __init__(self, title: str, manual_id: str, score: float | None, findings: int, words: int):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.manual_id = manual_id
        self.ring = ScoreRing(96)
        self.ring.set_value(score)
        name = QLabel(f"<b>{title}</b>")
        name.setWordWrap(True)
        info = QLabel(f"{findings} finding{'s' if findings != 1 else ''} · {fmt_int(words)} words")
        info.setEnabled(False)
        lay = QVBoxLayout(self)
        lay.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(name, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(info, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setMinimumWidth(170)


class DashboardView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.run: ReviewRun | None = None
        self.empty = empty_label(NO_RUN_DASHBOARD)

        self.title = heading_label("", 1.5)
        self.ring = ScoreRing(190, "set score")
        self.band = QLabel()
        self.no_findings = QLabel(NO_FINDINGS)
        nf = self.no_findings.font()
        nf.setPointSizeF(nf.pointSizeF() * 1.3)
        nf.setBold(True)
        self.no_findings.setFont(nf)
        self.facts = QGridLayout()
        self.facts.setHorizontalSpacing(16)
        facts_box = QWidget()
        facts_box.setLayout(self.facts)

        hero = QHBoxLayout()
        ring_col = QVBoxLayout()
        ring_col.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        ring_col.addWidget(self.band, 0, Qt.AlignmentFlag.AlignHCenter)
        hero.addLayout(ring_col)
        hero.addSpacing(24)
        info_col = QVBoxLayout()
        info_col.addWidget(self.title)
        info_col.addWidget(self.no_findings)
        info_col.addWidget(facts_box)
        info_col.addStretch(1)
        hero.addLayout(info_col, 1)

        self.cards_box = QGroupBox("Manuals")
        self.cards_layout = QHBoxLayout(self.cards_box)
        self.cards: list[ManualScoreCard] = []

        self.bars = SeverityBars()
        bars_box = QGroupBox("Findings by severity")
        QVBoxLayout(bars_box).addWidget(self.bars)

        self.heat = HeatmapWidget()
        self.heat_empty = QLabel("No verified findings with a location.")
        self.heat_empty.setEnabled(False)
        heat_box = QGroupBox("Heatmap — verified findings per page and category")
        hl = QVBoxLayout(heat_box)
        heat_scroll = QScrollArea()
        heat_scroll.setWidget(self.heat)
        heat_scroll.setWidgetResizable(False)
        heat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        heat_scroll.setMinimumHeight(220)
        self.heat_scroll = heat_scroll
        hl.addWidget(self.heat_empty)
        hl.addWidget(heat_scroll)

        self.errors_box = QGroupBox("Checks that did not complete")
        self.errors_label = QLabel()
        self.errors_label.setWordWrap(True)
        self.errors_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        QVBoxLayout(self.errors_box).addWidget(self.errors_label)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.addLayout(hero)
        cl.addWidget(self.errors_box)
        cl.addWidget(self.cards_box)
        cl.addWidget(bars_box)
        cl.addWidget(heat_box)
        cl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(scroll)
        QVBoxLayout(self).addWidget(self.stack)

    def set_run(self, run: ReviewRun | None, journey: Journey | None = None) -> None:
        self.run = run
        if run is None:
            self.stack.setCurrentWidget(self.empty)
            return
        self.stack.setCurrentIndex(1)
        self.title.setText(run.journey_name)
        value = set_score(run)
        self.ring.set_value(value)
        self.band.setText("" if value is None else f"{value:.1f} — {band_name(value)}")
        self.no_findings.setVisible(not run.findings)

        clear_layout(self.facts)
        for i, (k, v) in enumerate(run_facts(run)):
            key = QLabel(k)
            key.setEnabled(False)
            val = QLabel(v)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.facts.addWidget(key, i // 2, (i % 2) * 2)
            self.facts.addWidget(val, i // 2, (i % 2) * 2 + 1)

        for card in self.cards:
            card.deleteLater()
        self.cards = [ManualScoreCard(c.title, c.manual_id, c.score, c.finding_count, c.word_count)
                      for c in manual_cards(run, journey)]
        while self.cards_layout.count():
            self.cards_layout.takeAt(0)
        for card in self.cards:
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

        self.bars.set_counts(severity_counts(run.findings))
        hm = heatmap(run, journey)
        self.heat.set_data(hm)
        has_heat = bool(hm.cols)
        self.heat_scroll.setVisible(has_heat)
        self.heat_empty.setVisible(not has_heat)
        self.heat_scroll.setMinimumHeight(min(self.heat.sizeHint().height() + 8, 600) if has_heat else 0)

        self.errors_box.setVisible(bool(run.errors))
        self.errors_label.setText("<br>".join(f"<b>{html.escape(e.check_id)}</b>: {html.escape(e.message)}"
                                              for e in run.errors))
