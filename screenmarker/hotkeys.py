"""Atajos globales opcionales (funcionan aunque otra ventana tenga el foco).

Requiere `pynput`. Si no está instalado, la aplicación sigue funcionando con los
atajos normales de Qt (activos cuando ScreenMarker tiene el foco) y la barra.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

DEFAULT_BINDINGS = {
    "<ctrl>+<alt>+d": "toggle_passthrough",
    "<ctrl>+<alt>+c": "clear",
    "<ctrl>+<alt>+z": "undo",
    "<ctrl>+<alt>+y": "redo",
    "<ctrl>+<alt>+s": "screenshot",
    "<ctrl>+<alt>+b": "board",
    "<ctrl>+<alt>+q": "quit",
}


class GlobalHotkeys(QObject):
    """Publica una señal de Qt por cada atajo global detectado."""

    activated = Signal(str)

    def __init__(self, bindings: dict[str, str] | None = None) -> None:
        super().__init__()
        self.bindings = bindings or DEFAULT_BINDINGS
        self._listener = None
        self.error: str | None = None

    def start(self) -> bool:
        try:
            from pynput import keyboard  # import diferido: dependencia opcional
        except Exception as exc:  # pragma: no cover - depende del entorno
            self.error = f"pynput no disponible ({exc})"
            return False
        try:
            mapping = {
                combo: (lambda action=action: self.activated.emit(action))
                for combo, action in self.bindings.items()
            }
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.daemon = True
            self._listener.start()
            return True
        except Exception as exc:  # pragma: no cover - depende del entorno
            self.error = f"no se pudieron registrar los atajos globales ({exc})"
            self._listener = None
            return False

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
