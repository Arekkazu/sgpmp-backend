"""Pruebas de integración para la seguridad del listado de usuarios RF-11."""
from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


def test_endpoint_legacy_no_existe(client) -> None:
    """GET /usuarios/ no debe exponer el listado legacy."""
    respuesta = client.get("/usuarios/")

    assert respuesta.status_code in {404, 405}


def test_listado_admin_requiere_permiso(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """GET /usuarios/admin debe conservar la protección RBAC."""
    sin_permiso = crear_usuario_db(
        id_rol=9,
        estado=2,
    )

    respuesta = client.get(
        "/usuarios/admin",
        headers=crear_auth_headers(sin_permiso),
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"