"""Integración PostgreSQL de INC-M02-82-G102 / TC-M02-261.

La prueba omite ``fecha`` como la colección QA y mantiene una transacción
exterior. Esto reproduce el desfase entre el reloj de Python y el
``CURRENT_TIMESTAMP`` fijado al inicio de la transacción. El fixture revierte
todas las escrituras al finalizar.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

import src.identity_access.infrastructure.models  # noqa: F401
from src.biological_assets.infrastructure.routers import activo_biologico_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


def _aplicar_migracion_en_transaccion(db_session: Session) -> ModuleType:
    ruta = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "d6a8f2c941b7_v5_2_0_rf41_reloj_eventos_activos.py"
    )
    spec = importlib.util.spec_from_file_location("migration_rf41_g102", ruta)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = Operations(MigrationContext.configure(db_session.connection()))
    migration.upgrade()
    return migration


def _definiciones_temporales(db_session: Session) -> tuple[str, str]:
    funcion = db_session.execute(
        text(
            "SELECT pg_get_functiondef("
            "'modulo2.trg_fn_evento_fecha_coherente()'::regprocedure)"
        )
    ).scalar_one()
    constraint = db_session.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'modulo2.eventos_activos'::regclass
              AND conname = 'chk_eventos_fecha_no_futura'
            """
        )
    ).scalar_one()
    return funcion, constraint


def test_migracion_rf41_es_reversible(db_session: Session) -> None:
    migration = _aplicar_migracion_en_transaccion(db_session)
    funcion, constraint = _definiciones_temporales(db_session)
    assert "clock_timestamp()" in funcion
    assert "clock_timestamp()" in constraint

    migration.downgrade()
    funcion, constraint = _definiciones_temporales(db_session)
    assert "clock_timestamp()" not in funcion
    assert "clock_timestamp()" not in constraint
    assert "now()" in funcion
    assert "now()" in constraint


def test_tc_m02_261_control_preventivo_valido_responde_201_y_se_audita(
    db_session: Session,
) -> None:
    _aplicar_migracion_en_transaccion(db_session)
    funcion, constraint = _definiciones_temporales(db_session)
    assert "clock_timestamp()" in funcion
    assert "clock_timestamp()" in constraint

    administrador = db_session.execute(
        text(
            """
            SELECT u.id_usuario, r.id_rol
            FROM modulo1.usuarios u
            JOIN modulo1.roles r ON r.id_rol = u.id_rol
            WHERE lower(r.nombre_rol) = 'administrador'
            ORDER BY u.id_usuario
            LIMIT 1
            """
        )
    ).one()
    id_activo = db_session.execute(
        text(
            """
            SELECT a.id_activo_biologico
            FROM modulo2.activos_biologicos a
            JOIN modulo2.estados_activos_biologicos e
              ON e.id_estado_activo_biologico = a.id_estado
            WHERE upper(e.nombre) IN ('ACTIVO', 'EN_TRATAMIENTO', 'AISLADO')
              AND a.fecha_creacion <= CURRENT_TIMESTAMP
            ORDER BY a.id_activo_biologico
            LIMIT 1
            """
        )
    ).scalar_one()

    def cantidad_eventos() -> int:
        return db_session.execute(
            text(
                """
                SELECT count(*)
                FROM modulo2.eventos_sanitarios es
                JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
                WHERE ea.id_activo_biologico = :id_activo
                """
            ),
            {"id_activo": id_activo},
        ).scalar_one()

    def cantidad_auditorias() -> int:
        return db_session.execute(
            text(
                """
                SELECT count(*)
                FROM modulo2.bitacora_auditoria_m02
                WHERE id_activo_biologico = :id_activo
                  AND rf_origen = 'RF41'
                  AND tipo_evento = 'EVENTO_SANITARIO_REGISTRADO'
                  AND resultado = 'EXITOSO'
                """
            ),
            {"id_activo": id_activo},
        ).scalar_one()

    eventos_antes = cantidad_eventos()
    auditorias_antes = cantidad_auditorias()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(activo_biologico_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=administrador.id_usuario,
        id_token=1,
        id_rol=administrador.id_rol,
        id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.post(
            f"/activos-biologicos/{id_activo}/eventos/sanitario",
            json={
                "tipo": "CONTROL_PREVENTIVO",
                "observaciones": (
                    "TC-M02-G102 - revision rutinaria "
                    "(prueba QA de clasificacion)"
                ),
            },
        )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["cambio_estado"] is None
    assert cuerpo["evento"]["id_activo_biologico"] == id_activo
    assert cuerpo["evento"]["sanitario"]["tipo"] == "CONTROL_PREVENTIVO"
    assert cantidad_eventos() == eventos_antes + 1
    assert cantidad_auditorias() == auditorias_antes + 1

    with pytest.raises(DBAPIError) as exc_info:
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    INSERT INTO modulo2.eventos_activos (
                        id_activo_biologico, fecha, descripcion, id_usuario
                    ) VALUES (
                        :id_activo, clock_timestamp() + interval '1 day',
                        'Fecha futura G102', :id_usuario
                    )
                    """
                ),
                {
                    "id_activo": id_activo,
                    "id_usuario": administrador.id_usuario,
                },
            )

    assert exc_info.value.orig.pgcode == "P0215"

    auditoria = db_session.execute(
        text(
            """
            SELECT clasificacion_biologica, severidad_log, detalle_tecnico
            FROM modulo2.bitacora_auditoria_m02
            WHERE id_activo_biologico = :id_activo
              AND rf_origen = 'RF41'
              AND tipo_evento = 'EVENTO_SANITARIO_REGISTRADO'
            ORDER BY id_bitacora DESC
            LIMIT 1
            """
        ),
        {"id_activo": id_activo},
    ).one()
    assert auditoria.clasificacion_biologica == "SANITARIO"
    assert auditoria.severidad_log == "INFO"
    assert auditoria.detalle_tecnico["tipo_sanitario"] == "CONTROL_PREVENTIVO"
