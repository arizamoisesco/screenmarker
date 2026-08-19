"""Barra de herramientas flotante de ScreenMarker."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .model import TOOL_LABELS, Tool

PALETTE = [
    "#ff2d55",
    "#ffcc00",
    "#34c759",
    "#0a84ff",
    "#af52de",
    "#ff9f0a",
    "#ffffff",
    "#000000",
]

TOOL_ORDER = [
    (Tool.PEN, "Lápiz", "P"),
    (Tool.HIGHLIGHTER, "Resaltador", "H"),
    (Tool.LINE, "Línea", "L"),
    (Tool.ARROW, "Flecha", "A"),
    (Tool.RECT, "Rectángulo", "R"),
    (Tool.ELLIPSE, "Elipse", "E"),
    (Tool.TEXT, "Texto", "T"),
    (Tool.ERASER, "Borrador", "X"),
    (Tool.LASER, "Láser", "G"),
]

STYLE = """
QWidget#panel {
    background: rgba(24, 24, 28, 240);
    border: 1px solid rgba(255, 255, 255, 40);
    border-radius: 10px;
}
QLabel { color: #f2f2f7; font-size: 11px; }
QLabel#title { font-weight: bold; font-size: 12px; }
QPushButton {
    color: #f2f2f7;
    background: rgba(255, 255, 255, 18);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}
QPushButton:hover { background: rgba(255, 255, 255, 45); }
QPushButton:checked {
    background: #0a84ff;
    border: 1px solid #66b8ff;
    font-weight: bold;
}
QPushButton#swatch { border-radius: 11px; padding: 0px; }
QPushButton#swatch:checked { border: 2px solid #ffffff; }
QPushButton#danger:hover { background: #ff3b30; }
QSlider::groove:horizontal {
    height: 4px; background: rgba(255,255,255,60); border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #f2f2f7; width: 12px; margin: -5px 0; border-radius: 6px;
}
"""


class Toolbar(QWidget):
    """Panel flotante con las herramientas, colores y acciones."""

    tool_selected = Signal(object)
    color_selected = Signal(QColor)
    width_selected = Signal(int)
    filled_toggled = Signal(bool)
    undo_requested = Signal()
    redo_requested = Signal()
    clear_requested = Signal()
    board_requested = Signal()
    screenshot_requested = Signal()
    passthrough_requested = Signal()
    hide_requested = Signal()
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ScreenMarker · Herramientas")
        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if sys.platform.startswith("linux"):
            # KWin y otros gestores ocultan las ventanas de utilidad cuando la
            # aplicación deja de estar activa: al ignorar el gestor la barra
            # permanece siempre visible sobre las demás ventanas.
            flags |= Qt.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(STYLE)
        self._drag_offset: QPoint | None = None
        self._build()

    # ------------------------------------------------------------ interfaz
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Sin esto la ventana conserva su tamaño aunque se oculte contenido.
        outer.setSizeConstraint(QLayout.SetFixedSize)

        panel = QWidget(self)
        panel.setObjectName("panel")
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("✎ ScreenMarker")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        minimize = QPushButton("–")
        minimize.setFixedWidth(26)
        minimize.setToolTip(
            "Ocultar la barra (Ctrl+Alt+M).\n"
            "Vuelve a mostrarla desde el icono de ScreenMarker en la bandeja del sistema."
        )
        minimize.clicked.connect(self.hide_requested.emit)
        header.addWidget(minimize)
        close = QPushButton("✕")
        close.setObjectName("danger")
        close.setFixedWidth(26)
        close.setToolTip("Salir (Ctrl+Alt+Q)")
        close.clicked.connect(self.quit_requested.emit)
        header.addWidget(close)
        layout.addLayout(header)

        self.body = QWidget(panel)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        layout.addWidget(self.body)

        # Herramientas
        tools = QGridLayout()
        tools.setSpacing(4)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for index, (tool, label, key) in enumerate(TOOL_ORDER):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setToolTip(f"{TOOL_LABELS[tool]} ({key})")
            button.clicked.connect(lambda _=False, t=tool: self.tool_selected.emit(t))
            self.tool_group.addButton(button, index)
            tools.addWidget(button, index // 3, index % 3)
        self.tool_group.button(0).setChecked(True)
        body_layout.addLayout(tools)

        body_layout.addWidget(self._separator())

        # Colores
        colors = QGridLayout()
        colors.setSpacing(4)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for index, name in enumerate(PALETTE):
            swatch = QPushButton()
            swatch.setObjectName("swatch")
            swatch.setCheckable(True)
            swatch.setFixedSize(22, 22)
            swatch.setStyleSheet(
                f"QPushButton#swatch {{ background: {name};"
                " border: 1px solid rgba(255,255,255,60); border-radius: 11px; }"
                "QPushButton#swatch:checked { border: 3px solid #ffffff; }"
            )
            swatch.setToolTip(f"Color {name} ({index + 1})")
            swatch.clicked.connect(
                lambda _=False, c=name: self.color_selected.emit(QColor(c))
            )
            self.color_group.addButton(swatch, index)
            colors.addWidget(swatch, index // 4, index % 4)
        self.color_group.button(0).setChecked(True)
        body_layout.addLayout(colors)

        custom = QPushButton("Color personalizado…")
        custom.clicked.connect(self._pick_color)
        body_layout.addWidget(custom)

        # Grosor
        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("Grosor"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 24)
        self.width_slider.setValue(4)
        self.width_slider.valueChanged.connect(self.width_selected.emit)
        self.width_slider.valueChanged.connect(
            lambda value: self.width_value.setText(str(value))
        )
        width_row.addWidget(self.width_slider, 1)
        self.width_value = QLabel("4")
        self.width_value.setFixedWidth(18)
        width_row.addWidget(self.width_value)
        body_layout.addLayout(width_row)

        self.fill_button = QPushButton("Relleno de figuras")
        self.fill_button.setCheckable(True)
        self.fill_button.setToolTip("Rellenar rectángulos y elipses (F)")
        self.fill_button.toggled.connect(self.filled_toggled.emit)
        body_layout.addWidget(self.fill_button)

        body_layout.addWidget(self._separator())

        # Acciones
        actions = QGridLayout()
        actions.setSpacing(4)
        buttons = [
            ("Deshacer", "Ctrl+Z", self.undo_requested),
            ("Rehacer", "Ctrl+Y", self.redo_requested),
            ("Limpiar", "Ctrl+Alt+C", self.clear_requested),
            ("Pizarra", "B", self.board_requested),
            ("Captura", "Ctrl+Alt+S", self.screenshot_requested),
        ]
        for index, (label, shortcut, signal) in enumerate(buttons):
            button = QPushButton(label)
            button.setToolTip(f"{label} ({shortcut})")
            button.clicked.connect(signal.emit)
            actions.addWidget(button, index // 2, index % 2)
        body_layout.addLayout(actions)

        self.passthrough_button = QPushButton("Pasar clics (Ctrl+Alt+D)")
        self.passthrough_button.setCheckable(True)
        self.passthrough_button.setToolTip(
            "Deja de capturar el mouse para usar la aplicación de abajo.\n"
            "Las anotaciones siguen visibles."
        )
        self.passthrough_button.clicked.connect(self.passthrough_requested.emit)
        body_layout.addWidget(self.passthrough_button)

        self.status = QLabel("Modo dibujo · Lápiz")
        self.status.setWordWrap(True)
        body_layout.addWidget(self.status)

        self.adjustSize()

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(255,255,255,40);")
        return line

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(parent=self, title="Elige un color")
        if color.isValid():
            for button in self.color_group.buttons():
                button.setChecked(False)
            self.color_selected.emit(color)

    # ------------------------------------------------------------- estado
    def sync(self, tool: Tool, color: QColor, passthrough: bool, board_mode: str) -> None:
        for index, (candidate, _, _) in enumerate(TOOL_ORDER):
            if candidate is tool:
                self.tool_group.button(index).setChecked(True)
        self.passthrough_button.setChecked(passthrough)
        modo = "Pasar clics" if passthrough else "Modo dibujo"
        pizarra = {"off": "", "dark": " · Pizarra oscura", "light": " · Pizarra clara"}
        self.status.setText(
            f"{modo} · {TOOL_LABELS[tool]} · {color.name()}{pizarra[board_mode]}"
        )

    # -------------------------------------------------------------- arrastre
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
