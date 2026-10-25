# | Fecha      | Nombre  | Que se hizo                                           |
# |------------|---------|-------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: audita 403 sin modificar el RBAC comun   |
"""Auditoría CA-17 limitada a las rutas autenticadas de alertas operativas."""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import AppError
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository

logger = logging.getLogger(__name__)


def capturar_contexto_alertas(
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
) -> None:
    """Se ejecuta antes de RBAC; reutiliza sus dependencias autenticadas."""
    request.state.rf57_contexto = (db, usuario)


def _registrar_denegacion(request: Request, error: AppError | HTTPException) -> None:
    contexto = getattr(request.state, "rf57_contexto", None)
    if contexto is None or getattr(request.state, "rf57_403_auditado", False):
        return
    request.state.rf57_403_auditado = True
    db, usuario = contexto
    try:
        # Mismo patrón de RF-63 que los rechazos de transición: primero se
        # revierte negocio, luego la bitácora se confirma en una transacción nueva.
        db.rollback()
        id_alerta = request.path_params.get("id_alerta")
        RegistrarEventoAuditoriaIotUseCase(db, SqlAlchemyBitacoraAuditoriaIotRepository(db)).execute(
            tipo_evento="ACCESO_DENEGADO",
            resultado=TipoResultado.RECHAZADO,
            componente_origen=ComponenteOrigen.RF57,
            severidad_log=SeveridadLog.WARNING,
            descripcion="Operación de alertas rechazada por autorización.",
            entidad_afectada_tipo=EntidadAfectadaTipo.ALERTA,
            entidad_afectada_id=str(id_alerta) if id_alerta is not None else None,
            id_usuario=usuario.id_usuario,
            accion_detallada={
                "error_code": getattr(error, "code", "ACCESO_DENEGADO"),
                "metodo": request.method,
                "ruta": request.scope["route"].path,
                "id_recurso": 32,
                "id_accion": 2 if request.method == "GET" else 3,
            },
        )
    except Exception:
        # Nunca sustituir el 403 original ni registrar secretos del request.
        logger.warning("RF-57: no se pudo auditar el rechazo de autorización.")


class RutaAlertaAuditada(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def atender(request: Request):
            try:
                return await handler(request)
            except (AppError, HTTPException) as error:
                if error.status_code == 403:
                    await run_in_threadpool(_registrar_denegacion, request, error)
                raise

        return atender
