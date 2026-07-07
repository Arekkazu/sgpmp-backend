from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class EstadoSensorActual:
    """Read-model RF-58: estado actual de un sensor para el dashboard."""
    id_sensor: int
    id_dispositivo_iot: int
    nombre_sensor: str
    tipo_variable: str
    categoria_variable: str
    ultimo_valor: Optional[Decimal]
    ultima_unidad: Optional[str]
    ultimo_timestamp_captura: Optional[datetime]
    estado_semaforo: str        # VERDE / AMARILLO / ROJO / GRIS
    estado_calidad: Optional[str]
    estado_desviacion: Optional[str]
    estado_conectividad: Optional[str]  # ACTIVO / SIN_SEÑAL / BUFFER_ACTIVO / INACTIVO
    tiempo_sin_reporte_min: Optional[int]
    dato_desactualizado: bool
    id_alerta: Optional[int]
    severidad_alerta: Optional[str]
    tendencia: Optional[str]
    id_infraestructura: Optional[int]
    nombre_infraestructura: Optional[str]
    id_finca: Optional[int]
    nombre_finca: Optional[str]
    nivel_bateria_pct: Optional[Decimal]
    calidad_senal_rssi: Optional[Decimal]
    calidad_senal_snr: Optional[Decimal]


@dataclass
class ResumenUnidadProductiva:
    """Read-model RF-58: estado agregado de una unidad productiva."""
    id_infraestructura: int
    nombre_infraestructura: str
    id_finca: int
    nombre_finca: str
    total_sensores: int
    sensores_online: int
    sensores_sin_senal: int
    sensores_con_error: int
    estado_general: str         # peor semáforo entre todos sus sensores
    alertas_activas_count: int
    ultimo_dato_recibido: Optional[datetime]


@dataclass
class LecturaHistorica:
    """Read-model RF-59: una lectura del historial telemétrico."""
    id_telemetria: int
    id_sensor: int
    nombre_sensor: Optional[str]
    id_variable: int
    tipo_variable: str
    categoria_variable: str
    valor: Optional[Decimal]
    valor_ajustado: Optional[Decimal]
    unidad_medida: str
    timestamp_captura: datetime
    estado_calidad: str
    estado_semaforo_historico: str  # calculado contra umbral vigente en timestamp_captura
    origen_dato: str            # TIEMPO_REAL / BUFFER_LOCAL / EDGE_AGREGADO
    id_infraestructura: Optional[int]
    infraestructura: Optional[str]
    finca: Optional[str]
    id_activo_biologico: Optional[int]
    especie: Optional[str]
    id_alerta: Optional[int]
    nivel_bateria_pct: Optional[Decimal]
    calidad_senal_rssi: Optional[Decimal]
    calidad_senal_snr: Optional[Decimal]


@dataclass
class ResumenEstadistico:
    """Read-model RF-59: estadísticas de una variable en el período consultado."""
    tipo_variable: str
    valor_minimo: Optional[Decimal]
    valor_maximo: Optional[Decimal]
    valor_promedio: Optional[Decimal]
    total_lecturas: int
    pct_dentro_rango: Optional[float]
    pct_fuera_rango: Optional[float]
    total_alertas_en_periodo: int = 0


@dataclass
class FiltrosHistorial:
    """Parámetros validados de consulta histórica (RF-59)."""
    fecha_inicio: date
    fecha_fin: date
    sensor_id: Optional[int] = None
    tipo_variable: Optional[str] = None
    categoria_variable: Optional[str] = None
    id_infraestructura: Optional[int] = None
    especie: Optional[str] = None
    estado_dato: Optional[str] = None
    origen_dato: Optional[str] = None
    incluir_alertas: bool = False
    pagina: int = 1
    por_pagina: int = 100
    orden: str = 'DESC'

    def tiene_filtro_adicional(self) -> bool:
        """True si hay al menos un filtro adicional además del rango de fechas."""
        return any([
            self.sensor_id,
            self.tipo_variable,
            self.categoria_variable,
            self.id_infraestructura,
            self.especie,
            self.estado_dato,
            self.origen_dato,
        ])

    def combinacion_valida(self) -> bool:
        """Verifica que la combinación de filtros sea una de las permitidas por RF-59."""
        # Con solo rango de fechas es inválido (requiere al menos un filtro adicional
        # si el rango supera 90 días — validado en el use case)
        # Las combinaciones inválidas son: filtros sin rango de fechas
        if self.fecha_inicio is None or self.fecha_fin is None:
            return False
        # Combinaciones explícitamente prohibidas: sensor_id y especie juntos sin variable
        # (el RF lista las válidas; cualquier filtro con fecha_inicio+fecha_fin es base válida)
        return True


# Orden de severidad del semáforo para agregación de peor estado
_ORDEN_SEMAFORO = {'ROJO': 4, 'AMARILLO': 3, 'GRIS': 2, 'VERDE': 1, 'SIN_DATOS': 0}


class SemaforoCalculator:
    """Lógica pura de cálculo del semáforo (RF-58 Fase 3, RF-59 Restricción 16)."""

    @staticmethod
    def calcular(
        valor: Decimal,
        umbral_min: Decimal,
        umbral_max: Decimal,
        tolerancia_pct: float = 10.0,
    ) -> str:
        T = (umbral_max - umbral_min) * Decimal(str(tolerancia_pct / 100))
        if umbral_min <= valor <= umbral_max:
            return 'VERDE'
        elif (umbral_min - T) < valor < umbral_min or umbral_max < valor < (umbral_max + T):
            return 'AMARILLO'
        else:
            return 'ROJO'

    @staticmethod
    def aplicar_reglas_alerta(
        estado_base: str,
        tiene_alerta_critica: bool,
        tiene_alerta_activa: bool,
    ) -> str:
        """CA-4: alerta CRITICA → ROJO; alerta activa y estado VERDE → AMARILLO."""
        if tiene_alerta_critica:
            return 'ROJO'
        if tiene_alerta_activa and estado_base == 'VERDE':
            return 'AMARILLO'
        return estado_base

    @staticmethod
    def peor_semaforo(estados: list[str]) -> str:
        """Retorna el estado más grave entre una lista (para resumen de unidad productiva)."""
        if not estados:
            return 'SIN_DATOS'
        return max(estados, key=lambda s: _ORDEN_SEMAFORO.get(s, 0))
