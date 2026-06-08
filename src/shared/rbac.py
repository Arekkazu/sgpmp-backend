"""Control de acceso basado en roles (RBAC) para endpoints FastAPI.

Provee la dependencia ``require_permission`` que verifica en tiempo de
request si el rol del usuario autenticado tiene el permiso requerido sobre
un recurso y acción específicos, consultando la tabla ``modulo1.permisos``.
"""
from typing import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.shared.database import get_db
from src.shared.errors import AuthorizationError


def require_permission(id_recurso: int, id_accion: int) -> Callable:
    """Fábrica de dependencias FastAPI para verificación RBAC por endpoint.

    Genera una dependencia que, al ejecutarse en cada request, consulta si el
    rol del usuario autenticado tiene un permiso activo para la combinación
    ``(id_recurso, id_accion)``. Se usa en el parámetro ``dependencies`` del
    decorador de ruta.

    Ejemplo de uso::

        @router.get("/recurso", dependencies=[Depends(require_permission(1, 2))])
        def mi_endpoint(): ...

    Args:
        id_recurso: ID del recurso protegido (tabla ``modulo1.recursos``).
        id_accion: ID de la acción requerida (tabla ``modulo1.acciones``).

    Returns:
        Función de dependencia compatible con ``fastapi.Depends``.

    Raises:
        AuthorizationError: Si el rol del usuario no tiene el permiso activo,
            con código ``ACCESO_DENEGADO`` y HTTP 403.
    """
    def dependency(
        db: Session = Depends(get_db),
        usuario_actual: UsuarioActual = Depends(get_current_user),
    ) -> None:
        tiene_permiso = (
            db.query(Permisos)
            .filter(
                Permisos.id_rol == usuario_actual.id_rol,
                Permisos.id_recurso == id_recurso,
                Permisos.id_accion == id_accion,
                Permisos.es_activo.is_(True),
            )
            .first()
        )
        if tiene_permiso is None:
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message="Acceso denegado. Su rol no tiene permisos para realizar esta operación.",
            )

    return dependency
