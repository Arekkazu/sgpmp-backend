# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-62: política vigente del índice de visión para el panel de calidad |
from __future__ import annotations

from src.configuration.domain.entities.parametros_vision import (
    DEGRADADA, FACTOR, LIMITES_VISION, OPTIMA, TOLERABLES, W1, W2, W3, vision_configurada,
)
from src.shared.errors import AppError
from src.telemetry.domain.entities.calidad_vision_listado import PoliticaVisionVigente
from src.telemetry.domain.repositories.calidad_vision_repository import PoliticaVisionPort


class PoliticaVisionMLOpsAdapter(PoliticaVisionPort):
    """Lee la política con el repositorio de parámetros que se le pase. El router le da uno sobre
    una sesión de sistema: la RLS de parametros_mlops solo deja leer estas claves con
    version_modelo · Leer, y quien revisa la calidad (38 · Leer) también debe verlas."""

    def __init__(self, parametros_repo) -> None:
        self._repo = parametros_repo

    def vigente(self):
        try:
            v = vision_configurada(self._repo.obtener(tuple(LIMITES_VISION)))
        except AppError as exc:
            return None, exc.message
        return PoliticaVisionVigente(
            w1=v[W1], w2=v[W2], w3=v[W3], tracks_perdidos_tolerables=int(v[TOLERABLES]),
            umbral_optima=v[OPTIMA], umbral_degradada=v[DEGRADADA], factor_en_calibracion=v[FACTOR],
        ), None
