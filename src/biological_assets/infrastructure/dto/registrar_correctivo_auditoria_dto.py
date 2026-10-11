"""DTO de entrada de ``POST /activos-biologicos/auditoria/registros-correctivos`` (RF-52
E5).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class RegistrarCorrectivoAuditoriaDTO(BaseDTO):
    """Fila del historial RF-46 a la que se le completa el rastro, con su motivo.

    ``tabla``: ``eventos_activos`` | ``historicos_estados_activos`` | ``gestiones_fases`` |
    ``movimientos`` | ``historial_activos``.
    """
    # Las tablas del historial RF-46, con el nombre que usa registros_rf46 en la bitácora.
    tabla: Literal['eventos_activos', 'historicos_estados_activos', 'gestiones_fases', 'movimientos', 'historial_activos']
    id_registro: int = Field(gt=0)
    motivo: str

    @field_validator('motivo')
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('El motivo del registro correctivo es obligatorio.')
        return v
