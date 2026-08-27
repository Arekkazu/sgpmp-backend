"""Integración RF-01: contrato HTTP y protección numérica en PostgreSQL."""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.repositories.usuario_repository import (
    SqlAlchemyUsuarioRepository,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
MIGRACION = (
    ROOT
    / "alembic"
    / "versions"
    / "e7b31f4a6c20_rf01_identificacion_numerica.py"
)


def _aplicar_migracion_si_falta(db_session: Session) -> None:
    existe = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM pg_trigger
            WHERE tgrelid='modulo1.usuarios'::regclass
              AND tgname='trg_validar_identificacion_numerica'
              AND NOT tgisinternal
            """
        )
    ).scalar_one()
    if existe:
        return

    spec = importlib.util.spec_from_file_location("migracion_rf01_id", MIGRACION)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    contexto = MigrationContext.configure(db_session.connection())
    with Operations.context(contexto):
        modulo.upgrade()


def _registro(**cambios) -> dict:
    sufijo = uuid.uuid4().hex
    datos = {
        "correo_electronico": f"rf01-{sufijo}@example.com",
        "telefono": "3001234567",
        "tipo_identificacion": "CC",
        "numero_identificacion": str(uuid.uuid4().int % 10**15).zfill(15),
        "nombre": "Registro",
        "apellidos": "Integración",
        "fecha_nacimiento": "1990-01-01",
        "genero": "M",
        "contrasena": "Segura1!",
        "confirmar_contrasena": "Segura1!",
        "direccion": "Dirección de prueba",
    }
    datos.update(cambios)
    return datos


@pytest.mark.parametrize(
    "cambio",
    [
        {"confirmar_contrasena": None},
        {"confirmar_contrasena": "Distinta2!"},
        {"numero_identificacion": "123-ABC"},
    ],
)
def test_registro_rechaza_confirmacion_o_identificacion_invalida(
    client,
    cambio: dict,
) -> None:
    datos = _registro(**cambio)
    if (
        "confirmar_contrasena" in cambio
        and cambio["confirmar_contrasena"] is None
    ):
        datos.pop("confirmar_contrasena")

    respuesta = client.post("/usuarios/", json=datos)

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "VAL_ENTRADA"


def test_registro_valido_responde_que_el_correo_esta_en_proceso(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.shared import notificacion_service

    monkeypatch.setattr(notificacion_service, "send_email", lambda **_datos: None)

    respuesta = client.post("/usuarios/", json=_registro())

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json() == {
        "message": "Registro exitoso, envío de correo en proceso."
    }


def test_migracion_protege_altas_sin_bloquear_filas_historicas(
    db_session: Session,
    crear_usuario_db,
) -> None:
    legado = crear_usuario_db(numero_identificacion=f"LEGACY-{uuid.uuid4().hex[:8]}")

    _aplicar_migracion_si_falta(db_session)

    trigger = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM pg_trigger
            WHERE tgrelid='modulo1.usuarios'::regclass
              AND tgname='trg_validar_identificacion_numerica'
              AND NOT tgisinternal
            """
        )
    ).scalar_one()
    assert trigger == 1

    usuario = SqlAlchemyUsuarioRepository(db_session).obtener_por_id(
        legado["id_usuario"]
    )
    usuario.nombre = "Legado Actualizado"
    actualizado = SqlAlchemyUsuarioRepository(db_session).actualizar(
        usuario,
        legado["version"],
    )
    assert actualizado.nombre == "Legado Actualizado"

    with pytest.raises(DBAPIError, match="numero_identificacion"):
        with db_session.begin_nested():
            crear_usuario_db(numero_identificacion=f"INVALIDO-{uuid.uuid4().hex[:8]}")

    db_session.expire_all()
    with pytest.raises(DBAPIError, match="numero_identificacion"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    UPDATE modulo1.usuarios
                    SET numero_identificacion=:numero
                    WHERE id_usuario=:usuario
                    """
                ),
                {
                    "numero": f"OTRO-{uuid.uuid4().hex[:8]}",
                    "usuario": legado["id_usuario"],
                },
            )

    db_session.expire_all()
    db_session.execute(
        text(
            """
            UPDATE modulo1.usuarios
            SET numero_identificacion=:numero
            WHERE id_usuario=:usuario
            """
        ),
        {
            "numero": str(uuid.uuid4().int % 10**15).zfill(15),
            "usuario": legado["id_usuario"],
        },
    )
    nuevo = crear_usuario_db()
    assert nuevo["id_usuario"] is not None
