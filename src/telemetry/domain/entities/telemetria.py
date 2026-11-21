# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: retira catalogo estatico de variables |
# | 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: incluir captura original en el resultado del evento Edge. |
# | 2026-10-26 | destroyerban | INC-M03-111-G43 RF-55.1: guarda valor y umbrales aplicados por el Edge |
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: 5 intentos con backoff 0/5/15/30/60 s y reenvio automatico |
# | 2026-10-27 | destroyerban | INC-M03-117-G60 RF-56: huella SHA-256 del contenido del paquete para idempotencia |
# | 2026-10-27 | destroyerban | INC-M03-118-G61 RF-55: latencia de deteccion medida en el Edge y SLA de 500 ms |
# | 2026-10-28 | destroyerban | INC-M03-199-G54 RF-55: trazabilidad de la regla (regla_aplicada, nombre_regla, version_regla) |
# | 2026-10-28 | Arekkazu | BE-2 RF-55: id_regla_alerta en el evento Edge |
from __future__ import annotations

import hashlib
import json
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
    # RF-62: proyección de aptitud desde la evaluación vigente de telemetria_calidad.
    # Sin evaluación vigente, False. No representa las columnas legadas de RF-53.
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


# RF-56 restricción 5: máximo 500 registros por envío al motor; más se fragmenta.
MAX_REGISTROS_POR_ENVIO_INFERENCIA = 500

# RF-56 restricción 14: intento 1 inmediato, luego 5, 15, 30 y 60 s. El índice n es la
# espera antes del intento n+1 (tras n intentos fallidos).
ESPERAS_REINTENTO_INFERENCIA_SEG = (0, 5, 15, 30, 60)
MAX_INTENTOS_ENVIO_INFERENCIA = len(ESPERAS_REINTENTO_INFERENCIA_SEG)


def estado_tras_envio_fallido(intentos: int) -> "EstadoPaqueteInferencia":
    """Tras un intento no confirmado: PENDIENTE (se reintenta) hasta agotar los 5; luego FALLIDO."""
    if intentos >= MAX_INTENTOS_ENVIO_INFERENCIA:
        return EstadoPaqueteInferencia.FALLIDO
    return EstadoPaqueteInferencia.PENDIENTE


# Mapeo de clasificación RF-55 al enum tipo_evento de eventos_edge_computing en BD
_MAPA_TIPO_EVENTO_BD: dict[str, str] = {
    TipoEventoEdge.NORMAL: "DATOS_PROCESADOS",
    TipoEventoEdge.DESVIACION_SIMPLE: "ALERTA_GENERADA",
    TipoEventoEdge.DESVIACION_COMPUESTA: "ALERTA_GENERADA",
    TipoEventoEdge.ERROR_CONFIGURACION: "ERROR_PROCESAMIENTO",
}


# RF-55 restricción 1 y CA-1: detección en ≤ 500 ms desde la captura, medida en el nodo Edge.
LATENCIA_MAX_MS_RF55 = 500


def latencia_edge_ms(fecha_captura: datetime, fecha_procesamiento: datetime) -> int:
    """Latencia de detección del Edge: los dos instantes son del reloj del nodo, así que no
    incluye red, broker ni backend (separada de la latencia de consolidación de RF-56)."""
    return round((fecha_procesamiento - fecha_captura).total_seconds() * 1000)


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
    valor_evaluado: Optional[Decimal] = None        # RF-55.1: valor que clasificó el Edge
    umbral_min_aplicado: Optional[Decimal] = None
    umbral_max_aplicado: Optional[Decimal] = None
    # BE-2: regla de modulo3.reglas_alertas que evaluó el Edge (metadata_edge.id_regla_alerta).
    id_regla_alerta: Optional[int] = None


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


# RF-56 restricciones 3 y 10 (INC-M03-117-G60): con id_paquetes_inferencia, identifica un envío.
# Mismo id y misma huella = reintento del mismo paquete; mismo id y otra huella = el contenido
# cambió y el receptor no debe tratarlo como reintento.
CLAVE_HUELLA_CONTENIDO = "huella_contenido"


def _normalizar(valor: Any) -> Any:
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal):
        # 38.5 y 38.5000 son el mismo valor: la huella no depende de la escala con que se guardó.
        return format(valor.normalize(), "f")
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {str(k): _normalizar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_normalizar(v) for v in valor]
    return valor


def huella_contenido_paquete(paquete: PaqueteInferencia) -> str:
    """SHA-256 del contenido del paquete, sin el estado de envío.

    Excluye el id (va aparte), estado_paquete, intento_envios y fecha_envio (cambian en cada
    intento) y la propia huella. Determinista: JSON canónico con claves ordenadas.
    """
    metadatos = {k: v for k, v in (paquete.metadatos or {}).items() if k != CLAVE_HUELLA_CONTENIDO}
    contenido = _normalizar({
        "id_sensor": paquete.id_sensor,
        "id_dispositivo_iot": paquete.id_dispositivo_iot,
        "id_evento_edge_computing": paquete.id_evento_edge_computing,
        "tipo_variable": paquete.tipo_variable,
        "valor_numerico": paquete.valor_numerico,
        "unidad": paquete.unidad,
        "estado_calidad": paquete.estado_calidad,
        "estado_desviacion": paquete.estado_desviacion,
        "severidad": paquete.severidad,
        "origen": paquete.origen,
        "contexto_ambiental": paquete.contexto_ambiental,
        "contexto_incompleto": paquete.contexto_incompleto,
        "id_version_modelo": paquete.id_version_modelo,
        "metadatos": metadatos,
    })
    canonico = json.dumps(contenido, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def huella_coincide(paquete: PaqueteInferencia) -> bool:
    """El contenido actual corresponde a la huella guardada al generar el paquete."""
    guardada = (paquete.metadatos or {}).get(CLAVE_HUELLA_CONTENIDO)
    return guardada is not None and guardada == huella_contenido_paquete(paquete)


@dataclass
class ResultadoEventoEdge:
    id_evento_edge_computing: int
    clasificacion_rf55: str
    severidad: Optional[str]
    estado_conectividad: bool
    fecha_captura: datetime
    fecha_procesamiento: datetime
    paquete_inferencia_estado: Optional[str] = None
    valor_evaluado: Optional[Decimal] = None
    umbral_min_aplicado: Optional[Decimal] = None
    umbral_max_aplicado: Optional[Decimal] = None
    latencia_edge_ms: Optional[int] = None
    sla_edge_excedido: Optional[bool] = None


#: INC-M03-199-G54 (RF-55 §6, "contexto: variables y reglas usadas"): trazabilidad de la regla que
#: produjo la clasificación. La emite el nodo Edge; el backend la conserva en evento, paquete y alerta.
CAMPOS_TRAZABILIDAD_REGLA = ("regla_aplicada", "nombre_regla", "version_regla")
