from __future__ import annotations

from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

# SUPERADA se incluye en el CHECK de BD (asociaciones_activos_sensores_estado_asociacion_check)
# pero es exclusivamente system-managed (AsociarSensorActivoUseCase la asigna al reemplazar
# una asociacion). Se acepta aqui como valor sintacticamente valido para que el intento de
# fijarla manualmente caiga en TRANSICION_INVALIDA (422, regla de negocio) en vez de un 400
# de formato -- son cosas distintas: el valor existe en el dominio, la transicion no esta permitida.
_ESTADOS_VALIDOS = {'ACTIVA', 'INACTIVA', 'SUPERADA'}


class CambiarEstadoAsociacionSensorDTO(BaseDTO):
    estado_nuevo: str
    motivo: Optional[str] = None

    @field_validator('estado_nuevo')
    @classmethod
    def estado_valido(cls, v: str) -> str:
        if v not in _ESTADOS_VALIDOS:
            raise ValueError(
                f'Estado inválido. Valores permitidos: {", ".join(sorted(_ESTADOS_VALIDOS))}.'
            )
        return v
