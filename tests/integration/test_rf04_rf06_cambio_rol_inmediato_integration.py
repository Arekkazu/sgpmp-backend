"""Integración RF-04/06: el rol cambia sin invalidar el JWT vigente."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_cambio_de_rol_aplica_permisos_sin_relogin(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    objetivo = crear_usuario_db(id_rol=2, estado=2)
    admin = crear_usuario_db(id_rol=1, estado=2)
    token_objetivo = crear_auth_headers(objetivo)
    token_admin = crear_auth_headers(admin)

    respuesta_edicion = client.patch(
        f"/usuarios/{objetivo['id_usuario']}",
        headers=token_admin,
        json={
            "nombre": "Integracion",
            "apellidos": "Prueba",
            "id_rol": 3,
            "version": objetivo["version"],
        },
    )
    assert respuesta_edicion.status_code == 200, respuesta_edicion.text

    estado_sesion = db_session.execute(
        text(
            """
            SELECT s.es_activa, t.fecha_uso
            FROM modulo1.sesiones AS s
            JOIN modulo1.tokens AS t ON t.id_token = s.id_token
            WHERE s.id_cuenta_usuario = :id_cuenta
            """
        ),
        {"id_cuenta": objetivo["id_cuenta_usuario"]},
    ).mappings().one()
    assert estado_sesion["es_activa"] is True
    assert estado_sesion["fecha_uso"] is None

    permisos_rol_nuevo = {
        (fila["id_recurso"], fila["id_accion"])
        for fila in db_session.execute(
            text(
                """
                SELECT id_recurso, id_accion
                FROM modulo1.permisos
                WHERE id_rol = 3 AND es_activo = TRUE
                """
            )
        ).mappings()
    }
    permisos_rol_anterior = {
        (fila["id_recurso"], fila["id_accion"])
        for fila in db_session.execute(
            text(
                """
                SELECT id_recurso, id_accion
                FROM modulo1.permisos
                WHERE id_rol = 2 AND es_activo = TRUE
                """
            )
        ).mappings()
    }
    assert permisos_rol_nuevo != permisos_rol_anterior

    respuesta_permisos = client.get(
        "/sesiones/me/permisos",
        headers=token_objetivo,
    )
    assert respuesta_permisos.status_code == 200, respuesta_permisos.text

    permisos_respuesta = {
        (permiso["id_recurso"], permiso["id_accion"])
        for permiso in respuesta_permisos.json()["permisos"]
    }
    assert permisos_respuesta == permisos_rol_nuevo
    assert permisos_respuesta != permisos_rol_anterior

    rol_vigente = db_session.execute(
        text(
            "SELECT id_rol FROM modulo1.usuarios WHERE id_usuario = :id_usuario"
        ),
        {"id_usuario": objetivo["id_usuario"]},
    ).scalar_one()
    assert rol_vigente == 3
