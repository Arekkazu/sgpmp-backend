from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel


class AlertaSchema(BaseModel):
    id_alerta: int
    tipo_alerta: str
    severidad: str
    estado_alerta: str
    origen_evento: str
    tipo_variable: str
    valor: Optional[Decimal] = None
    unidad: Optional[str] = None
    fecha_evento: datetime
    fecha_generacion: datetime
    fecha_registro: Optional[datetime] = None
    fecha_notificacion: Optional[datetime] = None
    fecha_atencion: Optional[datetime] = None
    fecha_resolucion: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    ultima_ocurrencia: Optional[datetime] = None
    frecuencia_evento: int = 1
    reglas_activas: list[Any] = []
    contexto_activo_biologico: Optional[dict] = None
    metadato_evento: Optional[dict] = None
    accion_sugerida: Optional[str] = None
    motivo_descarte: Optional[str] = None
    diagnostico: Optional[str] = None
    conflicto_resolucion: Optional[str] = None
    severidad_edge_original: Optional[str] = None
    severidad_ia: Optional[str] = None
    tiene_inferencia_no_disponible: bool = False
    tiene_contexto_incompleto: bool = False
    tiene_generada_por_reevaluacion: bool = False
    id_sensor: Optional[int] = None
    id_dispositivo_ioit: Optional[int] = None
    id_activo_biologico: Optional[int] = None
    id_infraestructura: Optional[int] = None
    id_evento_edge_computing: Optional[int] = None
    id_telemetria: Optional[int] = None
    id_paquete_inferencia: Optional[int] = None
    id_usuario_atencion: Optional[int] = None
    id_usuario_resolucion: Optional[int] = None
    referencia_alerta_original: Optional[int] = None

    model_config = {"from_attributes": True}


class HistoricoEstadoAlertaSchema(BaseModel):
    id_historico_estado_alerta: Optional[int] = None
    id_alerta: int
    estado_anterior: str
    estado_nuevo: str
    fecha_cambio: datetime
    id_usuario: Optional[int] = None
    motivo: Optional[str] = None

    model_config = {"from_attributes": True}


class AlertaDetalleSchema(AlertaSchema):
    historico_estados: list[HistoricoEstadoAlertaSchema] = []


class ResultadoGeneracionAlertaSchema(BaseModel):
    es_duplicado: bool
    id_alerta: Optional[int] = None
    tipo_alerta: Optional[str] = None
    severidad: Optional[str] = None
    alerta_existente_id: Optional[int] = None
    motivo_descarte: Optional[str] = None

    model_config = {"from_attributes": True}


class ListaAlertasSchema(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[AlertaSchema]
