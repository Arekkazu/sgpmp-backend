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


def test_cuenta_no_activa_no_ejerce_los_permisos_de_su_rol(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """RF-04: los permisos solo son efectivos para usuarios en estado activo."""
    activo = crear_usuario_db(id_rol=1, estado=2)
    inactivo = crear_usuario_db(id_rol=1, estado=3)

    # Mismo rol Administrador, mismo permiso de listado: solo cambia el estado.
    permitido = client.get("/usuarios/admin", headers=crear_auth_headers(activo))
    assert permitido.status_code == 200, permitido.text

    denegado = client.get("/usuarios/admin", headers=crear_auth_headers(inactivo))
    assert denegado.status_code == 403, denegado.text
    assert denegado.json()["error_code"] == "CUENTA_NO_ACTIVA"


def test_cuenta_pendiente_de_datos_sigue_autenticando_para_completar_perfil(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """El gate de estado vive en RBAC, no en la autenticación: el alta por SSO
    deja la cuenta en PENDIENTE_DATOS y aun así debe poder usar `/usuarios/me`."""
    pendiente = crear_usuario_db(id_rol=2, estado=6)
    headers = crear_auth_headers(pendiente)

    perfil = client.get("/usuarios/me", headers=headers)
    assert perfil.status_code == 200, perfil.text

    # Pero sí queda fuera de cualquier endpoint protegido por RBAC.
    denegado = client.get("/usuarios/admin", headers=headers)
    assert denegado.status_code == 403, denegado.text


def test_require_permission_pasa_de_403_a_200_con_el_mismo_jwt(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """El criterio de RF-04, extremo a extremo y sobre un endpoint con RBAC real.

    A diferencia del test de arriba, aquí el JWT sale de un login de verdad y lo
    que se mide es ``require_permission``, no el listado informativo de permisos.
    """
    objetivo = crear_usuario_db(id_rol=2, estado=2)   # Productor
    admin = crear_usuario_db(id_rol=1, estado=2)      # Administrador

    correo = db_session.execute(
        text("SELECT correo_electronico FROM modulo1.usuarios WHERE id_usuario = :i"),
        {"i": objetivo["id_usuario"]},
    ).scalar_one()

    login = client.post(
        "/sesiones/",
        json={"correo_electronico": correo, "contrasena": "Inicial1!"},
    )
    assert login.status_code == 200, login.text
    jwt_vigente = {"Authorization": f"Bearer {login.json()['token']}"}

    # El listado administrativo exige recurso 1 / accion 2, que solo tiene el rol 1.
    antes = client.get("/usuarios/admin", headers=jwt_vigente)
    assert antes.status_code == 403, antes.text

    patch = client.patch(
        f"/usuarios/{objetivo['id_usuario']}",
        headers=crear_auth_headers(admin),
        json={
            "nombre": "Integracion",
            "apellidos": "Prueba",
            "id_rol": 1,
            "version": objetivo["version"],
        },
    )
    assert patch.status_code == 200, patch.text

    # Mismo JWT, sin relogin: ahora pasa el control de acceso.
    despues = client.get("/usuarios/admin", headers=jwt_vigente)
    assert despues.status_code == 200, despues.text

    # Y la sesion emitida en el login sigue viva.
    sesion = db_session.execute(
        text(
            """
            SELECT s.es_activa, t.fecha_uso
            FROM modulo1.sesiones AS s
            JOIN modulo1.tokens AS t ON t.id_token = s.id_token
            WHERE s.id_cuenta_usuario = :c AND s.es_activa IS TRUE
            """
        ),
        {"c": objetivo["id_cuenta_usuario"]},
    ).mappings().one()
    assert sesion["es_activa"] is True
    assert sesion["fecha_uso"] is None
