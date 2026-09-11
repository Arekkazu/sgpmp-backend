"""Implementación SQLAlchemy de :class:`ConsumoICAReadPort` (RF-74).

Suma el alimento VALIDADO de ``modulo5.registros_consumo_alimentos`` en el período.
Reutiliza el modelo ORM y el enum de estado de CU-01.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.consumo_ica_read_port import ConsumoICAReadPort
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
from src.supplies.infrastructure.models.registro_consumo_alimento_model import RegistroConsumoAlimentoModel


class SqlAlchemyConsumoICAReadRepository(ConsumoICAReadPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def sumar_alimento_validado(
        self, id_activo_biologico: int, fecha_desde: date, fecha_hasta: date
    ) -> Optional[Decimal]:
        total = (
            self.db.query(func.sum(RegistroConsumoAlimentoModel.cantidad_suministrada))
            .filter(
                RegistroConsumoAlimentoModel.id_activo_biologico == id_activo_biologico,
                RegistroConsumoAlimentoModel.estado_registro == EstadoRegistro.VALIDADO.value,
                RegistroConsumoAlimentoModel.fecha_consumo >= fecha_desde,
                RegistroConsumoAlimentoModel.fecha_consumo <= fecha_hasta,
            )
            .scalar()
        )
        # ``None`` = ningún registro VALIDADO en el período (distinto de 0).
        return total
