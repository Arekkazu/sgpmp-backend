# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de ventana por resultado  |
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.ampliacion_ventana_retroalimentacion import AmpliacionVentanaRetroalimentacion


class AmpliacionVentanaRetroalimentacionRepository(ABC):
    @abstractmethod
    def guardar(self, entidad: AmpliacionVentanaRetroalimentacion) -> AmpliacionVentanaRetroalimentacion: ...

    @abstractmethod
    def fecha_limite_vigente(self, id_resultado: uuid.UUID) -> Optional[datetime]:
        """La fecha límite más lejana autorizada para el resultado, o None si no tiene ampliación."""
