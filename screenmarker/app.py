"""Punto de entrada de ScreenMarker: marcador para rayar la pantalla."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

from .hotkeys import GlobalHotkeys
from .model import Tool
from .overlay import Overlay
from .toolbar import PALETTE, TOOL_ORDER, Toolbar

APP_NAME = "ScreenMarker"


def default_screenshot_dir() -> Path:
    pictures = Path.home() / "Pictures"
    if not pictures.exists():
        pictures = Path.home() / "Imágenes"
    if not pictures.exists():
        pictures = Path.home()
    return pictures / "ScreenMarker"


class ScreenMarker:
    """Conecta la superposición de dibujo con la barra de herramientas."""

    def __init__(self, screenshot_dir: Path) -> None:
        self.screenshot_dir = screenshot_dir
        self.overlay = Overlay()
        self.toolbar = Toolbar()
        self.last_screenshot: Path | None = None

        self._connect_toolbar()
        self._register_shortcuts()
        self.overlay.state_changed.connect(self._sync)

        # Algunos gestores de ventanas colocan la ventana activa encima de la
        # superposición al hacer clic en modo "pasar clics"; este temporizador la
        # mantiene visible por encima del resto.
        self._keep_on_top = QTimer()
        self._keep_on_top.setInterval(700)
        self._keep_on_top.timeout.connect(self._raise_windows)
        self._keep_on_top.start()

        self.hotkeys = GlobalHotkeys()
        self.hotkeys.activated.connect(self._on_global_hotkey)
        self.hotkeys_enabled = self.hotkeys.start()

    # ------------------------------------------------------------ arranque
    def show(self) -> None:
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.toolbar.show()
        self.toolbar.raise_()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.toolbar.move(
            screen.right() - self.toolbar.width() - 24, screen.top() + 60
        )
        self._sync()

    def _raise_windows(self) -> None:
        if self.overlay.isVisible():
            self.overlay.raise_()
        if self.toolbar.isVisible():
            self.toolbar.raise_()

    # ------------------------------------------------------------ conexiones
    def _connect_toolbar(self) -> None:
        bar, overlay = self.toolbar, self.overlay
        bar.tool_selected.connect(overlay.set_tool)
        bar.color_selected.connect(overlay.set_color)
        bar.width_selected.connect(overlay.set_width)
        bar.filled_toggled.connect(overlay.set_filled)
        bar.undo_requested.connect(overlay.undo)
        bar.redo_requested.connect(overlay.redo)
        bar.clear_requested.connect(overlay.clear)
        bar.board_requested.connect(overlay.cycle_board)
        bar.screenshot_requested.connect(self.save_screenshot)
        bar.passthrough_requested.connect(overlay.toggle_passthrough)
        bar.quit_requested.connect(self.quit)

    def _register_shortcuts(self) -> None:
        bindings: list[tuple[str, object]] = [
            ("Ctrl+Z", self.overlay.undo),
            ("Ctrl+Y", self.overlay.redo),
            ("Ctrl+Shift+Z", self.overlay.redo),
            ("Ctrl+Alt+Z", self.overlay.undo),
            ("Ctrl+Alt+Y", self.overlay.redo),
            ("Ctrl+Alt+C", self.overlay.clear),
            ("Ctrl+Alt+D", self.overlay.toggle_passthrough),
            ("Ctrl+Alt+B", self.overlay.cycle_board),
            ("Ctrl+Alt+S", self.save_screenshot),
            ("Ctrl+Alt+Q", self.quit),
            ("B", self.overlay.cycle_board),
            ("F", self._toggle_fill),
            ("[", lambda: self._step_width(-1)),
            ("]", lambda: self._step_width(+1)),
        ]
        for tool, _label, key in TOOL_ORDER:
            bindings.append((key, lambda t=tool: self._select_tool(t)))
        for index, name in enumerate(PALETTE, start=1):
            if index <= 9:
                bindings.append((str(index), lambda c=name: self._select_color(QColor(c))))

        self._shortcuts = []
        for host in (self.overlay, self.toolbar):
            for sequence, handler in bindings:
                shortcut = QShortcut(QKeySequence(sequence), host)
                shortcut.setContext(Qt.ApplicationShortcut)
                shortcut.activated.connect(handler)
                self._shortcuts.append(shortcut)

    # --------------------------------------------------------------- acciones
    def _select_tool(self, tool: Tool) -> None:
        self.overlay.set_tool(tool)

    def _select_color(self, color: QColor) -> None:
        self.overlay.set_color(color)
        for index, name in enumerate(PALETTE):
            if QColor(name) == color:
                self.toolbar.color_group.button(index).setChecked(True)

    def _toggle_fill(self) -> None:
        self.toolbar.fill_button.toggle()

    def _step_width(self, delta: int) -> None:
        self.toolbar.width_slider.setValue(self.toolbar.width_slider.value() + delta)

    def save_screenshot(self) -> None:
        """Oculta la interfaz, captura la pantalla y vuelve a pintar las anotaciones."""
        toolbar_was_visible = self.toolbar.isVisible()
        self.overlay.hide()
        self.toolbar.hide()
        QApplication.processEvents()

        def grab() -> None:
            try:
                self.last_screenshot = self.overlay.save_screenshot(self.screenshot_dir)
            finally:
                self.overlay.show()
                self.overlay.raise_()
                if toolbar_was_visible:
                    self.toolbar.show()
                    self.toolbar.raise_()
                if self.last_screenshot is not None:
                    self.toolbar.status.setText(
                        f"Captura guardada en {self.last_screenshot}"
                    )

        QTimer.singleShot(300, grab)

    def _on_global_hotkey(self, action: str) -> None:
        handlers = {
            "toggle_passthrough": self.overlay.toggle_passthrough,
            "clear": self.overlay.clear,
            "undo": self.overlay.undo,
            "redo": self.overlay.redo,
            "board": self.overlay.cycle_board,
            "screenshot": self.save_screenshot,
            "quit": self.quit,
        }
        handler = handlers.get(action)
        if handler is not None:
            handler()

    def quit(self) -> None:
        self._keep_on_top.stop()
        self.hotkeys.stop()
        self.overlay.close()
        self.toolbar.close()
        QApplication.quit()

    # ----------------------------------------------------------------- estado
    def _sync(self) -> None:
        self.toolbar.sync(
            self.overlay.tool,
            self.overlay.color,
            self.overlay.passthrough,
            self.overlay.board_mode,
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="screenmarker",
        description="Marcador para rayar la pantalla sobre cualquier ventana "
        "(Linux y Windows).",
    )
    parser.add_argument("--color", default="#ff2d55", help="color inicial (hex o nombre)")
    parser.add_argument("--width", type=int, default=4, help="grosor inicial del trazo")
    parser.add_argument(
        "--tool",
        default="pen",
        choices=[tool.value for tool in Tool],
        help="herramienta inicial",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=default_screenshot_dir(),
        help="carpeta donde se guardan las capturas",
    )
    parser.add_argument(
        "--passthrough",
        action="store_true",
        help="iniciar en modo 'pasar clics' (sin capturar el mouse)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    marker = ScreenMarker(args.screenshot_dir)
    marker.overlay.set_color(QColor(args.color))
    marker.overlay.set_width(args.width)
    marker.overlay.set_tool(Tool(args.tool))
    marker.toolbar.width_slider.setValue(args.width)
    marker.show()
    if args.passthrough:
        marker.overlay.set_passthrough(True)
    if not marker.hotkeys_enabled:
        marker.toolbar.status.setText(
            "Atajos globales inactivos (instala pynput). Usa la barra o el modo dibujo."
        )
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
