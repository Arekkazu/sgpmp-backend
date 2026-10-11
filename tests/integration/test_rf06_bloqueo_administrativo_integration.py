"""RF-06 / RF-02 de punta a punta: bloqueo administrativo y bloqueo por intentos.

Reproduce lo visto en DEV (cuenta 23, 2026-10-11): el administrador bloqueaba
la cuenta, el usuario iniciaba sesión con su contraseña y el login la
reactivaba (`UPDATE ... SET id_estado_cuenta=2`), porque una cuenta BLOQUEADA
sin `bloqueado_hasta` se tomaba como bloqueo de login ya vencido.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import declarar_identidad, get_db

pytestmark = pytest.mark.integration

CLAVE = "Inicial1!"


def _estado(db_session: Session, id_usuario: int) -> Any:
    return db_session.execute(
        text(
            "SELECT id_estado_cuenta, bloqueado_hasta, intentos_fallidos "
            "FROM modulo1.cuentas_usuarios WHERE id_usuario = :i"
        ),
        {"i": id_usuario},
    ).mappings().one()


def test_cuenta_bloqueada_por_admin_no_se_reactiva_al_iniciar_sesion(
    client, integration_app, db_session: Session, crear_usuario_db
) -> None:
    admin = crear_usuario_db(id_rol=1)
    usuario = crear_usuario_db(id_rol=2)

    def actual(db: Session = Depends(get_db)) -> UsuarioActual:
        declarar_identidad(db, admin["id_usuario"], "Administrador")
        return UsuarioActual(id_usuario=admin["id_usuario"], id_token=1, id_rol=1, id_estado_cuenta=2)

    integration_app.dependency_overrides[get_current_user] = actual
    try:
        bloqueo = client.post(
            f"/usuarios/{usuario['id_usuario']}/gestionar",
            json={"accion_cuenta": "bloquear", "motivo_accion": "mal uso de la app"},
        )
    finally:
        integration_app.dependency_overrides.pop(get_current_user, None)
    assert bloqueo.status_code == 200, bloqueo.text

    login = client.post(
        "/sesiones/", json={"correo_electronico": usuario["correo"], "contrasena": CLAVE}
    )

    assert login.status_code == 403, login.text
    assert login.json()["error_code"] == "CUENTA_DESHABILITADA"
    assert _estado(db_session, usuario["id_usuario"])["id_estado_cuenta"] == 4


def test_al_vencer_el_bloqueo_por_intentos_hay_cinco_intentos_nuevos(
    client, db_session: Session, crear_usuario_db
) -> None:
    usuario = crear_usuario_db(id_rol=2)
    db_session.execute(
        text(
            "UPDATE modulo1.cuentas_usuarios SET id_estado_cuenta = 4, intentos_fallidos = 5, "
            "bloqueado_hasta = :vencio WHERE id_usuario = :i"
        ),
        {"vencio": datetime.now(timezone.utc) - timedelta(minutes=1), "i": usuario["id_usuario"]},
    )
    db_session.flush()

    fallo = client.post(
        "/sesiones/", json={"correo_electronico": usuario["correo"], "contrasena": "Incorrecta9!"}
    )

    assert fallo.status_code == 401, fallo.text
    assert "Intento 1 de 5" in fallo.json()["message"]
    fila = _estado(db_session, usuario["id_usuario"])
    assert fila["id_estado_cuenta"] == 2
    assert fila["intentos_fallidos"] == 1
    assert fila["bloqueado_hasta"] is None
