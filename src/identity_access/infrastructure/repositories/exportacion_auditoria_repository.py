"""Implementación SQLAlchemy de la cola de exportaciones de auditoría (RF-10)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.exportacion_auditoria import (
    ConfiguracionExportacion,
    EstadoExportacion,
    ResultadoExportacion,
    TrabajoExportacion,
)
from src.identity_access.domain.repositories.exportacion_auditoria_repository import (
    ExportacionAuditoriaRepository,
)
from src.identity_access.infrastructure.models.cola_exportacion_auditoria_model import (
    ColaExportacionAuditoria,
    ConfiguracionBatchExportacionAuditoria,
    EjecucionExportacionAuditoria,
)
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyExportacionAuditoriaRepository(ExportacionAuditoriaRepository):
    """Adaptador SQLAlchemy de la cola y sus resultados."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(
        orm: ColaExportacionAuditoria,
        ejecucion: Optional[EjecucionExportacionAuditoria] = None,
    ) -> TrabajoExportacion:
        return TrabajoExportacion(
            id_cola=orm.id_cola,
            parametros=orm.parametros,
            id_usuario_solicitante=orm.id_usuario_solicitante,
            estado=orm.estado,
            intentos=orm.intentos,
            error=orm.error,
            fecha_solicitud=orm.fecha_solicitud,
            fecha_procesado=orm.fecha_procesado,
            total_exportado=ejecucion.total_exportado if ejecucion else None,
            total_disponible=ejecucion.total_disponible if ejecucion else None,
        )

    def encolar(self, trabajo: TrabajoExportacion) -> TrabajoExportacion:
        try:
            orm = ColaExportacionAuditoria(
                parametros=trabajo.parametros,
                id_usuario_solicitante=trabajo.id_usuario_solicitante,
                estado=EstadoExportacion.PENDIENTE.value,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener(self, id_cola: int) -> Optional[TrabajoExportacion]:
        orm = self.db.get(ColaExportacionAuditoria, id_cola)
        if orm is None:
            return None
        ejecucion = self.db.scalar(
            select(EjecucionExportacionAuditoria).where(
                EjecucionExportacionAuditoria.id_cola == id_cola
            )
        )
        return self._a_entidad(orm, ejecucion)

    def contar_activos(self) -> int:
        return (
            self.db.query(ColaExportacionAuditoria)
            .filter(
                ColaExportacionAuditoria.estado.in_(
                    (EstadoExportacion.PENDIENTE.value, EstadoExportacion.EN_PROCESO.value)
                )
            )
            .count()
        )

    def tomar_pendiente(self) -> Optional[TrabajoExportacion]:
        # SKIP LOCKED evita que dos workers reclamen el mismo trabajo: el segundo
        # salta la fila bloqueada en vez de esperarla.
        orm = self.db.scalars(
            select(ColaExportacionAuditoria)
            .where(ColaExportacionAuditoria.estado == EstadoExportacion.PENDIENTE.value)
            .order_by(ColaExportacionAuditoria.fecha_solicitud)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if orm is None:
            return None

        orm.estado = EstadoExportacion.EN_PROCESO.value
        orm.intentos += 1
        self.db.flush()
        return self._a_entidad(orm)

    def completar(self, id_cola: int, resultado: ResultadoExportacion) -> None:
        try:
            self.db.add(
                EjecucionExportacionAuditoria(
                    id_cola=id_cola,
                    contenido_csv=resultado.contenido_csv,
                    nombre_archivo=resultado.nombre_archivo,
                    total_exportado=resultado.total_exportado,
                    total_disponible=resultado.total_disponible,
                )
            )
            orm = self.db.get(ColaExportacionAuditoria, id_cola)
            orm.estado = EstadoExportacion.COMPLETADO.value
            orm.fecha_procesado = datetime.now(timezone.utc)
            orm.error = None
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def fallar(self, id_cola: int, error: str, reintentable: bool) -> None:
        orm = self.db.get(ColaExportacionAuditoria, id_cola)
        if orm is None:
            return
        # Vuelve a PENDIENTE mientras queden reintentos; el poller lo retomará.
        orm.estado = (
            EstadoExportacion.PENDIENTE.value
            if reintentable
            else EstadoExportacion.FALLIDO.value
        )
        orm.error = error[:2000]
        if not reintentable:
            orm.fecha_procesado = datetime.now(timezone.utc)
        self.db.flush()

    def obtener_resultado(self, id_cola: int) -> Optional[ResultadoExportacion]:
        ejecucion = self.db.scalar(
            select(EjecucionExportacionAuditoria).where(
                EjecucionExportacionAuditoria.id_cola == id_cola
            )
        )
        if ejecucion is None:
            return None
        return ResultadoExportacion(
            contenido_csv=ejecucion.contenido_csv,
            nombre_archivo=ejecucion.nombre_archivo,
            total_exportado=ejecucion.total_exportado,
            total_disponible=ejecucion.total_disponible,
        )

    def obtener_configuracion(self) -> ConfiguracionExportacion:
        orm = self.db.scalars(
            select(ConfiguracionBatchExportacionAuditoria).limit(1)
        ).first()
        if orm is None:
            # La migración siembra la fila; si no está, los valores por defecto
            # dejan el sistema operativo en vez de tumbar el poller.
            return ConfiguracionExportacion()
        return ConfiguracionExportacion(
            num_workers_max=orm.num_workers_max,
            max_reintentos=orm.max_reintentos,
            umbral_exportacion_async=orm.umbral_exportacion_async,
            limite_concurrencia=orm.limite_concurrencia,
            intervalo_poll_segundos=orm.intervalo_poll_segundos,
            es_activo=orm.es_activo,
        )
