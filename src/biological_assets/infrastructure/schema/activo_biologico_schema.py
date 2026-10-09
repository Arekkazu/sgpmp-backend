"""Schemas de respuesta de los endpoints de activos biológicos (M02)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Optional

from pydantic import AfterValidator, BaseModel

# #213: la columna `densidad` es NUMERIC sin escala; la división en BD llega con
# 20 decimales ("0.01000000000000000000") o en notación científica ("0E-20").
Densidad = Annotated[Decimal, AfterValidator(lambda d: d.quantize(Decimal('0.0001')))]


# ── Schemas de CU04 (RF-44, RF-38) ──────────────────────────────────────────

class HistoricoEstadoResponse(BaseModel):
    """Un cambio de estado registrado en el histórico (RF-44)."""
    id_historico: Optional[int]
    id_activo_biologico: int
    id_estado_anterior: int
    nombre_estado_anterior: Optional[str] = None
    id_estado_nuevo: int
    nombre_estado_nuevo: Optional[str] = None
    fecha_cambio: datetime
    motivo_cambio: Optional[str]
    modulo_origen: str
    id_usuario: int

    model_config = {'from_attributes': True}


class CambioEstadoResponse(BaseModel):
    """Resultado de un cambio de estado manual (RF-44)."""
    id_activo_biologico: int
    estado_anterior: int
    estado_nuevo: int
    historial: HistoricoEstadoResponse


class CierreActivoResponse(BaseModel):
    """Resultado del cierre de ciclo del activo (RF-38)."""
    id_activo_biologico: int
    estado: str
    fecha_cierre: date
    motivo_cierre: str
    fase_finalizada: bool


class DetalleIndividualResponse(BaseModel):
    """Datos propios de un activo INDIVIDUAL."""
    id_detalle: Optional[int]
    raza: str
    sexo: str
    fecha_nacimiento: datetime
    peso_inicial: Optional[Decimal]
    fecha_creacion: Optional[datetime]

    model_config = {'from_attributes': True}


class ParametroEspecieResponse(BaseModel):
    """Atributo dinámico que la especie exige o admite al registrar un activo (#194)."""
    nombre: str
    tipo_dato: str
    es_obligatorio: bool
    unidad_medida: Optional[str] = None
    valor_min: Optional[Decimal] = None
    valor_max: Optional[Decimal] = None

    model_config = {'from_attributes': True}


class DetallePoblacionalResponse(BaseModel):
    """Datos propios de un lote POBLACIONAL: conteo, peso promedio, biomasa y densidad.
    """
    id_detalle: Optional[int]
    cantidad_inicial: int
    cantidad_actual: Optional[int]
    peso_promedio_inicial: Optional[Decimal]
    peso_promedio: Optional[Decimal]
    biomasa_total: Optional[Decimal]
    densidad: Optional[Densidad]

    model_config = {'from_attributes': True}


class ActivoBiologicoResponse(BaseModel):
    """Activo biológico con su detalle individual o poblacional según ``tipo``."""
    id_activo_biologico: int
    id_especie: int
    tipo: str
    identificador: Optional[str]
    fecha_inicio_ciclo: Optional[date]
    detalles_procedencia: Optional[str]
    origen_financiero: str
    costo_adquisicion: Optional[Decimal]
    soporte_documental: Optional[str]
    descripcion: Optional[str]
    id_infraestructura: int
    atributos_dinamicos: Optional[dict]
    id_estado: int
    nombre_estado: Optional[str]
    id_usuario: int
    fecha_creacion: Optional[datetime]
    fecha_actualizacion: Optional[datetime] = None
    detalle_individual: Optional[DetalleIndividualResponse]
    detalle_poblacional: Optional[DetallePoblacionalResponse]
    # M2-04 (reporte UAT): el listado mostraba "Especie #4" y la ficha "Cachama
    # Blanca". Solo los llena el listado; el detalle ya los trae por otras vías.
    nombre_especie: Optional[str] = None
    nombre_infraestructura: Optional[str] = None

    model_config = {'from_attributes': True}


class ActivosPaginadosResponse(BaseModel):
    """Página del listado de activos."""
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int
    registros: list[ActivoBiologicoResponse]


class AsociacionInfraestructuraResponse(BaseModel):
    """Periodo de alojamiento del activo en una infraestructura (``fecha_fin`` nula =
    vigente).
    """
    id_historial: int
    id_activo_biologico: int
    id_infraestructura: int
    nombre_infraestructura: str
    tipo_infraestructura: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]

    model_config = {'from_attributes': True}


class SensorEnInfraestructuraResponse(BaseModel):
    """Sensor activo instalado en la infraestructura del activo."""
    id_sensor: int
    nombre: str
    id_dispositivo_iot: int
    punto_instalacion: str
    categoria: Optional[str] = None

    model_config = {'from_attributes': True}


class ConsultaAsociacionResponse(BaseModel):
    """Infraestructura del activo: vigente, en una fecha o historial completo (RF-34).
    """
    tipo_consulta: str
    id_activo_biologico: int
    asociacion_activa: Optional[AsociacionInfraestructuraResponse] = None
    historial: Optional[list[AsociacionInfraestructuraResponse]] = None
    sensores_en_infraestructura: list[SensorEnInfraestructuraResponse] = []
    advertencia_integridad: Optional[str] = None


class GestionFaseResponse(BaseModel):
    """Paso del activo por una fase de su ciclo productivo (RF-37)."""
    id_gestion_fases: Optional[int]
    id_activo_biologico: int
    id_ciclo_productiva: int
    id_ciclos_productivo_biologico: Optional[int] = None
    nombre_ciclo: str
    nombre_fase_actual: Optional[str]
    paso_actual: Optional[int]
    total_pasos: Optional[int]
    fecha_inicio: datetime
    fecha_finalizacion: Optional[datetime]
    es_activa: bool
    motivo_cambio: Optional[str]
    es_transicion_no_estandar: bool = False

    model_config = {'from_attributes': True}


class HistorialFasesResponse(BaseModel):
    """Todas las gestiones de fase del activo."""
    id_activo_biologico: int
    fases: list[GestionFaseResponse]


class FaseCicloProductivoResponse(BaseModel):
    """Fase de un ciclo productivo, en su orden dentro de la secuencia."""
    id_ciclos_productivo_biologico: int
    id_ciclo_biologico: int
    nombre_fase: str
    duracion_dias: int


class CicloProductivoResponse(BaseModel):
    """Ciclo productivo de M09 con sus fases."""
    id_ciclo_productivo: int
    nombre: str
    fases: list[FaseCicloProductivoResponse]


class CiclosProductivosActivoResponse(BaseModel):
    """Ciclos productivos asignables al activo (los de su especie)."""
    id_activo_biologico: int
    total: int
    items: list[CicloProductivoResponse]


# ── Schemas de eventos biológicos (CU05 - RF-39/RF-40) ──────────────────────

class EventoCrecimientoResponse(BaseModel):
    """Detalle de un evento de crecimiento."""
    tipo_medicion: str
    valor_medicion: Decimal
    unidad_medida: str
    tipo_agregacion: Optional[str] = None
    frecuencia: Optional[str] = None
    nuevo_peso_promedio: Optional[Decimal] = None
    cantidad_medida: Optional[int] = None

    model_config = {'from_attributes': True}


class EventoBajaResponse(BaseModel):
    """Detalle de un evento de baja."""
    cantidad_afectada: int
    tipo: str
    motivo_baja: Optional[str]

    model_config = {'from_attributes': True}


class EventoIngresoResponse(BaseModel):
    """Detalle de un ingreso de individuos a un lote."""
    cantidad_ingresada: int
    tipo: str
    motivo_ingreso: Optional[str]

    model_config = {'from_attributes': True}


class EventoSanitarioResponse(BaseModel):
    """Detalle de un evento sanitario."""
    tipo: str
    diagnostico: Optional[str]
    medicamento: Optional[str]
    dosis: Optional[Decimal]
    unidad_dosis: Optional[str]
    frecuencia: Optional[int]
    duracion: Optional[int]
    observaciones: Optional[str]

    model_config = {'from_attributes': True}


class EventoProductivoResponse(BaseModel):
    """Detalle de un evento productivo."""
    cantidad: Decimal
    id_metrica_produccion: int
    id_ciclo_productivo: int
    condiciones: Optional[str]
    tipo_producto: Optional[str] = None
    unidad_medida: Optional[str] = None

    model_config = {'from_attributes': True}


class EventoReproductivoResponse(BaseModel):
    """Detalle de un evento reproductivo."""
    categoria: str
    resultado: str
    numero_cria: int
    id_padre: Optional[int]
    id_madre: Optional[int]

    model_config = {'from_attributes': True}


class EventoActivoResponse(BaseModel):
    """Evento biológico con el subtipo que le corresponde poblado (RF-39)."""
    id_eventos: int
    id_activo_biologico: int
    fecha: datetime
    descripcion: Optional[str]
    id_usuario: Optional[int]
    crecimiento: Optional[EventoCrecimientoResponse] = None
    baja: Optional[EventoBajaResponse] = None
    sanitario: Optional[EventoSanitarioResponse] = None
    productivo: Optional[EventoProductivoResponse] = None
    reproductivo: Optional[EventoReproductivoResponse] = None
    ingreso: Optional[EventoIngresoResponse] = None

    model_config = {'from_attributes': True}


class HistorialEventosResponse(BaseModel):
    """Eventos del activo, del más reciente al más antiguo."""
    id_activo_biologico: int
    total: int
    eventos: list[EventoActivoResponse]


# ── Schema de respuesta para CU06 (RF-40) ────────────────────────────────────

class RegistrarEventoCrecimientoResponse(BaseModel):
    """Evento de crecimiento registrado y valores recalculados del lote."""
    evento: EventoActivoResponse
    fase_avanzada: bool = False


class RegistrarEventoSanitarioResponse(BaseModel):
    """Evento sanitario registrado y estado resultante del activo."""
    evento: EventoActivoResponse
    cambio_estado: Optional[HistoricoEstadoResponse] = None


# ── Schema de respuesta para CU08 (RF-42) ────────────────────────────────────

class RegistrarEventoReproductivoResponse(BaseModel):
    """Evento reproductivo registrado."""
    evento: EventoActivoResponse


# ── Schemas CU10 (RF-46, RF-47, RF-48) ───────────────────────────────────────

class RegistroHistorialResponse(BaseModel):
    """Línea del historial consolidado (RF-46)."""
    categoria: str
    fecha_evento: datetime
    descripcion: str
    detalle_especifico: dict
    usuario_responsable: str
    modulo_origen: str


class HistorialActivoResponse(BaseModel):
    """Página del historial consolidado del activo (RF-46)."""
    id_activo_biologico: int
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int
    registros: list[RegistroHistorialResponse]
    mensaje: Optional[str] = None


class AccesoDirectoResponse(BaseModel):
    """RF-47 Sección 8: acción disponible desde la ficha para el rol del usuario."""
    codigo: str
    nombre: str
    metodo: str
    ruta: str
    rf_origen: str
    tipos_evento: Optional[list[str]] = None


class FichaIntegralResponse(BaseModel):
    """Ficha integral del activo (RF-47); las secciones que no cargan llegan vacías con
    advertencia.
    """
    id_activo_biologico: int
    identificador: Optional[str]
    tipo: str
    especie: str
    fecha_registro: Optional[date]
    dias_en_sistema: Optional[int]
    estado_actual: str
    infraestructura_asociada: Optional[str]
    fase_productiva_activa: Optional[str]
    raza: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    peso_actual: Optional[Decimal] = None
    unidad_peso: Optional[str] = None
    fecha_ultimo_peso: Optional[date] = None
    cantidad_actual: Optional[int] = None
    biomasa_total: Optional[Decimal] = None
    densidad: Optional[Densidad] = None
    eventos_sanitarios: list[dict] = []
    eventos_productivos: list[dict] = []
    eventos_crecimiento: list[dict] = []
    eventos_reproductivos: list[dict] = []
    indicadores: list[dict] = []
    advertencias: list[str] = []
    accesos_directos: list[AccesoDirectoResponse] = []


class FichaLoteResponse(BaseModel):
    """Ficha de gestión de un lote con densidad, densidad máxima e historial (RF-36)."""
    id_activo_biologico: int
    identificador: Optional[str]
    especie: Optional[str] = None
    infraestructura_asociada: Optional[str] = None
    estado_actual: str
    fecha_registro: Optional[datetime] = None
    cantidad_inicial: int
    cantidad_actual: Optional[int] = None
    peso_promedio_inicial: Optional[Decimal] = None
    peso_promedio: Optional[Decimal] = None
    biomasa_total: Optional[Decimal] = None
    densidad: Optional[Densidad] = None
    densidad_maxima: Optional[Decimal] = None
    historial: list[RegistroHistorialResponse] = []
    total_registros_historial: int = 0


class TransferenciaResponse(BaseModel):
    """Transferencia interna registrada (RF-48)."""
    id_movimiento: Optional[int]
    id_activo_biologico: int
    infraestructura_origen: str
    infraestructura_destino: str
    fecha_transferencia: datetime
    motivo_transferencia: str
    mensaje: str


class InfraestructuraDisponibleResponse(BaseModel):
    """Infraestructura válida como destino de una transferencia."""
    id_infraestructura: int
    nombre: str
    tipo: str
    capacidad_maxima: Optional[int] = None
    ocupacion_actual: Optional[int] = None
    id_especie: Optional[int] = None


# ── Schemas de CU11 (RF-49) ──────────────────────────────────────────────────

class AsociacionSensorActivoResponse(BaseModel):
    """Asociación sensor ↔ activo/infraestructura (RF-49); ``advertencia`` avisa si el
    dispositivo está fuera de línea.
    """
    id_asociacion_activo_sensor: int
    # None para una asociación AMBIENTAL a nivel de infraestructura (RF-49
    # Tipo B, INC-M02-66-G90/#217) -- aplica a todos los activos de esa
    # infraestructura en vez de a un activo puntual.
    id_activo_biologico: Optional[int]
    tipo_activo: Optional[str]
    tipo_asociacion: str
    dispositivo_iot_id: int
    sensor_id: int
    id_infraestructura: int
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]
    estado_asociacion: str
    motivo: Optional[str]
    advertencia: Optional[str] = None

    model_config = {'from_attributes': True}


class ConsultaAsociacionesSensorResponse(BaseModel):
    """RF-49 (INC-M02-68-G91): GET /{id_activo}/sensores. `tipo_consulta='ACTIVA'`
    (default) devuelve solo las asociaciones vigentes; `'HISTORIAL'` devuelve
    todas, incluidas `INACTIVA` y `SUPERADA`."""
    id_activo_biologico: int
    tipo_consulta: str
    asociaciones: list[AsociacionSensorActivoResponse]


# ── Schemas CU12 (RF-50, RF-51) ──────────────────────────────────────────────

class IndicadorZootecnicoResponse(BaseModel):
    """Indicador calculado; ``disponible=false`` cuando no hay datos suficientes."""
    tipo: str
    valor: Optional[Decimal] = None
    unidad: str
    periodo_inicio: Optional[date] = None
    periodo_fin: Optional[date] = None
    variables_usadas: dict = {}
    fecha_calculo: datetime
    disponible: bool


class IndicadoresActivoResponse(BaseModel):
    """Indicadores zootécnicos del activo (RF-51)."""
    id_activo_biologico: int
    tipo_activo: str
    indicadores: list[IndicadorZootecnicoResponse]
    advertencias: list[str] = []


class DatosConsolidadosResponse(BaseModel):
    """Vista consolidada del activo para módulos analíticos (RF-50)."""
    id_activo_biologico: int
    identificador: Optional[str]
    tipo_activo: str
    especie: str
    estado_actual: str
    infraestructura_asociada: Optional[str]
    fase_productiva_activa: Optional[str]
    historial_eventos: list[dict] = []
    historial_fases: list[dict] = []
    historico_estados: list[dict] = []
    metricas_actuales: dict = {}
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int
    fecha_generacion: datetime


# ── CU13 RF-52 — Auditoría y Trazabilidad ────────────────────────────────────

class EventoAuditoriaResponse(BaseModel):
    """Entrada de la bitácora de M02 con su hash de integridad (RF-52)."""
    id_bitacora: int
    id_evento: str
    rf_origen: str
    tipo_evento: str
    clasificacion_biologica: str
    id_activo_biologico: Optional[int]
    tipo_activo: Optional[str]
    timestamp_evento: datetime
    timestamp_registro: datetime
    resultado: str
    descripcion: Optional[str]
    detalle_tecnico: Optional[dict]
    id_usuario_responsable: Optional[int]
    modulo_consumidor: Optional[str]
    severidad_log: str
    id_evento_correlacionado: Optional[str]
    hash_integridad: str
    registro_incompleto: bool


class BitacoraAuditoriaResponse(BaseModel):
    """Página de la bitácora de M02 (RF-52)."""
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int
    registros: list[EventoAuditoriaResponse]


class RegistroCorrectivoAuditoriaResponse(BaseModel):
    """Registro correctivo creado en la bitácora (RF-52 E5)."""
    tabla: str
    id_registro: int
    id_activo_biologico: Optional[int]
    motivo: str
    timestamp_evento: datetime
