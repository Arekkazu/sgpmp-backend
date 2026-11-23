# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: representar métricas reportadas y clasificar ocupación sin reconstruir el buffer Edge. |
# | 2026-10-29 | Arekkazu | TC-DIS-148 RF-54: listado del buffer de todos los dispositivos del alcance |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clases y miembros públicos |
"""Estado del buffer local de un dispositivo IoT y sus métricas de ocupación (RF-54).

Modela el snapshot que el Edge reporta en el heartbeat: capacidad total y
utilizada, política activa y último dato pendiente. A partir de esas métricas
se clasifica la ocupación en normal, advertencia o crítico sin reconstruir el
buffer. No conoce SQLAlchemy.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class EstadoOcupacionBuffer(str, Enum):
    """Nivel de ocupación del buffer local del dispositivo."""

    NORMAL = 'NORMAL'
    WARNING = 'WARNING'
    CRITICO = 'CRITICO'


class PoliticaBuffer(str, Enum):
    """Política que aplica el Edge cuando el buffer llega a su capacidad."""

    RECHAZO = 'POLITICA_RECHAZO'
    SOBRESCRITURA = 'POLITICA_SOBRESCRITURA'


@dataclass(frozen=True)
class MetricasBuffer:
    """Métricas de capacidad del buffer reportadas por el dispositivo.

    Valida en la construcción que la capacidad total sea positiva y finita y
    que la utilizada quede entre cero y el total.
    """

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
        """Porcentaje de la capacidad total que está en uso (0-100)."""
        return self.capacidad_utilizada / self.capacidad_total * 100

    @property
    def estado_buffer(self) -> EstadoOcupacionBuffer:
        """Clasifica la ocupación: crítico desde 95 %, advertencia desde 80 %."""
        if self.capacidad_utilizada >= self.capacidad_total * Decimal('0.95'):
            return EstadoOcupacionBuffer.CRITICO
        if self.capacidad_utilizada >= self.capacidad_total * Decimal('0.80'):
            return EstadoOcupacionBuffer.WARNING
        return EstadoOcupacionBuffer.NORMAL


@dataclass(frozen=True)
class EstadoBufferReportado:
    """Read-model del estado del buffer de un dispositivo para el panel de monitoreo.

    Incluye los datos del último heartbeat y, para el listado de todos los
    dispositivos del alcance (TC-DIS-148), el serial, la infraestructura y la
    finca a los que pertenece.
    """

    id_dispositivo_iot: int
    id_heartbeat: int | None = None
    fecha_reporte: datetime | None = None
    fecha_recepcion: datetime | None = None
    estado_local_buffer: str | None = None
    datos_pendientes: int | None = None
    metricas: MetricasBuffer | None = None
    # TC-DIS-148: el panel lista todos los dispositivos y necesita saber cuál es cuál.
    serial: str | None = None
    descripcion: str | None = None
    nombre_infraestructura: str | None = None
    nombre_finca: str | None = None
    estado_dispositivo: str | None = None
