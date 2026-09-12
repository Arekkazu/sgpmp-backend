"""Dependencia RBAC con auditoría RF-52 para el módulo de activos biológicos."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.auditoria.registrar_acceso_no_autorizado_use_case import (
    RegistrarAccesoNoAutorizadoUseCase,
)
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
    SqlAlchemyBitacoraAuditoriaRepository,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import AuthorizationError
from src.shared.rbac import require_permission


def _id_activo_desde_request(request: Request) -> int | None:
    valor = request.path_params.get('id_activo')
    try:
        id_activo = int(valor)
    except (TypeError, ValueError):
        return None
    return id_activo if id_activo > 0 else None


def _ruta_auditada(request: Request) -> str:
    route = request.scope.get('route')
    return getattr(route, 'path', request.url.path)


def require_permission_m02(
    id_recurso: int,
    id_accion: int,
    *,
    rf_origen: str,
    mensaje_denegado: str | None = None,
) -> Callable:
    """Aplica el RBAC compartido y registra en RF-52 cualquier rechazo 403.

    La autorización continúa delegada a ``src.shared.rbac.require_permission``;
    esta capa solo añade el contexto propio de M02 que el componente compartido
    no conoce: RF origen, activo de la ruta y repositorio de auditoría destino.
    """
    verificar_permiso = require_permission(
        id_recurso,
        id_accion,
        mensaje_denegado=mensaje_denegado,
    )

    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        usuario_actual: UsuarioActual = Depends(get_current_user),
    ) -> None:
        try:
            verificar_permiso(db=db, usuario_actual=usuario_actual)
        except AuthorizationError as exc:
            RegistrarAccesoNoAutorizadoUseCase(
                db=db,
                bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
            ).execute(
                rf_origen=rf_origen,
                id_usuario=usuario_actual.id_usuario,
                id_recurso=id_recurso,
                id_accion=id_accion,
                error_code=exc.code,
                causa=exc.message,
                metodo_http=request.method,
                ruta=_ruta_auditada(request),
                id_activo_biologico=_id_activo_desde_request(request),
            )
            raise

    # Metadatos simples usados por las pruebas para asegurar que ninguna ruta
    # protegida de M02 vuelva a quedar con RBAC sin auditoría.
    dependency.audita_rechazo_rbac_m02 = True
    dependency.rf_origen = rf_origen
    dependency.id_recurso = id_recurso
    dependency.id_accion = id_accion
    return dependency
