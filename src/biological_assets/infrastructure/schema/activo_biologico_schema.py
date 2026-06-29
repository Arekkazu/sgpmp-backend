from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

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
    detalles: Optional[str]

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
