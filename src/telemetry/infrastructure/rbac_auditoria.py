# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
"""Dependencia RBAC que deja en la bitácora de RF-63 los intentos sin permiso (M03).

Mismo patrón que ``require_permission_m02`` de activos biológicos: la autorización sigue
delegada a ``src.shared.rbac.require_permission``; esta capa solo registra el 403.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import AuthorizationError
from src.shared.rbac import require_permission
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, SeveridadLog, TipoResultado
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
    SqlAlchemyBitacoraAuditoriaIotRepository,
)


def require_permission_auditado(
    id_recurso: int,
    id_accion: int,
    *,
    componente_origen: ComponenteOrigen,
    tipo_evento: str,
) -> Callable:
    """Aplica el RBAC compartido y registra en RF-63 cualquier rechazo 403."""
    verificar_permiso = require_permission(id_recurso, id_accion)

    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        usuario_actual: UsuarioActual = Depends(get_current_user),
    ) -> None:
        try:
            verificar_permiso(db=db, usuario_actual=usuario_actual)
        except AuthorizationError as exc:
            RegistrarEventoAuditoriaIotUseCase(db, SqlAlchemyBitacoraAuditoriaIotRepository(db)).execute(
                tipo_evento=tipo_evento,
                resultado=TipoResultado.RECHAZADO,
                componente_origen=componente_origen,
                severidad_log=SeveridadLog.WARNING,
                descripcion=exc.message,
                id_usuario=usuario_actual.id_usuario,
                accion_detallada={
                    'id_usuario': usuario_actual.id_usuario,
                    'id_rol': usuario_actual.id_rol,
                    'id_recurso': id_recurso,
                    'id_accion': id_accion,
                    'error_code': exc.code,
                    'metodo_http': request.method,
                    'ruta': getattr(request.scope.get('route'), 'path', request.url.path),
                    'filtros': dict(request.query_params),
                },
            )
            raise

    return dependency
