"""Conftest local para que TC-M09-G38 corra fuera del árbol `tests/integration/`.

Este test vive junto a la evidencia QA del caso (TC-M09-G38-resultados.md) en
vez de en `tests/integration/`, pero necesita los mismos fixtures reales que
usa el resto de la suite de integración (`db_session`, `crear_usuario_db`,
etc.) — pytest solo expone los fixtures de un `conftest.py` a los tests que
viven dentro de su mismo árbol de directorios, así que sin este archivo la
prueba falla con `fixture 'db_session' not found`.

En vez de duplicar esa lógica (sesión con savepoints sobre PostgreSQL real,
creación de usuarios de prueba, etc.), se carga el `conftest.py` real de
`tests/integration/` por ruta y se reexportan sus fixtures. Si ese archivo
cambia, este sigue funcionando sin tocarlo.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_RUTA_CONFTEST_INTEGRACION = Path(__file__).resolve().parents[4] / "integration" / "conftest.py"

_spec = importlib.util.spec_from_file_location("_conftest_integracion_rf18", _RUTA_CONFTEST_INTEGRACION)
_conftest_integracion = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_conftest_integracion)

# Reexportados para que pytest los descubra como fixtures de este conftest.
integration_engine = _conftest_integracion.integration_engine
db_session = _conftest_integracion.db_session
password_hash = _conftest_integracion.password_hash
crear_usuario_db = _conftest_integracion.crear_usuario_db
