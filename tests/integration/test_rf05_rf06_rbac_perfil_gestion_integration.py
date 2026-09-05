"""Pruebas de integración para RF-05/RF-06: perfil, RBAC y gestión de cuenta."""

from __future__ import annotations

import uuid

import bcrypt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


pytestmark = pytest.mark.integration


def test_perfil_propio_usa_ruta_me_y_rechaza_estado_de_cuenta(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    usuario = crear_usuario_db(id_rol=2, estado=2)
    headers = crear_auth_headers(usuario)

    dto = {
        "nombre": "Perfil",
        "apellidos": "Actualizado",
        "correo_electronico": usuario["correo"],
        "telefono": "3009999999",
        "direccion": "Direccion Nueva",
        "version": usuario["version"],
    }

    respuesta = client.patch(
        "/usuarios/me",
        headers=headers,
        json=dto,
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["nombre"] == "Perfil"

    con_estado = client.patch(
        "/usuarios/me",
        headers=headers,
        json={
            **dto,
            "version": respuesta.json()["version"],
            "id_estado_cuenta": 3,
        },
    )

    assert con_estado.status_code == 400

    assert any(
        campo["field"] == "id_estado_cuenta"
        for campo in con_estado.json()["fields"]
    )


def test_completar_perfil_sso_parcialmente_no_revienta_en_500(
    client,
    db_session: Session,
    crear_auth_headers,
) -> None:
    """Issue #18: PATCH /usuarios/me con solo parte de los 6 campos de una
    cuenta PENDIENTE_DATOS (provista vía SSO) no debe romper la serialización
    de la respuesta cuando genero/tipo/numero de identificación siguen NULL.
    """
    identificador = uuid.uuid4().int
    fila = db_session.execute(
        text(
            """
            INSERT INTO modulo1.usuarios (
                tipo_identificacion, numero_identificacion, nombre, apellidos,
                fecha_nacimiento, genero, correo_electronico,
                contrasena_cifrada, telefono, direccion, id_rol, fecha_registro
            ) VALUES (
                NULL, NULL, NULL, NULL, NULL, NULL, :correo,
                :contrasena, NULL, NULL, 2, now()
            )
            RETURNING id_usuario, version
            """
        ),
        {
            "correo": f"it-sso-{identificador}@example.com",
            "contrasena": bcrypt.hashpw(
                b"Inicial1!", bcrypt.gensalt(rounds=4)
            ).decode("utf-8"),
        },
    ).mappings().one()

    id_cuenta = db_session.execute(
        text(
            """
            INSERT INTO modulo1.cuentas_usuarios (
                id_usuario, id_estado_cuenta, tiene_correo_verificado,
                ultimo_acceso
            ) VALUES (:id_usuario, 6, TRUE, now())
            RETURNING id_cuenta_usuario
            """
        ),
        {"id_usuario": fila["id_usuario"]},
    ).scalar_one()
    db_session.flush()

    usuario = {
        "id_usuario": fila["id_usuario"],
        "id_cuenta_usuario": id_cuenta,
        "id_rol": 2,
    }
    headers = crear_auth_headers(usuario)

    respuesta = client.patch(
        "/usuarios/me",
        headers=headers,
        json={
            "nombre": "Pendiente",
            "apellidos": "Datos",
            "tipo_identificacion": "CC",
            "numero_identificacion": str(identificador % 10**15).zfill(15),
            "version": fila["version"],
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["tipo_identificacion"] == "CC"
    assert cuerpo["genero"] is None


def test_edicion_administrativa_requiere_permiso_del_router(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    objetivo = crear_usuario_db(
        id_rol=2,
        estado=2,
    )

    sin_permiso = crear_usuario_db(
        id_rol=9,
        estado=2,
    )

    admin = crear_usuario_db(
        id_rol=1,
        estado=2,
    )

    dto = {
        "nombre": "Administrado",
        "apellidos": "Integracion",
        "correo_electronico": objetivo["correo"],
        "telefono": "3001234567",
        "direccion": "Direccion Integracion",
        "version": objetivo["version"],
        "id_rol": 2,
    }

    denegada = client.patch(
        f"/usuarios/{objetivo['id_usuario']}",
        headers=crear_auth_headers(sin_permiso),
        json=dto,
    )

    assert denegada.status_code == 403
    assert denegada.json()["error_code"] == "ACCESO_DENEGADO"

    autorizada = client.patch(
        f"/usuarios/{objetivo['id_usuario']}",
        headers=crear_auth_headers(admin),
        json=dto,
    )

    assert autorizada.status_code == 200, autorizada.text


def test_gestion_protege_ultimo_usuario_activo_de_rol_protegido(
    client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(
        id_rol=1,
        estado=2,
    )

    id_rol_protegido = db_session.execute(
        text(
            """
            INSERT INTO modulo1.roles (
                nombre_rol,
                descripcion,
                es_protegido
            )
            VALUES (
                :nombre,
                'Rol temporal de integración',
                TRUE
            )
            RETURNING id_rol
            """
        ),
        {
            "nombre": (
                f"Protegido Integracion {admin['id_usuario']}"
            )
        },
    ).scalar_one()

    objetivo = crear_usuario_db(
        id_rol=id_rol_protegido,
        estado=2,
    )

    respuesta = client.post(
        f"/usuarios/{objetivo['id_usuario']}/gestionar",
        headers=crear_auth_headers(admin),
        json={
            "accion_cuenta": "inactivar",
            "motivo_accion": (
                "Prueba de protección del último usuario"
            ),
        },
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "ULTIMO_ADMIN_PROTEGIDO"