# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: descarga solo del dueño, 48 h y verificación de integridad |
"""Caso de uso: descargar una parte de un reporte generado (RF-104, CA-13, CA-14, RNF-05, RNF-10).

Solo quien lo pidió (403 para otro usuario), cuantas veces quiera dentro de las 48 h (después, 410). Antes de
entregar el archivo se verifica su checksum: si no coincide, el reporte queda FALLIDO y se avisa al usuario."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.reporting.domain.repositories.solicitud_reporte_repository import AvisosReportesPort, SolicitudReporteRepository
from src.reporting.domain.reportes.catalogo import CATALOGO
from src.reporting.domain.reportes.solicitud import ArchivoReporte
from src.shared.errors import BusinessRuleError, NotFoundError

_NO_EXISTE = NotFoundError(code="REPORTE_INEXISTENTE", message="Ese reporte no existe.", field="id_reporte")
MENSAJE_INTEGRIDAD = "El archivo del reporte no pasó la verificación de integridad. Vuelve a generarlo."


class DescargarReporteUseCase:

    def __init__(self, db: Session, repo: SolicitudReporteRepository, avisos: AvisosReportesPort) -> None:
        self.db = db
        self.repo = repo
        self.avisos = avisos

    def execute(self, id_reporte: UUID, numero_parte: int, id_usuario: int,
                ahora: Optional[datetime] = None) -> ArchivoReporte:
        ahora = ahora or datetime.now(timezone.utc)
        solicitud = self.repo.obtener(id_reporte)
        if solicitud is None:
            raise _NO_EXISTE
        solicitud.exigir_descargable(id_usuario, ahora)
        archivo = self.repo.obtener_archivo(id_reporte, numero_parte)
        if archivo is None:
            raise NotFoundError(code="PARTE_INEXISTENTE", message="Esa parte del reporte no existe.",
                                field="numero_parte")
        if archivo.integro():
            return archivo
        try:
            solicitud.marcar_fallida(MENSAJE_INTEGRIDAD)
            self.repo.guardar(solicitud)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.avisos.registrar(solicitud, CATALOGO[solicitud.tipo_reporte].titulo, {
            "id_reporte": str(id_reporte), "tipo_reporte": solicitud.tipo_reporte, "estado_final": solicitud.estado,
            "checksum": solicitud.checksum_sha256, "motivo": "checksum"}, notificar=True)
        raise BusinessRuleError(code="REPORTE_CORRUPTO", message=MENSAJE_INTEGRIDAD, field="id_reporte")
