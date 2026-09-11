"""Entidad de dominio ``TipoDispositivoIot`` — tipo de hardware y sus rangos (RF-23).

Cada tipo define los límites min/max permitidos para los parámetros
configurables de un dispositivo IoT. Un dispositivo pertenece a un tipo, y su
configuración remota debe caer dentro de esos rangos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TipoDispositivoIot:
    id_tipo_dispositivo: int
    nombre: str
    frecuencia_captura_min: int
    frecuencia_captura_max: int
    intervalo_transmision_min: int
    intervalo_transmision_max: int

    def verificar_rango(
        self, frecuencia_captura: int, intervalo_transmision: int
    ) -> Optional[dict]:
        """Devuelve la primera violación de rango como dict (field/min/max/valor), o None si todo cabe."""
        if not (self.frecuencia_captura_min <= frecuencia_captura <= self.frecuencia_captura_max):
            return {
                "field": "frecuencia_captura",
                "min": self.frecuencia_captura_min,
                "max": self.frecuencia_captura_max,
                "valor": frecuencia_captura,
            }
        if not (self.intervalo_transmision_min <= intervalo_transmision <= self.intervalo_transmision_max):
            return {
                "field": "intervalo_transmision",
                "min": self.intervalo_transmision_min,
                "max": self.intervalo_transmision_max,
                "valor": intervalo_transmision,
            }
        return None
