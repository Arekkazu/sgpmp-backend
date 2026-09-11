from __future__ import annotations

from decimal import Decimal
from typing import Optional

from src.shared.base_dto import BaseDTO


class ConfigurarMotorDTO(BaseDTO):
    tipo_modelo: str
    umbral_riesgo_alto: Decimal
    umbral_alerta_critica: Decimal
    ventana_temporal_min: int
    modo_ejecucion: str = "SERVIDOR"
    w_factor_sanitario: Decimal = Decimal("0.500")
    w_factor_ambiental: Decimal = Decimal("0.300")
    w_factor_densidad: Decimal = Decimal("0.200")
    id_version_modelo_activa: Optional[int] = None
    temp_min_config: Optional[Decimal] = None
    temp_max_config: Optional[Decimal] = None
    hr_min_config: Optional[Decimal] = None
    hr_max_config: Optional[Decimal] = None
    densidad_maxima_config: Optional[Decimal] = None
