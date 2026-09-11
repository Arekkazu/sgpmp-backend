"""Integracion de DELETE /roles/{id_rol} para INC-M01-03-119 (RF-03)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError


pytestmark = pytest.mark.integration


def _crear_rol_con_permiso(db_session, *, nombre: str | None = None) -> tuple[int, int]:
    sufijo = uuid.uuid4().hex[:8]
    nombre_rol = nombre or f"Auxiliar TC119 {sufijo}"
    id_rol = db_session.execute(
        text(
            """
            INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
            VALUES (:nombre, 'Rol temporal de integracion INC-M01-03-119', FALSE)
            RETURNING id_rol
            """
        ),
        {"nombre": nombre_rol},
    ).scalar_one()
    id_permiso = db_session.execute(
        text(
            """
            INSERT INTO modulo1.permisos
                (nombre, id_recurso, id_accion, id_rol, es_activo)
            VALUES (:nombre, 1, 2, :id_rol, TRUE)
            RETURNING id_permiso
            """
        ),
        {"nombre": f"tc119_{sufijo}", "id_rol": id_rol},
    ).scalar_one()
    db_session.flush()
    return id_rol, id_permiso


def test_delete_rol_sin_usuarios_elimina_rol_permisos_y_registra_evento(
    client,
    db_session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    id_rol, id_permiso = _crear_rol_con_permiso(
        db_session,
        nombre="Auxiliar de Campo TC119",
    )

    respuesta = client.delete(
        f"/roles/{id_rol}",
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"message": f"Rol {id_rol} eliminado exitosamente."}
    assert db_session.execute(
        text("SELECT count(*) FROM modulo1.roles WHERE id_rol=:id"),
        {"id": id_rol},
    ).scalar_one() == 0
    assert db_session.execute(
        text("SELECT count(*) FROM modulo1.permisos WHERE id_permiso=:id"),
        {"id": id_permiso},
    ).scalar_one() == 0
    assert db_session.execute(
        text(
            """
            SELECT count(*)
            FROM modulo1.eventos
            WHERE tipo_evento = 13
              AND resultado::text = 'exitoso'
              AND (detalle->>'id_rol')::integer = :id_rol
            """
        ),
        {"id_rol": id_rol},
    ).scalar_one() == 1


def test_delete_rol_con_usuario_responde_422_y_no_borra_permisos(
    client,
    db_session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    id_rol, id_permiso = _crear_rol_con_permiso(db_session)
    crear_usuario_db(id_rol=id_rol, estado=2)

    respuesta = client.delete(
        f"/roles/{id_rol}",
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "ROL_EN_USO"
    assert db_session.execute(
        text("SELECT count(*) FROM modulo1.roles WHERE id_rol=:id"),
        {"id": id_rol},
    ).scalar_one() == 1
    assert db_session.execute(
        text("SELECT count(*) FROM modulo1.permisos WHERE id_permiso=:id"),
        {"id": id_permiso},
    ).scalar_one() == 1


def test_delete_rol_protegido_responde_403_y_lo_conserva(
    client,
    db_session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)

    respuesta = client.delete(
        "/roles/1",
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ROL_PROTEGIDO"
    assert db_session.execute(
        text("SELECT count(*) FROM modulo1.roles WHERE id_rol=1")
    ).scalar_one() == 1


def test_retirar_directamente_el_ultimo_permiso_sigue_bloqueado(
    db_session,
) -> None:
    _, id_permiso = _crear_rol_con_permiso(db_session)

    with pytest.raises(InternalError) as exc_info:
        db_session.execute(
            text("DELETE FROM modulo1.permisos WHERE id_permiso=:id"),
            {"id": id_permiso},
        )

    assert getattr(exc_info.value.orig, "pgcode", "") == "P0006"
