#!/usr/bin/env bash
# Inicia ScreenMarker creando el entorno virtual la primera vez.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
    ./.venv/bin/pip install --upgrade pip
    ./.venv/bin/pip install -r requirements.txt
fi

exec ./.venv/bin/python -m screenmarker "$@"
