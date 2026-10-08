"""DTO de entrada para registrar una calibración de sensor (POST /{id}/calibrar RF-24)."""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from typing import Optional, Union

from pydantic import field_validator

from src.configuration.domain.value_objects.modo_calibracion import ModoCalibracion
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
    # TC-M09-141 (#503): sin declararlo, un modo arbitrario se descartaba en
    # silencio. Por defecto SENSOR para no romper a los clientes que no lo envían.
    modo_calibracion: ModoCalibracion = ModoCalibracion.SENSOR

    # INC-M09-75-G132 (#511): los literales JSON NaN/Infinity/-Infinity llegan como
    # float no finito y Pydantic los rechazaba con 422 (Decimal exige finito). Se
    # pasan a texto para que el use case los rechace con el 400 de formato de RF-24.
    @field_validator("valor_referencia", mode="before")
    @classmethod
    def no_finito_como_texto(cls, v):
        if isinstance(v, float) and not math.isfinite(v):
            return "NaN" if math.isnan(v) else ("Infinity" if v > 0 else "-Infinity")
        return v

    # El rango válido de valor_referencia/offset lo impone el rango por tipo de
    # sensor en el use case (RF-24); aquí solo se valida que la ganancia sea
    # positiva (un factor de escala no puede ser <= 0).
    @field_validator("ganancia")
    @classmethod
    def validar_ganancia(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError(f"La ganancia debe ser positiva. Valor recibido: {v}.")
        return v
