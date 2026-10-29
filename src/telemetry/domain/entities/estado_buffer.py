# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: representar métricas reportadas y clasificar ocupación sin reconstruir el buffer Edge. |
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class EstadoOcupacionBuffer(str, Enum):
    NORMAL = 'NORMAL'
    WARNING = 'WARNING'
    CRITICO = 'CRITICO'


class PoliticaBuffer(str, Enum):
    RECHAZO = 'POLITICA_RECHAZO'
    SOBRESCRITURA = 'POLITICA_SOBRESCRITURA'


@dataclass(frozen=True)
class MetricasBuffer:
    capacidad_total: Decimal
    capacidad_utilizada: Decimal
    ultimo_timestamp_pendiente: datetime | None
    politica_buffer_activa: PoliticaBuffer

    def __post_init__(self):
        if (not self.capacidad_total.is_finite() or not self.capacidad_utilizada.is_finite()
                or self.capacidad_total <= 0 or not 0 <= self.capacidad_utilizada <= self.capacidad_total):
            raise ValueError('La capacidad total debe ser positiva y la utilizada estar entre cero y el total.')

    @property
    def porcentaje_ocupacion(self) -> Decimal:
        return self.capacidad_utilizada / self.capacidad_total * 100

    @property
    def estado_buffer(self) -> EstadoOcupacionBuffer:
        if self.capacidad_utilizada >= self.capacidad_total * Decimal('0.95'):
            return EstadoOcupacionBuffer.CRITICO
        if self.capacidad_utilizada >= self.capacidad_total * Decimal('0.80'):
            return EstadoOcupacionBuffer.WARNING
        return EstadoOcupacionBuffer.NORMAL


@dataclass(frozen=True)
class EstadoBufferReportado:
    id_dispositivo_iot: int
    id_heartbeat: int | None = None
    fecha_reporte: datetime | None = None
    fecha_recepcion: datetime | None = None
    estado_local_buffer: str | None = None
    datos_pendientes: int | None = None
    metricas: MetricasBuffer | None = None
