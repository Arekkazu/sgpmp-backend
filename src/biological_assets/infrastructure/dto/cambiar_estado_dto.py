from __future__ import annotations

from datetime import date

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

# CERRADO y BAJA quedan fuera de este endpoint a propósito (RF-44 "Principio de
# Centralización Obligatoria"): solo se alcanzan vía CerrarCicloUseCase (RF-38) y
# RegistrarEventoBajaUseCase (RF-45), que aplican las validaciones y efectos
# secundarios propios de esas transiciones (cierre de fase, sensores IoT, descuento
# de cantidad de lote, fila en eventos_bajas) que este cambio manual no reproduce.
_ESTADOS_VALIDOS = {'ACTIVO', 'INACTIVO', 'EN_TRATAMIENTO', 'AISLADO'}
_ESTADO_A_ID = {
    'ACTIVO': 1,
    'INACTIVO': 2,
    'EN_TRATAMIENTO': 3,
    'AISLADO': 4,
}


class CambiarEstadoDTO(BaseDTO):
    estado_nuevo: str
    fecha_cambio_estado: date
    motivo_cambio: str

    @field_validator('estado_nuevo')
    @classmethod
    def estado_valido(cls, v: str) -> str:
        if v not in _ESTADOS_VALIDOS:
            raise ValueError(
                f'Estado inválido para cambio manual. Valores permitidos: {", ".join(sorted(_ESTADOS_VALIDOS))}. '
                'CERRADO se establece con POST /{id}/cierre (RF-38) y BAJA con POST /{id}/eventos/baja (RF-45).'
            )
        return v

    @field_validator('fecha_cambio_estado')
    @classmethod
    def fecha_no_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('La fecha del cambio de estado no puede ser futura.')
        return v

    @field_validator('motivo_cambio')
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('El motivo del cambio de estado es obligatorio.')
        return v.strip()

    @property
    def id_estado_nuevo(self) -> int:
        return _ESTADO_A_ID[self.estado_nuevo]
