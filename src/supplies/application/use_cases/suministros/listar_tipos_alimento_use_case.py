# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-23 | Arekkazu         | M05 RF-75: catálogo de tipos de alimento      |
"""Caso de uso: listar el catálogo de tipos de alimento (RF-75).

El registro de consumo exige un ``id_tipo_alimento`` existente y ACTIVO
(``TIPO_ALIMENTO_NO_ENCONTRADO`` / ``TIPO_ALIMENTO_INACTIVO``); este listado es
lo que el cliente ofrece para elegirlo. El catálogo es global, no por finca.
"""
from __future__ import annotations

from src.supplies.domain.repositories.consumo_alimento_repository import (
    ConsumoAlimentoRepository,
    TipoAlimentoRef,
)


class ListarTiposAlimentoUseCase:
    """Devuelve los tipos de alimento ordenados por nombre."""

    def __init__(self, consumo_repo: ConsumoAlimentoRepository) -> None:
        self.consumo_repo = consumo_repo

    def execute(self, *, solo_activos: bool = True) -> list[TipoAlimentoRef]:
        return self.consumo_repo.listar_tipos_alimento(solo_activos=solo_activos)
