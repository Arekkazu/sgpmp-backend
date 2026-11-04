# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82/RF-88: clasificación, categoría de precio y vida útil por especie |
"""Caso de uso: parámetros contables de una especie (clasificación PRODUCCION/CONSUMO de NIC 41
¶43, categoría de precio con que se mide y vida útil para el modelo de costo de RF-88). Un cambio de
vida útil aplica a las depreciaciones siguientes, no recalcula las ya registradas (RF-88 R3)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, ParametroEspecie
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository


class GuardarParametroEspecieUseCase:
    def __init__(self, db: Session, config: ConfiguracionContableRepository, auditoria: AuditoriaFinancieraRepository) -> None:
        self.db = db
        self.config = config
        self.auditoria = auditoria

    def execute(self, parametro: ParametroEspecie, id_usuario: int) -> ParametroEspecie:
        anterior = self.config.parametro_especie(parametro.id_especie)
        try:
            self.config.guardar_parametro_especie(parametro, id_usuario)
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="CONFIGURACION_CONTABLE_ACTUALIZADA", severidad="INFO", id_usuario=id_usuario,
                payload={"parametro_especie": parametro.__dict__},
                datos_anteriores=anterior.__dict__ if anterior else None, id_referencia=parametro.id_especie,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return parametro
