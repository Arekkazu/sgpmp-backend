# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-93: generar y aprobar el estado de resultados del período agropecuario |
# | 2026-11-10 | Arekkazu | INC-M06-337-G37 RF-86: acumulado del período abierto sin versión |
# | 2026-11-12 | LuisfNarvaez01 | INC-M06-359-G79 RF-93: el estado generado a pedido resta los activos excluidos del cierre |
# | 2026-11-13 | Arekkazu | TC-M06-G74 RF-93 FA-2: conciliación del estado de resultados con sus fuentes (hechos sin asiento) |
"""Casos de uso RF-93. Solo sobre períodos CERRADOS (R1), salvo el acumulado de RF-86 (sin versión).
Cada generación es una versión nueva; la anterior no cambia (R5). Los filtros (especie, activo, infraestructura, finca) suman al consolidado
porque cada línea y cada costo pertenecen a un solo activo (CA-2, CA-11)."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.reportes import ConciliacionError, ConstructorEstadoResultados
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.shared.errors import BusinessRuleError, NotFoundError

logger = logging.getLogger(__name__)


class GenerarEstadoResultadosUseCase:
    def __init__(self, db: Session, periodos: PeriodoRepository, reportes: ReporteRepository,
                 constructor: ConstructorEstadoResultados, auditoria: AuditoriaFinancieraRepository,
                 notificador: Optional[NotificacionFinancieraPort] = None) -> None:
        self.db = db
        self.periodos = periodos
        self.reportes = reportes
        self.constructor = constructor
        self.auditoria = auditoria
        self.notificador = notificador

    def _cerrado(self, id_periodo_contable: int):
        periodo = self.periodos.obtener(id_periodo_contable)
        if periodo is None:
            raise NotFoundError(code="PERIODO_NO_ENCONTRADO", message="El período contable no existe.")
        if periodo.estado != "CERRADO":  # FA-1
            raise BusinessRuleError(code="PERIODO_NO_CERRADO",
                                    message="Período no cerrado; ejecute el cierre antes de generar el estado.")
        return periodo

    def acumulado(self, id_periodo_contable: int, filtros: dict) -> dict:
        """RF-86: lo que el período lleva acumulado, sin guardar versión; sirve también con el período ABIERTO.
        RF-93 (versionado, aprobación y descarga) sigue siendo solo del período cerrado."""
        periodo = self.periodos.obtener(id_periodo_contable)
        if periodo is None:
            raise NotFoundError(code="PERIODO_NO_ENCONTRADO", message="El período contable no existe.")
        calculo = self.constructor.calcular(id_periodo_contable, {k: v for k, v in filtros.items() if v})
        return {**calculo, "id_periodo_contable": id_periodo_contable, "estado_periodo": periodo.estado,
                "es_definitivo": periodo.estado == "CERRADO"}

    def generar(self, id_periodo_contable: int, filtros: dict, id_usuario: int) -> dict:
        self._cerrado(id_periodo_contable)
        ejecucion = self.periodos.ultima_ejecucion(id_periodo_contable) or {}
        filtros = {k: v for k, v in filtros.items() if v}
        try:
            # Solo los activos excluidos del cierre: las líneas con trazabilidad pendiente (las que traen
            # id_linea) ya pasaron al período siguiente y no cuentan en este (RF-87 paso 3).
            excluidos = [e for e in (ejecucion.get("activos_excluidos") or []) if not e.get("id_linea")]
            resultado = self.constructor.guardar(id_periodo_contable, filtros, id_usuario, excluidos)
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="ESTADO_RESULTADOS_GENERADO", severidad="INFO", id_usuario=id_usuario,
                payload={"filtros": filtros, "resultado_neto": str(resultado["resultado_neto"]), "version": resultado["version"]},
                id_periodo_contable=id_periodo_contable, id_referencia=resultado["id_estado"],
                monto_afectado=resultado["resultado_neto"],
            ))
            self.db.commit()
        except ConciliacionError as exc:  # FA-2: no se genera; la discrepancia queda en RF-94 y se avisa
            self.db.rollback()
            self._discrepancia(exc, id_usuario)
            raise
        except Exception:
            self.db.rollback()
            raise
        return resultado

    def _discrepancia(self, exc: ConciliacionError, id_usuario: int) -> None:
        try:
            self.auditoria.registrar(exc.evento(id_usuario))
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("RF-93 FA-2: no se pudo registrar la discrepancia del período %s.", exc.id_periodo_contable)
        if self.notificador is not None:
            exc.avisar(self.notificador)

    def aprobar(self, id_estado: int, id_usuario: int) -> dict:
        estado = self.reportes.obtener_estado(id_estado)
        if estado is None:
            raise NotFoundError(code="ESTADO_RESULTADOS_NO_ENCONTRADO", message="El estado de resultados no existe.")
        if estado["estado"] != "GENERADO":
            raise BusinessRuleError(code="ESTADO_RESULTADOS_YA_APROBADO", message="El estado de resultados ya fue aprobado.")
        try:
            self.reportes.aprobar_estado(id_estado, id_usuario)
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="ESTADO_RESULTADOS_APROBADO", severidad="INFO", id_usuario=id_usuario, payload={},
                id_periodo_contable=estado["id_periodo_contable"], id_referencia=id_estado))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.reportes.obtener_estado(id_estado)
