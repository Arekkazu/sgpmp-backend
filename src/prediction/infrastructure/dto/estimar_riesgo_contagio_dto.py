# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: permitir densidad negativa finita para resolver el error de sensor en E2. |
# | 2026-10-30 | Leandro | INC-M04-222-G034 RF-68: documentar el filtro de identidad y el conteo sanitario derivado. |
"""``POST /prediccion/riesgo-contagio`` (RF-68 Entradas)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class SalidaRf66DTO(BaseDTO):
    """Salida RF-66: la identidad debe coincidir con el activo que representa al lote."""
    id_activo_biologico: Optional[int] = Field(
        default=None, gt=0, description="Solo se usa si coincide con id_lote; sin ID se excluye de RF-68."
    )
    probabilidad_riesgo_alto: Decimal = Field(ge=0, le=1)
    fecha_inferencia: FechaHoraUtc


class VariablesAmbientalesDTO(BaseDTO):
    temperatura: Optional[Decimal] = None
    humedad_relativa: Optional[Decimal] = Field(default=None, ge=0, le=100)
    fecha_captura: FechaHoraUtc


class EstimarRiesgoContagioDTO(BaseDTO):
    id_lote: int = Field(gt=0, description="Activo biológico (lote) a evaluar.")
    salidas_rf66: list[SalidaRf66DTO] = Field(default_factory=list, max_length=10_000)
    n_enfermos_detectados: Optional[int] = Field(
        default=None, ge=0, description="Con salidas_rf66, el conteo se deriva de las salidas propias con P(Riesgo Alto) > 0.70."
    )
    total_activos_lote: Optional[int] = Field(
        default=None, gt=0, description="Si se omite: cantidad de salidas de RF-66."
    )
    score_anomalia: Optional[Decimal] = Field(
        default=None, ge=0, le=1, description="Lote POBLACIONAL: Fs desde el score del área (RFC-009)."
    )
    densidad_poblacional: Optional[Decimal] = Field(
        default=None, allow_inf_nan=False, description="Animales/m² (RF-36). Negativa: histórico E2; nula: capacidad máxima."
    )
    variables_ambientales: Optional[VariablesAmbientalesDTO] = None
    porcentaje_sensores_activos: Decimal = Field(default=Decimal("100"), ge=0, le=100)
