"""Conftest local para que TC-M09-G39 corra fuera del árbol `tests/integration/`.

Ver el mismo archivo en `TC-M09-G38/conftest.py`: reexporta por ruta los
fixtures reales de `tests/integration/conftest.py` (db_session,
crear_usuario_db, etc.) en vez de duplicarlos, porque pytest solo expone los
fixtures de un `conftest.py` a los tests dentro de su propio árbol.
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
