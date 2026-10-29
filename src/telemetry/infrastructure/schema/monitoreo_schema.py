# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
# | 2026-10-23 | destroyerban | DEV-39 RF-58: vista por permiso, GRIS sin umbral y anomalías visibles |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-08 RF-58: conteo del semáforo sobre todos los sensores, no la página |
# | 2026-10-26 | Arekkazu | INC-M03 lote 26-10 RF-58/59: unidad sin sensores, lote, desviación, alertas y series |
# | 2026-10-26 | Leandro | ISSUE-678 G87 RF-58: exponer separadamente referencia válida y condición actual por rol. |
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: alertas vencidas sin atención en el dashboard |
# | 2026-10-29 | Arekkazu | INC-M03-211-G98 RF-58: panel integrado de alertas activas |
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
    estado_calidad_valor_operativo: Optional[str] = None
    timestamp_estado_actual: Optional[datetime] = None
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
    # técnicos — solo con R sobre datos_tecnicos_dashboard (DB-08); si no, None
    nivel_bateria_pct: Optional[Decimal] = None
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None
    # DEV-39: E7 (GRIS sin umbral), R2/E2 (anomalía visible) y su etiqueta para la UI
    sin_umbral: bool = False
    indicador_anomalia: bool = False
    es_valor_operativo: bool = True
    etiqueta_estado: Optional[str] = None

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
    # CU04 E1: "Sin datos disponibles" cuando la unidad no tiene sensores (estado GRIS).
    mensaje_estado: Optional[str] = None

    model_config = {"from_attributes": True}


class AlertaActivaPanelSchema(BaseModel):
    """RF-58 CA-11 — alerta ACTIVA del panel; ``id_activo_biologico`` lleva al detalle del activo."""
    id_alerta: int
    tipo_alerta: str
    severidad: Optional[str] = None
    tipo_variable: Optional[str] = None
    valor: Optional[Decimal] = None
    unidad: Optional[str] = None
    fecha_generacion: datetime
    minutos_transcurridos: int
    id_infraestructura: Optional[int] = None
    id_activo_biologico: Optional[int] = None
    identificador_activo: Optional[str] = None

    model_config = {"from_attributes": True}


class PanelAlertasActivasSchema(BaseModel):
    """RF-58 CU04 salida 2: total de alertas ACTIVA del alcance y las primeras 50, CRITICO primero."""
    total: int = 0
    alertas: list[AlertaActivaPanelSchema] = []


class DashboardResponseSchema(BaseModel):
    """RF-58 — respuesta completa del dashboard de monitoreo."""
    total: int
    pagina: int
    por_pagina: int
    resumen_unidades: list[ResumenUnidadSchema]
    sensores: list[EstadoSensorSchema]
    # M3-08: sensores por color de todo el alcance (VERDE/AMARILLO/ROJO/GRIS), no de la página.
    conteo_semaforo: dict[str, int] = {}
    # G57B (RF-57 Salida 3): alertas VENCIDA sin reconocer del alcance (todas las fincas o el área).
    alertas_vencidas_sin_atencion: int = 0
    # G98: `total` de arriba es de sensores; este es el de alertas ACTIVA.
    panel_alertas_activas: PanelAlertasActivasSchema = PanelAlertasActivasSchema()


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
    id_especie: Optional[int] = None
    id_alerta: Optional[int] = None
    nivel_bateria_pct: Optional[Decimal] = None
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None
    # RF-17 — umbral M09 usado para calcular estado_semaforo_historico (None si GRIS)
    id_umbral_ambiental: Optional[int] = None
    valor_min_umbral: Optional[Decimal] = None
    valor_max_umbral: Optional[Decimal] = None
    version_umbral: Optional[datetime] = None
    # Contexto del activo (Fase 4): identificador del lote o individuo y su tipo.
    identificador_activo: Optional[str] = None
    tipo_activo: Optional[str] = None

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
    desviacion_estandar: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class AlertaCorrelacionadaSchema(BaseModel):
    """RF-59 Salida 5 — alerta de RF-57 del periodo (con ``incluir_alertas=true``)."""
    id_alerta: int
    tipo_alerta: str
    severidad: str
    timestamp_generacion: Optional[datetime] = None
    variable_afectada: Optional[str] = None
    estado_final: str


class PuntoSerieSchema(BaseModel):
    timestamp_captura: datetime
    valor: Optional[Decimal] = None
    estado_semaforo_historico: str
    id_sensor: int


class SerieTemporalSchema(BaseModel):
    """RF-59 Salida 3 / CA-9 — serie de una variable (sobre las lecturas de la página)."""
    tipo_variable: str
    unidad_medida: str
    umbral_min: Optional[Decimal] = None
    umbral_max: Optional[Decimal] = None
    puntos: list[PuntoSerieSchema]


class VacioTemporalSchema(BaseModel):
    """RF-59 E7 / CA-17 — intervalo sin lecturas mayor que 3 × la frecuencia de muestreo."""
    sensor_id: int
    tipo_variable: str
    desde: datetime
    hasta: datetime
    duracion_min: int
    frecuencia_esperada_min: int


class HistorialPageSchema(BaseModel):
    """RF-59 — respuesta paginada del historial.

    ``total`` son los registros navegables (como mucho 10 000, CA-19); ``total_encontrado``
    los que cumplen los filtros. Si los supera, ``truncado`` y ``aviso`` lo explican (E6);
    sin resultados, ``aviso`` trae el mensaje de estado vacío (E3).
    """
    total: int
    total_encontrado: int
    truncado: bool = False
    aviso: Optional[str] = None
    pagina: int
    por_pagina: int
    paginas_totales: int
    filtros_aplicados: dict[str, Any]
    rango_real_datos: dict[str, Any]
    items: list[LecturaHistoricaSchema]
    estadisticas: list[ResumenEstadisticoSchema]
    vacios_temporales: list[VacioTemporalSchema] = []
    series: list[SerieTemporalSchema] = []
    alertas_correlacionadas: list[AlertaCorrelacionadaSchema] = []
