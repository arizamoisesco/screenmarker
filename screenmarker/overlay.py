"""Ventana transparente a pantalla completa donde se dibujan las anotaciones."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import QLineEdit, QWidget

from .model import Annotation, Tool
from .passthrough import create_click_through

BOARD_MODES = ("off", "dark", "light")
BOARD_COLORS = {
    "off": QColor(0, 0, 0, 0),
    "dark": QColor(18, 18, 22, 235),
    "light": QColor(248, 248, 248, 240),
}
LASER_LIFETIME = 0.8  # segundos que dura el rastro del puntero láser
# Fondo prácticamente invisible: Windows no repinta de forma fiable una ventana
# por capas cuyo contenido es 100 % transparente, así que los trazos solo se veían
# con la pizarra encendida. Con alfa 1 la ventana siempre tiene contenido.
CANVAS_FILL = QColor(0, 0, 0, 1)


def virtual_geometry() -> QRect:
    """Rectángulo que cubre todos los monitores conectados."""
    geometry = QRect()
    for screen in QGuiApplication.screens():
        geometry = geometry.united(screen.geometry())
    return geometry


class Overlay(QWidget):
    """Lienzo transparente siempre encima del resto de ventanas."""

    state_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ScreenMarker")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.items: list[Annotation] = []
        self.redo_stack: list[Annotation] = []
        self.current: Annotation | None = None
        self.tool: Tool = Tool.PEN
        self.color: QColor = QColor("#ff2d55")
        self.width: int = 4
        self.filled: bool = False
        self.board_mode: str = "off"
        self.passthrough: bool = False

        self._laser: list[tuple[QPointF, float]] = []
        self._laser_timer = QTimer(self)
        self._laser_timer.setInterval(30)
        self._laser_timer.timeout.connect(self._tick_laser)

        self._editor: QLineEdit | None = None
        self._click_through = create_click_through()
        self._apply_window_flags()
        self.setGeometry(virtual_geometry())
        self._update_cursor()

    # ------------------------------------------------------------- ventana
    def _apply_window_flags(self) -> None:
        flags = (
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        if self.passthrough and self._click_through is None:
            # Sin soporte nativo hay que recrear la ventana para ignorar el mouse.
            flags |= Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()
            self.raise_()

    def _apply_click_through(self) -> None:
        if self._click_through is None:
            self._apply_window_flags()
            self.setGeometry(virtual_geometry())
            self.show()
            return
        self.setAttribute(Qt.WA_TransparentForMouseEvents, self.passthrough)
        try:
            self._click_through.apply(int(self.winId()), self.passthrough)
        except Exception:  # pragma: no cover - depende del entorno gráfico
            self._click_through = None
            self._apply_window_flags()
            self.show()

    def set_passthrough(self, enabled: bool) -> None:
        """Activa/desactiva el modo 'pasar clics' (las anotaciones siguen visibles)."""
        if enabled == self.passthrough:
            return
        self.passthrough = enabled
        self._commit_editor()
        self.current = None
        self._apply_click_through()
        self.show()
        self.raise_()
        if not enabled:
            self.activateWindow()
            self.setFocus(Qt.OtherFocusReason)
        self._update_cursor()
        self.update()
        self.state_changed.emit()

    def toggle_passthrough(self) -> None:
        self.set_passthrough(not self.passthrough)

    def _update_cursor(self) -> None:
        if self.tool is Tool.ERASER:
            self.setCursor(Qt.PointingHandCursor)
        elif self.tool is Tool.TEXT:
            self.setCursor(Qt.IBeamCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    # ----------------------------------------------------- estado / opciones
    def set_tool(self, tool: Tool) -> None:
        self._commit_editor()
        self.tool = tool
        if tool is Tool.LASER:
            self._laser_timer.start()
        else:
            self._laser_timer.stop()
            self._laser.clear()
        self.set_passthrough(False)
        self._update_cursor()
        self.update()
        self.state_changed.emit()

    def set_color(self, color: QColor) -> None:
        self.color = QColor(color)
        self.state_changed.emit()

    def set_width(self, width: int) -> None:
        self.width = max(1, int(width))
        self.state_changed.emit()

    def set_filled(self, filled: bool) -> None:
        self.filled = bool(filled)
        self.state_changed.emit()

    def cycle_board(self) -> None:
        index = (BOARD_MODES.index(self.board_mode) + 1) % len(BOARD_MODES)
        self.board_mode = BOARD_MODES[index]
        if self.board_mode != "off":
            self.set_passthrough(False)
        self.update()
        self.state_changed.emit()

    # ---------------------------------------------------------- histórico
    def _push(self, annotation: Annotation) -> None:
        self.items.append(annotation)
        self.redo_stack.clear()
        self.update()
        self.state_changed.emit()

    def undo(self) -> None:
        if self.items:
            self.redo_stack.append(self.items.pop())
            self.update()
            self.state_changed.emit()

    def redo(self) -> None:
        if self.redo_stack:
            self.items.append(self.redo_stack.pop())
            self.update()
            self.state_changed.emit()

    def clear(self) -> None:
        if self.items:
            self.redo_stack = list(reversed(self.items))
            self.items = []
            self.update()
            self.state_changed.emit()

    # ------------------------------------------------------------- dibujado
    def paintEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        if self.board_mode == "off":
            painter.fillRect(self.rect(), CANVAS_FILL)
        else:
            painter.fillRect(self.rect(), BOARD_COLORS[self.board_mode])
        self.render_annotations(painter)
        self._draw_laser(painter)

    def render_annotations(self, painter: QPainter) -> None:
        for item in self.items:
            item.draw(painter)
        if self.current is not None:
            self.current.draw(painter)

    def _draw_laser(self, painter: QPainter) -> None:
        if not self._laser:
            return
        now = time.monotonic()
        painter.save()
        for point, created in self._laser:
            age = (now - created) / LASER_LIFETIME
            if age >= 1:
                continue
            alpha = int(220 * (1 - age))
            radius = max(3.0, self.width * 2.0 * (1 - age * 0.5))
            glow = QColor(255, 40, 40, max(0, alpha // 3))
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(point, radius * 2.5, radius * 2.5)
            painter.setBrush(QColor(255, 80, 80, alpha))
            painter.drawEllipse(point, radius, radius)
        painter.restore()

    def _tick_laser(self) -> None:
        now = time.monotonic()
        self._laser = [p for p in self._laser if now - p[1] < LASER_LIFETIME]
        if self.tool is Tool.LASER:
            self.update()

    # ----------------------------------------------------------- mouse/teclas
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        position = QPointF(event.position())
        self._commit_editor()
        if self.tool is Tool.ERASER:
            self._erase_at(position)
            return
        if self.tool is Tool.LASER:
            self._laser.append((position, time.monotonic()))
            return
        if self.tool is Tool.TEXT:
            self._start_editor(position)
            return
        self.current = Annotation(
            tool=self.tool,
            color=QColor(self.color),
            width=self.width,
            points=[position, position],
            filled=self.filled,
        )
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        position = QPointF(event.position())
        if self.tool is Tool.LASER:
            self._laser.append((position, time.monotonic()))
            self.update()
            return
        if not (event.buttons() & Qt.LeftButton):
            return
        if self.tool is Tool.ERASER:
            self._erase_at(position)
            return
        if self.current is None:
            return
        if self.current.tool in (Tool.PEN, Tool.HIGHLIGHTER):
            self.current.points.append(position)
        else:
            self.current.points[-1] = position
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or self.current is None:
            return
        annotation = self.current
        self.current = None
        if annotation.tool in (Tool.PEN, Tool.HIGHLIGHTER):
            if len(annotation.points) >= 2:
                self._push(annotation)
        elif (annotation.end - annotation.start).manhattanLength() > 3:
            self._push(annotation)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            if self._editor is not None:
                self._cancel_editor()
            else:
                self.set_passthrough(True)
            return
        super().keyPressEvent(event)

    def _erase_at(self, position: QPointF) -> None:
        for index in range(len(self.items) - 1, -1, -1):
            if self.items[index].hits(position):
                self.redo_stack.append(self.items.pop(index))
                self.update()
                self.state_changed.emit()
                return

    # ---------------------------------------------------------------- texto
    def _start_editor(self, position: QPointF) -> None:
        annotation = Annotation(
            tool=Tool.TEXT, color=QColor(self.color), width=self.width, points=[position]
        )
        editor = QLineEdit(self)
        editor.setFont(annotation.font())
        color = self.color.name()
        editor.setStyleSheet(
            f"QLineEdit {{ background: rgba(0,0,0,140); border: 1px dashed {color};"
            f" color: {color}; padding: 2px; }}"
        )
        editor.move(QPoint(int(position.x()), int(position.y())))
        editor.setMinimumWidth(220)
        editor.returnPressed.connect(self._commit_editor)
        editor.show()
        editor.setFocus(Qt.OtherFocusReason)
        editor.setProperty("annotation_x", position.x())
        editor.setProperty("annotation_y", position.y())
        self._editor = editor
        self._editor_annotation = annotation

    def _commit_editor(self) -> None:
        editor, self._editor = self._editor, None
        if editor is None:
            return
        text = editor.text().strip()
        editor.deleteLater()
        if text:
            self._editor_annotation.text = text
            self._push(self._editor_annotation)

    def _cancel_editor(self) -> None:
        editor, self._editor = self._editor, None
        if editor is not None:
            editor.deleteLater()
        self.update()

    # ------------------------------------------------------------- captura
    def grab_screenshot(self) -> QImage:
        """Compone la pantalla real con las anotaciones dibujadas encima."""
        geometry = virtual_geometry()
        image = QImage(geometry.size(), QImage.Format_ARGB32)
        image.fill(Qt.black)
        painter = QPainter(image)
        for screen in QGuiApplication.screens():
            pixmap = screen.grabWindow(0)
            target = screen.geometry().topLeft() - geometry.topLeft()
            painter.drawPixmap(target, pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.translate(-geometry.topLeft())
        if self.board_mode != "off":
            painter.fillRect(QRectF(geometry), BOARD_COLORS[self.board_mode])
        self.render_annotations(painter)
        painter.end()
        return image

    def save_screenshot(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"screenmarker-{time.strftime('%Y%m%d-%H%M%S')}.png"
        image = self.grab_screenshot()
        image.save(str(path), "PNG")
        QGuiApplication.clipboard().setImage(image)
        return path
