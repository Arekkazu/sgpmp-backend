# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: indicadores de estado del sistema de alertas |
# | 2026-10-29 | Arekkazu | INC-M03-211-G98 RF-58: panel integrado de alertas activas en el dashboard |
"""Indicadores de estado del sistema de alertas (RF-57, Salida 3).

Solo alertas operativas (las técnicas son de RF-60). "Abiertas" son las que siguen en el
ciclo de vida (ACTIVA o EN_ATENCION). Las históricas (vencidas, tiempo de resolución y
falsos positivos) se acotan por la fecha de cierre, que el trigger de transición fija en
``fecha_resolucion`` al pasar a RESUELTA, DESCARTADA o VENCIDA.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

ESTADOS_ABIERTOS = ('ACTIVA', 'EN_ATENCION')


@dataclass(frozen=True)
class FiltroIndicadoresAlertas:
    id_infraestructura: Optional[int] = None
    ids_fincas_permitidas: Optional[list[int]] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None


@dataclass
class AlertaActivaPanel:
    """RF-58 CU04 salida 2 / CA-11: una alerta ACTIVA del panel integrado del dashboard."""
    id_alerta: int
    tipo_alerta: str
    severidad: Optional[str]
    tipo_variable: Optional[str]
    valor: Optional[Decimal]
    unidad: Optional[str]
    fecha_generacion: datetime
    minutos_transcurridos: int
    id_infraestructura: Optional[int]
    id_activo_biologico: Optional[int]
    identificador_activo: Optional[str]


@dataclass
class IndicadoresAlertas:
    alertas_activas_total: int = 0
    alertas_criticas_activas: int = 0
    alertas_por_tipo: dict[str, int] = field(default_factory=dict)
    # VENCIDA sin haber sido reconocida (fecha_atencion nula): E10 / CA-12.
    alertas_vencidas_sin_atencion: int = 0
    alertas_resueltas: int = 0
    alertas_descartadas: int = 0
    tiempo_promedio_resolucion_min: Optional[float] = None
    tasa_falsos_positivos: Optional[float] = None

    @staticmethod
    def tasa(descartadas: int, resueltas: int) -> Optional[float]:
        """Falsos positivos (DESCARTADA) sobre las alertas cerradas con un dictamen."""
        dictaminadas = descartadas + resueltas
        return round(descartadas / dictaminadas, 4) if dictaminadas else None
