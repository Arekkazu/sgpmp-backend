# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: umbrales y politica temporal tipados |
# | 2026-10-22 | Leandro | DEV-42 RF-60: evidencia temporal para heartbeat ausente |
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: transportar los pendientes del mismo último heartbeat sin romper constructores previos. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clases, puerto y métodos |
"""Puerto y parámetros de dominio para evaluar heartbeats y conectividad (RF-54/RF-60).

``ParametrosHeartbeat`` fija los umbrales de batería y señal; ``ParametrosComunicacionHeartbeat``
resuelve las ventanas temporales con las que se detecta un heartbeat ausente o
un dispositivo inactivo. El puerto abstrae de dónde salen esos valores.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ParametrosHeartbeat:
    """Umbrales de batería y calidad de señal para clasificar un heartbeat.

    Valida que los umbrales de batería sean coherentes: crítica ≤ baja ≤ 100 %.
    """

    bateria_critica: Decimal
    bateria_baja: Decimal
    rssi_degradado: Decimal
    snr_degradado: Decimal | None = None

    def __post_init__(self):
        if not Decimal(0) <= self.bateria_critica <= self.bateria_baja <= Decimal(100):
            raise ValueError('Los umbrales de batería son inconsistentes.')


class ParametrosHeartbeatPort(Protocol):
    """Contrato para obtener los umbrales globales y los de un dispositivo."""

    def obtener(self) -> ParametrosHeartbeat:
        """Devuelve los umbrales globales de batería y señal."""
        ...

    def obtener_comunicacion(self, id_dispositivo: int) -> 'ParametrosComunicacionHeartbeat':
        """Devuelve los parámetros de comunicación del dispositivo indicado."""
        ...


@dataclass(frozen=True)
class ParametrosComunicacionHeartbeat:
    """Ventanas temporales para detectar pérdida de señal o inactividad.

    Deriva los umbrales de ``sin señal`` e ``inactivo`` a partir del intervalo
    de heartbeat, la frecuencia de muestreo y el margen de tolerancia.
    """

    intervalo_heartbeat_seg: int
    frecuencia_muestreo_seg: int
    margen_tolerancia_seg: int
    inactividad_extendida_seg: int
    estado_local_buffer: str | None
    ultima_telemetria: datetime | None = None
    ultimo_heartbeat: datetime | None = None
    primera_telemetria: datetime | None = None
    id_infraestructura: int | None = None
    datos_pendientes_buffer: int | None = None

    def heartbeat_ausente(self, ahora: datetime) -> bool:
        """Indica si hay telemetría reciente sin el heartbeat que la respalde.

        Args:
            ahora: Instante actual en UTC con el que se comparan las ventanas.
        """
        if self.ultima_telemetria is None:
            return False
        referencia = self.ultimo_heartbeat or self.primera_telemetria
        return (referencia is not None
            and 0 <= (ahora-self.ultima_telemetria).total_seconds() <= self.frecuencia_muestreo_seg
            and (ahora-referencia).total_seconds() > 2*self.intervalo_heartbeat_seg)

    def __post_init__(self):
        from src.configuration.domain.entities.parametros_heartbeat import validar_cadena
        if self.inactividad_extendida_seg <= 0:
            raise ValueError('La inactividad extendida debe ser positiva.')
        validar_cadena([self.intervalo_heartbeat_seg], self.frecuencia_muestreo_seg,
                       self.umbral_sin_senal, self.margen_tolerancia_seg)

    @property
    def umbral_activo(self):
        """Ventana base de actividad: el mayor entre heartbeat y muestreo."""
        return max(self.intervalo_heartbeat_seg, self.frecuencia_muestreo_seg)

    @property
    def umbral_sin_senal(self):
        """Segundos sin reportar a partir de los cuales se considera sin señal."""
        return self.umbral_activo + self.margen_tolerancia_seg

    @property
    def umbral_inactivo(self):
        """Segundos sin reportar a partir de los cuales el dispositivo está inactivo."""
        return self.umbral_sin_senal + self.inactividad_extendida_seg
