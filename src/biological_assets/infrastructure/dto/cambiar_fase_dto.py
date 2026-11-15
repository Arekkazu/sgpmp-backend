# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-11-14 | Arekkazu | QA-M06 RF-37: el inicio de fase de hoy no es futuro aunque el reloj del usuario vaya adelantado |
"""DTO de entrada de ``POST /activos-biologicos/{id_activo}/fases`` (RF-37)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc, hasta_ahora


class CambiarFaseDTO(BaseDTO):
    """Asignación o avance de fase del ciclo productivo.

    ``id_ciclo_productiva`` es el id de ``modulo9.ciclos_productivos`` (ver
    ``GET /activos-biologicos/{id_activo}/ciclos-productivos``). Sin
    ``fase_destino_id`` se avanza a la siguiente fase; si se indica una que no es
    la siguiente hay que enviar ``confirmacion_no_estandar=true``.
    """
    id_ciclo_productiva: int
    motivo_cambio: Optional[str] = None
    fecha_inicio: Optional[FechaHoraUtc] = None
    # RF-37 (tarea Taiga fase_destino/confirmacion_no_estandar): fase
    # específica del ciclo a la que se quiere transicionar
    # (id_ciclos_productivo_biologico). Si se omite, se asume la siguiente
    # fase estándar de la secuencia -- mismo comportamiento que antes de
    # esta tarea, sin cambios para quien no use este campo.
    fase_destino_id: Optional[int] = None
    # Requerido en True cuando fase_destino_id no es la siguiente fase
    # estándar de la secuencia (salto hacia adelante o retroceso); si no se
    # confirma, el use case rechaza con 409.
    confirmacion_no_estandar: bool = False

    @field_validator('fecha_inicio')
    @classmethod
    def fecha_no_futura(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            # Normalizada a UTC: el use case la compara con fechas timestamptz de la BD.
            v_utc = hasta_ahora(v)
            if v_utc is None:
                raise ValueError('La fecha de inicio de la fase no puede ser futura.')
            return v_utc
        return v
