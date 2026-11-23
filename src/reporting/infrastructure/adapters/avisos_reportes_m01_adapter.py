# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: auditoría de reportes y aviso de los generados en fondo |
# | 2026-11-23 | Arekkazu | QA-M08 CU02 H-02 RF-104: la descripción del evento dice formato, filtros y checksum |
"""Adaptador de :class:`AvisosReportesPort` sobre M01, mismo patrón que los avisos de M05 y M06.

Cada generación deja un evento en ``modulo1.eventos`` (hash de integridad) con tipo, filtros, formato, momento de
la instantánea, estado final y checksum (CA-15). Si el reporte se generó en segundo plano, de ese evento cuelga la
notificación interna del usuario: INFORMATIVA si quedó listo, ADVERTENCIA si falló (RF-105, CA-10). Usa una sesión
aparte como sistema y nunca propaga errores."""
from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.reporting.domain.repositories.solicitud_reporte_repository import AvisosReportesPort
from src.reporting.domain.reportes.solicitud import GENERADO, SolicitudReporte

logger = logging.getLogger(__name__)

_ID_CANAL_INTERNO = 2
_FORMATOS = {"PDF": "PDF", "EXCEL": "Excel"}
_SQL_TIPO = text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = :n")


def descripcion_evento(titulo: str, detalle: dict) -> str:
    """Lo que la auditoría muestra del evento (CA-15): reporte, formato, filtros elegidos y checksum del archivo."""
    partes = [f"Reporte {titulo}"]
    if detalle.get("formato") in _FORMATOS:
        partes[0] += f" en {_FORMATOS[detalle['formato']]}"
    if "filtros_legibles" in detalle:
        partes.append("Filtros: " + ("; ".join(detalle["filtros_legibles"]) or "ninguno, todos los registros"))
    if detalle.get("checksum"):
        partes.append(f"Checksum SHA-256: {detalle['checksum']}")
    return ". ".join(partes) + "."


class AvisosReportesM01Adapter(AvisosReportesPort):

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def registrar(self, solicitud: SolicitudReporte, titulo: str, detalle: dict, notificar: bool) -> None:
        generado = solicitud.estado == GENERADO
        tipo = "REPORTE_GENERADO" if generado else "REPORTE_FALLIDO"
        if generado:
            mensaje = (f"Tu reporte «{titulo}» está listo. Descárgalo en Reportes: estará disponible durante "
                       "48 horas.")
        else:
            mensaje = f"No pudimos generar tu reporte «{titulo}». Vuelve a intentarlo desde Reportes."
        db = self.session_factory()
        try:
            id_tipo = db.execute(_SQL_TIPO, {"n": tipo}).scalar()
            if id_tipo is None:
                logger.error("RF-104: falta el tipo de evento %s; el reporte %s queda sin auditoría.", tipo,
                             solicitud.id_solicitud_reporte)
                return
            id_evento = SqlAlchemyEventoRepository(db).registrar(
                tipo_evento=id_tipo, exitoso=generado, id_usuario=solicitud.id_usuario, detalle=detalle,
                descripcion=descripcion_evento(titulo, detalle), modulo="MODULO8")
            if notificar:
                SqlAlchemyNotificacionRepository(db).registrar(
                    id_evento=id_evento, id_usuario=solicitud.id_usuario, id_canal=_ID_CANAL_INTERNO, mensaje=mensaje,
                    estado="en_cola", contexto={"url": "reportes", "id_reporte": str(solicitud.id_solicitud_reporte)})
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("RF-104: no se pudo auditar o avisar el reporte %s.", solicitud.id_solicitud_reporte)
        finally:
            db.close()
