# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: purga de archivos vencidos   |
"""Caso de uso: purgar los archivos exportados vencidos (RF-77 24 h, RF-81 72 h).

Borra el contenido (la fila queda para que la descarga responda 410) y, para
las exportaciones de historial, deja la eliminación en la bitácora de M05
(RF-81 RNF-06). Corre en la tarea de fondo del historial, como usuario de servicio.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.supplies.domain.repositories.archivo_exportacion_repository import ArchivoExportacionRepository
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)


class PurgarArchivosVencidosUseCase:
    def __init__(
        self,
        db: Session,
        archivo_repo: ArchivoExportacionRepository,
        auditoria_port: AuditoriaSuministroPort,
        id_usuario_sistema: int,
    ) -> None:
        self.db = db
        self.archivo_repo = archivo_repo
        self.auditoria_port = auditoria_port
        self.id_usuario_sistema = id_usuario_sistema

    def execute(self) -> int:
        try:
            purgados = self.archivo_repo.purgar_vencidos(datetime.now(timezone.utc))
            for archivo in purgados:
                if archivo.origen != "RF81":
                    continue
                self.auditoria_port.registrar(
                    EventoAuditoriaSuministro(
                        entidad_afectada="archivos_exportacion_suministros",
                        tipo_operacion="EXPORTACION_HISTORIAL_ELIMINADA",
                        id_usuario=self.id_usuario_sistema,
                        resultado="EXITOSO",
                        detalle_causa=(
                            f"Archivo {archivo.nombre_archivo} (trabajo {archivo.id_referencia}) eliminado al "
                            "cumplir 72 horas (RF-81 Restricción 3)."
                        ),
                    )
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(purgados)
