from __future__ import annotations

from decimal import Decimal
from typing import Optional

from src.shared.base_dto import BaseDTO
from src.shared.tipo_modelo import Componente


class ConfigurarMotorDTO(BaseDTO):
    tipo_modelo: str
    # RF-65 v2.0 (RFC-009): obligatorios según el paradigma del tipo_modelo; el use
    # case exige los que aplican y descarta los que no.
    umbral_riesgo_alto: Optional[Decimal] = None
    umbral_alerta_critica: Optional[Decimal] = None
    umbral_score_anomalia: Optional[Decimal] = None
    versiones_activas_por_componente: Optional[dict[Componente, int]] = None
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
