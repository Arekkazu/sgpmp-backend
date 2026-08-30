"""RF-06: bloquear una cuenta por intentos fallidos invalida sus tokens activos.

El escenario es el del atacante: la víctima tiene su sesión abierta en otro
dispositivo y un tercero le agota los intentos de login desde fuera. Antes, la
cuenta quedaba BLOQUEADA pero el JWT de la víctima seguía siendo aceptado,
porque `trg_invalidar_sesiones_por_estado` solo marca `sesiones.es_activa` y la
autenticación valida contra `tokens.fecha_uso`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.sesiones.login_use_case import MAX_INTENTOS

pytestmark = pytest.mark.integration


def test_bloqueo_por_intentos_fallidos_revoca_la_sesion_ya_abierta(
    client,
    db_session: Session,
    crear_usuario_db,
) -> None:
    # Rol no protegido: trg_proteger_estado_cuenta_admin impide bloquear al Administrador.
    victima = crear_usuario_db(id_rol=2, estado=2)
    correo = db_session.execute(
        text("SELECT correo_electronico FROM modulo1.usuarios WHERE id_usuario = :i"),
        {"i": victima["id_usuario"]},
    ).scalar_one()

    # La víctima inicia sesión en su dispositivo.
    login = client.post(
        "/sesiones/",
        json={"correo_electronico": correo, "contrasena": "Inicial1!"},
    )
    assert login.status_code == 200, login.text
    jwt_victima = {"Authorization": f"Bearer {login.json()['token']}"}
    assert client.get("/usuarios/me", headers=jwt_victima).status_code == 200

    # Un tercero agota los intentos desde fuera hasta bloquear la cuenta.
    for _ in range(MAX_INTENTOS):
        client.post(
            "/sesiones/",
            json={"correo_electronico": correo, "contrasena": "ClaveIncorrecta9!"},
        )

    estado = db_session.execute(
        text(
            "SELECT id_estado_cuenta FROM modulo1.cuentas_usuarios "
            "WHERE id_usuario = :i"
        ),
        {"i": victima["id_usuario"]},
    ).scalar_one()
    assert estado == 4, "la cuenta deberia haber quedado BLOQUEADA"

    # El JWT que ya tenia la victima deja de servir.
    revocado = client.get("/usuarios/me", headers=jwt_victima)
    assert revocado.status_code == 401, revocado.text
    assert revocado.json()["error_code"] == "TOKEN_REVOCADO"

    # Y en base el token quedo marcado como usado, no solo la sesion inactiva.
    fila = db_session.execute(
        text(
            """
            SELECT s.es_activa, t.fecha_uso
            FROM modulo1.sesiones AS s
            JOIN modulo1.tokens AS t ON t.id_token = s.id_token
            WHERE s.id_cuenta_usuario = :c
            """
        ),
        {"c": victima["id_cuenta_usuario"]},
    ).mappings().one()
    assert fila["es_activa"] is False
    assert fila["fecha_uso"] is not None


def test_el_trigger_revoca_tokens_ante_un_cambio_de_estado_por_sql_directo(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """Red de seguridad de BD: `trg_invalidar_sesiones_por_estado`.

    Antes solo marcaba `sesiones.es_activa`, que la autenticación no mira, así
    que un cambio de estado hecho fuera de la aplicación dejaba el JWT vivo.
    Aquí se cambia el estado por SQL directo, sin pasar por ningún caso de uso.
    """
    usuario = crear_usuario_db(id_rol=2, estado=2)
    headers = crear_auth_headers(usuario)
    assert client.get("/usuarios/me", headers=headers).status_code == 200

    db_session.execute(
        text(
            "UPDATE modulo1.cuentas_usuarios SET id_estado_cuenta = 3 "
            "WHERE id_cuenta_usuario = :c"
        ),
        {"c": usuario["id_cuenta_usuario"]},
    )
    db_session.flush()

    revocado = client.get("/usuarios/me", headers=headers)
    assert revocado.status_code == 401, revocado.text
    assert revocado.json()["error_code"] == "TOKEN_REVOCADO"


def test_activar_una_cuenta_no_revoca_la_sesion_del_propio_usuario(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """El trigger solo revoca hacia INACTIVO/BLOQUEADO/ELIMINADO.

    Si revocara en cualquier cambio de estado, el alta por SSO se rompería: al
    completar el perfil la cuenta pasa de PENDIENTE_DATOS a ACTIVO y el usuario
    quedaría fuera de su propia sesión.
    """
    usuario = crear_usuario_db(id_rol=2, estado=6)  # PENDIENTE_DATOS
    headers = crear_auth_headers(usuario)
    assert client.get("/usuarios/me", headers=headers).status_code == 200

    db_session.execute(
        text(
            "UPDATE modulo1.cuentas_usuarios SET id_estado_cuenta = 2 "
            "WHERE id_cuenta_usuario = :c"
        ),
        {"c": usuario["id_cuenta_usuario"]},
    )
    db_session.flush()

    sigue = client.get("/usuarios/me", headers=headers)
    assert sigue.status_code == 200, sigue.text
