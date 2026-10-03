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


def test_cookie_refresh_respeta_flags_explicitos(
    client, db_session: Session, crear_usuario_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """COOKIE_SECURE/COOKIE_SAMESITE mandan sobre ENV al emitir la cookie."""
    from src.shared import notificacion_service

    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    respuesta = _login(client, usuario)

    set_cookie = respuesta.headers.get("set-cookie", "").lower()
    assert "refresh_token" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=none" in set_cookie
    assert "httponly" in set_cookie


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

    auditoria = db_session.execute(
        text(
            """
            SELECT resultado::text, categoria, id_sesion, detalle
            FROM modulo1.eventos
            WHERE tipo_evento = 23 AND id_usuario = :id_usuario
            ORDER BY id_evento DESC
            LIMIT 1
            """
        ),
        {"id_usuario": usuario["id_usuario"]},
    ).mappings().one()
    assert auditoria["resultado"] == "exitoso"
    assert auditoria["categoria"] == "AUTENTICACION"
    assert auditoria["id_sesion"] is not None
    assert auditoria["detalle"]["user_agent"]


def test_access_token_anterior_a_un_refresh_queda_revocado(
    client, crear_usuario_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INC-M09-TC-M09-G94 (#309): un cliente que retiene el access token emitido
    antes de un refresh (p.ej. un caso Cypress que capturo el token del login y
    lo reutiliza tras una navegacion que dispara un refresh silencioso) debe
    recibir 401 TOKEN_REVOCADO, nunca un 200 con datos obsoletos ni un 500.
    Esto confirma que el 401 observado en #309 es el rechazo correcto de un
    token ya rotado, no un defecto de get_current_user/RBAC sobre el recurso
    contexto_interfaz.
    """
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    login = _login(client, usuario)
    token_viejo = login.json()["token"]

    respuesta = client.post("/sesiones/refresh")
    assert respuesta.status_code == 200, respuesta.text

    reintento = client.get(
        "/sesiones/me/permisos",
        headers={"Authorization": f"Bearer {token_viejo}"},
    )
    assert reintento.status_code == 401, reintento.text
    assert reintento.json()["error_code"] == "TOKEN_REVOCADO"


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

    auditoria = db_session.execute(
        text(
            """
            SELECT resultado::text, categoria, id_sesion
            FROM modulo1.eventos
            WHERE tipo_evento = 24 AND id_usuario = :id_usuario
            ORDER BY id_evento DESC
            LIMIT 1
            """
        ),
        {"id_usuario": usuario["id_usuario"]},
    ).mappings().one()
    assert auditoria["resultado"] == "fallido"
    assert auditoria["categoria"] == "AUTENTICACION"
    assert auditoria["id_sesion"] is not None


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


def test_refresh_con_cookie_desconocida_responde_401(client) -> None:
    client.cookies.set("refresh_token", "token-que-no-existe")

    respuesta = client.post("/sesiones/refresh")

    assert respuesta.status_code == 401, respuesta.text
    assert respuesta.json()["error_code"] == "REFRESH_TOKEN_INVALIDO"


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
