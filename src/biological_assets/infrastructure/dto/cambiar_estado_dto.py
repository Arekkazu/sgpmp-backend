"""DTO de entrada de ``PATCH /activos-biologicos/{id_activo}/estado`` (RF-44)."""

from __future__ import annotations

from datetime import date

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

# El DTO solo rechaza (400) lo que no es un estado del sistema. Las reglas que
# RF-44 clasifica como 422 viven en CambiarEstadoUseCase: fecha futura (E-05),
# motivo vacío (E-06) y CERRADO/BAJA por este endpoint (E-07, principio de
# centralización obligatoria: solo se alcanzan vía RF-38 y RF-45).
_ESTADO_A_ID = {
    'ACTIVO': 1,
    'INACTIVO': 2,
    'EN_TRATAMIENTO': 3,
    'AISLADO': 4,
    'CERRADO': 5,
    'BAJA': 6,
}


class CambiarEstadoDTO(BaseDTO):
    """Cambio manual de estado del activo.

    ``estado_nuevo``: ``ACTIVO`` | ``INACTIVO`` | ``EN_TRATAMIENTO`` | ``AISLADO``.
    ``CERRADO`` y ``BAJA`` se rechazan aquí: se alcanzan con el cierre de ciclo
    (RF-38) y el registro de baja (RF-45). El motivo es obligatorio y la fecha no
    puede ser futura.
    """
    estado_nuevo: str
    fecha_cambio_estado: date
    motivo_cambio: str

    @field_validator('estado_nuevo')
    @classmethod
    def estado_valido(cls, v: str) -> str:
        if v not in _ESTADO_A_ID:
            raise ValueError(f'Estado inválido. Valores permitidos: {", ".join(_ESTADO_A_ID)}.')
        return v

    @property
    def id_estado_nuevo(self) -> int:
        return _ESTADO_A_ID[self.estado_nuevo]
