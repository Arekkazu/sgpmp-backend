# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: generación inmediata (≤1.000) o en segundo plano (>1.000) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: el usuario confirma la exportación de un reporte (RF-104 Fase 3).

Hasta 1.000 registros el archivo se genera aquí y queda listo para descargar (CA-3); por encima, la solicitud queda
EN_PROCESO y la toma el proceso en segundo plano, que avisa por la bandeja cuando termina (CA-10). Sin datos para
los filtros responde 422 (FA-2). Cada generación queda auditada (CA-15)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from src.reporting.application.use_cases.reportes.generacion import (
    AbrirFuente,
    Solicitante,
    detalle_auditoria,
    exigir_datos,
    limitar_solicitudes,
    partir_en_archivos,
    preparar,
)
from src.reporting.domain.repositories.solicitud_reporte_repository import (
    AvisosReportesPort,
    RenderizadorReportePort,
    SolicitudReporteRepository,
)
from src.reporting.domain.reportes.catalogo import LIMITE_SINCRONO, filtros_serializables
from src.reporting.domain.reportes.solicitud import EN_PROCESO, SolicitudReporte
from src.shared.errors import TooManyRequestsError

# Reportes grandes en cola a la vez por usuario.
MAX_EN_PROCESO_POR_USUARIO = 5

MENSAJE_SEGUNDO_PLANO = "Tu reporte está siendo generado. Te avisaremos cuando esté listo."


class SolicitarReporteUseCase:
    """Solicita la generación de un reporte."""

    def __init__(self, db: Session, repo: SolicitudReporteRepository, abrir_fuente: AbrirFuente,
                 renderizador: RenderizadorReportePort, avisos: AvisosReportesPort) -> None:
        self.db = db
        self.repo = repo
        self.abrir_fuente = abrir_fuente
        self.renderizador = renderizador
        self.avisos = avisos

    def execute(self, tipo: str, formato: str, filtros: Optional[dict[str, Any]], solicitante: Solicitante,
                ahora: Optional[datetime] = None) -> SolicitudReporte:
        """Genera el reporte al momento o lo deja pendiente si es grande."""
        ahora = ahora or datetime.now(timezone.utc)
        limitar_solicitudes(solicitante.id_usuario)
        recientes = self.repo.listar_por_usuario(solicitante.id_usuario, 50)
        if sum(1 for s in recientes if s.estado == EN_PROCESO) >= MAX_EN_PROCESO_POR_USUARIO:
            raise TooManyRequestsError(code="REPORTES_EN_PROCESO", headers={"Retry-After": "60"}, message=(
                f"Ya tiene {MAX_EN_PROCESO_POR_USUARIO} reportes en preparación. Espere a que terminen."))
        partes = []
        with self.abrir_fuente(solicitante.id_usuario, solicitante.zona_horaria) as fuente:
            preparado = preparar(fuente, tipo, filtros, solicitante, ahora)
            exigir_datos(preparado.contenido)
            if preparado.contenido.numero_registros <= LIMITE_SINCRONO:
                # Dentro de la instantánea: fechas y nombre del archivo en la zona del usuario.
                ruta_logo = fuente.ruta_logo(preparado.id_finca_logo) if preparado.id_finca_logo else None
                partes = partir_en_archivos(preparado.contenido, formato, self.renderizador, ruta_logo, ahora)
        solicitud = SolicitudReporte(id_solicitud_reporte=uuid4(), id_usuario=solicitante.id_usuario, tipo_reporte=tipo,
                                     formato=formato, filtros=filtros_serializables(preparado.filtros),
                                     zona_horaria=solicitante.zona_horaria)
        registros = preparado.contenido.numero_registros
        if registros > LIMITE_SINCRONO:
            solicitud.encolar(ahora)
            solicitud.numero_registros = registros
            try:
                solicitud = self.repo.guardar(solicitud)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return solicitud

        solicitud.registrar_generacion(partes, registros, preparado.fecha_snapshot or ahora, ahora)
        try:
            solicitud = self.repo.guardar(solicitud)
            self.repo.guardar_archivos(solicitud.id_solicitud_reporte, partes)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.avisos.registrar(solicitud, preparado.definicion.titulo, detalle_auditoria(
            preparado, formato, solicitud.estado, solicitud.checksum_sha256, registros, solicitud.id_solicitud_reporte),
            notificar=False)
        return solicitud
