"""Icono en la bandeja del sistema (área de notificación de Windows)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def build_icon() -> QIcon:
    """Icono dibujado en memoria: un trazo rojo sobre un cuadro oscuro."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor(24, 24, 28, 235))
    painter.setPen(QPen(QColor(255, 255, 255, 90), 3))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 14, 14)
    painter.setPen(QPen(QColor("#ff2d55"), 9, Qt.SolidLine, Qt.RoundCap))
    painter.drawPolyline(
        [QPointF(16, 44), QPointF(28, 22), QPointF(38, 40), QPointF(48, 20)]
    )
    painter.end()
    return QIcon(pixmap)


class Tray(QSystemTrayIcon):
    """Menú de acceso rápido cuando la barra está oculta."""

    toggle_toolbar_requested = Signal()
    passthrough_requested = Signal()
    board_requested = Signal()
    clear_requested = Signal()
    screenshot_requested = Signal()
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__(build_icon())
        self.setToolTip("ScreenMarker · clic para mostrar u ocultar la barra")

        menu = QMenu()
        self.toolbar_action = QAction("Mostrar barra", menu)
        self.toolbar_action.triggered.connect(self.toggle_toolbar_requested.emit)
        menu.addAction(self.toolbar_action)
        menu.addSeparator()
        for label, signal in (
            ("Pasar clics (Ctrl+Alt+D)", self.passthrough_requested),
            ("Pizarra (Ctrl+Alt+B)", self.board_requested),
            ("Limpiar (Ctrl+Alt+C)", self.clear_requested),
            ("Captura (Ctrl+Alt+S)", self.screenshot_requested),
        ):
            action = QAction(label, menu)
            action.triggered.connect(signal.emit)
            menu.addAction(action)
        menu.addSeparator()
        quit_action = QAction("Salir", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self._menu = menu  # el menú debe sobrevivir al constructor
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.Trigger,
            QSystemTrayIcon.DoubleClick,
            QSystemTrayIcon.MiddleClick,
        ):
            self.toggle_toolbar_requested.emit()

    def sync(self, toolbar_visible: bool) -> None:
        self.toolbar_action.setText("Ocultar barra" if toolbar_visible else "Mostrar barra")
