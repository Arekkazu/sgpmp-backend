# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-26 | destroyerban | INC-M03-111-G43 RF-55.1: guarda valor y umbrales aplicados por el Edge |
# | 2026-10-28 | destroyerban | INC-M03-199-G54 RF-55: trazabilidad de la regla (regla_aplicada, nombre_regla, version_regla) |
# | 2026-10-28 | Arekkazu | BE-1 RF-55: sensor, serial y sensor_id por variable involucrada |
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Union

from pydantic import Field, field_validator, model_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc
from src.telemetry.domain.entities.telemetria import CAMPOS_TRAZABILIDAD_REGLA


class VariableInvolucradaDTO(BaseDTO):
    tipo_variable: str
    valor: Decimal
    unidad: str
    timestamp_captura: Optional[FechaHoraUtc] = None
    # BE-1: el firmware los manda por variable y el broker resuelve sensor_id; antes
    # Pydantic los descartaba sin error. Se guardan con la variable.
    sensor: Optional[str] = Field(default=None, max_length=100)
    serial: Optional[str] = Field(default=None, max_length=100)
    sensor_id: Optional[int] = Field(default=None, gt=0)


class RecibirEventoEdgeDTO(BaseDTO):
    device_id: int
    sensor_id: int
    serial: str = Field(..., min_length=1, max_length=100)
    # Clasificación producida por RF-55 en el dispositivo Edge
    clasificacion_rf55: str       # NORMAL | DESVIACION_SIMPLE | DESVIACION_COMPUESTA | ERROR_CONFIGURACION
    severidad: Optional[str] = None  # LEVE | MODERADO | CRITICO
    variables_involucradas: list[VariableInvolucradaDTO]
    timestamp_captura: FechaHoraUtc
    timestamp_procesamiento_edge: FechaHoraUtc
    origen: str = "TIEMPO_REAL"   # TIEMPO_REAL | BUFFER_LOCAL
    estado_conectividad: bool
    metadata_edge: Optional[dict[str, Any]] = None
    # G54: regla que produjo la clasificación (RF-55 §6). Opcionales hasta que se apruebe el contrato;
    # se aceptan en el nivel superior o dentro de metadata_edge y siempre se conservan en metadata_edge.
    regla_aplicada: Optional[Union[int, str]] = None
    nombre_regla: Optional[str] = Field(default=None, min_length=1, max_length=150)
    version_regla: Optional[int] = Field(default=None, ge=1)
    version_modelo_objetivo: Optional[str] = None
    # Evidencia de RF-55.1: valor que el Edge evaluó y umbrales con que lo clasificó
    valor_evaluado: Optional[Decimal] = None
    umbral_min_aplicado: Optional[Decimal] = None
    umbral_max_aplicado: Optional[Decimal] = None

    @model_validator(mode='after')
    def unificar_trazabilidad_regla(self) -> 'RecibirEventoEdgeDTO':
        """Sin esto, un campo enviado en el nivel superior se descartaba en silencio (extra='ignore')."""
        meta = dict(self.metadata_edge or {})
        for campo in CAMPOS_TRAZABILIDAD_REGLA:
            arriba, dentro = getattr(self, campo), meta.get(campo)
            if arriba is not None and dentro is not None and str(arriba) != str(dentro):
                raise ValueError(f"{campo} no coincide entre el evento ({arriba}) y metadata_edge ({dentro}).")
            valor = arriba if arriba is not None else dentro
            if valor is not None:
                meta[campo] = valor
                object.__setattr__(self, campo, valor)
        if isinstance(self.regla_aplicada, str) and not self.regla_aplicada.strip():
            raise ValueError("regla_aplicada no puede estar vacía.")
        if self.version_regla is not None and (isinstance(self.version_regla, bool) or int(self.version_regla) < 1):
            raise ValueError("version_regla debe ser un entero ≥ 1.")
        if meta or self.metadata_edge is not None:
            object.__setattr__(self, 'metadata_edge', meta)
        return self

    @field_validator('clasificacion_rf55')
    @classmethod
    def validar_clasificacion(cls, v: str) -> str:
        validos = {"NORMAL", "DESVIACION_SIMPLE", "DESVIACION_COMPUESTA", "ERROR_CONFIGURACION"}
        if v not in validos:
            raise ValueError(f"clasificacion_rf55 debe ser uno de: {', '.join(sorted(validos))}")
        return v

    @field_validator('severidad')
    @classmethod
    def validar_severidad(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"LEVE", "MODERADO", "CRITICO"}:
            raise ValueError("severidad debe ser LEVE, MODERADO o CRITICO")
        return v

    @field_validator('origen')
    @classmethod
    def validar_origen(cls, v: str) -> str:
        if v not in {"TIEMPO_REAL", "BUFFER_LOCAL"}:
            raise ValueError("origen debe ser TIEMPO_REAL o BUFFER_LOCAL")
        return v

    @model_validator(mode='after')
    def validar_umbrales(self) -> 'RecibirEventoEdgeDTO':
        if (self.umbral_min_aplicado is not None and self.umbral_max_aplicado is not None
                and self.umbral_min_aplicado > self.umbral_max_aplicado):
            raise ValueError("umbral_min_aplicado no puede ser mayor que umbral_max_aplicado")
        return self
