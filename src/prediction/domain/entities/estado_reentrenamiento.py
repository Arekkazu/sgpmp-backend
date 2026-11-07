# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: aviso de datos insuficientes para reentrenar el modelo individual |
"""Cuántas retroalimentaciones RF-72 nuevas tiene cada modelo individual y qué permiten (RF-71).

"Nuevas" = registradas después de la última versión de ese ``tipo_modelo`` (o todas, si aún no
hay versión). Cada resultado de inferencia con retroalimentación cuenta una vez, aunque lo hayan
retroalimentado varios veterinarios: RF-71 lo consume como una etiqueta ponderada (RF-72 Regla 3).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

#: Modelos de predicción de enfermedades individuales (ET-02, paradigma INDIVIDUAL).
TIPOS_MODELO_INDIVIDUAL = ("MODELO_ESPECIES_GRANDES", "MODELO_ESPECIES_MEDIANAS")


@dataclass(frozen=True)
class EstadoReentrenamiento:
    tipo_modelo: str
    registros_nuevos: int
    desde: Optional[datetime]
    minimo_solicitud: int
    minimo_reentrenamiento: int

    @property
    def estado(self) -> str:
        """INSUFICIENTE (aviso) / PUEDE_SOLICITARSE / LISTO (alcanza la precondición de RF-71)."""
        if self.registros_nuevos >= self.minimo_reentrenamiento:
            return "LISTO"
        if self.registros_nuevos >= self.minimo_solicitud:
            return "PUEDE_SOLICITARSE"
        return "INSUFICIENTE"

    @property
    def faltan(self) -> int:
        """Registros que faltan para el siguiente estado (0 si ya está LISTO)."""
        meta = self.minimo_solicitud if self.estado == "INSUFICIENTE" else self.minimo_reentrenamiento
        return max(0, meta - self.registros_nuevos)
