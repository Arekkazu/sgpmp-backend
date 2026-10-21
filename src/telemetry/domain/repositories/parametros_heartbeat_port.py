# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: umbrales y politica temporal tipados |
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ParametrosHeartbeat:
    bateria_critica: Decimal
    bateria_baja: Decimal
    rssi_degradado: Decimal
    snr_degradado: Decimal | None = None

    def __post_init__(self):
        if not Decimal(0) <= self.bateria_critica <= self.bateria_baja <= Decimal(100):
            raise ValueError('Los umbrales de batería son inconsistentes.')


class ParametrosHeartbeatPort(Protocol):
    def obtener(self) -> ParametrosHeartbeat: ...

    def obtener_comunicacion(self, id_dispositivo: int) -> 'ParametrosComunicacionHeartbeat': ...


@dataclass(frozen=True)
class ParametrosComunicacionHeartbeat:
    intervalo_heartbeat_seg: int
    frecuencia_muestreo_seg: int
    margen_tolerancia_seg: int
    inactividad_extendida_seg: int
    estado_local_buffer: str | None

    def __post_init__(self):
        from src.configuration.domain.entities.parametros_heartbeat import validar_cadena
        if self.inactividad_extendida_seg <= 0:
            raise ValueError('La inactividad extendida debe ser positiva.')
        validar_cadena([self.intervalo_heartbeat_seg], self.frecuencia_muestreo_seg,
                       self.umbral_sin_senal, self.margen_tolerancia_seg)

    @property
    def umbral_activo(self):
        return max(self.intervalo_heartbeat_seg, self.frecuencia_muestreo_seg)

    @property
    def umbral_sin_senal(self):
        return self.umbral_activo + self.margen_tolerancia_seg

    @property
    def umbral_inactivo(self):
        return self.umbral_sin_senal + self.inactividad_extendida_seg
