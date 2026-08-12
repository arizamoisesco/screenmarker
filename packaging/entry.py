"""Punto de entrada usado por PyInstaller para generar el ejecutable."""

import sys

from screenmarker.app import main

if __name__ == "__main__":
    sys.exit(main())
