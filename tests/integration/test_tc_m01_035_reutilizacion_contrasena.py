"""TC-M01-035: impedir reutilizar la contraseña actual en RF-07."""
from __future__ import annotations

import bcrypt
import pytest
from jose import jwt as jose_jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.notificacion_service import NotificacionService

pytestmark = pytest.mark.integration

JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"
CONTRASENA_REPORTE = "Nueva#2027"
MENSAJE_REUTILIZACION = (
    "No se permite reutilizar la contraseña actual. "
    "Defina una clave completamente nueva."
)


def test_tc_m01_035_rechaza_reutilizacion_sin_efectos_colaterales(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduce login + PUT del reporte y valida el estado persistido."""
    usuario = crear_usuario_db(id_rol=2, estado=2)
    hash_reporte = bcrypt.hashpw(
        CONTRASENA_REPORTE.encode("utf-8"),
        bcrypt.gensalt(rounds=4),
    ).decode("utf-8")
    db_session.execute(
        text(
            """
            UPDATE modulo1.usuarios
            SET contrasena_cifrada = :contrasena
            WHERE id_usuario = :id_usuario
            """
        ),
        {"contrasena": hash_reporte, "id_usuario": usuario["id_usuario"]},
    )
    db_session.flush()

    notificaciones: list[dict] = []
    monkeypatch.setattr(
        NotificacionService,
        "notificar",
        lambda _service, **datos: notificaciones.append(datos),
    )

    login = client.post(
        "/sesiones/",
        json={
            "correo_electronico": usuario["correo"],
            "contrasena": CONTRASENA_REPORTE,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    notificaciones.clear()
    id_token = int(
        jose_jwt.decode(
            token,
            JWT_SECRET_INTEGRACION,
            algorithms=["HS256"],
        )["jti"]
    )

    estado_antes = db_session.execute(
        text(
            """
            SELECT u.contrasena_cifrada, c.intentos_fallidos,
                   c.bloqueado_hasta, s.es_activa, t.fecha_uso,
                   (
                       SELECT count(*)
                       FROM modulo1.eventos e
                       WHERE e.id_usuario = u.id_usuario
                         AND e.tipo_evento = 6
                   ) AS eventos_cambio
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            JOIN modulo1.sesiones s USING (id_cuenta_usuario)
            JOIN modulo1.tokens t USING (id_token)
            WHERE u.id_usuario = :id_usuario
              AND t.id_token = :id_token
            """
        ),
        {"id_usuario": usuario["id_usuario"], "id_token": id_token},
    ).mappings().one()

    respuesta = client.put(
        f"/contrasena/usuarios/{usuario['id_usuario']}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "contrasena_actual": CONTRASENA_REPORTE,
            "nueva_contrasena": CONTRASENA_REPORTE,
            "confirmar_nueva_contrasena": CONTRASENA_REPORTE,
        },
    )

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "CONTRASENA_REUTILIZADA"
    assert respuesta.json()["message"] == MENSAJE_REUTILIZACION

    db_session.expire_all()
    estado_despues = db_session.execute(
        text(
            """
            SELECT u.contrasena_cifrada, c.intentos_fallidos,
                   c.bloqueado_hasta, s.es_activa, t.fecha_uso,
                   (
                       SELECT count(*)
                       FROM modulo1.eventos e
                       WHERE e.id_usuario = u.id_usuario
                         AND e.tipo_evento = 6
                   ) AS eventos_cambio
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            JOIN modulo1.sesiones s USING (id_cuenta_usuario)
            JOIN modulo1.tokens t USING (id_token)
            WHERE u.id_usuario = :id_usuario
              AND t.id_token = :id_token
            """
        ),
        {"id_usuario": usuario["id_usuario"], "id_token": id_token},
    ).mappings().one()

    assert estado_despues["contrasena_cifrada"] == estado_antes["contrasena_cifrada"]
    assert bcrypt.checkpw(
        CONTRASENA_REPORTE.encode("utf-8"),
        estado_despues["contrasena_cifrada"].encode("utf-8"),
    )
    assert estado_despues["intentos_fallidos"] == estado_antes["intentos_fallidos"]
    assert estado_despues["bloqueado_hasta"] == estado_antes["bloqueado_hasta"]
    assert estado_despues["es_activa"] is True
    assert estado_despues["fecha_uso"] is None
    assert estado_despues["eventos_cambio"] == estado_antes["eventos_cambio"]
    assert notificaciones == []
