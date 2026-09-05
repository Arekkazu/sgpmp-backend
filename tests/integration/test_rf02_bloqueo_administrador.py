"""RF-02 (#116, INC-M01-23-045) — bloqueo por intentos fallidos en cuenta Administrador.

Causa raíz: el trigger real `modulo1.trg_fn_proteger_estado_cuenta_admin` (el
que de verdad dispara `modulo1.cuentas_usuarios`) bloqueaba *cualquier* cambio
de `id_estado_cuenta` en roles protegidos (Administrador lo es), sin excepción
para el propio mecanismo automático de bloqueo por fuerza bruta. El 5to
intento fallido disparaba la excepción del trigger sin traducir → 500, y
`intentos_fallidos` nunca llegaba a 5 porque cada intento hacía rollback.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.sesiones.login_use_case import MAX_INTENTOS

pytestmark = pytest.mark.integration


def test_login_administrador_bloquea_cuenta_tras_5_intentos_fallidos(
    client, db_session: Session, crear_usuario_db
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    correo = db_session.execute(
        text("SELECT correo_electronico FROM modulo1.usuarios WHERE id_usuario = :i"),
        {"i": admin["id_usuario"]},
    ).scalar_one()

    respuestas = [
        client.post(
            "/sesiones/",
            json={"correo_electronico": correo, "contrasena": "ClaveIncorrecta9!"},
        )
        for _ in range(MAX_INTENTOS)
    ]

    for resp in respuestas[:-1]:
        assert resp.status_code == 401, resp.text

    ultima = respuestas[-1]
    assert ultima.status_code == 423, ultima.text
    assert ultima.json()["error_code"] == "CUENTA_BLOQUEADA"

    fila = db_session.execute(
        text(
            "SELECT id_estado_cuenta, intentos_fallidos FROM modulo1.cuentas_usuarios "
            "WHERE id_usuario = :i"
        ),
        {"i": admin["id_usuario"]},
    ).mappings().one()
    assert fila["intentos_fallidos"] == MAX_INTENTOS
    assert fila["id_estado_cuenta"] == 4, "la cuenta Administrador deberia haber quedado BLOQUEADA"
