"""Modo 'pasar clics' (click-through) dependiente del sistema operativo.

En Linux/X11 se usa la extensión XShape para vaciar la región de entrada de la
ventana; en Windows se activa el estilo extendido ``WS_EX_TRANSPARENT``. Si
ninguna de las dos vías está disponible, se devuelve ``False`` y la aplicación
usa el método genérico de Qt (recrear la ventana con
``Qt.WindowTransparentForInput``).
"""

from __future__ import annotations

import ctypes
import sys

_SHAPE_INPUT = 2
_SHAPE_SET = 0
_UNSORTED = 0

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000


class _XRectangle(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_short),
        ("y", ctypes.c_short),
        ("width", ctypes.c_ushort),
        ("height", ctypes.c_ushort),
    ]


class _X11ClickThrough:
    """Implementación con la extensión XShape de X11."""

    def __init__(self) -> None:
        self._x11 = ctypes.CDLL("libX11.so.6")
        self._xext = ctypes.CDLL("libXext.so.6")
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._display = self._x11.XOpenDisplay(None)
        if not self._display:
            raise RuntimeError("no se pudo abrir el display de X11")
        self._xext.XShapeCombineRectangles.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(_XRectangle),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]

    def apply(self, window_id: int, enabled: bool) -> None:
        if enabled:
            rectangles = (_XRectangle * 0)()
            count = 0
        else:
            rectangles = (_XRectangle * 1)(_XRectangle(0, 0, 65535, 65535))
            count = 1
        self._xext.XShapeCombineRectangles(
            self._display,
            ctypes.c_ulong(window_id),
            _SHAPE_INPUT,
            0,
            0,
            rectangles,
            count,
            _SHAPE_SET,
            _UNSORTED,
        )
        self._x11.XFlush(ctypes.c_void_p(self._display))


class _WindowsClickThrough:
    """Implementación con estilos extendidos de la API Win32."""

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        self._get = getattr(self._user32, "GetWindowLongPtrW", self._user32.GetWindowLongW)
        self._set = getattr(self._user32, "SetWindowLongPtrW", self._user32.SetWindowLongW)

    def apply(self, window_id: int, enabled: bool) -> None:
        handle = ctypes.c_void_p(window_id)
        style = self._get(handle, GWL_EXSTYLE)
        if enabled:
            style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            style &= ~WS_EX_TRANSPARENT
        self._set(handle, GWL_EXSTYLE, style)


def create_click_through():
    """Devuelve el ayudante nativo del sistema o ``None`` si no hay soporte."""
    try:
        if sys.platform.startswith("win"):
            return _WindowsClickThrough()
        if sys.platform.startswith("linux"):
            return _X11ClickThrough()
    except Exception:  # pragma: no cover - depende del entorno gráfico
        return None
    return None
