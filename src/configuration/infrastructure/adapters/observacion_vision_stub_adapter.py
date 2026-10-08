"""Adaptador stub de :class:`ObservacionVisionPort`.

Retorna una lista vacía siempre: M03 todavía no expone los vectores de
comportamiento (RF-53/RF-56) ni su índice de calidad (RF-62). Con este stub un
área que cumple las precondiciones termina en la Etapa 1 (sin observaciones
válidas) y la calibración queda FALLIDA, sin publicar línea base. Cuando M03
exista, se reemplaza por la implementación real sin tocar el use case.
"""
from __future__ import annotations

import datetime

from src.configuration.domain.entities.observacion_vision import ObservacionVision
from src.configuration.domain.repositories.observacion_vision_port import ObservacionVisionPort


class ObservacionVisionStubAdapter(ObservacionVisionPort):

    def listar(
        self,
        ids_dispositivos: list[int],
        inicio: datetime.datetime,
        fin: datetime.datetime,
    ) -> list[ObservacionVision]:
        return []
