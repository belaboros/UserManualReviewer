"""Custom-painted visual widgets: score ring, severity bars, heatmap, rate-bar delegate."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import QLabel, QLayout, QSizePolicy, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from umr.domain import Severity
from umr.gui.viewmodels import SEVERITY_COLORS, Heatmap, fmt_score, score_band


def text_color(widget: QWidget) -> QColor:
    return widget.palette().color(QPalette.ColorRole.WindowText)


def muted_color(widget: QWidget) -> QColor:
    c = text_color(widget)
    c.setAlphaF(0.6)
    return c


def track_color(widget: QWidget) -> QColor:
    c = text_color(widget)
    c.setAlphaF(0.12)
    return c


class ScoreRing(QWidget):
    """Ring gauge for a 0–100 score; colour by band, number always written in the middle."""

    def __init__(self, diameter: int = 160, caption: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._value: float | None = None
        self.caption = caption
        self.diameter = diameter
        self.setMinimumSize(diameter, diameter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(self.diameter, self.diameter)

    @property
    def value(self) -> float | None:
        return self._value

    def set_value(self, value: float | None) -> None:
        self._value = value
        self.setToolTip("" if value is None else f"Quality score {value:.1f} of 100")
        self.update()

    def band_color(self) -> QColor | None:
        return None if self._value is None else QColor(score_band(self._value))

    def paintEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        thick = max(8.0, side * 0.09)
        rect = QRectF((self.width() - side) / 2 + thick / 2, (self.height() - side) / 2 + thick / 2,
                      side - thick, side - thick)
        pen = QPen(track_color(self), thick)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)
        if self._value is not None:
            pen.setColor(QColor(score_band(self._value)))
            if self._value > 3:  # a round cap on a tiny arc would look like a dot
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            span = int(-360 * 16 * max(0.0, min(100.0, self._value)) / 100)
            p.drawArc(rect, 90 * 16, span)
        p.setPen(text_color(self))
        f = QFont(self.font())
        f.setPointSizeF(max(9.0, side * 0.16))
        f.setBold(True)
        p.setFont(f)
        text_rect = rect.adjusted(0, -side * 0.06 if self.caption else 0, 0, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, fmt_score(self._value))
        if self.caption:
            f2 = QFont(self.font())
            f2.setPointSizeF(max(7.0, side * 0.065))
            p.setFont(f2)
            p.setPen(muted_color(self))
            p.drawText(rect.adjusted(0, side * 0.22, 0, 0), Qt.AlignmentFlag.AlignCenter, self.caption)
        p.end()


class SeverityBars(QWidget):
    """Horizontal bars of finding counts per severity (verified solid, unverified hatched)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.counts: list[tuple[Severity, int, int]] = []
        self.setMinimumHeight(4 * 30 + 10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_counts(self, counts: list[tuple[Severity, int, int]]) -> None:
        self.counts = counts
        self.setToolTip("\n".join(f"{s.value}: {v} verified, {u} unverified" for s, v, u in counts))
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = p.fontMetrics()
        label_w = fm.horizontalAdvance("critical") + 16
        num_w = fm.horizontalAdvance("000 (+000 unverified)") + 8
        bar_w = max(20, self.width() - label_w - num_w)
        top = max((v + u for _, v, u in self.counts), default=0) or 1
        row_h = 30
        for i, (sev, ver, unv) in enumerate(self.counts):
            y = 5 + i * row_h
            p.setPen(text_color(self))
            p.drawText(QRectF(0, y, label_w - 8, row_h - 8), Qt.AlignmentFlag.AlignVCenter, sev.value)
            p.fillRect(QRectF(label_w, y, bar_w, row_h - 8), track_color(self))
            color = QColor(SEVERITY_COLORS[sev])
            wv = bar_w * ver / top
            p.fillRect(QRectF(label_w, y, wv, row_h - 8), color)
            if unv:
                faded = QColor(color)
                faded.setAlphaF(0.35)
                p.fillRect(QRectF(label_w + wv, y, bar_w * unv / top, row_h - 8), faded)
            p.setPen(text_color(self))
            txt = f"{ver}" + (f" (+{unv} unverified)" if unv else "")
            p.drawText(QRectF(label_w + bar_w + 8, y, num_w, row_h - 8), Qt.AlignmentFlag.AlignVCenter, txt)
        p.end()


class HeatmapWidget(QWidget):
    """Pages × categories grid; colour intensity by count; the count is written in each non-empty cell."""

    CELL_W = 64
    CELL_H = 24

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.data = Heatmap([], [], [])
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def set_data(self, data: Heatmap) -> None:
        self.data = data
        self.updateGeometry()
        self.setMinimumSize(self.sizeHint())
        self.update()

    def _label_w(self) -> int:
        fm = self.fontMetrics()
        return max((fm.horizontalAdvance(r) for r in self.data.rows), default=60) + 12

    def _header_h(self) -> int:
        fm = self.fontMetrics()
        return max((fm.horizontalAdvance(c) for c in self.data.cols), default=40) + 12

    def sizeHint(self) -> QSize:
        overhang = int(0.5 * (self._header_h() - 12))  # headers are rotated by 60°, they lean right
        return QSize(self._label_w() + self.CELL_W * max(1, len(self.data.cols)) + 4 + overhang,
                     self._header_h() + self.CELL_H * max(1, len(self.data.rows)) + 4)

    def cell_color(self, count: int) -> QColor:
        c = QColor(SEVERITY_COLORS[Severity.CRITICAL])
        if count <= 0 or self.data.max <= 0:
            c = track_color(self)
            c.setAlphaF(0.06)
            return c
        c.setAlphaF(0.2 + 0.8 * count / self.data.max)
        return c

    def paintEvent(self, event: object) -> None:  # noqa: N802
        p = QPainter(self)
        lw, hh = self._label_w(), self._header_h()
        p.setPen(text_color(self))
        for j, cat in enumerate(self.data.cols):
            p.save()
            p.translate(lw + j * self.CELL_W + self.CELL_W / 2 + 4, hh - 6)
            p.rotate(-60)
            p.drawText(0, 0, cat)
            p.restore()
        grid = track_color(self)
        for i, row in enumerate(self.data.rows):
            y = hh + i * self.CELL_H
            p.setPen(text_color(self))
            p.drawText(QRectF(0, y, lw - 8, self.CELL_H), Qt.AlignmentFlag.AlignVCenter
                       | Qt.AlignmentFlag.AlignRight, row)
            for j in range(len(self.data.cols)):
                n = self.data.counts[i][j]
                r = QRectF(lw + j * self.CELL_W, y, self.CELL_W - 2, self.CELL_H - 2)
                p.fillRect(r, self.cell_color(n))
                p.setPen(grid)
                p.drawRect(r)
                if n:
                    strong = n / max(1, self.data.max) > 0.55
                    p.setPen(QColor("#ffffff") if strong else text_color(self))
                    p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(n))
        p.end()


class RateBarDelegate(QStyledItemDelegate):
    """Draws a 0–1 rate as a bar with the percentage on top (Qt.UserRole holds the float)."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex | QPersistentModelIndex) -> None:
        value = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(value, float):
            super().paint(painter, option, index)
            return
        painter.save()
        rect = option.rect.adjusted(4, 4, -4, -4)  # type: ignore[attr-defined]
        pal = option.palette  # type: ignore[attr-defined]
        track = pal.color(QPalette.ColorRole.Text)
        track.setAlphaF(0.1)
        painter.fillRect(rect, track)
        bar = QColor(score_band(value * 100))
        bar.setAlphaF(0.75)
        painter.fillRect(rect.adjusted(0, 0, int(-rect.width() * (1 - max(0.0, min(1.0, value)))), 0), bar)
        painter.setPen(pal.color(QPalette.ColorRole.Text))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{value * 100:.0f}%")
        painter.restore()


def clear_layout(layout: QLayout) -> None:
    """Remove and delete every item of a layout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.deleteLater()


def heading_label(text: str, scale: float = 1.4) -> QLabel:
    label = QLabel(text)
    f = label.font()
    f.setBold(True)
    f.setPointSizeF(f.pointSizeF() * scale)
    label.setFont(f)
    return label


def empty_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    f = label.font()
    f.setPointSizeF(f.pointSizeF() * 1.3)
    label.setFont(f)
    label.setEnabled(False)  # palette's disabled text colour: muted on light and dark
    label.setObjectName("emptyState")
    return label
