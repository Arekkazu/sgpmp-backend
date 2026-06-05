from typing import Optional

from pydantic import field_validator

from src.identity_access.infrastructure.models.enums_models import EnumAccionCuenta
from src.shared.base_dto import BaseDTO

_ACCIONES_CRITICAS = {EnumAccionCuenta.INACTIVAR, EnumAccionCuenta.ELIMINAR}


class GestionarCuentaDTO(BaseDTO):
    accion_cuenta: EnumAccionCuenta
    motivo_accion: Optional[str] = None

    @field_validator("accion_cuenta", mode="before")
    @classmethod
    def validar_accion(cls, v: str) -> str:
        valores_validos = [e.value for e in EnumAccionCuenta if e != EnumAccionCuenta.PENDIENTE]
        if v not in valores_validos:
            raise ValueError(
                f"Acción inválida. Las acciones permitidas son: {', '.join(valores_validos)}."
            )
        return v

    @field_validator("motivo_accion")
    @classmethod
    def validar_longitud_motivo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            return None
        return v
