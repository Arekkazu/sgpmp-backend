"""Integración RF-01: contrato HTTP y protección numérica en PostgreSQL."""
from __future__ import annotations

import importlib.util
import uuid
from contextlib import contextmanager
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
        {"tipo_identificacion": "Pasaporte", "numero_identificacion": "AB-123"},
        {"tipo_identificacion": "NIT"},
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


def test_registro_acepta_pasaporte_alfanumerico(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.shared import notificacion_service

    monkeypatch.setattr(notificacion_service, "send_email", lambda **_datos: None)

    respuesta = client.post(
        "/usuarios/",
        json=_registro(
            tipo_identificacion="Pasaporte",
            numero_identificacion=f"AB{uuid.uuid4().hex[:10].upper()}",
        ),
    )

    assert respuesta.status_code == 201, respuesta.text


def _sin_trigger(db_session: Session):
    """Contexto que desactiva el trigger para simular datos heredados.

    Las filas incompatibles de DEV son anteriores a la migración; aquí no se
    pueden insertar de otro modo porque el trigger ya está instalado. El
    ``ALTER TABLE`` vive dentro de la transacción de la prueba, que hace
    rollback al terminar.
    """

    @contextmanager
    def _ctx():
        db_session.execute(
            text(
                "ALTER TABLE modulo1.usuarios "
                "DISABLE TRIGGER trg_validar_identificacion_numerica"
            )
        )
        try:
            yield
        finally:
            db_session.execute(
                text(
                    "ALTER TABLE modulo1.usuarios "
                    "ENABLE TRIGGER trg_validar_identificacion_numerica"
                )
            )

    return _ctx()


def test_migracion_protege_altas_sin_bloquear_filas_historicas(
    db_session: Session,
    crear_usuario_db,
) -> None:
    _aplicar_migracion_si_falta(db_session)

    with _sin_trigger(db_session):
        legado = crear_usuario_db(
            numero_identificacion=f"LEGACY-{uuid.uuid4().hex[:8]}"
        )

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

    # Cambiar solo el tipo también dispara la validación: el número heredado
    # no es válido bajo la regla de pasaporte (contiene guiones).
    db_session.expire_all()
    with pytest.raises(DBAPIError, match="numero_identificacion"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    UPDATE modulo1.usuarios
                    SET tipo_identificacion='Pasaporte'
                    WHERE id_usuario=:usuario
                    """
                ),
                {"usuario": legado["id_usuario"]},
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


def test_trigger_admite_pasaporte_alfanumerico_y_rechaza_cc_con_letras(
    db_session: Session,
) -> None:
    """La regla de BD depende del tipo, igual que la de la aplicación."""
    _aplicar_migracion_si_falta(db_session)

    def insertar(tipo: str, numero: str) -> None:
        db_session.execute(
            text(
                """
                INSERT INTO modulo1.usuarios (
                    tipo_identificacion, numero_identificacion, nombre, apellidos,
                    fecha_nacimiento, genero, correo_electronico,
                    contrasena_cifrada, telefono, direccion, id_rol
                ) VALUES (
                    :tipo, :numero, 'Trigger', 'Prueba', '1990-01-01',
                    CAST('M' AS modulo1.enum_usuario_genero), :correo,
                    'x', '3001234567', 'Direccion', 2
                )
                """
            ),
            {
                "tipo": tipo,
                "numero": numero,
                "correo": f"trg-{uuid.uuid4().hex}@example.com",
            },
        )

    with db_session.begin_nested():
        insertar("Pasaporte", f"AB{uuid.uuid4().hex[:10].upper()}")

    with pytest.raises(DBAPIError, match="numero_identificacion"):
        with db_session.begin_nested():
            insertar("CC", f"CC{uuid.uuid4().hex[:8].upper()}")

    with pytest.raises(DBAPIError, match="numero_identificacion"):
        with db_session.begin_nested():
            insertar("Pasaporte", f"AB-{uuid.uuid4().hex[:8].upper()}")


def test_edicion_administrativa_valida_el_par_tipo_numero(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """El DTO de perfil no valida el formato; el use case sí, sobre el par
    efectivo. Un pasaporte alfanumérico pasa y un CC con letras no."""
    objetivo = crear_usuario_db(estado=2)
    cabeceras = crear_auth_headers(crear_usuario_db(id_rol=1, estado=2))

    def editar(**identificacion) -> object:
        return client.patch(
            f"/usuarios/{objetivo['id_usuario']}",
            headers=cabeceras,
            json={
                "nombre": "Administrado",
                "apellidos": "Integracion",
                "version": objetivo["version"],
                **identificacion,
            },
        )

    invalida = editar(tipo_identificacion="CC", numero_identificacion="123ABC")
    assert invalida.status_code == 400, invalida.text
    assert invalida.json()["error_code"] == "NUMERO_IDENTIFICACION_INVALIDO"

    valida = editar(
        tipo_identificacion="Pasaporte",
        numero_identificacion=f"AB{uuid.uuid4().hex[:10].upper()}",
    )
    assert valida.status_code == 200, valida.text


def test_cambiar_solo_el_tipo_revalida_el_numero_existente(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """Cambiar solo el tipo revalida el número ya guardado: el documento
    numérico del usuario también es válido como pasaporte."""
    objetivo = crear_usuario_db(estado=2)
    admin = crear_usuario_db(id_rol=1, estado=2)

    respuesta = client.patch(
        f"/usuarios/{objetivo['id_usuario']}",
        headers=crear_auth_headers(admin),
        json={
            "nombre": "Administrado",
            "apellidos": "Integracion",
            "version": objetivo["version"],
            "tipo_identificacion": "Pasaporte",
        },
    )

    assert respuesta.status_code == 200, respuesta.text
