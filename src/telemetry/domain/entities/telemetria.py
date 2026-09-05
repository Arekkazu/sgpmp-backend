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
    # RF-62: flags de aptitud (actualizados por el servicio de calidad)
    apto_para_ia: bool = False
    apto_para_nic41: bool = False


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


# ─── CU02 / RF-56 ────────────────────────────────────────────────────────────

class TipoEventoEdge(str, Enum):
    NORMAL = "NORMAL"
    DESVIACION_SIMPLE = "DESVIACION_SIMPLE"
    DESVIACION_COMPUESTA = "DESVIACION_COMPUESTA"
    ERROR_CONFIGURACION = "ERROR_CONFIGURACION"


class SeveridadEdge(str, Enum):
    LEVE = "LEVE"
    MODERADO = "MODERADO"
    CRITICO = "CRITICO"


class EstadoPaqueteInferencia(str, Enum):
    ENVIADO = "ENVIADO"
    PENDIENTE = "PENDIENTE"
    FALLIDO = "FALLIDO"


# Mapeo de clasificación RF-55 al enum tipo_evento de eventos_edge_computing en BD
_MAPA_TIPO_EVENTO_BD: dict[str, str] = {
    TipoEventoEdge.NORMAL: "DATOS_PROCESADOS",
    TipoEventoEdge.DESVIACION_SIMPLE: "ALERTA_GENERADA",
    TipoEventoEdge.DESVIACION_COMPUESTA: "ALERTA_GENERADA",
    TipoEventoEdge.ERROR_CONFIGURACION: "ERROR_PROCESAMIENTO",
}


def clasificacion_a_tipo_evento_bd(clasificacion_rf55: str) -> str:
    return _MAPA_TIPO_EVENTO_BD.get(clasificacion_rf55, "DATOS_PROCESADOS")


@dataclass
class EventoEdgeComputing:
    id_dispositivo_iot: int
    id_sensor: int
    clasificacion_rf55: str          # TipoEventoEdge — clasificación real de RF-55
    tipo_evento: str                 # valor del enum en BD (DATOS_PROCESADOS / ALERTA_GENERADA / etc.)
    fecha_captura: datetime
    fecha_procesamiento: datetime
    origen_dato: str                 # OrigenTelemetria
    estado_conectividad: bool
    variables_involucradas: list[dict[str, Any]]

    id_evento_edge_computing: Optional[int] = None
    severidad: Optional[str] = None  # SeveridadEdge
    metadatos: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaqueteInferencia:
    id_sensor: int
    id_dispositivo_iot: int
    id_evento_edge_computing: int
    tipo_variable: str
    valor_numerico: Decimal
    estado_calidad: str
    fecha_envio: datetime
    estado_paquete: str              # EstadoPaqueteInferencia
    intento_envios: int
    contexto_incompleto: bool

    id_paquetes_inferencia: Optional[int] = None
    unidad: Optional[str] = None
    estado_desviacion: Optional[str] = None   # TipoEventoEdge
    severidad: Optional[str] = None           # SeveridadEdge
    origen: Optional[str] = None              # OrigenTelemetria
    contexto_ambiental: Optional[dict] = None
    metadatos: Optional[dict] = None
    id_version_modelo: Optional[int] = None


@dataclass
class ResultadoEventoEdge:
    id_evento_edge_computing: int
    clasificacion_rf55: str
    severidad: Optional[str]
    estado_conectividad: bool
    fecha_procesamiento: datetime
    paquete_inferencia_estado: Optional[str] = None
