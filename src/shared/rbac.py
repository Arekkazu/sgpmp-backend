from typing import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.shared.database import get_db
from src.shared.errors import AuthorizationError


def require_permission(id_recurso: int, id_accion: int) -> Callable:
    """
    Dependency factory para verificación RBAC por endpoint.
    Consulta modulo1.permisos con (id_rol, id_recurso, id_accion, es_activo=TRUE).
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
