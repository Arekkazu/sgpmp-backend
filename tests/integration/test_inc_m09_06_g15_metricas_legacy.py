"""Integración INC-M09-06-G15: métricas RF-16 con tipo legado."""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
MIGRACION = (
    ROOT
    / "alembic"
    / "versions"
    / "9a5de7d9973f_v5_3_0_rf16_normalizar_tipos_medicion_.py"
)


class DependenciaActivaFake:
    def __init__(self, _db: Session) -> None:
        pass

    def tiene_dependencias_activas(self, _id_metrica_produccion: int) -> bool:
        return True


class AuditoriaNoEsperadaFake:
    def __init__(self, _db: Session) -> None:
        pass

    def registrar(self, **_kwargs) -> None:
        raise AssertionError("Una desactivación rechazada no debe auditar éxito")


def _cargar_migracion():
    spec = importlib.util.spec_from_file_location("migracion_rf16_g15", MIGRACION)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_migracion_normaliza_manual_y_endpoint_evalua_dependencias(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not inspect(db_session.bind).has_table("metricas_produccion", schema="modulo9"):
        pytest.skip("La base de integración no contiene modulo9.metricas_produccion.")

    db_session.execute(
        text(
            "ALTER TABLE modulo9.metricas_produccion "
            "DROP CONSTRAINT IF EXISTS chk_metricas_tipo_medicion"
        )
    )
    nombre = f"Metrica legacy G15 {uuid.uuid4().hex[:10]}"
    id_metrica = db_session.execute(
        text(
            """
            INSERT INTO modulo9.metricas_produccion (
                nombre, unidad_medida, tipo_medicion, tiene_estado,
                id_especie, aplica_a_tipo_activo, tipo_dato,
                es_obligatorio, es_activo
            ) VALUES (
                :nombre, 'g', 'manual', false,
                NULL, 'AMBOS', 'TEXTO', false, true
            )
            RETURNING id_metrica_produccion
            """
        ),
        {"nombre": nombre},
    ).scalar_one()
    db_session.execute(
        text(
            "ALTER TABLE modulo9.metricas_produccion "
            "ADD CONSTRAINT chk_metricas_tipo_medicion "
            "CHECK (tipo_medicion IN "
            "('PESO','VOLUMEN','LONGITUD','CONTEO','OTRO')) NOT VALID"
        )
    )

    migracion = _cargar_migracion()
    contexto = MigrationContext.configure(db_session.connection())
    with Operations.context(contexto):
        migracion.upgrade()

    fila = db_session.execute(
        text(
            "SELECT tipo_medicion, tipo_dato, es_activo "
            "FROM modulo9.metricas_produccion "
            "WHERE id_metrica_produccion=:id"
        ),
        {"id": id_metrica},
    ).one()
    constraint_validado = db_session.execute(
        text(
            "SELECT convalidated FROM pg_constraint "
            "WHERE conrelid='modulo9.metricas_produccion'::regclass "
            "AND conname='chk_metricas_tipo_medicion'"
        )
    ).scalar_one()

    assert fila.tipo_medicion == "PESO"
    assert fila.tipo_dato == "NUMERICO"
    assert fila.es_activo is True
    assert constraint_validado is True

    from src.configuration.infrastructure.routers import metrica_router as modulo_router
    from src.shared import rbac

    monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
    monkeypatch.setattr(
        modulo_router,
        "SqlAlchemyDependenciaMetricaRepository",
        DependenciaActivaFake,
    )
    monkeypatch.setattr(
        modulo_router,
        "SqlAlchemyAuditoriaMetricaRepository",
        AuditoriaNoEsperadaFake,
    )

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(modulo_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=1,
        id_token=1,
        id_rol=1,
        id_estado_cuenta=2,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.patch(f"/configuracion/metricas/{id_metrica}/desactivar")

    assert response.status_code == 422
    assert response.json()["error_code"] == "METRICA_CON_REGISTROS"
    assert db_session.execute(
        text(
            "SELECT es_activo FROM modulo9.metricas_produccion "
            "WHERE id_metrica_produccion=:id"
        ),
        {"id": id_metrica},
    ).scalar_one() is True
