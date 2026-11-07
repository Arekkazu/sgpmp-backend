# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-87/RF-89/RF-109: periodicidad, umbral de desviación y alertas de precio |
"""Caso de uso: actualizar la configuración contable de la instalación (fila única).

La periodicidad nueva rige para los períodos que se creen desde ahora (RF-87 v1.1: "un cambio
rige desde el período siguiente"); los períodos ya creados conservan su tipo."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import ConfiguracionContable, EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository


class ActualizarConfiguracionContableUseCase:
    def __init__(self, db: Session, config: ConfiguracionContableRepository, auditoria: AuditoriaFinancieraRepository) -> None:
        self.db = db
        self.config = config
        self.auditoria = auditoria

    def execute(self, tipo_cierre: str, pct_umbral: Decimal, dias_alerta: int, id_usuario: int) -> ConfiguracionContable:
        anterior = self.config.obtener()
        try:
            nueva = self.config.actualizar(tipo_cierre, pct_umbral, dias_alerta, id_usuario)
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="CONFIGURACION_CONTABLE_ACTUALIZADA", severidad="INFO", id_usuario=id_usuario,
                payload={"tipo_cierre": tipo_cierre, "pct_umbral_desviacion_precio": str(pct_umbral),
                         "dias_alerta_vencimiento_precio": dias_alerta},
                datos_anteriores={"tipo_cierre": anterior.tipo_cierre,
                                  "pct_umbral_desviacion_precio": str(anterior.pct_umbral_desviacion_precio),
                                  "dias_alerta_vencimiento_precio": anterior.dias_alerta_vencimiento_precio},
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return nueva
