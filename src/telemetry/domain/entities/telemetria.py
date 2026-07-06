from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


class OrigenTelemetria(str, Enum):
    TIEMPO_REAL = "TIEMPO_REAL"
    BUFFER_LOCAL = "BUFFER_LOCAL"
    EDGE_AGREGADO = "EDGE_AGREGADO"


class EstadoCalidadTelemetria(str, Enum):
    LECTURA_VALIDA = "LECTURA_VALIDA"
    FUERA_DE_RANGO = "FUERA_DE_RANGO"
    ERROR_CALIBRACION = "ERROR_CALIBRACION"


class EstadoCalidadBitacora(str, Enum):
    LECTURA_VALIDA = "LECTURA_VALIDA"
    FUERA_DE_RANGO = "FUERA_DE_RANGO"
    ERROR_CALIBRACION = "ERROR_CALIBRACION"
    ERROR_ESTRUCTURA = "ERROR_ESTRUCTURA"
    ERROR_AUTENTICACION = "ERROR_AUTENTICACION"
    ERROR_DUPLICADO = "ERROR_DUPLICADO"
    ERROR_TIEMPO = "ERROR_TIEMPO"
    ERROR_UNIDAD = "ERROR_UNIDAD"
    ERROR_SENSOR = "ERROR_SENSOR"


class CategoriaTelemetria(str, Enum):
    AMBIENTAL = "AMBIENTAL"
    ANIMAL = "ANIMAL"
    HIDRICA = "HIDRICA"


class TipoDato(str, Enum):
    CRUDO = "CRUDO"
    AGREGADO = "AGREGADO"
    EVENTO_EDGE = "EVENTO_EDGE"


# Catálogo I3P-1: mapeo de tipo_variable → (id_variable en M09, categoria, unidades_aceptadas)
CATALOGO_I3P1: dict[str, dict] = {
    "TEMPERATURA_AMBIENTAL": {
        "id_variable": 9,
        "categoria": CategoriaTelemetria.AMBIENTAL,
        "unidades": ["°C", "°F", "K"],
        "unidad_estandar": "°C",
    },
    "HUMEDAD_RELATIVA": {
        "id_variable": 10,
        "categoria": CategoriaTelemetria.AMBIENTAL,
        "unidades": ["%"],
        "unidad_estandar": "%",
    },
    "NH3": {
        "id_variable": 11,
        "categoria": CategoriaTelemetria.AMBIENTAL,
        "unidades": ["ppm", "mg/L"],
        "unidad_estandar": "ppm",
    },
    "CO2": {
        "id_variable": 12,
        "categoria": CategoriaTelemetria.AMBIENTAL,
        "unidades": ["ppm"],
        "unidad_estandar": "ppm",
    },
    "TEMPERATURA_CORPORAL": {
        "id_variable": 13,
        "categoria": CategoriaTelemetria.ANIMAL,
        "unidades": ["°C", "°F"],
        "unidad_estandar": "°C",
    },
    "TEMP_CORPORAL": {
        "id_variable": 13,
        "categoria": CategoriaTelemetria.ANIMAL,
        "unidades": ["°C", "°F"],
        "unidad_estandar": "°C",
    },
    "FRECUENCIA_CARDIACA": {
        "id_variable": 14,
        "categoria": CategoriaTelemetria.ANIMAL,
        "unidades": ["bpm"],
        "unidad_estandar": "bpm",
    },
    "FRECUENCIA_RESPIRATORIA": {
        "id_variable": 15,
        "categoria": CategoriaTelemetria.ANIMAL,
        "unidades": ["rpm"],
        "unidad_estandar": "rpm",
    },
    "ACTIVIDAD_MOVIMIENTO": {
        "id_variable": 16,
        "categoria": CategoriaTelemetria.ANIMAL,
        "unidades": ["m/s²", "g"],
        "unidad_estandar": "m/s²",
    },
    "ACTIVIDAD": {
        "id_variable": 16,
        "categoria": CategoriaTelemetria.ANIMAL,
        "unidades": ["m/s²", "g"],
        "unidad_estandar": "m/s²",
    },
    "PH_AGUA": {
        "id_variable": 2,
        "categoria": CategoriaTelemetria.HIDRICA,
        "unidades": ["pH"],
        "unidad_estandar": "pH",
    },
    "OXIGENO_DISUELTO": {
        "id_variable": 3,
        "categoria": CategoriaTelemetria.HIDRICA,
        "unidades": ["mg/L"],
        "unidad_estandar": "mg/L",
    },
    "TDS": {
        "id_variable": 8,
        "categoria": CategoriaTelemetria.HIDRICA,
        "unidades": ["µS/cm", "mS/cm"],
        "unidad_estandar": "µS/cm",
    },
    "CONDUCTIVIDAD_ELECTRICA": {
        "id_variable": 8,
        "categoria": CategoriaTelemetria.HIDRICA,
        "unidades": ["µS/cm", "mS/cm"],
        "unidad_estandar": "µS/cm",
    },
}

# Rangos físicos imposibles por variable (id_variable → (min_fisico, max_fisico))
RANGOS_FISICOS: dict[int, tuple[Decimal, Decimal]] = {
    9: (Decimal('-50'), Decimal('100')),    # Temp ambiental
    10: (Decimal('0'), Decimal('100')),     # Humedad
    11: (Decimal('0'), Decimal('500')),     # NH3
    12: (Decimal('0'), Decimal('100000')), # CO2
    13: (Decimal('30'), Decimal('50')),    # Temp corporal
    14: (Decimal('0'), Decimal('500')),    # Freq cardiaca
    15: (Decimal('0'), Decimal('200')),    # Freq respiratoria
    16: (Decimal('0'), Decimal('200')),    # Actividad
    2: (Decimal('0'), Decimal('14')),      # pH
    3: (Decimal('0'), Decimal('20')),      # O2 disuelto
    8: (Decimal('0'), Decimal('5000')),    # TDS/conductividad
}


@dataclass
class Telemetria:
    id_sensor: int
    id_variable: int
    id_dispositivo_iot: int
    valor_crudo: Decimal
    timestamp_captura: datetime
    timestamp_procesamiento: datetime
    origen: str
    estado_calidad: str
    calibrado: bool
    categoria_variable: str
    unidad_medida: str
    valor_agregado: bool
    tipo_dato: str

    id_telemetria: Optional[int] = None
    valor_ajustado: Optional[Decimal] = None
    timestamp_envio: Optional[datetime] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    metadatos: dict[str, Any] = field(default_factory=dict)
    version_calibracion: Optional[str] = None
    parametros_calibracion: Optional[dict] = None
    ventana_agregacion_min: Optional[int] = None

    # Flags de metadata
    latencia_alta: bool = False
    frecuencia_anomala: bool = False
    posible_drift: bool = False
    dato_buferizado: bool = False
    dato_agregado_edge: bool = False  # mapea a columna dat_agredado_edge (typo en DB)
    reloj_desincronizado: bool = False
    latencia_procesamiento_ms: Optional[int] = None
    nivel_bateria_pct: Optional[Decimal] = None
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None
    frecuencia_muestreo_min: Optional[int] = None
    estado_conectividad: Optional[bool] = None


@dataclass
class DispositivoInfo:
    id_dispositivo_iot: int
    id_sensor: int
    es_activo_dispositivo: bool
    es_activo_sensor: bool
    id_infraestructura: int


@dataclass
class ReglaVariableI3P1:
    id_variable: int
    tipo_variable: str
    categoria: str
    unidad_estandar: str
    unidades_aceptadas: list[str]
    valor_fisico_min: Decimal
    valor_fisico_max: Decimal


@dataclass
class ParametrosCalibacion:
    ganancia: Decimal
    offset: Decimal
    version: str


@dataclass
class ResultadoIngesta:
    id_telemetria: Optional[int]
    estado_calidad: str
    timestamp_procesamiento: datetime
    latencia_procesamiento_ms: Optional[int] = None
    es_duplicado: bool = False


@dataclass
class ResultadoItemBatch:
    sensor_id: int
    timestamp_captura: datetime
    estado: str
    id_telemetria: Optional[int] = None
    error: Optional[str] = None
