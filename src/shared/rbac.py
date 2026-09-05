"""Control de acceso basado en roles (RBAC) para endpoints FastAPI.

Provee la dependencia ``require_permission`` que verifica en tiempo de
request si el rol del usuario autenticado tiene el permiso requerido sobre
un recurso y acción específicos, consultando la tabla ``modulo1.permisos``.
"""
from typing import Callable, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.shared.database import get_db
from src.shared.errors import AuthorizationError


def require_permission(
    id_recurso: int,
    id_accion: int,
    *,
    mensaje_denegado: Optional[str] = None,
) -> Callable:
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
        mensaje_denegado: Texto del 403 cuando el RF exige uno propio para ese
            endpoint (ej. RF-29: "Solo el Administrador del sistema puede definir
            el idioma predeterminado global"). Solo cambia el mensaje; la
            compuerta sigue siendo la tabla ``modulo1.permisos``, nunca un rol
            quemado en código. Si se omite, se usa el texto genérico.

    Returns:
        Función de dependencia compatible con ``fastapi.Depends``.

    Raises:
        AuthorizationError: Si la cuenta del usuario no está activa
            (``CUENTA_NO_ACTIVA``) o si su rol no tiene el permiso activo
            (``ACCESO_DENEGADO``). Ambos con HTTP 403.
    """
    def dependency(
        db: Session = Depends(get_db),
        usuario_actual: UsuarioActual = Depends(get_current_user),
    ) -> None:
        # RF-04: "Los permisos asociados a un rol solo serán efectivos para
        # usuarios que se encuentren en estado activo dentro del sistema."
        # El estado ya viene resuelto en ``UsuarioActual``, así que no hay
        # consulta extra. El gate va aquí y no en ``get_current_user`` porque
        # una cuenta PENDIENTE_DATOS (alta por SSO) sí debe poder autenticarse
        # para completar su perfil por `/usuarios/me`, que no pasa por RBAC.
        if usuario_actual.id_estado_cuenta != Cuenta.ESTADO_ACTIVO:
            raise AuthorizationError(
                code="CUENTA_NO_ACTIVA",
                message=(
                    "Acceso denegado. Su cuenta no se encuentra activa, por lo "
                    "que los permisos de su rol no son efectivos."
                ),
            )

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
                message=(
                    mensaje_denegado
                    or "Acceso denegado. Su rol no tiene permisos para realizar esta operación."
                ),
            )

    return dependency
