# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: listar y obtener reglas de alerta |
"""Consultar reglas de alerta (RF-55/RF-57, BE-0)."""
from __future__ import annotations

from typing import Optional

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.alerta import ReglaAlerta
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository


def obtener_regla_o_404(repo: ReglaAlertaRepository, id_regla_alertas: int, *, bloquear: bool = False) -> ReglaAlerta:
    regla = repo.obtener_por_id(id_regla_alertas, bloquear=bloquear)
    if regla is None:
        raise NotFoundError(code="REGLA_ALERTA_NO_ENCONTRADA", message="La regla de alerta no existe.")
    return regla


class ConsultarReglasAlertasUseCase:

    def __init__(self, regla_repo: ReglaAlertaRepository) -> None:
        self.regla_repo = regla_repo

    def listar(
        self,
        tipo_sensor: Optional[str] = None,
        es_activa: Optional[bool] = None,
        es_regla_compuesta: Optional[bool] = None,
    ) -> list[ReglaAlerta]:
        return self.regla_repo.listar(
            tipo_sensor=tipo_sensor, es_activa=es_activa, es_regla_compuesta=es_regla_compuesta,
        )

    def obtener(self, id_regla_alertas: int) -> ReglaAlerta:
        return obtener_regla_o_404(self.regla_repo, id_regla_alertas)
