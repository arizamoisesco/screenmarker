"""Punto de entrada usado por PyInstaller para generar el ejecutable.

Además de arrancar la aplicación, deja constancia de cualquier fallo: el
ejecutable se abre sin consola, así que sin esto un error de arranque solo
muestra el cuadro genérico de PyInstaller y no se puede diagnosticar.
"""

from __future__ import annotations

import ctypes
import datetime as dt
import os
import sys
import traceback
from pathlib import Path

APP_NAME = "ScreenMarker"


def log_file() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
    else:
        base = Path.home() / ".local" / "state" / "screenmarker"
    base.mkdir(parents=True, exist_ok=True)
    return base / "screenmarker.log"


def report(error: BaseException) -> None:
    detail = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    destination: Path | None = None
    try:
        destination = log_file()
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(f"\n=== {dt.datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
            handle.write(f"python={sys.version} platform={sys.platform}\n")
            handle.write(detail)
    except Exception:  # el log es opcional, nunca debe tapar el error original
        destination = None

    message = detail.strip().splitlines()[-1] if detail.strip() else str(error)
    if destination is not None:
        message += f"\n\nDetalle completo en:\n{destination}"
    if sys.platform.startswith("win"):
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            None, message, f"{APP_NAME}: error al iniciar", 0x10
        )
    else:
        print(detail, file=sys.stderr)


def run() -> int:
    from screenmarker.app import main

    return main()


if __name__ == "__main__":
    try:
        sys.exit(run())
    except SystemExit:
        raise
    except BaseException as error:  # noqa: BLE001 - se registra y se muestra
        report(error)
        sys.exit(1)
