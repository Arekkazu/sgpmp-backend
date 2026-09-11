from __future__ import annotations

from datetime import date

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class RegistrarTransferenciaDTO(BaseDTO):
    infraestructura_origen_id: int
    infraestructura_destino_id: int
    fecha_transferencia: date
    motivo_transferencia: str

    @field_validator('motivo_transferencia', mode='before')
    @classmethod
    def validar_motivo(cls, v: object) -> str:
        v_str = str(v).strip()
        if not v_str:
            raise ValueError('El motivo de transferencia es obligatorio.')
        return v_str

    @field_validator('fecha_transferencia', mode='before')
    @classmethod
    def validar_fecha(cls, v: object) -> date:
        from datetime import date as date_cls
        if isinstance(v, str):
            v = date_cls.fromisoformat(v)
        if v > date_cls.today():
            raise ValueError('La fecha de transferencia no puede ser posterior a la fecha actual.')
        return v
