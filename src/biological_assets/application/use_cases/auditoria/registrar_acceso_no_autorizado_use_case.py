"""RF-52: registra rechazos RBAC de los endpoints del módulo M02."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import (
    BitacoraAuditoriaRepository,
)

logger = logging.getLogger(__name__)


class UnidadTrabajoAuditoria(Protocol):
    """Operaciones transaccionales mínimas requeridas por el caso de uso."""

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class RegistrarAccesoNoAutorizadoUseCase:
    """Persiste un 403 RBAC sin alterar la respuesta de autorización.

    RF-52 establece que la auditoría no debe bloquear el flujo emisor. Por eso
    un fallo de persistencia se revierte y se informa en el log técnico, pero no
    sustituye el ``403`` original por un error de infraestructura.
    """

    def __init__(
        self,
        db: UnidadTrabajoAuditoria,
        bitacora_repo: BitacoraAuditoriaRepository,
    ) -> None:
        self.db = db
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        *,
        rf_origen: str,
        id_usuario: int,
        id_recurso: int,
        id_accion: int,
        error_code: str,
        causa: str,
        metodo_http: str,
        ruta: str,
        id_activo_biologico: int | None = None,
    ) -> bool:
        evento = EventoAuditoria(
            rf_origen=rf_origen,
            tipo_evento='ACCESO_NO_AUTORIZADO',
            clasificacion_biologica='ACCESO_DATOS',
            timestamp_evento=datetime.now(timezone.utc),
            resultado='RECHAZADO',
            severidad_log='WARNING',
            id_activo_biologico=id_activo_biologico,
            descripcion='Solicitud rechazada por el control de acceso RBAC.',
            detalle_tecnico={
                'error_code': error_code,
                'causa': causa,
                'id_recurso': id_recurso,
                'id_accion': id_accion,
                'metodo_http': metodo_http,
                'ruta': ruta,
            },
            id_usuario_responsable=id_usuario,
        )

        try:
            self.bitacora_repo.registrar(evento)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            logger.exception(
                'No se pudo registrar ACCESO_NO_AUTORIZADO de %s para el usuario %s.',
                rf_origen,
                id_usuario,
            )
            return False
