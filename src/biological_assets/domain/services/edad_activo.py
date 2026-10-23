# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-20 RF-33: fecha_nacimiento opcional y advertencia de edad (RFC-014) |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Edad del activo frente a la esperanza de vida de su especie (RF-33 1.4, RFC-014).

Validación informativa y NO bloqueante: nunca rechaza un registro, solo produce
la advertencia de trazabilidad cuando la edad alcanza o supera la esperanza de vida.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from src.shared.fechas import fecha_usuario


@dataclass(frozen=True)
class AdvertenciaEdad:
    edad_dias: int
    esperanza_vida_dias: int

    @property
    def mensaje(self) -> str:
        return (
            f"La edad del activo ({self.edad_dias} días) alcanza o supera la esperanza de vida "
            f"de la especie ({self.esperanza_vida_dias} días). Verifique la fecha de nacimiento."
        )


def evaluar_edad(
    fecha_nacimiento: Optional[datetime | date],
    esperanza_vida_dias: Optional[int],
    hoy: date,
) -> Optional[AdvertenciaEdad]:
    """Advertencia si la edad en días (a ``hoy``, día en la zona del usuario) es ≥ la esperanza de vida.

    Sin fecha de nacimiento o sin esperanza de vida en la especie no hay nada que evaluar.
    """
    if fecha_nacimiento is None or esperanza_vida_dias is None:
        return None
    edad_dias = (hoy - fecha_usuario(fecha_nacimiento)).days
    if edad_dias < esperanza_vida_dias:
        return None
    return AdvertenciaEdad(edad_dias=edad_dias, esperanza_vida_dias=esperanza_vida_dias)
