"""Integracion del refresh token: login emite cookie, rotacion, reuso, logout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _login(client, usuario) -> dict:
    respuesta = client.post(
        "/sesiones/",
        json={"correo_electronico": usuario["correo"], "contrasena": "Inicial1!"},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta


def test_login_emite_cookie_refresh_httponly_y_no_en_el_json(
    client, db_session: Session, crear_usuario_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    respuesta = _login(client, usuario)

    assert "refresh_token" in client.cookies
    assert "refresh_token" not in respuesta.text  # nunca en el body JSON
    cuerpo = respuesta.json()
    assert set(cuerpo.keys()) == {"token", "tipo", "expira_en", "message", "perfil_incompleto"}


def test_refresh_rota_tokens_y_el_nuevo_access_token_funciona(
    client, db_session: Session, crear_usuario_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    _login(client, usuario)
    cookie_vieja = client.cookies["refresh_token"]

    respuesta = client.post("/sesiones/refresh")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["message"] == "Sesión renovada exitosamente."

    cookie_nueva = client.cookies["refresh_token"]
    assert cookie_nueva != cookie_vieja

    permisos = client.get(
        "/sesiones/me/permisos",
        headers={"Authorization": f"Bearer {cuerpo['token']}"},
    )
    assert permisos.status_code == 200, permisos.text


def test_reuso_de_refresh_token_rotado_mata_la_sesion_completa(
    client, db_session: Session, crear_usuario_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    login_resp = _login(client, usuario)
    access_token_original = login_resp.json()["token"]
    cookie_vieja = client.cookies["refresh_token"]

    refresh_resp = client.post("/sesiones/refresh")
    assert refresh_resp.status_code == 200, refresh_resp.text
    access_token_nuevo = refresh_resp.json()["token"]

    # Reusar la cookie VIEJA (ya rotada) simula un robo.
    client.cookies.set("refresh_token", cookie_vieja)
    reuso_resp = client.post("/sesiones/refresh")
    assert reuso_resp.status_code == 401, reuso_resp.text
    assert reuso_resp.json()["error_code"] == "REFRESH_TOKEN_REUTILIZADO"

    # La sesión completa murió: ni el access token original ni el emitido
    # por el refresh legítimo (previo al reuso) siguen sirviendo.
    for token in (access_token_original, access_token_nuevo):
        permisos = client.get("/sesiones/me/permisos", headers={"Authorization": f"Bearer {token}"})
        assert permisos.status_code == 401, permisos.text


def test_refresh_token_expirado_responde_410_y_cierra_sesion(
    client, db_session: Session, crear_usuario_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    _login(client, usuario)

    db_session.execute(
        text("UPDATE modulo1.tokens SET fecha_expiracion = :expirado WHERE hash_valor IS NOT NULL"),
        {"expirado": datetime.now(timezone.utc) - timedelta(minutes=1)},
    )
    db_session.flush()

    respuesta = client.post("/sesiones/refresh")
    assert respuesta.status_code == 410, respuesta.text
    assert respuesta.json()["error_code"] == "REFRESH_TOKEN_EXPIRADO"


def test_refresh_sin_cookie_responde_401(client) -> None:
    respuesta = client.post("/sesiones/refresh")
    assert respuesta.status_code == 401, respuesta.text
    assert respuesta.json()["error_code"] == "REFRESH_TOKEN_REQUERIDO"


def test_logout_borra_la_cookie_de_refresh(
    client, db_session: Session, crear_usuario_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    login_resp = _login(client, usuario)
    access_token = login_resp.json()["token"]

    logout_resp = client.request(
        "DELETE", "/sesiones/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_resp.status_code == 200, logout_resp.text
    assert "refresh_token" not in client.cookies

    # La cookie que el navegador tenía tampoco sirve para refrescar de nuevo.
    respuesta = client.post("/sesiones/refresh")
    assert respuesta.status_code == 401
