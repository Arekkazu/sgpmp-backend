# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Fases de un ciclo productivo a partir de las etapas elegidas, en el orden en que llegan."""
from __future__ import annotations

from src.configuration.domain.entities.ciclo_productivo import FaseCicloProductivo
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.shared.errors import BusinessRuleError


def resolver_fases(etapas: CicloBiologicoRepository, id_especie: int, ids: list[int]) -> list[FaseCicloProductivo]:
    activas = {e.id_ciclo_biologico: e for e in etapas.listar_por_especie(id_especie, solo_activas=True)}
    if any(i not in activas for i in ids):
        raise BusinessRuleError(code="ETAPA_NO_DISPONIBLE", field="id_ciclos_biologicos", message=(
            "Alguna de las etapas elegidas no existe, está inactiva o es de otra especie. "
            "Recargue la lista de etapas e intente de nuevo."))
    return [FaseCicloProductivo(id_ciclo_biologico=i, nombre=activas[i].nombre.valor,
                                duracion_dias=activas[i].duracion_dias.valor) for i in ids]
