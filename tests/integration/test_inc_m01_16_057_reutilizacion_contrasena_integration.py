"""Integración INC-M01-16-057 para reutilización de contraseña en RF-09."""
from __future__ import annotations

import bcrypt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.shared.notificacion_service import NotificacionService

pytestmark = pytest.mark.integration


def test_rechazo_409_conserva_token_sesiones_y_permite_restaurar_con_otra_clave(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = crear_usuario_db(id_rol=2, estado=2)
    crear_auth_headers(usuario)
    token = "token-inc-m01-16-057"
    token_hash = calcular_hash_token(token)
    db_session.execute(
        text(
            """
            UPDATE modulo1.cuentas_usuarios
            SET token_activacion_actual = :token,
                fecha_cambio_estado = now()
            WHERE id_usuario = :usuario
            """
        ),
        {"token": token_hash, "usuario": usuario["id_usuario"]},
    )
    db_session.flush()

    notificaciones: list[dict] = []
    monkeypatch.setattr(
        NotificacionService,
        "notificar",
        lambda *args, **kwargs: notificaciones.append(kwargs),
    )

    estado_inicial = db_session.execute(
        text(
            """
            SELECT u.contrasena_cifrada, c.token_activacion_actual,
                   c.intentos_fallidos, c.bloqueado_hasta
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            WHERE u.id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).mappings().one()
    sesiones_iniciales = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM modulo1.sesiones s
            JOIN modulo1.cuentas_usuarios c USING (id_cuenta_usuario)
            WHERE c.id_usuario = :usuario AND s.es_activa IS TRUE
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert sesiones_iniciales == 1

    rechazada = client.post(
        "/contrasena/restablecer",
        json={
            "token": token,
            "nueva_contrasena": "Inicial1!",
            "confirmar_contrasena": "Inicial1!",
        },
    )

    assert rechazada.status_code == 409, rechazada.text
    assert rechazada.json()["error_code"] == "CONTRASENA_REUTILIZADA"
    assert rechazada.json()["message"] == (
        "La nueva contraseña no puede ser igual a la anterior."
    )

    despues_rechazo = db_session.execute(
        text(
            """
            SELECT u.contrasena_cifrada, c.token_activacion_actual,
                   c.intentos_fallidos, c.bloqueado_hasta
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            WHERE u.id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).mappings().one()
    assert despues_rechazo == estado_inicial
    assert bcrypt.checkpw(b"Inicial1!", despues_rechazo["contrasena_cifrada"].encode())
    assert despues_rechazo["token_activacion_actual"] == token_hash

    sesiones_despues_rechazo = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM modulo1.sesiones s
            JOIN modulo1.cuentas_usuarios c USING (id_cuenta_usuario)
            WHERE c.id_usuario = :usuario AND s.es_activa IS TRUE
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert sesiones_despues_rechazo == sesiones_iniciales
    assert db_session.execute(
        text(
            """
            SELECT count(*) FROM modulo1.eventos
            WHERE id_usuario = :usuario AND tipo_evento = 8
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one() == 0
    assert notificaciones == []

    login_actual = client.post(
        "/sesiones/",
        json={
            "correo_electronico": usuario["correo"],
            "contrasena": "Inicial1!",
        },
    )
    assert login_actual.status_code == 200, login_actual.text

    # El mismo token debe seguir disponible para una contraseña realmente nueva.
    notificaciones.clear()
    aceptada = client.post(
        "/contrasena/restablecer",
        json={
            "token": token,
            "nueva_contrasena": "NuevaSegura2!",
            "confirmar_contrasena": "NuevaSegura2!",
        },
    )
    assert aceptada.status_code == 200, aceptada.text

    estado_final = db_session.execute(
        text(
            """
            SELECT u.contrasena_cifrada, c.token_activacion_actual
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            WHERE u.id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).mappings().one()
    assert estado_final["token_activacion_actual"] is None
    assert bcrypt.checkpw(b"NuevaSegura2!", estado_final["contrasena_cifrada"].encode())
    assert not bcrypt.checkpw(b"Inicial1!", estado_final["contrasena_cifrada"].encode())
    assert db_session.execute(
        text(
            """
            SELECT count(*)
            FROM modulo1.sesiones s
            JOIN modulo1.cuentas_usuarios c USING (id_cuenta_usuario)
            WHERE c.id_usuario = :usuario AND s.es_activa IS TRUE
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one() == 0
    assert db_session.execute(
        text(
            """
            SELECT count(*) FROM modulo1.eventos
            WHERE id_usuario = :usuario AND tipo_evento = 8
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one() == 1
    assert [n["tipo_evento"] for n in notificaciones] == [8]
