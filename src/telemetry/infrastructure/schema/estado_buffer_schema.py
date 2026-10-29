# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: exponer métricas conocidas y timestamps de su fuente sin inventar normalidad. |
# | 2026-10-29 | Arekkazu | TC-DIS-148 RF-54: listado del buffer de todos los dispositivos del alcance |
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from src.telemetry.domain.entities.estado_buffer import EstadoBufferReportado, EstadoOcupacionBuffer, PoliticaBuffer


class EstadoBufferSchema(BaseModel):
    id_dispositivo_iot: int
    capacidad_total: Decimal | None = None
    capacidad_utilizada: Decimal | None = None
    porcentaje_ocupacion: Decimal | None = None
    datos_pendientes: int | None = None
    ultimo_timestamp_pendiente: datetime | None = None
    estado_buffer: EstadoOcupacionBuffer | None = None
    politica_buffer_activa: PoliticaBuffer | None = None
    id_heartbeat: int | None = None
    fecha_reporte: datetime | None = None
    fecha_recepcion: datetime | None = None
    estado_local_buffer: str | None = None
    metricas_disponibles: bool = False
    serial: str | None = None
    descripcion: str | None = None
    nombre_infraestructura: str | None = None
    nombre_finca: str | None = None
    estado_dispositivo: str | None = None

    @classmethod
    def desde_reporte(cls, reporte: EstadoBufferReportado):
        salida = cls(id_dispositivo_iot=reporte.id_dispositivo_iot,datos_pendientes=reporte.datos_pendientes,
                     id_heartbeat=reporte.id_heartbeat,fecha_reporte=reporte.fecha_reporte,
                     fecha_recepcion=reporte.fecha_recepcion,estado_local_buffer=reporte.estado_local_buffer,
                     serial=reporte.serial,descripcion=reporte.descripcion,
                     nombre_infraestructura=reporte.nombre_infraestructura,nombre_finca=reporte.nombre_finca,
                     estado_dispositivo=reporte.estado_dispositivo)
        if reporte.metricas is not None:
            m = reporte.metricas
            salida.capacidad_total, salida.capacidad_utilizada = m.capacidad_total, m.capacidad_utilizada
            salida.porcentaje_ocupacion, salida.estado_buffer = m.porcentaje_ocupacion, m.estado_buffer
            salida.ultimo_timestamp_pendiente = m.ultimo_timestamp_pendiente
            salida.politica_buffer_activa, salida.metricas_disponibles = m.politica_buffer_activa, True
        return salida
