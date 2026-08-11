"""Pruebas del modelo de anotaciones (se ejecutan con QT_QPA_PLATFORM=offscreen)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QGuiApplication

from screenmarker.model import Annotation, Tool


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


def line(tool: Tool = Tool.LINE) -> Annotation:
    return Annotation(
        tool=tool,
        color=QColor("#ff0000"),
        width=4,
        points=[QPointF(0, 0), QPointF(100, 0)],
    )


def test_rect_is_normalized():
    annotation = Annotation(
        tool=Tool.RECT,
        color=QColor("#ff0000"),
        width=2,
        points=[QPointF(100, 80), QPointF(20, 10)],
    )
    rect = annotation.rect()
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (20, 10, 80, 70)


def test_eraser_hit_detection():
    annotation = line()
    assert annotation.hits(QPointF(50, 2))
    assert not annotation.hits(QPointF(50, 200))


def test_highlighter_is_wider_and_translucent():
    pen = line(Tool.HIGHLIGHTER).pen()
    assert pen.widthF() > line().pen().widthF()
    assert pen.color().alpha() < 255


def test_pen_path_follows_every_point():
    annotation = Annotation(
        tool=Tool.PEN,
        color=QColor("#00ff00"),
        width=3,
        points=[QPointF(0, 0), QPointF(10, 10), QPointF(20, 0)],
    )
    assert annotation.path().elementCount() == 3
    assert annotation.bounding_rect().contains(QPointF(10, 10))


def test_text_bounding_rect_grows_with_content():
    short = Annotation(
        tool=Tool.TEXT, color=QColor("#fff"), width=4, points=[QPointF(0, 0)], text="a"
    )
    long = Annotation(
        tool=Tool.TEXT, color=QColor("#fff"), width=4, points=[QPointF(0, 0)], text="a" * 20
    )
    assert long.path().boundingRect().width() > short.path().boundingRect().width()
