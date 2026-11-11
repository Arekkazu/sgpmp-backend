# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-93: generar y aprobar el estado de resultados del período agropecuario |
# | 2026-11-10 | Arekkazu | INC-M06-337-G37 RF-86: acumulado del período abierto sin versión |
"""Casos de uso RF-93. Solo sobre períodos CERRADOS (R1), salvo el acumulado de RF-86 (sin versión).
Cada generación es una versión nueva; la anterior no cambia (R5). Los filtros (especie, activo, infraestructura, finca) suman al consolidado
porque cada línea y cada costo pertenecen a un solo activo (CA-2, CA-11)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.shared.errors import BusinessRuleError, NotFoundError


class GenerarEstadoResultadosUseCase:
    def __init__(self, db: Session, periodos: PeriodoRepository, reportes: ReporteRepository,
                 constructor: ConstructorEstadoResultados, auditoria: AuditoriaFinancieraRepository) -> None:
        self.db = db
        self.periodos = periodos
        self.reportes = reportes
        self.constructor = constructor
        self.auditoria = auditoria

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
            resultado = self.constructor.guardar(id_periodo_contable, filtros, id_usuario,
                                                 ejecucion.get("activos_excluidos") or [])
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="ESTADO_RESULTADOS_GENERADO", severidad="INFO", id_usuario=id_usuario,
                payload={"filtros": filtros, "resultado_neto": str(resultado["resultado_neto"]), "version": resultado["version"]},
                id_periodo_contable=id_periodo_contable, id_referencia=resultado["id_estado"],
                monto_afectado=resultado["resultado_neto"],
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return resultado

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
