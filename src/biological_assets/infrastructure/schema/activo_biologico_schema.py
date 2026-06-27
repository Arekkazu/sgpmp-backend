from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


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
