from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel


# ── Schemas de CU04 (RF-44, RF-38) ──────────────────────────────────────────

class HistoricoEstadoResponse(BaseModel):
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
    id_activo_biologico: int
    estado_anterior: int
    estado_nuevo: int
    historial: HistoricoEstadoResponse


class CierreActivoResponse(BaseModel):
    id_activo_biologico: int
    estado: str
    fecha_cierre: date
    motivo_cierre: str
    fase_finalizada: bool


class DetalleIndividualResponse(BaseModel):
    id_detalle: Optional[int]
    raza: str
    sexo: str
    fecha_nacimiento: datetime
    peso_inicial: Optional[Decimal]
    fecha_creacion: Optional[datetime]

    model_config = {'from_attributes': True}


class DetallePoblacionalResponse(BaseModel):
    id_detalle: Optional[int]
    cantidad_inicial: int
    cantidad_actual: Optional[int]
    peso_promedio_inicial: Optional[Decimal]
    peso_promedio: Optional[Decimal]
    biomasa_total: Optional[Decimal]
    densidad: Optional[Decimal]

    model_config = {'from_attributes': True}


class ActivoBiologicoResponse(BaseModel):
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
    detalle_individual: Optional[DetalleIndividualResponse]
    detalle_poblacional: Optional[DetallePoblacionalResponse]

    model_config = {'from_attributes': True}


class ActivosPaginadosResponse(BaseModel):
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int
    registros: list[ActivoBiologicoResponse]


class AsociacionInfraestructuraResponse(BaseModel):
    id_historial: int
    id_activo_biologico: int
    id_infraestructura: int
    nombre_infraestructura: str
    tipo_infraestructura: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]

    model_config = {'from_attributes': True}


class ConsultaAsociacionResponse(BaseModel):
    tipo_consulta: str
    id_activo_biologico: int
    asociacion_activa: Optional[AsociacionInfraestructuraResponse] = None
    historial: Optional[list[AsociacionInfraestructuraResponse]] = None


class GestionFaseResponse(BaseModel):
    id_gestion_fases: Optional[int]
    id_activo_biologico: int
    id_ciclo_productiva: int
    nombre_ciclo: str
    nombre_fase_actual: Optional[str]
    paso_actual: Optional[int]
    total_pasos: Optional[int]
    fecha_inicio: datetime
    fecha_finalizacion: Optional[datetime]
    es_activa: bool
    motivo_cambio: Optional[str]

    model_config = {'from_attributes': True}


class HistorialFasesResponse(BaseModel):
    id_activo_biologico: int
    fases: list[GestionFaseResponse]


# ── Schemas de eventos biológicos (CU05 - RF-39/RF-40) ──────────────────────

class EventoCrecimientoResponse(BaseModel):
    tipo_medicion: str
    valor_medicion: Decimal
    unidad_medida: str
    tipo_agregacion: Optional[str] = None
    frecuencia: Optional[str] = None
    nuevo_peso_promedio: Optional[Decimal] = None
    cantidad_medida: Optional[int] = None

    model_config = {'from_attributes': True}


class EventoBajaResponse(BaseModel):
    cantidad_afectada: int
    tipo: str
    motivo_baja: Optional[str]

    model_config = {'from_attributes': True}


class EventoSanitarioResponse(BaseModel):
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
    cantidad: Decimal
    id_metrica_produccion: int
    id_ciclo_productivo: int
    condiciones: Optional[str]
    tipo_producto: Optional[str] = None
    unidad_medida: Optional[str] = None

    model_config = {'from_attributes': True}


class EventoReproductivoResponse(BaseModel):
    categoria: str
    resultado: str
    numero_cria: int
    id_padre: Optional[int]
    id_madre: Optional[int]

    model_config = {'from_attributes': True}


class EventoActivoResponse(BaseModel):
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

    model_config = {'from_attributes': True}


class HistorialEventosResponse(BaseModel):
    id_activo_biologico: int
    total: int
    eventos: list[EventoActivoResponse]


# ── Schema de respuesta para CU06 (RF-40) ────────────────────────────────────

class RegistrarEventoCrecimientoResponse(BaseModel):
    evento: EventoActivoResponse
    fase_avanzada: bool = False


class RegistrarEventoSanitarioResponse(BaseModel):
    evento: EventoActivoResponse
    cambio_estado: Optional[HistoricoEstadoResponse] = None


# ── Schema de respuesta para CU08 (RF-42) ────────────────────────────────────

class RegistrarEventoReproductivoResponse(BaseModel):
    evento: EventoActivoResponse


# ── Schemas CU10 (RF-46, RF-47, RF-48) ───────────────────────────────────────

class RegistroHistorialResponse(BaseModel):
    categoria: str
    fecha_evento: datetime
    descripcion: str
    detalle_especifico: dict
    usuario_responsable: str
    modulo_origen: str


class HistorialActivoResponse(BaseModel):
    id_activo_biologico: int
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int
    registros: list[RegistroHistorialResponse]


class FichaIntegralResponse(BaseModel):
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
    densidad: Optional[Decimal] = None
    eventos_sanitarios: list[dict] = []
    eventos_productivos: list[dict] = []
    eventos_crecimiento: list[dict] = []
    eventos_reproductivos: list[dict] = []
    indicadores: list[dict] = []
    advertencias: list[str] = []


class TransferenciaResponse(BaseModel):
    id_movimiento: Optional[int]
    id_activo_biologico: int
    infraestructura_origen: str
    infraestructura_destino: str
    fecha_transferencia: datetime
    motivo_transferencia: str
    mensaje: str


class InfraestructuraDisponibleResponse(BaseModel):
    id_infraestructura: int
    nombre: str
    tipo: str
    capacidad_maxima: Optional[int] = None
    id_especie: Optional[int] = None


# ── Schemas de CU11 (RF-49) ──────────────────────────────────────────────────

class AsociacionSensorActivoResponse(BaseModel):
    id_asociacion_activo_sensor: int
    id_activo_biologico: int
    tipo_activo: str
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


# ── Schemas CU12 (RF-50, RF-51) ──────────────────────────────────────────────

class IndicadorZootecnicoResponse(BaseModel):
    tipo: str
    valor: Optional[Decimal] = None
    unidad: str
    periodo_inicio: Optional[date] = None
    periodo_fin: Optional[date] = None
    variables_usadas: dict = {}
    fecha_calculo: datetime
    disponible: bool


class IndicadoresActivoResponse(BaseModel):
    id_activo_biologico: int
    tipo_activo: str
    indicadores: list[IndicadorZootecnicoResponse]
    advertencias: list[str] = []


class DatosConsolidadosResponse(BaseModel):
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
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int
    registros: list[EventoAuditoriaResponse]
