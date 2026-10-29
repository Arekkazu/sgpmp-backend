#!/usr/bin/env bash
# Genera la documentación HTML del código (pdoc, a partir de los docstrings) en docs/.
# El HTML no se versiona (.gitignore): pesa más de 100 MB y cambia con cada commit.
# Uso: scripts/generar_docs.sh [opciones de pdoc]   (p. ej. --no-show-source)
set -euo pipefail
cd "$(dirname "$0")/.."

PDOC="${PDOC:-.venv/bin/pdoc}"
if [ ! -x "$PDOC" ]; then
  echo "No se encontró pdoc. Instálalo con: .venv/bin/pip install pdoc==16.0.0" >&2
  exit 1
fi

rm -rf docs/src docs/src.html docs/index.html docs/search.js
# pdoc importa cada módulo y la app exige estas variables al importar; no se conecta a nada.
DATABASE_URL="postgresql://docs:docs@127.0.0.1:1/docs" \
SECRET_KEY="solo-para-generar-docs" \
  "$PDOC" ./src -o docs "$@"

echo "Listo: abre docs/index.html"
