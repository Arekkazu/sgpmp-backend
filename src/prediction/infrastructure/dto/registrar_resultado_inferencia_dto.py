# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: resultado que envía el motor IA (Salida de RF-66)         |
"""Cuerpo de ``POST /prediccion/inferencias``: la Salida de RF-66 que entrega el motor IA.

``id_especie`` no viaja: el backend lo toma del activo. ``latencia_excedida`` tampoco:
se deriva de ``latencia_ms`` contra el límite de CA-1.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import Field, model_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc

Probabilidades = dict[str, Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]]


class RegistrarResultadoInferenciaDTO(BaseDTO):
    id_resultado_inferencia: uuid.UUID = Field(
        ..., description="Lo genera el motor. Reenviar el mismo id no duplica el resultado."
    )
    id_paquete_inferencia: Optional[int] = Field(None, gt=0, description="Paquete de RF-56 que lo originó.")
    id_activo_biologico: int = Field(..., gt=0)
    fase_productiva: Optional[str] = Field(None, max_length=50)
    tipo_modelo: Literal[
        "MODELO_AVES", "MODELO_ESPECIES_MEDIANAS", "MODELO_ESPECIES_GRANDES",
        "MODELO_RIESGO_CONTAGIO", "MODELO_PORCINOS", "MODELO_ACUICULTURA",
    ]
    id_version_modelo: int = Field(..., gt=0, description="Versión de RF-69 con la que se infirió.")
    nivel_riesgo: int = Field(..., ge=0, le=3, description="0 Normal, 1 Bajo, 2 Moderado, 3 Alto")
    probabilidad_riesgo: Probabilidades = Field(..., min_length=1)
    id_patologia: Optional[int] = Field(None, gt=0, description="enfermedad_estimada, del catálogo RF-64.")
    probabilidad_enfermedad: Probabilidades = Field(..., min_length=1)
    confianza_global: Decimal = Field(..., ge=0, le=1, allow_inf_nan=False)
    contexto_incompleto: bool
    modo_ejecucion: Literal["EDGE", "SERVIDOR", "HIBRIDO"]
    latencia_ms: Optional[int] = Field(None, ge=0)
    fecha_inicio_ventana: Optional[FechaHoraUtc] = None
    fecha_fin_ventana: Optional[FechaHoraUtc] = None
    fecha_inferencia: FechaHoraUtc = Field(..., description="timestamp_inferencia del motor.")
    modo_sombra: bool = Field(..., description="true: se registra pero no alerta (modelo no vinculante).")

    @model_validator(mode="after")
    def ventana_coherente(self):
        if (
            self.fecha_inicio_ventana is not None
            and self.fecha_fin_ventana is not None
            and self.fecha_inicio_ventana >= self.fecha_fin_ventana
        ):
            raise ValueError("fecha_inicio_ventana debe ser anterior a fecha_fin_ventana.")
        return self
