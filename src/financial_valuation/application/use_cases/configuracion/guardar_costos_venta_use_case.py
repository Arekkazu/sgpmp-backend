# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-84: costos de venta parametrizados por especie |
"""Caso de uso RF-84: porcentajes de costos de venta (transporte, comisiones, impuestos de la
transacción) por especie. El parámetro anterior queda en el historial; los cálculos ya hechos no
cambian (RNF-84-05)."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository
from src.financial_valuation.domain.value_objects.nic41 import REGION_GENERAL


class GuardarCostosVentaUseCase:
    def __init__(self, db: Session, config: ConfiguracionContableRepository, auditoria: AuditoriaFinancieraRepository) -> None:
        self.db = db
        self.config = config
        self.auditoria = auditoria

    def execute(self, id_especie: int, pct_transporte: Decimal, pct_comisiones: Decimal, pct_impuestos: Decimal,
                id_usuario: int) -> int:
        try:
            nuevo = self.config.guardar_costos_venta(id_especie, REGION_GENERAL, pct_transporte, pct_comisiones,
                                                     pct_impuestos, id_usuario)
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="PARAMETRO_COSTOS_VENTA_ACTUALIZADO", severidad="INFO", id_usuario=id_usuario,
                payload={"id_especie": id_especie, "pct_transporte": str(pct_transporte),
                         "pct_comisiones": str(pct_comisiones), "pct_impuestos": str(pct_impuestos)},
                id_referencia=nuevo,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return nuevo
