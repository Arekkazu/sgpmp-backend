"""DTO de entrada para registrar una calibración de sensor (POST /{id}/calibrar RF-24)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Union

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class RegistrarCalibracionDTO(BaseDTO):
    id_dispositivo_iot: int
    id_infraestructura: int
    # RF-24 FA "Datos no numéricos o incompletos" pide 400 (no el 422 de Pydantic)
    # cuando valor_referencia llega vacío o no numérico. Se acepta permisivo
    # (Decimal | str | None) para que Pydantic no lo rechace con 422, y el use case
    # lo convierte y devuelve 400 VALOR_CALIBRACION_INVALIDO si no es un decimal válido.
    valor_referencia: Optional[Union[Decimal, str]] = None
    ganancia: Decimal = Decimal("1.0")
    offset: Optional[Decimal] = None
    fecha_calibracion: datetime
    observaciones: Optional[str] = None

    # El rango válido de valor_referencia/offset lo impone el rango por tipo de
    # sensor en el use case (RF-24); aquí solo se valida que la ganancia sea
    # positiva (un factor de escala no puede ser <= 0).
    @field_validator("ganancia")
    @classmethod
    def validar_ganancia(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError(f"La ganancia debe ser positiva. Valor recibido: {v}.")
        return v
