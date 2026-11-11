# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-306-G07 RF-82: RBAC de M06 que audita el rechazo 403 |
# | 2026-11-10 | Arekkazu | INC-M06-351 RF-87: el 403 auditado también nombra el rol del usuario |
# | 2026-11-10 | Arekkazu | TC-DIS-262 RF-93: variante «alguno de» para lecturas compartidas |
"""Dependencia RBAC de M06 que registra en RF-94 cada rechazo 403 (RNF-82-05).

La autorización sigue siendo ``require_permission_sobre``; esta capa solo agrega el evento
``ACCESO_NO_AUTORIZADO`` con la ruta y el activo o período que trae la URL. Un token ausente
o inválido es un 401 de M01 y no llega hasta aquí."""
from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.financial_valuation.application.use_cases.auditoria.registrar_acceso_no_autorizado_use_case import (
    RegistrarAccesoNoAutorizadoUseCase,
)
from src.financial_valuation.infrastructure.repositories.auditoria_financiera_repository import (
    SqlAlchemyAuditoriaFinancieraRepository,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import AuthorizationError
from src.shared.rbac import require_alguno_sobre, require_permission_sobre


def _id_de_ruta(request: Request, nombre: str) -> Optional[int]:
    try:
        valor = int(request.path_params.get(nombre))
    except (TypeError, ValueError):
        return None
    return valor if valor > 0 else None


def require_permission_m06(nombre_recurso: str, id_accion: int, *, mensaje_denegado: Optional[str] = None) -> Callable:
    return _auditada(require_permission_sobre(nombre_recurso, id_accion, mensaje_denegado=mensaje_denegado), nombre_recurso, id_accion)


def require_alguno_m06(pares: list[tuple[str, int]], *, mensaje_denegado: Optional[str] = None) -> Callable:
    """Como ``require_permission_m06``, pero basta uno de los permisos; el rechazo se audita con el primero."""
    return _auditada(require_alguno_sobre(pares, mensaje_denegado=mensaje_denegado), *pares[0])


def _auditada(verificar_permiso: Callable, nombre_recurso: str, id_accion: int) -> Callable:
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        usuario_actual: UsuarioActual = Depends(get_current_user),
    ) -> None:
        try:
            verificar_permiso(db=db, usuario_actual=usuario_actual)
        except AuthorizationError as exc:
            RegistrarAccesoNoAutorizadoUseCase(db, SqlAlchemyAuditoriaFinancieraRepository(db)).execute(
                id_usuario=usuario_actual.id_usuario, id_rol=usuario_actual.id_rol, recurso=nombre_recurso,
                id_accion=id_accion, error_code=exc.code, metodo_http=request.method,
                ruta=getattr(request.scope.get("route"), "path", request.url.path),
                id_activo_biologico=_id_de_ruta(request, "id_activo_biologico"),
                id_periodo_contable=_id_de_ruta(request, "id_periodo_contable"),
            )
            raise

    # Las pruebas lo usan para asegurar que ninguna ruta de M06 quede con RBAC sin auditoría.
    dependency.audita_rechazo_rbac_m06 = True
    return dependency
