# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-92: informe de revelaciones NIC 41 (borrador, aprobación, rechazo) |
# | 2026-11-13 | Leandro | TC-M06-G61 RF-92: avisar al Contador tras guardar el informe con faltantes. |
"""Casos de uso RF-92. El informe se genera en BORRADOR sobre un período CERRADO; las alertas de
consistencia no lo bloquean, pero continuar con ellas exige justificación (paso 3, FA-2). Al aprobar
una versión, la APROBADA anterior pasa a ARCHIVADO (R4)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.reportes import ConstructorInformeRevelaciones, avisar_supuestos_insuficientes
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class GenerarInformeRevelacionesUseCase:
    def __init__(self, db: Session, periodos: PeriodoRepository, reportes: ReporteRepository,
                 constructor: ConstructorInformeRevelaciones, auditoria: AuditoriaFinancieraRepository,
                 notificador: NotificacionFinancieraPort) -> None:
        self.db = db
        self.periodos = periodos
        self.reportes = reportes
        self.constructor = constructor
        self.auditoria = auditoria
        self.notificador = notificador

    def generar(self, id_periodo_contable: int, manuales: dict, justificacion_inconsistencias: Optional[str],
                id_usuario: int) -> dict:
        periodo = self.periodos.obtener(id_periodo_contable)
        if periodo is None or periodo.estado != "CERRADO":  # FA-1
            raise BusinessRuleError(code="PERIODO_NO_CERRADO", message="El informe solo se genera sobre períodos cerrados.")
        if not (manuales.get("compromisos_vigentes") or manuales.get("activos_pignorados") or manuales.get("declaracion_sin_novedad")):
            raise BusinessRuleError(code="REVELACIONES_MANUALES_REQUERIDAS", message=(
                "Ingrese los compromisos y activos pignorados del período o declare que no existen (NIC 41 ¶49)."))
        previa = self.constructor.construir(id_periodo_contable, manuales)
        if previa["alertas_consistencia"] and len((justificacion_inconsistencias or "").strip()) < 20:
            raise ConflictError(code="ALERTA_CONSISTENCIA", message=(
                "Se detectaron inconsistencias entre las fuentes: " +
                "; ".join(a["detalle"] for a in previa["alertas_consistencia"][:5]) +
                ". Resuélvalas o continúe con una justificación (mínimo 20 caracteres)."))
        try:
            if previa["alertas_consistencia"]:
                self.auditoria.registrar(EventoAuditoria(
                    tipo_evento="ERROR_CONSISTENCIA", severidad="WARNING", id_usuario=id_usuario,
                    payload={"alertas": previa["alertas_consistencia"], "justificacion": justificacion_inconsistencias},
                    id_periodo_contable=id_periodo_contable))
            resultado = self.constructor.guardar(
                id_periodo_contable, manuales, id_usuario, justificacion_inconsistencias, informe=previa,
            )
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="INFORME_REVELACIONES_GENERADO", severidad="INFO", id_usuario=id_usuario,
                payload={"version": resultado["version_informe"]}, id_periodo_contable=id_periodo_contable,
                id_referencia=resultado["id_informe"]))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        avisar_supuestos_insuficientes(self.notificador, id_periodo_contable, resultado)
        resultado.pop("supuestos_insuficientes")
        return resultado

    def resolver(self, id_informe: int, aprobar: bool, razon: Optional[str], id_usuario: int) -> dict:
        informe = self.reportes.obtener_informe(id_informe)
        if informe is None:
            raise NotFoundError(code="INFORME_NO_ENCONTRADO", message="El informe no existe.")
        if informe["estado"] != "BORRADOR":
            raise BusinessRuleError(code="INFORME_NO_EDITABLE", message=f"El informe está {informe['estado']}.")
        if not aprobar and len((razon or "").strip()) < 20:  # FA-4
            raise BusinessRuleError(code="RAZON_RECHAZO_OBLIGATORIA", message="Indique la razón del rechazo (mínimo 20 caracteres).")
        try:
            if aprobar:
                self.reportes.aprobar_informe(id_informe, id_usuario)
            else:
                self.reportes.rechazar_informe(id_informe, razon.strip())
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="INFORME_REVELACIONES_APROBADO" if aprobar else "INFORME_REVELACIONES_RECHAZADO",
                severidad="INFO", id_usuario=id_usuario, payload={"version": informe["version_informe"], "razon": razon},
                id_periodo_contable=informe["id_periodo_contable"], id_referencia=id_informe))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.reportes.obtener_informe(id_informe)
