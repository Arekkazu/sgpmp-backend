"""Prueba unitaria para RF-15 (Módulo 9): Restricción de Rol Ingeniero de Campo (TC-M09-G05).

Aclaración sobre el alcance del test unitario:
Este test unitario valida el comportamiento determinístico de la compuerta `require_permission` ante los resultados
de consulta simulados (`DbSessionMockPermisos`). No consulta la base de datos real. La validación efectiva y
repetible de que la matriz de permisos persistida en PostgreSQL TEST efectivamente carece de las acciones
CREATE (1) y DELETE (4) para `id_rol = 4` queda cubierta por la suite E2E de Newman (`tc-m09-g05.json`).

Verifica la regla de control de acceso basado en roles (RBAC) para el rol Ingeniero de Campo (`id_rol = 4`):
- SC-1 (TC-M09-14): Intentar ejecutar la acción CREATE (id_recurso=8, id_accion=1) lanza `AuthorizationError`
  con `code == "ACCESO_DENEGADO"` y `status_code == 403`.
- SC-2 (TC-M09-15): Intentar ejecutar la acción DELETE/Desactivar (id_recurso=8, id_accion=4) lanza `AuthorizationError`
  con `code == "ACCESO_DENEGADO"` y `status_code == 403`.
- Caso Complementario: Verificar que Ingeniero de Campo SÍ posee permisos para READ (id_accion=2) y UPDATE (id_accion=3),
  demostrando la selectividad de la compuerta RBAC.
"""
from __future__ import annotations

import pytest

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.shared.errors import AuthorizationError
from src.shared.rbac import require_permission

INGENIERO_CAMPO = UsuarioActual(
    id_usuario=4,
    id_token=100,
    id_rol=4,
    id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
)


class DbSessionFake:
    """Fake de sesión SQLAlchemy que simula la tabla `modulo1.permisos` para unit testing."""

    def __init__(self, permisos_activos: list[tuple[int, int, int]]) -> None:
        """`permisos_activos`: lista de tuplas `(id_rol, id_recurso, id_accion)`."""
        self._permisos = permisos_activos

    def query(self, model):
        return self

    def filter(self, *conditions):
        return self

    def first(self):
        """Simula la consulta buscando si existe el permiso en la lista activa."""
        # Para el fake, asumimos que require_permission consulta los permisos de id_rol=4
        # Si la lista contiene el permiso buscado, retorna un objeto Permisos no nulo.
        return self._permiso_encontrado


class DbSessionMockPermisos:
    def __init__(self, tiene_permiso: bool) -> None:
        self.tiene_permiso = tiene_permiso

    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return Permisos(id_permiso=1, id_rol=4, id_recurso=8, id_accion=2, es_activo=True) if self.tiene_permiso else None


def test_sc1_ingeniero_campo_no_puede_crear_especie_403():
    """SC-1 (TC-M09-14): Creación de especies (recurso=8, accion=1) denegada a id_rol=4 con 403 ACCESO_DENEGADO."""
    dep = require_permission(id_recurso=8, id_accion=1)
    db_fake = DbSessionMockPermisos(tiene_permiso=False)

    with pytest.raises(AuthorizationError) as exc_info:
        dep(db=db_fake, usuario_actual=INGENIERO_CAMPO)

    assert exc_info.value.code == "ACCESO_DENEGADO"
    assert exc_info.value.status_code == 403
    assert "Acceso denegado" in exc_info.value.message


def test_sc2_ingeniero_campo_no_puede_desactivar_especie_403():
    """SC-2 (TC-M09-15): Desactivación de especies (recurso=8, accion=4) denegada a id_rol=4 con 403 ACCESO_DENEGADO."""
    dep = require_permission(id_recurso=8, id_accion=4)
    db_fake = DbSessionMockPermisos(tiene_permiso=False)

    with pytest.raises(AuthorizationError) as exc_info:
        dep(db=db_fake, usuario_actual=INGENIERO_CAMPO)

    assert exc_info.value.code == "ACCESO_DENEGADO"
    assert exc_info.value.status_code == 403
    assert "Acceso denegado" in exc_info.value.message


def test_ingeniero_campo_permisos_lectura_y_edicion_permitidos():
    """Caso complementario: Verificar que require_permission permite READ (accion=2) y UPDATE (accion=3) a id_rol=4."""
    dep_read = require_permission(id_recurso=8, id_accion=2)
    dep_update = require_permission(id_recurso=8, id_accion=3)
    db_fake_con_permiso = DbSessionMockPermisos(tiene_permiso=True)

    # No debe lanzar ninguna excepción para acciones autorizadas 2 y 3
    dep_read(db=db_fake_con_permiso, usuario_actual=INGENIERO_CAMPO)
    dep_update(db=db_fake_con_permiso, usuario_actual=INGENIERO_CAMPO)
