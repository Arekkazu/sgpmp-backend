from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class CambiarFaseDTO(BaseDTO):
    id_ciclo_productiva: int
    motivo_cambio: Optional[str] = None
    fecha_inicio: Optional[datetime] = None
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
            ahora = datetime.now(timezone.utc)
            v_utc = v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)
            if v_utc > ahora:
                raise ValueError('La fecha de inicio de la fase no puede ser futura.')
            # Normalizada: el use case la compara con fechas timestamptz de la BD
            # (que corre en GMT, así que una fecha naive ya se guardaba como UTC).
            return v_utc
        return v
