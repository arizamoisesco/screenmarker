"""Modelo de datos y dibujado de las anotaciones."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
)


class Tool(str, Enum):
    PEN = "pen"
    HIGHLIGHTER = "highlighter"
    LINE = "line"
    ARROW = "arrow"
    RECT = "rect"
    ELLIPSE = "ellipse"
    TEXT = "text"
    ERASER = "eraser"
    LASER = "laser"


TOOL_LABELS: dict[Tool, str] = {
    Tool.PEN: "Lápiz",
    Tool.HIGHLIGHTER: "Resaltador",
    Tool.LINE: "Línea",
    Tool.ARROW: "Flecha",
    Tool.RECT: "Rectángulo",
    Tool.ELLIPSE: "Elipse",
    Tool.TEXT: "Texto",
    Tool.ERASER: "Borrador",
    Tool.LASER: "Láser",
}

HIGHLIGHTER_ALPHA = 90
HIGHLIGHTER_WIDTH_FACTOR = 4


@dataclass
class Annotation:
    """Una figura dibujada sobre la pantalla."""

    tool: Tool
    color: QColor
    width: int
    points: list[QPointF] = field(default_factory=list)
    text: str = ""
    filled: bool = False

    # ------------------------------------------------------------------ utils
    @property
    def start(self) -> QPointF:
        return self.points[0]

    @property
    def end(self) -> QPointF:
        return self.points[-1]

    def rect(self) -> QRectF:
        return QRectF(self.start, self.end).normalized()

    def font(self) -> QFont:
        font = QFont()
        font.setPointSizeF(max(10.0, 6.0 + self.width * 2.5))
        font.setBold(True)
        return font

    def pen(self) -> QPen:
        color = QColor(self.color)
        width = self.width
        if self.tool is Tool.HIGHLIGHTER:
            color.setAlpha(HIGHLIGHTER_ALPHA)
            width = self.width * HIGHLIGHTER_WIDTH_FACTOR
        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    # -------------------------------------------------------------- geometría
    def path(self) -> QPainterPath:
        path = QPainterPath()
        if not self.points:
            return path
        if self.tool in (Tool.PEN, Tool.HIGHLIGHTER):
            path.moveTo(self.points[0])
            for point in self.points[1:]:
                path.lineTo(point)
            if len(self.points) == 1:
                path.lineTo(self.points[0] + QPointF(0.1, 0.1))
        elif self.tool in (Tool.LINE, Tool.ARROW):
            path.moveTo(self.start)
            path.lineTo(self.end)
        elif self.tool is Tool.RECT:
            path.addRect(self.rect())
        elif self.tool is Tool.ELLIPSE:
            path.addEllipse(self.rect())
        elif self.tool is Tool.TEXT:
            metrics = QFontMetricsF(self.font())
            size = metrics.size(0, self.text or " ")
            path.addRect(QRectF(self.start, size))
        return path

    def bounding_rect(self) -> QRectF:
        margin = self.pen().widthF() + 4
        return self.path().boundingRect().adjusted(-margin, -margin, margin, margin)

    def hits(self, point: QPointF, tolerance: float = 8.0) -> bool:
        """True si el punto toca la figura (usado por el borrador)."""
        if self.tool is Tool.TEXT:
            return self.path().boundingRect().adjusted(-4, -4, 4, 4).contains(point)
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.pen().widthF(), 1.0) + tolerance * 2)
        return stroker.createStroke(self.path()).contains(point)

    # ---------------------------------------------------------------- dibujar
    def draw(self, painter: QPainter) -> None:
        if not self.points:
            return
        painter.save()
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        if self.tool is Tool.TEXT:
            self._draw_text(painter)
        elif self.tool is Tool.ARROW:
            painter.drawPath(self.path())
            self._draw_arrow_head(painter)
        else:
            if self.filled and self.tool in (Tool.RECT, Tool.ELLIPSE):
                fill = QColor(self.color)
                fill.setAlpha(70)
                painter.setBrush(QBrush(fill))
            painter.drawPath(self.path())
        painter.restore()

    def _draw_text(self, painter: QPainter) -> None:
        font = self.font()
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        origin = self.start + QPointF(0, metrics.ascent())
        # Contorno oscuro para que el texto se lea sobre cualquier fondo.
        outline = QPainterPath()
        outline.addText(origin, font, self.text)
        painter.setPen(QPen(QColor(0, 0, 0, 180), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(outline)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self.color))
        painter.drawPath(outline)

    def _draw_arrow_head(self, painter: QPainter) -> None:
        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        angle = math.atan2(dy, dx)
        head = max(12.0, self.width * 5.0)
        spread = math.radians(25)
        left = self.end - QPointF(
            math.cos(angle - spread) * head, math.sin(angle - spread) * head
        )
        right = self.end - QPointF(
            math.cos(angle + spread) * head, math.sin(angle + spread) * head
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self.color))
        painter.drawPolygon(QPolygonF([self.end, left, right]))
