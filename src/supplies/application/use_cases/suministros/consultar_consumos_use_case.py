"""Caso de uso: consultar/buscar registros de consumo de alimento (RF-75).

Permite filtrar por activo, rango de fechas, tipo de alimento y estado.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento
from src.supplies.domain.repositories.consumo_alimento_repository import ConsumoAlimentoRepository


class ConsultarConsumosUseCase:
    """Lista registros de consumo aplicando los filtros de búsqueda de RF-75."""

    def __init__(self, consumo_repo: ConsumoAlimentoRepository) -> None:
        self.consumo_repo = consumo_repo

    def execute(
        self,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        tipo_alimento: Optional[str] = None,
        estado_registro: Optional[str] = None,
    ) -> list[ConsumoAlimento]:
        return self.consumo_repo.listar(
            id_activo_biologico=id_activo_biologico,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            tipo_alimento=tipo_alimento,
            estado_registro=estado_registro,
        )
