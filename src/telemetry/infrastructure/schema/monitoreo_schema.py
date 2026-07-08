from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel


class EstadoSensorSchema(BaseModel):
    """RF-58 — estado actual de un sensor en el dashboard."""
    id_sensor: int
    id_dispositivo_iot: int
    nombre_sensor: str
    tipo_variable: str
    categoria_variable: str
    ultimo_valor: Optional[Decimal] = None
    ultima_unidad: Optional[str] = None
    ultimo_timestamp_captura: Optional[datetime] = None
    estado_semaforo: str
    estado_calidad: Optional[str] = None
    estado_desviacion: Optional[str] = None
    estado_conectividad: Optional[str] = None
    tiempo_sin_reporte_min: Optional[int] = None
    dato_desactualizado: bool = False
    id_alerta: Optional[int] = None
    severidad_alerta: Optional[str] = None
    tendencia: Optional[str] = None
    id_infraestructura: Optional[int] = None
    nombre_infraestructura: Optional[str] = None
    id_finca: Optional[int] = None
    nombre_finca: Optional[str] = None
    # técnicos — solo Ingeniero de Campo (Productor recibe None)
    nivel_bateria_pct: Optional[Decimal] = None
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class ResumenUnidadSchema(BaseModel):
    """RF-58 — estado agregado de una unidad productiva."""
    id_infraestructura: int
    nombre_infraestructura: str
    id_finca: int
    nombre_finca: str
    total_sensores: int
    sensores_online: int
    sensores_sin_senal: int
    sensores_con_error: int
    estado_general: str
    alertas_activas_count: int
    ultimo_dato_recibido: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DashboardResponseSchema(BaseModel):
    """RF-58 — respuesta completa del dashboard de monitoreo."""
    total: int
    pagina: int
    por_pagina: int
    resumen_unidades: list[ResumenUnidadSchema]
    sensores: list[EstadoSensorSchema]


class LecturaHistoricaSchema(BaseModel):
    """RF-59 — una lectura del historial."""
    id_telemetria: int
    id_sensor: int
    nombre_sensor: Optional[str] = None
    id_variable: int
    tipo_variable: str
    categoria_variable: str
    valor: Optional[Decimal] = None
    valor_ajustado: Optional[Decimal] = None
    unidad_medida: str
    timestamp_captura: datetime
    estado_calidad: str
    estado_semaforo_historico: str
    origen_dato: str
    id_infraestructura: Optional[int] = None
    infraestructura: Optional[str] = None
    finca: Optional[str] = None
    id_activo_biologico: Optional[int] = None
    especie: Optional[str] = None
    id_alerta: Optional[int] = None
    nivel_bateria_pct: Optional[Decimal] = None
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class ResumenEstadisticoSchema(BaseModel):
    """RF-59 — estadísticas por variable en el período consultado."""
    tipo_variable: str
    valor_minimo: Optional[Decimal] = None
    valor_maximo: Optional[Decimal] = None
    valor_promedio: Optional[Decimal] = None
    total_lecturas: int
    pct_dentro_rango: Optional[float] = None
    pct_fuera_rango: Optional[float] = None
    total_alertas_en_periodo: int = 0

    model_config = {"from_attributes": True}


class HistorialPageSchema(BaseModel):
    """RF-59 — respuesta paginada del historial."""
    total: int
    pagina: int
    por_pagina: int
    paginas_totales: int
    filtros_aplicados: dict[str, Any]
    rango_real_datos: dict[str, Any]
    items: list[LecturaHistoricaSchema]
    estadisticas: list[ResumenEstadisticoSchema]
