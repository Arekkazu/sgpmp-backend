"""Caso de uso: consultar/buscar aplicaciones de medicamento (RF-76).

Permite filtrar por activo, rango de fechas y estado.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.supplies.domain.entities.medicamento import Medicamento
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository


class ConsultarMedicamentosUseCase:
    """Lista aplicaciones de medicamento aplicando los filtros de búsqueda de RF-76."""

    def __init__(self, medicamento_repo: MedicamentoRepository) -> None:
        self.medicamento_repo = medicamento_repo

    def execute(
        self,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        estado_registro: Optional[str] = None,
    ) -> list[Medicamento]:
        return self.medicamento_repo.listar(
            id_activo_biologico=id_activo_biologico,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            estado_registro=estado_registro,
        )
