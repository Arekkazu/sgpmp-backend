"""Integracion del login, JWT y persistencia de la vigencia RF-02."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from jose import jwt as jose_jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


def test_login_emite_jwt_y_sesion_con_vigencia_de_ocho_horas(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    respuesta = client.post(
        "/sesiones/",
        json={
            "correo_electronico": usuario["correo"],
            "contrasena": "Inicial1!",
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert 8 * 60 * 60 - 5 <= cuerpo["expira_en"] <= 8 * 60 * 60

    payload = jose_jwt.decode(
        cuerpo["token"],
        JWT_SECRET_INTEGRACION,
        algorithms=["HS256"],
    )
    assert int(payload["exp"]) - int(payload["iat"]) == 8 * 60 * 60

    fila = db_session.execute(
        text(
            """
            SELECT t.fecha_expiracion, s.fecha_finalizacion, s.es_activa
            FROM modulo1.tokens t
            JOIN modulo1.sesiones s USING (id_token)
            WHERE t.id_token = :id_token
            """
        ),
        {"id_token": int(payload["jti"])},
    ).mappings().one()
    expiracion_jwt = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    assert abs((fila["fecha_expiracion"] - expiracion_jwt).total_seconds()) < 1
    assert fila["fecha_finalizacion"] == fila["fecha_expiracion"]
    assert fila["es_activa"] is True
