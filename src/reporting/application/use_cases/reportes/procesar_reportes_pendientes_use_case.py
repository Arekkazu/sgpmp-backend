# | Fecha      | Nombre   | Que se hizo                                                              |
# |------------|----------|--------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: generación en segundo plano con 2 reintentos y aviso al usuario |
"""Caso de uso: genera los reportes de más de 1.000 registros (RF-104 Fase 3, RNF-02, RNF-07).

Toma de a una las solicitudes EN_PROCESO cuyo intento ya llegó (``SKIP LOCKED``: dos procesos no toman la misma),
las vuelve a armar en una instantánea con la identidad y la zona de quien las pidió y guarda el archivo. Si falla,
reintenta a los 30 s hasta 2 veces y después la marca FALLIDA. Al terminar avisa al usuario por la bandeja (CA-10)
y deja la auditoría. Si el usuario ya no puede generar ese reporte (le quitaron el permiso o la finca), falla sin
reintentos."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.reporting.application.use_cases.reportes.generacion import (
    AbrirFuente,
    Solicitante,
    detalle_auditoria,
    exigir_datos,
    partir_en_archivos,
    preparar,
)
from src.reporting.domain.repositories.solicitud_reporte_repository import (
    AvisosReportesPort,
    RenderizadorReportePort,
    SolicitudReporteRepository,
)
from src.reporting.domain.reportes.catalogo import CATALOGO
from src.reporting.domain.reportes.solicitud import EN_PROCESO, FALLIDO, SolicitudReporte
from src.shared.errors import AuthorizationError, BusinessRuleError, FlowError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class ProcesarReportesPendientesUseCase:

    def __init__(self, db: Session, repo: SolicitudReporteRepository, abrir_fuente: AbrirFuente,
                 renderizador: RenderizadorReportePort, avisos: AvisosReportesPort,
                 solicitante: Callable[[int, str], Solicitante]) -> None:
        self.db = db
        self.repo = repo
        self.abrir_fuente = abrir_fuente
        self.renderizador = renderizador
        self.avisos = avisos
        self.solicitante = solicitante

    def execute(self, ahora: Optional[datetime] = None, maximo: int = 5) -> int:
        procesadas = 0
        for _ in range(maximo):
            ahora_i = ahora or datetime.now(timezone.utc)
            pendientes = self.repo.tomar_pendientes(ahora_i, 1)
            if not pendientes:
                break
            self._procesar(pendientes[0], ahora_i)
            procesadas += 1
        return procesadas

    def _procesar(self, solicitud: SolicitudReporte, ahora: datetime) -> None:
        titulo = CATALOGO[solicitud.tipo_reporte].titulo
        preparado = None
        try:
            solicitante = self.solicitante(solicitud.id_usuario, solicitud.zona_horaria)
            with self.abrir_fuente(solicitud.id_usuario, solicitud.zona_horaria) as fuente:
                preparado = preparar(fuente, solicitud.tipo_reporte, solicitud.filtros, solicitante, ahora)
                exigir_datos(preparado.contenido)
                ruta_logo = fuente.ruta_logo(preparado.id_finca_logo) if preparado.id_finca_logo else None
                partes = partir_en_archivos(preparado.contenido, solicitud.formato, self.renderizador, ruta_logo,
                                            ahora)
            solicitud.registrar_generacion(partes, preparado.contenido.numero_registros,
                                           preparado.fecha_snapshot or ahora, ahora)
            self.repo.guardar(solicitud)
            self.repo.guardar_archivos(solicitud.id_solicitud_reporte, partes)
            self.db.commit()
        except (ValidationError, AuthorizationError, NotFoundError, BusinessRuleError, FlowError) as exc:
            # Ya no se puede generar con esos filtros o ese usuario: reintentar no lo arregla.
            self.db.rollback()
            self._fallo(solicitud.id_solicitud_reporte, ahora, titulo, mensaje=exc.message)
            return
        except Exception:
            logger.exception("RF-104: falló la generación del reporte %s", solicitud.id_solicitud_reporte)
            self.db.rollback()
            self._fallo(solicitud.id_solicitud_reporte, ahora, titulo)
            return
        self.avisos.registrar(solicitud, titulo, detalle_auditoria(
            preparado, solicitud.formato, solicitud.estado, solicitud.checksum_sha256, solicitud.numero_registros,
            solicitud.id_solicitud_reporte), notificar=True)

    def _fallo(self, id_solicitud, ahora: datetime, titulo: str, mensaje: Optional[str] = None) -> None:
        try:
            solicitud = self.repo.obtener(id_solicitud, bloquear=True)
            if solicitud is None or solicitud.estado != EN_PROCESO:
                self.db.rollback()
                return
            if mensaje:
                solicitud.marcar_fallida(mensaje)
            else:
                solicitud.registrar_intento_fallido(ahora)
            self.repo.guardar(solicitud)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("RF-104: no se pudo registrar el fallo del reporte %s", id_solicitud)
            return
        if solicitud.estado == FALLIDO:
            self.avisos.registrar(solicitud, titulo, {
                "id_reporte": str(id_solicitud), "tipo_reporte": solicitud.tipo_reporte,
                "filtros_aplicados": solicitud.filtros, "formato": solicitud.formato, "estado_final": FALLIDO,
                "intentos": solicitud.intentos, "checksum": None}, notificar=True)
