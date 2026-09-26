"""RF-25 / INC-M09-29-G83 — Rol inexistente no concede permisos por defecto.

El backend resuelve el rol desde ``modulo1.usuarios.id_rol`` (no desde el claim
``rol`` del JWT), así que un usuario cuyo ``id_rol`` apunta a un rol que ya no
existe en ``modulo1.roles`` debe ser rechazado con 403 sin heredar permisos de
ningún otro rol. Estos tests fijan ese contrato con fakes (sin BD).
"""
from __future__ import annotations

import pytest

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError
from src.shared.rbac import require_permission


class PermisosQueryFake:
    """Devuelve siempre ``None``: ningún permiso coincide con el rol pedido."""

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def first(self) -> None:
        return None


class DbFake:
    def query(self, modelo):  # noqa: ANN001
        return PermisosQueryFake()


def _usuario(id_rol: int) -> UsuarioActual:
    return UsuarioActual(
        id_usuario=1,
        id_token=1,
        id_rol=id_rol,
        id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
    )


def test_rol_inexistente_no_concede_permiso_alguno() -> None:
    dependencia = require_permission(20, 2)  # R sobre umbrales_ambientales

    with pytest.raises(AuthorizationError) as excinfo:
        dependencia(db=DbFake(), usuario_actual=_usuario(999))

    assert excinfo.value.code == "ACCESO_DENEGADO"
    assert excinfo.value.status_code == 403


def test_rol_sin_permiso_sobre_el_recurso_tambien_se_deniega() -> None:
    # Un rol que sí existe pero no tiene el permiso pedido se deniega igual:
    # la compuerta es la tabla permisos, no la existencia del rol.
    dependencia = require_permission(20, 1)

    with pytest.raises(AuthorizationError) as excinfo:
        dependencia(db=DbFake(), usuario_actual=_usuario(2))

    assert excinfo.value.code == "ACCESO_DENEGADO"
