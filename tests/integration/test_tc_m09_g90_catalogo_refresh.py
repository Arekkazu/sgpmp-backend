"""Regresión TC-M09-G90: catálogo requerido por POST /sesiones/refresh."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

MIGRACION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "d8e232bc81a3_v5_3_0_sesiones_catalogo_eventos_refresh.py"
)


def _cargar_migracion():
    spec = importlib.util.spec_from_file_location(
        "migracion_catalogo_refresh", MIGRACION
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_migracion_formaliza_catalogo_refresh_de_forma_idempotente(
    db_session: Session,
) -> None:
    migracion = _cargar_migracion()
    contexto = MigrationContext.configure(db_session.connection())

    with Operations.context(contexto):
        migracion.upgrade()
        migracion.upgrade()

    filas = db_session.execute(
        text(
            """
            SELECT id_tipo_evento, nombre, accion
            FROM modulo1.tipos_eventos
            WHERE id_tipo_evento IN (23, 24)
            ORDER BY id_tipo_evento
            """
        )
    ).mappings().all()

    assert [dict(fila) for fila in filas] == [
        {
            "id_tipo_evento": 23,
            "nombre": "REFRESH_TOKEN_ROTADO",
            "accion": "Renovacion de sesion via refresh token",
        },
        {
            "id_tipo_evento": 24,
            "nombre": "REUSO_TOKEN_REFRESCO_DETECTADO",
            "accion": "Reuso de refresh token detectado - sesion revocada",
        },
    ]
